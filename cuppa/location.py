#          Copyright Jamie Allsop 2014-2019
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Location
#-------------------------------------------------------------------------------

import os
try:
    from urlparse import urlparse
    from urlparse import urlunparse
    from urlparse import ParseResult
    from urllib import unquote
    from urllib import urlretrieve
    from urllib import ContentTooShortError
except ImportError:
    from urllib.parse import urlparse
    from urllib.parse import urlunparse
    from urllib.parse import ParseResult
    from urllib.parse import unquote
    from urllib.request import urlretrieve
    from urllib.error import ContentTooShortError

import urllib
import zipfile
import tarfile
import shutil
import re
import shlex
import subprocess
import ntpath
import fnmatch
import hashlib
import platform
import sys
import logging

from .scms import subversion, git, mercurial, bazaar

from cuppa.colourise import as_notice, as_info, as_warning, as_error
from cuppa.log import logger, register_secret
from cuppa.path import split_common

try:
    import pip.vcs as pip_vcs
    import pip.download as pip_download
    import pip.exceptions as pip_exceptions
    from pip.download import is_url as pip_is_url

    def get_url_rev( vcs_backend ):
        return vcs_backend.get_url_rev()

    def update( vcs_backend, dest, rev_options ):
        return vcs_backend.update( dest, rev_options )

    def make_rev_options( vc_type, vcs_backend, url, rev, local_remote ):
        if vc_type == 'git':
            if rev:
                return [rev]
            elif local_remote:
                return [local_remote]
        elif vc_type == 'hg' and rev:
            return vcs_backend.get_rev_options( url, rev )
        elif vc_type == 'bzr' and rev:
            return ['-r', rev]
        return []

except:
    import pip._internal.vcs as pip_vcs
    import pip._internal.download as pip_download
    import pip._internal.exceptions as pip_exceptions
    try:
        from pip._internal.download import is_archive_file as pip_is_archive_file
        from pip._internal.download import is_url as pip_is_url
    except: # Pip version >= 19.3.1
        from pip._internal.req.constructors import is_archive_file as pip_is_archive_file
        from pip._internal.vcs import is_url as pip_is_url
        from pip._internal.utils.misc import hide_url as pip_hide_url

    def get_url_rev( vcs_backend ):
        url_rev_auth = vcs_backend.get_url_rev_and_auth( vcs_backend.url )
        return url_rev_auth[0], url_rev_auth[1]

    def update( vcs_backend, dest, rev_options ):
        return vcs_backend.update( dest, vcs_backend.url, rev_options )

    def make_rev_options( vc_type, vcs_backend, url, rev, local_remote ):
        logger.debug( "vc_type={vc_type}, url={url}, rev={rev}, local_remote={local_remote}".format(
            vc_type = as_info( str(vc_type) ),
            url = as_notice( str(url) ),
            rev = as_notice( str(rev) ),
            local_remote = as_notice( str(local_remote) )
        ) )
        if vc_type == 'git':
            if rev:
                return vcs_backend.make_rev_options( rev=rev )
            #elif local_remote:
                #return vcs_backend.make_rev_options( rev=local_remote )
        elif vc_type == 'hg' and rev:
            return vcs_backend.make_rev_options( rev=rev )
        elif vc_type == 'bzr' and rev:
            return vcs_backend.make_rev_options( rev=rev )
        return vcs_backend.make_rev_options()


class LocationException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


def path_leaf(path):
    base, leaf = ntpath.split( path )
    return leaf or ntpath.basename( base )


def get_common_top_directory_under( path ):
    dirs = os.listdir( path )
    top_dir = os.path.join( path, dirs[0] )
    if len(dirs) == 1 and os.path.isdir( top_dir ):
        return dirs[0]
    return None


class ReportDownloadProgress(object):

    def __init__( self ):
        self._step = 2.5
        self._percent_step = 10
        self._report_percent = self._percent_step
        self._expected = self._step
        sys.stdout.write( "cuppa: location: [info] Download progress {}".format( as_info("|") ) )
        sys.stdout.flush()

    def __call__( self, blocks_transferred, block_size, total_size ):
        percent = 100.0 * float(blocks_transferred) * float(block_size) / float(total_size)
        if percent >= self._expected:
            if percent >= 100.0:
                sys.stdout.write( "={} Complete\n".format( as_info("|") ) )
                sys.stdout.flush()
            else:
                sys.stdout.write( "=" )
                if percent >= float(self._report_percent):
                    sys.stdout.write( as_info( str(self._report_percent) + "%" ) )
                    self._report_percent += self._percent_step
                sys.stdout.flush()
                self._expected += self._step


