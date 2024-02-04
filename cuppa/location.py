#          Copyright Jamie Allsop 2014-2020
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

from .scms import scms, subversion, git, mercurial, bazaar

from cuppa.colourise import as_notice, as_info, as_warning, as_error, as_info_label
from cuppa.log import logger, register_secret
from cuppa.path import split_common
from cuppa.utility.python2to3 import as_str

from cuppa.utility.pip_imports import pip_vcs, pip_download, pip_exceptions, pip_is_url, pip_is_archive_file, get_url_rev, obtain, update, make_rev_options


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


    def option_set( self, option ):
        return option in self._cuppa_env and self._cuppa_env[option] or False


    def location_match_current_branch( self ):
        return 'location_match_current_branch' in self._cuppa_env and self._cuppa_env['location_match_current_branch']


    def location_match_branch( self ):
        return 'location_match_branch' in self._cuppa_env and self._cuppa_env['location_match_branch']


    def location_match_tag( self ):
        return 'location_match_tag' in self._cuppa_env and self._cuppa_env['location_match_tag']


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


    def folder_name_from_path( self, path ):

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
                path = os.path.normpath( os.path.join( self._cuppa_env['sconstruct_dir'], path ) )
                logger.debug( "normalised path = [{}]".format( path ) )
            common, tail1, tail2 = split_common( self._cuppa_env['abs_sconscript_dir'], os.path.abspath( path ) )
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


    @classmethod
    def expand_secret( cls, vcs_location ):
        expanded = os.path.expandvars( vcs_location )
        if expanded != vcs_location:
            expanded_location = expanded.split('+')[1]
            plain_location = vcs_location.split('+')[1]
            register_secret( expanded_location, plain_location )
        return expanded


    def get_local_directory_for_non_url( self, location, sub_dir, branch_path, base ):

        if pip_is_archive_file( location ):

            self._local_folder = self.folder_name_from_path( location )
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
            local_directory = branch_path and os.path.join( location, branch_path ) or location
            self._local_folder = self.folder_name_from_path( location )

            logger.debug( "(local file) Location = [{}]".format( as_info( location ) ) )
            logger.debug( "(local file) Local folder = [{}]".format( as_info( self._local_folder ) ) )

        return local_directory


    def get_local_directory_for_download_url( self, location, sub_dir, local_directory ):

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

        if self._cuppa_env['dump'] or self._cuppa_env['clean']:
            return local_directory

        # If not we then check to see if we cached the download
        cached_archive = self.get_cached_archive( self._cuppa_env['cache_root'], self._local_folder )
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
                if self._cuppa_env['cache_root']:
                    cached_archive = os.path.join( self._cuppa_env['cache_root'], self._local_folder )
                    logger.debug( "Caching downloaded file as [{}]".format( as_info( cached_archive ) ) )
                    shutil.copyfile( filename, cached_archive )
            except ContentTooShortError as error:
                logger.error( "Download of [{}] failed with error [{}]".format(
                        as_error( location ),
                        as_error( str(error) )
                ) )
                raise LocationException( error )

        return local_directory


    def update_from_repository( self, location, full_url, local_dir_with_sub_dir, vc_type, vcs_backend ):
        url, repository, branch, remote, revision = self.get_info( location, local_dir_with_sub_dir, full_url, vc_type )
        rev_options = self.get_rev_options( vc_type, vcs_backend, local_remote=remote )
        version = self.ver_rev_summary( branch, revision, self._full_url.path )[0]
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


    def obtain_from_repository( self, location, full_url, local_dir_with_sub_dir, vc_type, vcs_backend ):
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
                obtain( vcs_backend, local_dir_with_sub_dir, vcs_backend.url )
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


    def get_local_directory_for_repository( self, location, sub_dir, full_url, local_directory ):
        vc_type = location.split('+', 1)[0]
        backend = pip_vcs.vcs.get_backend( vc_type )
        if not backend:
            logger.error( "URL VC of [{}] for [{}] NOT recognised so location cannot be retrieved".format(
                        as_error( vc_type ),
                        as_error( location )
            ) )
            raise LocationException( "URL VC of [{}] for [{}] NOT recognised so location cannot be retrieved".format( vc_type, location ) )

        if self._cuppa_env['dump']:
            return local_directory

        local_dir_with_sub_dir = os.path.join( local_directory, sub_dir and sub_dir or "" )

        if not self._offline and not self._cuppa_env['clean']:
            try:
                vcs_backend = backend( self.expand_secret( location ) )
            except: # Pip version >= 19
                backend.url = self.expand_secret( location )
                vcs_backend = backend

            if os.path.exists( local_directory ):
                self.update_from_repository( location, full_url, local_dir_with_sub_dir, vc_type, vcs_backend )
            else:
                self.obtain_from_repository( location, full_url, local_dir_with_sub_dir, vc_type, vcs_backend )

            logger.debug( "(url path) Location = [{}]".format( as_info( location ) ) )
            logger.debug( "(url path) Local folder = [{}]".format( as_info( self._local_folder ) ) )
        else:
            branched_local_directory = None

            if self.location_match_current_branch():
                # If relative versioning is in play and we are offline check first to see
                # if the specified branch or tag is available and prefer that one
                if self._supports_relative_versioning and self._current_branch:
                    branched_local_directory = local_directory + "@" + self._current_branch
                    if os.path.exists( branched_local_directory ):
                        return branched_local_directory

                elif self._supports_relative_versioning and self._current_revision:
                    branched_local_directory = local_directory + "@" + self._current_revision
                    if os.path.exists( branched_local_directory ):
                        return branched_local_directory

            elif self.location_match_branch():
                if self._supports_relative_versioning:
                    branched_local_directory = local_directory + "@" + self.location_match_branch()
                    if os.path.exists( branched_local_directory ):
                        return branched_local_directory

            elif self.location_match_tag():
                if self._supports_relative_versioning:
                    branched_local_directory = local_directory + "@" + self.location_match_tag()
                    if os.path.exists( branched_local_directory ):
                        return branched_local_directory

            elif self._supports_relative_versioning and self._default_branch:
                branched_local_directory = local_directory + "@" + self._default_branch
                if os.path.exists( branched_local_directory ):
                    return branched_local_directory

            # If the preferred branch is not available then fallback to the
            # default of no branch being specified
            if os.path.exists( local_directory ):
                return local_directory
            else:
                if self.location_match_current_branch():
                    logger.error(
                        "Running in {offline} mode and neither [{local_dir}] or a branched dir"
                        " [{branched_dir}] exists so location cannot be retrieved".format(
                            offline      = as_info_label("OFFLINE"),
                            local_dir    = as_error(local_directory),
                            branched_dir = as_error(str(branched_local_directory))
                    ) )
                    raise LocationException(
                        "Running in {offline} mode and neither [{local_dir}] or a branched dir"
                        " [{branched_dir}] exists so location cannot be retrieved".format(
                            offline      = "OFFLINE",
                            local_dir    = local_directory,
                            branched_dir = str(branched_local_directory)
                    ) )
                else:
                    logger.error(
                        "Running in {offline} mode and [{local_dir}] does not exist"
                        " so location cannot be retrieved".format(
                            offline      = as_info_label("OFFLINE"),
                            local_dir    = as_error(local_directory)
                    ) )
                    raise LocationException(
                        "Running in {offline} mode and [{local_dir}] does not exist"
                        " so location cannot be retrieved".format(
                            offline      = "OFFLINE",
                            local_dir    = local_directory
                    ) )

        return local_directory


    def get_local_directory( self, location, sub_dir, branch_path, full_url ):

        logger.debug( "Determine local directory for [{location}] when {offline}".format(
                location=as_info(location),
                offline= self._offline and as_info_label("OFFLINE") or "online"
        ) )

        local_directory = None

        base = self._cuppa_env['download_root']
        if not os.path.isabs( base ):
            base = os.path.join( self._cuppa_env['working_dir'], base )

        if location.startswith( 'file:' ):
            location = pip_download.url_to_path( location )

        if not pip_is_url( location ):
            return self.get_local_directory_for_non_url( location, sub_dir, branch_path, base )

        else:
            self._local_folder = self.folder_name_from_path( full_url )
            local_directory = os.path.join( base, self._local_folder )

            if full_url.scheme.startswith( 'http' ) and self.url_is_download_archive_url( full_url.path ):
                return self.get_local_directory_for_download_url( location, sub_dir, local_directory )

            elif '+' in full_url.scheme:
                return self.get_local_directory_for_repository( location, sub_dir, full_url, local_directory )

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
                logger.trace( "expected_vc_type=[{expected_vc_type}], vcs_system=[{vc_type}], vcs_directory=[{directory}]".format(
                        expected_vc_type=as_info( str(expected_vc_type) ),
                        vc_type=as_info( vcs_system and vcs_system.vc_type() or "None" ),
                        directory=as_notice( str(vcs_directory) )
                ) )

                info = vcs_system.info( vcs_directory )

                logger.trace( "vcs_info=[{vcs_info}]".format( vcs_info=as_info(str(info)) ) )

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

        vcs_info = cls.detect_vcs_info( local_directory, expected_vc_type )
        if vcs_info:
            return tuple( as_str(t) for t in vcs_info )

        url         = location
        repository  = urlunparse( ( full_url.scheme, full_url.netloc, '',  '',  '',  '' ) )
        branch_path = unquote( full_url.path )
        remote      = None
        revision    = None

        return ( url, repository, branch_path, remote, revision )


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
        elif not branch and revision:
            version = 'rev. ' + str(revision)
        elif branch:
            version = str(branch)
        else:
            version = os.path.splitext( path_leaf( unquote( full_url_path ) ) )[0]
            name, ext = os.path.splitext( version )
            if ext == ".tar":
                version = name
            version = version
            revision = "not under version control"
        return version, revision


    def replace_sconstruct_anchor( self, path ):
        if path.startswith( "#" ):
            path = os.path.join( self._cuppa_env['sconstruct_dir'], path[1:] )
        return path


    @classmethod
    def get_scm_system_and_info( cls, location ):
        full_url = urlparse( location )
        #print( str(full_url) )
        if '+' in full_url.scheme:
            vc_type, scheme = full_url.scheme.split('+')
            path_elements = full_url.path.split('@')
            versioning = ''
            if len(path_elements) > 1:
                versioning = path_elements[1]
            repo_location = urlunparse( (scheme, full_url.netloc, path_elements[0], '', '', '', ) )
            return scms.get_scms( vc_type ), vc_type, repo_location, versioning
        return None, None, None, None


    def __init__( self, cuppa_env, location, develop=None, branch_path=None, extra_sub_path=None, name_hint=None ):

        logger.debug( "Create location using location=[{}], develop=[{}], branch_path=[{}], extra_sub_path=[{}], name_hint=[{}]".format(
                as_info( location ),
                as_info( str(develop) ),
                as_info( str(branch_path) ),
                as_info( str(extra_sub_path) ),
                as_info( str(name_hint) )
        ) )

        self._cuppa_env = cuppa_env
        self._supports_relative_versioning = False
        self._current_branch = self._cuppa_env['current_branch']
        self._current_revision = self._cuppa_env['current_revision']
        self._offline = self.option_set('offline')
        offline = self._offline
        self._default_branch = self._cuppa_env['location_default_branch']

        location = self.replace_sconstruct_anchor( location )

        if develop:
            if not os.path.isabs( develop ):
                develop = '#' + develop
            develop = self.replace_sconstruct_anchor( develop )
            logger.debug( "Develop location specified [{}]".format( as_info( develop ) ) )

        if self.option_set('develop') and develop:
            location = develop
            logger.debug( "--develop specified so using location=develop=[{}]".format( as_info( develop ) ) )

        scm_location = location

        if location[-1] == '@':
            self._supports_relative_versioning = True
            scm_location = location[:-1]

        scm_system, vc_type, repo_location, versioning = self.get_scm_system_and_info( self.expand_secret( scm_location ) )

        logger.debug( "Local location and actions for [{location}] being determined in context:{offline}"
                      " vc_type=[{vc_type}], repo_location=[{repo_location}],"
                      " versioning=[{versioning}]".format(
                location = as_info(location),
                offline  = self._offline and " " + as_info_label("OFFLINE") + "," or "",
                vc_type = as_info(str(vc_type)),
                repo_location = as_info(str(repo_location)),
                versioning = as_info(str(versioning))
        ) )

        if self._supports_relative_versioning:
            if self.location_match_current_branch():
                if not scm_system:
                    logger.warn( "Location [{}] specified using relative versioning, but no SCM system is available"
                                 " that matches the version control type [{}]. Relative versioning will be ignored"
                                 " for this location.".format( location, vc_type ) )
                else:
                    logger.debug( "Relative branching active for [{location}] with"
                                  " current branch [{branch}] and current revision [{revision}]".format(
                            location=as_info(str(location)),
                            branch=as_info(str(self._current_branch)),
                            revision=as_info(str(self._current_revision))
                    ) )

                    if self._current_branch:
                        # Try to checkout on the explicit branch but if that fails fall back to
                        # to the default by stripping off the '@' from the end of the path
                        if not offline and scm_system.remote_branch_exists( repo_location, self._current_branch ):
                            scm_location = location + self._current_branch
                            logger.trace( "scm_location = [{scm_location}]".format(
                                    scm_location=as_info(str(scm_location))
                            ) )
                    elif self._current_revision:
                        # Try to checkout on the explicit branch but if that fails fall back to
                        # to the default by stripping off the '@' from the end of the path
                        if not offline and scm_system.remote_branch_exists( repo_location, self._current_revision ):
                            scm_location = location + self._current_revision
                            logger.trace( "scm_location = [{scm_location}]".format(
                                    scm_location=as_info(str(scm_location))
                            ) )

            elif self.location_match_branch():
                if not scm_system:
                    logger.warn( "Location [{}] specified using relative versioning, but no SCM system is available"
                                 " that matches the version control type [{}]. Relative versioning will be ignored"
                                 " for this location.".format( location, vc_type ) )
                else:
                    logger.debug( "Relative branching active for [{location}] with"
                                  " branch [{branch}]".format(
                            location=as_info(str(location)),
                            branch=as_info(str(self.location_match_branch()))
                    ) )

                    if self.location_match_branch():
                        # Try to checkout on the explicit branch but if that fails fall back to
                        # to the default by stripping off the '@' from the end of the path
                        if not offline and scm_system.remote_branch_exists( repo_location, self.location_match_branch() ):
                            scm_location = location + self.location_match_branch()
                            logger.trace( "scm_location = [{scm_location}]".format(
                                    scm_location=as_info(str(scm_location))
                            ) )

            elif self.location_match_tag():
                if not scm_system:
                    logger.warn( "Location [{}] specified using relative versioning, but no SCM system is available"
                                 " that matches the version control type [{}]. Relative versioning will be ignored"
                                 " for this location.".format( location, vc_type ) )
                else:
                    logger.debug( "Relative tagging active for [{location}] with"
                                  " tag [{revision}]".format(
                            location=as_info(str(location)),
                            revision=as_info(str(self.location_match_tag()))
                    ) )

                    if self.location_match_tag():
                        # Try to checkout on the explicit branch but if that fails fall back to
                        # to the default by stripping off the '@' from the end of the path
                        if not offline and scm_system.remote_branch_exists( repo_location, self.location_match_tag() ):
                            scm_location = location + self.location_match_tag()
                            logger.trace( "scm_location = [{scm_location}]".format(
                                    scm_location=as_info(str(scm_location))
                            ) )

            elif scm_system and not offline:
                self._default_branch = scm_system.remote_default_branch( repo_location )
                if self._default_branch:
                    scm_location = location + self._default_branch

        elif( scm_system
                and not versioning
                and not offline
                and self.option_set('location_explicit_default_branch')
        ):
            self._default_branch = scm_system.remote_default_branch( repo_location )
            if self._default_branch:
                scm_location = location + '@' + self._default_branch

        location = scm_location

        self._location   = os.path.expanduser( location )
        self._full_url   = urlparse( self._location )
        self._sub_dir    = None
        self._name_hint  = name_hint

        if extra_sub_path:
            if os.path.isabs( extra_sub_path ):
                raise LocationException( "Error extra sub path [{}] is not relative".format(extra_sub_path) )
            else:
                self._sub_dir = os.path.normpath( extra_sub_path )

        ## Get the location for the source dependency. If the location is a URL or an Archive we'll need to
        ## retrieve the URL and extract the archive. get_local_directory() returns the location of the source
        ## once this is done
        local_directory = self.get_local_directory( self._location, self._sub_dir, branch_path, self._full_url )

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


