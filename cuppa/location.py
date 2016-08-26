#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Location
#-------------------------------------------------------------------------------

import os
import urlparse
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

import pip.vcs
import pip.download
import pip.exceptions

import scms.subversion
import scms.git
import scms.mercurial

from cuppa.colourise import as_notice, as_info, as_warning, as_error
from cuppa.log import logger


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


    def remove_common_top_directory_under( self, path ):
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


    def extract( self, filename, target_dir ):
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

        while self.remove_common_top_directory_under( target_dir ):
            pass


    def url_is_download_archive_url( self, path ):
        base, download = os.path.split( path )
        if download == "download":
            return pip.download.is_archive_file( base )
        else:
            return pip.download.is_archive_file( path )


    def folder_name_from_path( self, path ):

        def is_url( path ):
            return isinstance( path, urlparse.ParseResult )

        def name_from_url( url ):
            return self.url_replacement_char.join( [ url.scheme, url.netloc, urllib.unquote( url.path ) ] )

        def short_name_from_url( url ):
            return re.sub( r'[\\/+:() ]', self.url_replacement_char, urllib.unquote( url.path ) )

        def name_from_path( path ):
            folder_name = os.path.splitext( path_leaf( path ) )[0]
            name, ext = os.path.splitext( folder_name )
            if ext == ".tar":
                folder_name = name
            return folder_name

        local_folder = is_url( path ) and name_from_url( path ) or name_from_path( path )
        local_folder = re.sub( r'[\\/+:() ]', self.url_replacement_char, local_folder )

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


    def get_local_directory( self, cuppa_env, location, sub_dir, branch, full_url ):

        local_directory = None

        base = cuppa_env['download_root']
        if not os.path.isabs( base ):
            base = os.path.join( cuppa_env['working_dir'], base )

        if location.startswith( 'file:' ):
            location = pip.download.url_to_path( location )

        if not pip.download.is_url( location ):

            if pip.download.is_archive_file( location ):

                local_folder = self.folder_name_from_path( location )
                local_directory = os.path.join( base, local_folder )

                if os.path.exists( local_directory ):
                    try:
                        os.rmdir( local_directory )
                    except:
                        return local_directory, False

                self.extract( location, local_directory )
            else:
                local_directory = branch and os.path.join( location, branch ) or location
                return local_directory, False
        else:

            local_folder = self.folder_name_from_path( full_url )
            local_directory = os.path.join( base, local_folder )

            if full_url.scheme.startswith( 'http' ) and self.url_is_download_archive_url( full_url.path ):
                logger.debug( "[{}] is an archive download".format( as_info( location ) ) )

                local_dir_with_sub_dir = os.path.join( local_directory, sub_dir )

                # First we check to see if we already downloaded and extracted this archive before
                if os.path.exists( local_dir_with_sub_dir ):
                    try:
                        # If not empty this will fail
                        os.rmdir( local_dir_with_sub_dir )
                    except:
                        # Not empty so we'll return this as the local_directory
                        return local_directory, True

                # If not we then check to see if we cached the download
                cached_archive = self.get_cached_archive( cuppa_env['cache_root'], local_folder )
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
                        filename, headers = urllib.urlretrieve( location, reporthook=report_hook )
                        name, extension = os.path.splitext( filename )
                        logger.info( "[{}] successfully downloaded to [{}]".format(
                                as_info( location ),
                                as_info( filename )
                        ) )
                        self.extract( filename, local_dir_with_sub_dir )
                        if cuppa_env['cache_root']:
                            cached_archive = os.path.join( cuppa_env['cache_root'], local_folder )
                            logger.debug( "Caching downloaded file as [{}]".format( as_info( cached_archive ) ) )
                            shutil.copyfile( filename, cached_archive )
                    except urllib.ContentTooShortError as error:
                        logger.error( "Download of [{}] failed with error [{}]".format(
                                as_error( location ),
                                as_error( str(error) )
                        ) )
                        raise LocationException( "Error obtaining [{}]: {}".format( location, error ) )

            elif '+' in full_url.scheme:
                vc_type = location.split('+', 1)[0]
                backend = pip.vcs.vcs.get_backend( vc_type )
                if backend:
                    vcs_backend = backend( location )
                    rev_options = self.get_rev_options( vc_type, vcs_backend )

                    local_dir_with_sub_dir = os.path.join( local_directory, sub_dir )

                    if os.path.exists( local_directory ):

                        url, repository, branch, revision = self.get_info( location, local_dir_with_sub_dir, full_url )
                        version = self.ver_rev_summary( branch, revision, self._full_url.path )[0]
                        logger.debug( "Updating [{}] in [{}]{} at [{}]".format(
                                as_info( location ),
                                as_notice( local_dir_with_sub_dir ),
                                ( rev_options and  " on {}".format( as_notice( str(rev_options) ) ) or "" ),
                                as_info( version )
                        ) )
                        try:
                            vcs_backend.update( local_dir_with_sub_dir, rev_options )
                            logger.debug( "Successfully updated [{}]".format( as_info( location ) ) )
                        except pip.exceptions.InstallationError as error:
                            logger.warn( "Could not update [{}] in [{}]{} due to error [{}]".format(
                                    as_warning( location ),
                                    as_warning( local_dir_with_sub_dir ),
                                    ( rev_options and  " at {}".format( as_warning( str(rev_options) ) ) or "" ),
                                    as_warning( str(error) )
                            ) )
                    else:
                        action = "Cloning"
                        if vc_type == "svn":
                            action = "Checking out"
                        logger.info( "{} [{}] into [{}]".format(
                                action, as_info( location ),
                                as_info( local_dir_with_sub_dir )
                        ) )
                        try:
                            vcs_backend.obtain( local_dir_with_sub_dir )
                            logger.debug( "Successfully retrieved [{}]".format( as_info( location ) ) )
                        except pip.exceptions.InstallationError as error:
                            logger.error( "Could not retrieve [{}] into [{}]{} due to error [{}]".format(
                                    as_error( location ),
                                    as_error( local_dir_with_sub_dir ),
                                    ( rev_options and  " to {}".format( as_error(  str(rev_options) ) ) or ""),
                                    as_error( str( error ) )
                            ) )
                            raise LocationException( "Error obtaining [{}]: {}".format( location, error ) )

            return local_directory, True


    def get_rev_options( self, vc_type, vcs_backend ):
        url, rev = vcs_backend.get_url_rev()
        if vc_type == 'git':
            if rev:
                return [rev]
            else:
                return ['origin/master']
        elif vc_type == 'hg' and rev:
            return vcs_backend.get_rev_options( url, rev )
        elif vc_type == 'bzr' and rev:
            return ['-r', rev]
        return []


    def get_info( self, location, local_directory, full_url ):

        url        = location
        repository = urlparse.urlunparse( ( full_url.scheme, full_url.netloc, '',  '',  '',  '' ) )
        branch     = urllib.unquote( full_url.path )
        revision   = None

        info = ( url, repository, branch, revision )

        vcs_directory = local_directory
        try:
            info = scms.git.info( vcs_directory )
            return info
        except scms.git.GitException:
            pass
        try:
            info = scms.subversion.info( vcs_directory )
            return info
        except scms.subversion.SubversionException:
            pass
        try:
            info = scms.mercurial.info( vcs_directory )
            return info
        except scms.mercurial.MercurialException:
            pass

        return info


    def ver_rev_summary( self, branch, revision, full_url_path ):
        if branch and revision:
            version = ' rev. '.join( [ str(branch), str(revision) ] )
        elif branch and revision:
            version = ' rev. '.join( [ str(branch), str(revision) ] )
        else:
            version = os.path.splitext( path_leaf( urllib.unquote( full_url_path ) ) )[0]
            name, ext = os.path.splitext( version )
            if ext == ".tar":
                version = name
            version = version
            revision = "not under version control"
        return version, revision


    def __init__( self, cuppa_env, location, branch=None, extra_sub_path=None, name_hint=None ):

        self._location   = location
        self._full_url   = urlparse.urlparse( location )
        self._sub_dir    = ""
        self._name_hint  = name_hint

        if extra_sub_path:
            if os.path.isabs( extra_sub_path ):
                raise LocationException( "Error extra sub path [{}] is not relative".format(extra_sub_path) )
            else:
                self._sub_dir = os.path.normpath( extra_sub_path )

        ## Get the location for the source dependency. If the location is a URL or an Archive we'll need to
        ## retrieve the URL and extract the archive. get_local_directory() returns the location of the source
        ## once this is done
        local_directory, use_sub_dir = self.get_local_directory( cuppa_env, location, self._sub_dir, branch, self._full_url )

        self._base_local_directory = local_directory
        self._local_directory = use_sub_dir and os.path.join( local_directory, self._sub_dir ) or local_directory

        ## Now that we have a locally accessible version of the dependency we can try to collate some information
        ## about it to allow us to specify what we are building with.
        self._url, self._repository, self._branch, self._revision = self.get_info( self._location, self._local_directory, self._full_url )
        self._version, self._revision = self.ver_rev_summary( self._branch, self._revision, self._full_url.path )

        logger.debug( "Using [{}]{} at [{}] stored in [{}]".format(
                as_info( location ),
                ( branch and  ":[{}]".format( as_info(  str(branch) ) ) or "" ),
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


    def repository( self ):
        return self._repository


    def version( self ):
        return str(self._version)


    def revisions( self ):
        return [ self._revision ]


