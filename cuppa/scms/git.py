
#          Copyright Jamie Allsop 2014-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Git Source Control Management System
#-------------------------------------------------------------------------------

import logging
import subprocess
import shlex
import os
import re
import threading

from collections import namedtuple

from cuppa.log import logger
from cuppa.colourise import as_notice, as_info, colour_items, as_warning
from cuppa.utility.python2to3 import as_str, Exception


# What a working copy looks like without asking the network. Counts are relative to the last
# fetch; None means the question could not be answered rather than zero.
WorkingCopyState = namedtuple(
        'WorkingCopyState',
        [ 'branch', 'detached', 'upstream', 'ahead', 'behind', 'modified' ]
)


class Git:

    class Error(Exception):
        def __init__(self, value):
            self.parameter = value
        def __str__(self):
            return repr(self.parameter)


    @classmethod
    def vc_type( cls ):
        return "git"


    @classmethod
    def binary( cls ):
        return "git"


    @classmethod
    def execute_command( cls, command, path=None ):
        try:
            logger.trace( "Executing command [{command}]...".format(
                    command=as_info(command)
            ) )
            result = as_str( subprocess.check_output( shlex.split( command ), stderr=subprocess.STDOUT, cwd=path ) ).strip()
            logger.trace( "Result of calling [{command}] was [{result}]".format(
                    command=as_info(command),
                    result=as_notice(result)
            ) )
            return result
        except subprocess.CalledProcessError as error:
            logger.trace( "Command [{command}] failed with exit code [{exit_code}]".format(
                    command=as_warning(str(command)),
                    exit_code=as_warning(str(error.returncode))
            ) )
            raise cls.Error("Command [{command}] failed".format( command=str(command) ) )
        except OSError:
            logger.trace( "Binary [{git}] is not available".format(
                    git=as_warning(cls.binary())
            ) )
            raise cls.Error("Binary [{git}] is not available".format(  git=cls.binary() ) )


    @classmethod
    def _pump_git_progress(
            cls, src, dest, collected, rewrite=True, line_prefix="", single_line=False,
    ):
        """Copy git stderr to ``dest``, subduing each fragment; honour ``\\r`` on a tty.

        ``line_prefix`` is prepended to each visible fragment (e.g. which remote is
        being fetched). ``single_line`` keeps every update on one ``\\r``-rewritten
        line so a later clear can leave the ACTION table as the only surface.
        """
        from cuppa.colourise import as_subdued
        from cuppa.utility.storage import pad_visible, visible_len

        prefix = line_prefix or ""
        width = 0
        buf = b''
        while True:
            chunk = src.read( 256 )
            if not chunk:
                break
            buf += chunk
            while True:
                cr = buf.find( b'\r' )
                lf = buf.find( b'\n' )
                if cr < 0 and lf < 0:
                    break
                if cr < 0:
                    idx, end = lf, b'\n'
                elif lf < 0:
                    idx, end = cr, b'\r'
                elif cr < lf:
                    idx, end = cr, b'\r'
                else:
                    idx, end = lf, b'\n'
                piece = buf[:idx]
                buf = buf[idx + 1:]
                if end == b'\r' and buf.startswith( b'\n' ):
                    buf = buf[1:]
                    end = b'\n'
                text = as_str( piece )
                if text:
                    collected.append( text )
                body = prefix + text if text else prefix
                styled = as_subdued( body ) if body else ''
                if single_line or ( end == b'\r' and rewrite ):
                    width = max( width, visible_len( styled ) )
                    dest.write( '\r' + pad_visible( styled, width ) )
                else:
                    dest.write( styled + '\n' )
                try:
                    dest.flush()
                except Exception:
                    pass
        if buf:
            text = as_str( buf )
            if text:
                collected.append( text )
                body = prefix + text
                styled = as_subdued( body )
                if single_line or rewrite:
                    width = max( width, visible_len( styled ) )
                    dest.write( '\r' + pad_visible( styled, width ) )
                else:
                    dest.write( styled )
                try:
                    dest.flush()
                except Exception:
                    pass


    @classmethod
    def _progress_enabled( cls ):
        """Match HTTP/extract progress: show git ``--progress`` only at INFO or finer."""
        return logger.isEnabledFor( logging.INFO )


    @classmethod
    def _args_to_command( cls, args_list ):
        try:
            return shlex.join( args_list )
        except AttributeError:
            return " ".join( shlex.quote( part ) for part in args_list )


    @classmethod
    def _run_with_progress(
            cls, args_list, path=None, line_prefix="", progress_stream=None,
            owns_stream=None, single_line=False,
    ):
        """Run a long network git command, streaming subdued progress when possible.

        Stderr is piped and replayed onto the controlling terminal (or stderr in CI)
        so ``--progress`` ``\\r`` updates still work under the ``cuppa`` launcher, and
        so fragments can be wrapped with subdued colour. Not a cuppa byte bar.
        Callers should only use this when :meth:`_progress_enabled` is true.

        ``line_prefix`` / ``single_line`` keep a batch remote-check on one rewrite
        line (see ``--update-develop``). Pass an open ``progress_stream`` to share
        that line across several fetches; ``owns_stream`` defaults to whether this
        call opened the stream.
        """
        from cuppa.utility.download import open_progress_stream

        command = cls._args_to_command( args_list )

        logger.trace( "Executing command [{command}] with progress...".format(
                command=as_info( command )
        ) )

        if progress_stream is None:
            progress_stream, is_tty, opened_owns = open_progress_stream()
            if owns_stream is None:
                owns_stream = opened_owns
        else:
            is_tty = True
            try:
                is_tty = bool( progress_stream.isatty() )
            except Exception:
                is_tty = True
            if owns_stream is None:
                owns_stream = False

        stderr_lines = []
        rewrite = bool( is_tty )
        try:
            process = subprocess.Popen(
                    args_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=path,
                    bufsize=0,
            )
            pump = threading.Thread(
                    target=cls._pump_git_progress,
                    args=(
                        process.stderr,
                        progress_stream,
                        stderr_lines,
                        rewrite,
                        line_prefix,
                        bool( single_line and rewrite ),
                    ),
            )
            pump.daemon = True
            pump.start()
            stdout_data = process.stdout.read() if process.stdout else b''
            pump.join()
            returncode = process.wait()
            if returncode != 0:
                raise cls.Error(
                    "Command [{command}] failed".format( command=command )
                )
            return as_str( stdout_data ).strip()
        except cls.Error:
            raise
        except OSError:
            logger.trace( "Binary [{git}] is not available".format(
                    git=as_warning( cls.binary() )
            ) )
            raise cls.Error(
                "Binary [{git}] is not available".format( git=cls.binary() )
            )
        finally:
            if owns_stream:
                try:
                    progress_stream.close()
                except Exception:
                    pass


    @classmethod
    def remote_branch_exists( cls, repository, branch ):
        command = "{git} ls-remote --heads {repository} {branch}".format( git=cls.binary(), repository=repository, branch=branch )
        result = cls.execute_command( command )
        if result:
            for line in result.splitlines():
                if line.startswith( "warning: redirecting"):
                    logger.trace( "Ignoring redirection warning and proceeding" )
                elif branch in line:
                    logger.trace( "Branch {branch} found in {line}".format( branch=as_info(branch), line=as_notice(line) ) )
                    return True
        # Branch doesn't exist but a tag of the same name might
        command = "{git} ls-remote --tags {repository} {branch}".format( git=cls.binary(), repository=repository, branch=branch )
        result = cls.execute_command( command )
        if result:
            for line in result.splitlines():
                if line.startswith( "warning: redirecting"):
                    logger.trace( "Ignoring redirection warning and proceeding" )
                elif branch in line:
                    logger.trace( "Tag {branch} found in {line}".format( branch=as_info(branch), line=as_notice(line) ) )
                    return True
        return False


    @classmethod
    def remote_default_branch( cls, repository ):
        command = "{git} ls-remote --symref {repository} HEAD".format( git=cls.binary(), repository=repository )
        result = cls.execute_command( command )

        if result:
            branch_pattern = r'ref[:]\s+refs/heads/(?P<default_branch>[^\s]+)\s+HEAD'
            match = re.search( branch_pattern, result )
            logger.trace(
                    "When searching for default branch name for repoistory [{}] using regex [{}] the following match [{}] was returned".format(
                    as_info(repository), as_notice(branch_pattern), as_info(str(match))
            ) )
            if match:
                return match.group('default_branch')
        return None


    @classmethod
    def working_copy_default_branch( cls, path ):
        """Default branch of a local working copy from ``origin/HEAD`` (offline).

        Returns the short branch name (for example ``master``), or ``None`` when
        there is no remote HEAD symlink / the path is not a Git working copy.
        """
        if not path or not os.path.exists( os.path.join( path, ".git" ) ):
            return None
        try:
            ref = cls.execute_command(
                    "{git} symbolic-ref --short refs/remotes/origin/HEAD".format(
                            git=cls.binary()
                    ),
                    path,
            )
        except cls.Error:
            return None
        ref = ( ref or "" ).strip()
        if not ref:
            return None
        if ref.startswith( "refs/remotes/" ):
            ref = ref[ len( "refs/remotes/" ) : ]
        if "/" in ref:
            # ``origin/master`` → ``master``
            return ref.split( "/", 1 )[ 1 ]
        return ref


    ## Example outputs:
    #
    ## 1. rebasing branch "rebase_test"
    #
    #    $ git branch
    #    * (no branch, rebasing rebase_test)
    #        master
    #        rebase_test
    #
    #    $ git status -sb
    #    ## HEAD (no branch)
    #
    #    $ git show -s --pretty=\%d --decorate=full HEAD
    #     (HEAD, tag: refs/tags/product_beta_r1.13, refs/remotes/origin/master, refs/remotes/origin/HEAD, refs/heads/master)
    #
    ## 2. Detached HEAD
    #
    #    $ git branch
    #    * (HEAD detached at product_beta_r1.13)
    #      master
    #
    #    $ git status
    #    HEAD detached at product_beta_r1.13
    #    nothing to commit, working tree clean
    #
    #    $ git show -s --pretty=\%d --decorate=full HEAD
    #     (HEAD, tag: refs/tags/product_beta_r1.9, tag: refs/tags/product_beta_r1.13, refs/remotes/origin/master, refs/remotes/origin/HEAD, refs/heads/master)
    #
    ## 3. normal
    #


    @classmethod
    def get_branch( cls, path ):
        branch = None
        remote = None

        head_detached = False
        command = "{git} branch".format( git=cls.binary() )
        branch_info = cls.execute_command( command, path )
        if branch_info:
            match = re.search( r'^[*] [(]HEAD detached ', branch_info )
            if match:
                head_detached = True

        if not head_detached:
            result = cls.execute_command( "{git} status -sb".format( git=cls.binary() ), path )
            if result:
                match = re.search( r'## (?P<branch>(?:(?!\.\.)[^\^~:\s\\\n])+)(?:\.\.\.(?P<remote>[^\^~:\s\\\n]+))?', result )
                if match:
                    branch = match.group("branch")
                    remote = match.group("remote")
                match = re.search( r'## HEAD (no branch)', result )
                # Check if we are rebasing
                if match:
                    command = "{git} branch".format( git=cls.binary() )
                    branch_info = cls.execute_command( command, path )
                    if branch_info:
                        match = re.search( r'(no branch, rebasing (?P<branch>[^)]+))', branch_info )
                        if match:
                            branch = match.group("branch")
                            logger.warn( as_warning( "Currently rebasing branch [{}]".format( branch ) ) )

            return branch, remote

        else:
            result = cls.execute_command(
                    r"{git} show -s --pretty=\%d --decorate=full HEAD".format( git=cls.binary() ),
                    path
            )

            match = re.search( r'HEAD(?:(?:[^ ]* -> |[^,]*, )(?P<refs>[^)]+))?', result )

            if match and match.group("refs"):
                refs = [ { "ref":r.strip(), "type": "" } for r in match.group("refs").split(',') ]
                logger.trace( "Refs (using show) for [{}] are [{}]".format(
                        as_notice(path),
                        colour_items( (r["ref"] for r in refs) )
                ) )
                if refs:
                    for ref in refs:
                        if ref["ref"].startswith("refs/heads/"):
                            ref["ref"] = ref["ref"][len("refs/heads/"):]
                            ref["type"] = "L"
                        elif ref["ref"].startswith("refs/tags/"):
                            ref["ref"] = ref["ref"][len("refs/tags/"):]
                            ref["type"] = "T"
                        elif ref["ref"].startswith("tag: refs/tags/"):
                            ref["ref"] = ref["ref"][len("tag: refs/tags/"):]
                            ref["type"] = "T"
                        elif ref["ref"].startswith("refs/remotes/"):
                            ref["ref"] = ref["ref"][len("refs/remotes/"):]
                            ref["type"] = "R"
                        else:
                            ref["type"] = "U"

                    logger.trace( "Refs (after classification) for [{}] are [{}]".format(
                            as_notice(path),
                            colour_items( (":".join([r["type"], r["ref"]]) for r in refs) )
                    ) )

                    if refs[0]["type"] == "L":
                        branch = refs[0]["ref"]
                    #elif refs[0]["type"] == "T":
                        #branch = refs[0]["ref"]
                    elif refs[0]["type"] == "R":
                        branch = refs[0]["ref"].split('/')[1]

                    remote = next( ( ref["ref"] for ref in refs if ref["type"]=="R" ), None )

                logger.trace( "Branch (using show) for [{}] is [{}]".format( as_notice(path), as_info(str(branch)) ) )
            else:
                if result == "(HEAD)":
                    command = "{git} branch".format( git=cls.binary() )
                    branch_info = cls.execute_command( command )
                    if branch_info:
                        match = re.search( r'(no branch, rebasing (?P<branch>[^)]+))', branch_info )
                        if match:
                            branch = match.group("branch")
                            logger.warn( as_warning( "Currently rebasing branch [{}]".format( branch ) ) )

        return branch, remote


    @classmethod
    def get_revision( cls, path ):
        guessed_revision = None
        revision = None

        command = "{git} describe --always".format( git=cls.binary() )
        revision = cls.execute_command( command, path )
        if revision.strip():
            guessed_revision = revision

        command = "{git} rev-parse HEAD".format( git=cls.binary() )
        commit_sha = cls.execute_command( command, path )

        command = "{git} name-rev --tags --name-only {commit_sha}".format( git=cls.binary(), commit_sha=commit_sha.strip() )
        revision = cls.execute_command( command, path )
        if revision.strip() != "undefined":
            guessed_revision = revision
        return guessed_revision


    @classmethod
    def get_working_copy_state( cls, path ):
        """Branch, upstream, ahead, behind and modified, without touching the network.

        The counts describe the working copy against the upstream ref as it stood after the last
        fetch. ``modified`` is tracked dirt only (``status --porcelain
        --untracked-files=no``). Untracked paths that would be overwritten by a
        fast-forward are a separate check —
        :meth:`untracked_paths_blocking_fast_forward` — used by update decisions.
        """
        if not path or not os.path.exists( os.path.join( path, ".git" ) ):
            raise cls.Error("Not a Git working copy")

        branch = None
        detached = False
        try:
            branch = cls.execute_command(
                    "{git} symbolic-ref --short -q HEAD".format( git=cls.binary() ), path
            )
        except cls.Error:
            detached = True

        upstream = None
        if branch:
            try:
                upstream = cls.execute_command(
                        "{git} rev-parse --abbrev-ref --symbolic-full-name @{{upstream}}".format(
                                git=cls.binary()
                        ),
                        path
                )
            except cls.Error:
                logger.trace( "No upstream branch for [{}] in [{}]".format(
                        as_notice(branch), as_notice(path)
                ) )

        ahead = None
        behind = None
        if upstream:
            counts = cls.execute_command(
                    "{git} rev-list --left-right --count @{{upstream}}...HEAD".format(
                            git=cls.binary()
                    ),
                    path
            )
            fields = counts.split()
            if len(fields) == 2:
                behind, ahead = int(fields[0]), int(fields[1])

        status = cls.execute_command(
                "{git} status --porcelain --untracked-files=no".format( git=cls.binary() ), path
        )

        return WorkingCopyState(
                branch   = branch,
                detached = detached,
                upstream = upstream,
                ahead    = ahead,
                behind   = behind,
                modified = bool( status.strip() )
        )


    @classmethod
    def untracked_paths_blocking_fast_forward( cls, path ):
        """Untracked paths a fast-forward to ``@{upstream}`` would overwrite.

        Returns a sorted list. Empty when there is no overlap, no upstream delta,
        or the check cannot run. Harmless untracked files that do not collide
        with incoming paths are ignored.
        """
        if not path or not os.path.exists( os.path.join( path, ".git" ) ):
            return []
        try:
            incoming = cls.execute_command(
                    "{git} diff --name-only HEAD..@{{upstream}}".format(
                            git=cls.binary()
                    ),
                    path,
            )
            untracked = cls.execute_command(
                    "{git} ls-files --others --exclude-standard".format(
                            git=cls.binary()
                    ),
                    path,
            )
        except cls.Error:
            return []
        incoming_set = { line for line in incoming.splitlines() if line }
        untracked_set = { line for line in untracked.splitlines() if line }
        return sorted( incoming_set & untracked_set )


    @classmethod
    def fetch( cls, path, progress=None, line_prefix="", progress_stream=None ):
        """Update the remote-tracking refs. The one command in this family that uses the network.

        ``progress`` defaults to the usual INFO-gated streamed ``--progress``. Pass
        ``False`` for a quiet fetch. Pass ``line_prefix`` (and usually an open
        ``progress_stream``) for a single-line subdued status rewrite during a
        batch remote check — the caller clears the line before the ACTION table.
        """
        use_progress = cls._progress_enabled() if progress is None else bool( progress )
        if use_progress:
            return cls._run_with_progress(
                    [ cls.binary(), "fetch", "--progress" ],
                    path,
                    line_prefix=line_prefix,
                    progress_stream=progress_stream,
                    owns_stream=False if progress_stream is not None else None,
                    single_line=bool( line_prefix ),
            )
        return cls.execute_command(
                "{git} fetch".format( git=cls.binary() ),
                path,
        )


    @classmethod
    def is_tags_fetch_failure( cls, error ):
        """True when pip's ``git fetch --tags`` failed (moved tag or quiet exit 1)."""
        text = str( error ).lower()
        if "fetch --tags" not in text:
            return False
        return "clobber" in text or "exited with" in text


    @classmethod
    def fetch_tags_force( cls, path, progress=False ):
        """Force-update tags so the remote wins (Cuppa-owned download caches).

        Quiet by default: stdout/stderr are captured so a preceding cuppa info
        line is the only operator surface on success. Pass ``progress=True`` for
        subdued streamed ``--progress``.
        """
        if progress:
            return cls._run_with_progress(
                    [ cls.binary(), "fetch", "--tags", "--force", "--progress" ],
                    path,
            )
        return cls.execute_command(
                "{git} fetch --tags --force".format( git=cls.binary() ),
                path,
        )


    @classmethod
    def fast_forward( cls, path ):
        """Advance the checked-out branch to its upstream, refusing anything that is not a
        fast-forward. Git enforces that, so a copy that has moved on is never rewritten here."""
        return cls.execute_command( "{git} merge --ff-only @{{upstream}}".format(
                git=cls.binary()
        ), path )


    @classmethod
    def clone( cls, repository, path, branch=None, recurse_submodules=True ):
        """Clone ``repository`` into ``path`` on ``branch`` (unexpanded URL — no embedded secrets)."""
        parent = os.path.dirname( path.rstrip( os.sep ) ) or '.'
        if parent and not os.path.exists( parent ):
            os.makedirs( parent )
        parts = [ cls.binary(), "clone" ]
        if cls._progress_enabled():
            parts.append( "--progress" )
        if branch:
            parts.extend( [ "--branch", branch ] )
        if recurse_submodules:
            parts.append( "--recurse-submodules" )
        parts.extend( [ repository, path ] )
        if cls._progress_enabled():
            return cls._run_with_progress( parts )
        return cls.execute_command( cls._args_to_command( parts ) )


    @classmethod
    def remote_url( cls, path, remote='origin' ):
        """The configured URL of ``remote``, or None when there is no such remote."""
        try:
            return cls.execute_command(
                    "{git} config --get remote.{remote}.url".format(
                            git=cls.binary(), remote=remote
                    ),
                    path,
            )
        except cls.Error:
            return None


    @classmethod
    def update_submodules( cls, path ):
        """Bring submodules in line with the checked-out revision."""
        return cls.execute_command(
                "{git} submodule update --init --recursive".format( git=cls.binary() ),
                path,
        )


    @classmethod
    def local_branch_exists( cls, path, branch ):
        try:
            cls.execute_command(
                    "{git} show-ref --verify --quiet refs/heads/{branch}".format(
                            git=cls.binary(), branch=branch
                    ),
                    path,
            )
            return True
        except cls.Error:
            return False


    @classmethod
    def remote_tracking_branch_exists( cls, path, branch, remote='origin' ):
        try:
            cls.execute_command(
                    "{git} show-ref --verify --quiet refs/remotes/{remote}/{branch}".format(
                            git=cls.binary(), remote=remote, branch=branch
                    ),
                    path,
            )
            return True
        except cls.Error:
            return False


    @classmethod
    def checkout_branch( cls, path, branch ):
        """Switch to an existing local branch."""
        return cls.execute_command(
                "{git} checkout {branch}".format( git=cls.binary(), branch=branch ),
                path,
        )


    @classmethod
    def checkout_tracking_branch( cls, path, branch, remote='origin' ):
        """Create a local branch tracking ``remote/branch``, or switch if it already exists."""
        if cls.local_branch_exists( path, branch ):
            cls.checkout_branch( path, branch )
            return
        return cls.execute_command(
                "{git} checkout -b {branch} --track {remote}/{branch}".format(
                        git=cls.binary(), branch=branch, remote=remote
                ),
                path,
        )


    @classmethod
    def create_branch_from_head( cls, path, branch ):
        """Create and switch to ``branch`` from the current HEAD."""
        return cls.execute_command(
                "{git} checkout -b {branch}".format( git=cls.binary(), branch=branch ),
                path,
        )


    @classmethod
    def info( cls, path ):
        if not path:
            raise cls.Error("No working copy path specified for calling git commands with.")

        url        = None
        repository = None
        branch     = None
        remote     = None
        revision   = None

        if not os.path.exists( os.path.join( path, ".git" ) ):
            raise cls.Error("Not a Git working copy")

        revision = cls.get_revision( path )

        branch, remote = cls.get_branch( path )

        command = "{git} config --get remote.origin.url".format( git=cls.binary() )
        repository = cls.execute_command( command, path )
        repository = repository.strip()
        url = repository

        return url, repository, branch, remote, revision