class Location(object):

    url_replacement_char = r'_'

    def get_cached_archive( self, cache_root, path ):
        logger.debug( "Checking for cached archive [{}]...".format( as_info( path ) ) )
        for archive in os.listdir(cache_root):
            if fnmatch.fnmatch( archive, path ):
                logger.debug( "Found cached archive [{}] skipping download".format( as_info( archive ) ) )
                return os.path.join( cache_root, archive )
        return None


    @classmethod
    def remove_common_top_directory_under( cls, path ):
        dirs = os.listdir( path )
        if not dirs:
            raise LocationException( "Uncompressed archive [{}] is empty".format( path ) )
        top_dir = os.path.join( path, dirs[0] )
        if len(dirs) == 1 and os.path.isdir( top_dir ):
            logger.debug( "Removing redundant top directory [{}] from [{}]".format(
                    as_info( dirs[0] ),
                    as_info( path ) )
            )
            # we have a single top-level directory
            move_dirs = os.listdir( top_dir )
            for d in move_dirs:
                shutil.move( os.path.join( top_dir, d ), os.path.join( path, d ) )
            shutil.rmtree( top_dir )
            return True
        return False


    @classmethod
    def extract( cls, filename, target_dir ):
        os.makedirs( target_dir )
        if tarfile.is_tarfile( filename ):
            logger.debug( "Extracting [{}] into [{}]".format( as_info( filename ), as_info( target_dir ) ) )
            try:
                with tarfile.TarFile( filename ) as tf:
                    tf.extractall( target_dir )
            except tarfile.ReadError:
                command = "tar -xf {filename}".format( filename=filename )
                if subprocess.call( shlex.split( command ), cwd=target_dir ) != 0:
                    raise LocationException( "Could not untar downloaded file from [{}]".format( filename ) )

        if zipfile.is_zipfile( filename ):
            logger.debug( "Extracting [{}] into [{}]".format( as_info( filename ), as_info( target_dir ) ) )
            with zipfile.ZipFile( filename ) as zf:
                zf.extractall( target_dir )

        while cls.remove_common_top_directory_under( target_dir ):
            pass


    @classmethod
    def url_is_download_archive_url( cls, path ):
        base, download = os.path.split( path )
        if download == "download":
            return pip_is_archive_file( base )
        else:
            return pip_is_archive_file( path )


    def folder_name_from_path( self, path, cuppa_env ):

        replacement_regex = r'[$\\/+:() ]'

        def is_url( path ):
            return isinstance( path, ParseResult )

        def name_from_url( url ):
            return self.url_replacement_char.join( [ url.scheme, url.netloc, unquote( url.path ) ] )

        def short_name_from_url( url ):
            return re.sub( replacement_regex, self.url_replacement_char, unquote( url.path ) )

        def name_from_file( path ):
            folder_name = os.path.splitext( path_leaf( path ) )[0]
            name, ext = os.path.splitext( folder_name )
            if ext == ".tar":
                folder_name = name
            return folder_name

        def name_from_dir( path ):
            if not os.path.isabs( path ):
                path = os.path.normpath( os.path.join( cuppa_env['sconstruct_dir'], path ) )
                logger.debug( "normalised path = [{}]".format( path ) )
            common, tail1, tail2 = split_common( cuppa_env['abs_sconscript_dir'], os.path.abspath( path ) )
            logger.debug( "common[{}], tail1[{}], tail2[{}]".format( as_notice( common ), as_notice( tail1 ), as_notice( tail2 ) ) )
            return tail2 and tail2 or ""

        local_folder = is_url( path ) and name_from_url( path ) or os.path.isfile( path ) and name_from_file( path ) or name_from_dir( path )
        local_folder = re.sub( replacement_regex, self.url_replacement_char, local_folder )

        if platform.system() == "Windows":
            # Windows suffers from MAX_PATH limitations so we'll use a hash to shorten the name
            hasher = hashlib.md5()
            hasher.update( local_folder )
            digest = hasher.hexdigest()
            short_digest = digest[-8:]
            name_hint = self._name_hint
            if not name_hint:
                name_hint = is_url( path ) and short_name_from_url( path ) or local_folder
                name_hint = name_hint[:8]
            local_folder = name_hint + short_digest

        return local_folder


    def local_folder( self ):
        return self._local_folder


    def expand_secret( self, vcs_location ):
        expanded = os.path.expandvars( vcs_location )
        if expanded != vcs_location:
            self._expanded_location = expanded.split('+')[1]
            self._plain_location = vcs_location.split('+')[1]
            register_secret( self._expanded_location, self._plain_location )
        return expanded


    def get_local_directory( self, cuppa_env, location, sub_dir, branch, full_url ):

        offline = cuppa_env['offline']
        local_directory = None

        base = cuppa_env['download_root']
        if not os.path.isabs( base ):
            base = os.path.join( cuppa_env['working_dir'], base )

        if location.startswith( 'file:' ):
            location = pip_download.url_to_path( location )

        if not pip_is_url( location ):

            if pip_is_archive_file( location ):

                self._local_folder = self.folder_name_from_path( location, cuppa_env )
                local_directory = os.path.join( base, self._local_folder )

                local_dir_with_sub_dir = os.path.join( local_directory, sub_dir and sub_dir or "" )

                if os.path.exists( local_dir_with_sub_dir ):
                    try:
                        os.rmdir( local_dir_with_sub_dir )
                    except:
                        return local_directory

                self.extract( location, local_dir_with_sub_dir )
                logger.debug( "(local archive) Location = [{}]".format( as_info( location ) ) )
                logger.debug( "(local archive) Local folder = [{}]".format( as_info( self._local_folder ) ) )

            else:
                local_directory = branch and os.path.join( location, branch ) or location
                self._local_folder = self.folder_name_from_path( location, cuppa_env )

                logger.debug( "(local file) Location = [{}]".format( as_info( location ) ) )
                logger.debug( "(local file) Local folder = [{}]".format( as_info( self._local_folder ) ) )

            return local_directory
        else:

            self._local_folder = self.folder_name_from_path( full_url, cuppa_env )
            local_directory = os.path.join( base, self._local_folder )

            if full_url.scheme.startswith( 'http' ) and self.url_is_download_archive_url( full_url.path ):
                logger.debug( "[{}] is an archive download".format( as_info( location ) ) )

                local_dir_with_sub_dir = os.path.join( local_directory, sub_dir and sub_dir or "" )

                # First we check to see if we already downloaded and extracted this archive before
                if os.path.exists( local_dir_with_sub_dir ):
                    try:
                        # If not empty this will fail
                        os.rmdir( local_dir_with_sub_dir )
                    except:
                        # Not empty so we'll return this as the local_directory

                        logger.debug( "(already present) Location = [{}]".format( as_info( location ) ) )
                        logger.debug( "(already present) Local folder = [{}]".format( as_info( str(self._local_folder) ) ) )

                        return local_directory

                if cuppa_env['dump'] or cuppa_env['clean']:
                    return local_directory

                # If not we then check to see if we cached the download
                cached_archive = self.get_cached_archive( cuppa_env['cache_root'], self._local_folder )
                if cached_archive:
                    logger.debug( "Cached archive [{}] found for [{}]".format(
                            as_info( cached_archive ),
                            as_info( location )
                    ) )
                    self.extract( cached_archive, local_dir_with_sub_dir )
                else:
                    logger.info( "Downloading [{}]...".format( as_info( location ) ) )
                    try:
                        report_hook = None
                        if logger.isEnabledFor( logging.INFO ):
                            report_hook = ReportDownloadProgress()
                        filename, headers = urlretrieve( location, reporthook=report_hook )
                        name, extension = os.path.splitext( filename )
                        logger.info( "[{}] successfully downloaded to [{}]".format(
                                as_info( location ),
                                as_info( filename )
                        ) )
                        self.extract( filename, local_dir_with_sub_dir )
                        if cuppa_env['cache_root']:
                            cached_archive = os.path.join( cuppa_env['cache_root'], self._local_folder )
                            logger.debug( "Caching downloaded file as [{}]".format( as_info( cached_archive ) ) )
                            shutil.copyfile( filename, cached_archive )
                    except ContentTooShortError as error:
                        logger.error( "Download of [{}] failed with error [{}]".format(
                                as_error( location ),
                                as_error( str(error) )
                        ) )
                        raise LocationException( error )

            elif '+' in full_url.scheme:
                vc_type = location.split('+', 1)[0]
                backend = pip_vcs.vcs.get_backend( vc_type )
                if backend:
                    try:
                        vcs_backend = backend( self.expand_secret( location ) )
                    except: # Pip version >= 19
                        backend.url = self.expand_secret( location )
                        vcs_backend = backend
                    local_dir_with_sub_dir = os.path.join( local_directory, sub_dir and sub_dir or "" )

                    if cuppa_env['dump'] or cuppa_env['clean']:
                        return local_directory

                    if os.path.exists( local_directory ):
                        url, repository, branch, remote, revision = self.get_info( location, local_dir_with_sub_dir, full_url, vc_type )
                        rev_options = self.get_rev_options( vc_type, vcs_backend, local_remote=remote )
                        version = self.ver_rev_summary( branch, revision, self._full_url.path )[0]
                        if not offline:
                            logger.info( "Updating [{}] in [{}]{} at [{}]".format(
                                    as_info( location ),
                                    as_notice( local_dir_with_sub_dir ),
                                    ( rev_options and  " on {}".format( as_notice( str(rev_options) ) ) or "" ),
                                    as_info( version )
                            ) )
                            try:
                                update( vcs_backend, local_dir_with_sub_dir, rev_options )
                                logger.debug( "Successfully updated [{}]".format( as_info( location ) ) )
                            except pip_exceptions.PipError as error:
                                logger.warn( "Could not update [{}] in [{}]{} due to error [{}]".format(
                                        as_warning( location ),
                                        as_warning( local_dir_with_sub_dir ),
                                        ( rev_options and  " at {}".format( as_warning( str(rev_options) ) ) or "" ),
                                        as_warning( str(error) )
                                ) )
                        else:
                            logger.debug( "Skipping update for [{}] as running in offline mode".format( as_info( location ) ) )
                    else:
                        rev_options = self.get_rev_options( vc_type, vcs_backend )
                        action = "Cloning"
                        if vc_type == "svn":
                            action = "Checking out"
                        max_attempts = 2
                        attempt = 1
                        while attempt <= max_attempts:
                            logger.info( "{} [{}] into [{}]{}".format(
                                    action,
                                    as_info( location ),
                                    as_info( local_dir_with_sub_dir ),
                                    attempt > 1 and "(attempt {})".format( str(attempt) ) or ""
                            ) )
                            try:
                                try:
                                    vcs_backend.obtain( local_dir_with_sub_dir )
                                except TypeError as e: # Pip version >= 19
                                    vcs_backend.obtain( local_dir_with_sub_dir, pip_hide_url( vcs_backend.url ) )
                                logger.debug( "Successfully retrieved [{}]".format( as_info( location ) ) )
                                break
                            except pip_exceptions.PipError as error:
                                attempt = attempt + 1
                                log_as = logger.warn
                                if attempt > max_attempts:
                                    log_as = logger.error

                                log_as( "Could not retrieve [{}] into [{}]{} due to error [{}]".format(
                                        as_info( location ),
                                        as_notice( local_dir_with_sub_dir ),
                                        ( rev_options and  " to {}".format( as_notice(  str(rev_options) ) ) or ""),
                                        as_error( str(error) )
                                ) )
                                if attempt > max_attempts:
                                    raise LocationException( str(error) )

                logger.debug( "(url path) Location = [{}]".format( as_info( location ) ) )
                logger.debug( "(url path) Local folder = [{}]".format( as_info( self._local_folder ) ) )

            return local_directory


    def get_rev_options( self, vc_type, vcs_backend, local_remote=None ):
        url, rev = get_url_rev( vcs_backend )

        logger.debug( "make_rev_options for [{}] at url [{}] with rev [{}]/[{}]".format(
            as_info( vc_type ),
            as_notice( str(url) ),
            as_notice( str(rev) ),
            as_notice( str(local_remote) )
        ) )

        return make_rev_options( vc_type, vcs_backend, url, rev, local_remote )


    @classmethod
    def retrieve_repo_info( cls, vcs_system, vcs_directory, expected_vc_type ):
        if not expected_vc_type or expected_vc_type == vcs_system.vc_type():
            try:
                info = vcs_system.info( vcs_directory )
                return info
            except vcs_system.Error as ex:
                if expected_vc_type:
                    logger.error( "Failed to retreive info for [{}] because [{}]".format(
                            as_error( vcs_directory ),
                            as_error( str(ex) )
                    ) )
                    raise
                return None


    @classmethod
    def get_info( cls, location, local_directory, full_url, expected_vc_type = None ):

        url        = location
        repository = urlunparse( ( full_url.scheme, full_url.netloc, '',  '',  '',  '' ) )
        branch     = unquote( full_url.path )
        remote     = None
        revision   = None

        info = ( url, repository, branch, remote, revision )

        vcs_info = cls.detect_vcs_info( local_directory, expected_vc_type )
        if vcs_info:
            return vcs_info

        return info


    @classmethod
    def detect_vcs_info( cls, local_directory, expected_vc_type = None ):
        vcs_systems = [
            git.Git,
            subversion.Subversion,
            mercurial.Mercurial,
            bazaar.Bazaar
        ]

        for vcs_system in vcs_systems:
            vcs_info = cls.retrieve_repo_info( vcs_system, local_directory, expected_vc_type )
            if vcs_info:
                return vcs_info
        return None


    def ver_rev_summary( self, branch, revision, full_url_path ):
        if branch and revision:
            version = ' rev. '.join( [ str(branch), str(revision) ] )
        elif branch and revision:
            version = ' rev. '.join( [ str(branch), str(revision) ] )
        else:
            version = os.path.splitext( path_leaf( unquote( full_url_path ) ) )[0]
            name, ext = os.path.splitext( version )
            if ext == ".tar":
                version = name
            version = version
            revision = "not under version control"
        return version, revision


    @classmethod
    def replace_sconstruct_anchor( cls, path, cuppa_env ):
        if path.startswith( "#" ):
            path = os.path.join( cuppa_env['sconstruct_dir'], path[1:] )
        return path


    def __init__( self, cuppa_env, location, develop=None, branch=None, extra_sub_path=None, name_hint=None ):

        logger.debug( "Create location using location=[{}], develop=[{}], branch=[{}], extra_sub_path=[{}], name_hint=[{}]".format(
                as_info( location ),
                as_info( str(develop) ),
                as_info( str(branch) ),
                as_info( str(extra_sub_path) ),
                as_info( str(name_hint) )
        ) )

        location = self.replace_sconstruct_anchor( location, cuppa_env )

        if develop:
            if not os.path.isabs( develop ):
                develop = '#' + develop
            develop = self.replace_sconstruct_anchor( develop, cuppa_env )
            logger.debug( "Develop location specified [{}]".format( as_info( develop ) ) )

        if 'develop' in cuppa_env and cuppa_env['develop'] and develop:
            location = develop
            logger.debug( "--develop specified so using location=develop=[{}]".format( as_info( develop ) ) )

        self._location   = os.path.expanduser( location )
        self._full_url   = urlparse( self._location )
        self._sub_dir    = None
        self._name_hint  = name_hint

        self._expanded_location = None
        self._plain_location = ""

        if extra_sub_path:
            if os.path.isabs( extra_sub_path ):
                raise LocationException( "Error extra sub path [{}] is not relative".format(extra_sub_path) )
            else:
                self._sub_dir = os.path.normpath( extra_sub_path )

        ## Get the location for the source dependency. If the location is a URL or an Archive we'll need to
        ## retrieve the URL and extract the archive. get_local_directory() returns the location of the source
        ## once this is done
        local_directory = self.get_local_directory( cuppa_env, self._location, self._sub_dir, branch, self._full_url )

        logger.trace( "Local Directory for [{}] returned as [{}]".format(
                as_notice( self._location ),
                as_notice( local_directory )
        ) )

        self._base_local_directory = local_directory
        self._local_directory = self._sub_dir and os.path.join( local_directory, self._sub_dir ) or local_directory

        ## Now that we have a locally accessible version of the dependency we can try to collate some information
        ## about it to allow us to specify what we are building with.
        self._url, self._repository, self._branch, self._remote, self._revision = self.get_info( self._location, self._local_directory, self._full_url )
        self._version, self._revision = self.ver_rev_summary( self._branch, self._revision, self._full_url.path )

        logger.debug( "Using [{}]{}{} at [{}] stored in [{}]".format(
                as_info( location ),
                ( self._branch and ":[{}]".format( as_info( str(self._branch) ) ) or "" ),
                ( self._remote and " from [{}]".format( as_info( str(self._remote) ) ) or "" ),
                as_info( self._version ),
                as_notice( self._local_directory )
        ) )


    def local( self ):
        return self._local_directory


    def base_local( self ):
        return self._base_local_directory


    def sub_dir( self ):
        return self._sub_dir


    def location( self ):
        return self._location


    def url( self ):
        return self._url


    def branch( self ):
        return self._branch


    def remote( self ):
        return self._remote


    def repository( self ):
        return self._repository


    def version( self ):
        return str(self._version)


    def revisions( self ):
        return [ self._revision ]


