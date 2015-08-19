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

import pip.vcs
import pip.download
import pip.exceptions

import scms.subversion
import scms.git
import scms.mercurial


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


class Location(object):


    def get_cached_archive( self, cache_root, path ):
        print "cuppa: location: Checking for cached archive [{}]...".format( self._as_info( path ) )
        for archive in os.listdir(cache_root):
            if fnmatch.fnmatch( archive, path ):
                print "cuppa: location: Found cached archive [{}] skipping download".format( self._as_info( archive ) )
                return os.path.join( cache_root, archive )
        return None


    def remove_common_top_directory_under( self, path ):
        dirs = os.listdir( path )
        if not dirs:
            raise LocationException( "Uncompressed archive [{}] is empty".format( path ) )
        top_dir = os.path.join( path, dirs[0] )
        if len(dirs) == 1 and os.path.isdir( top_dir ):
            print "cuppa: location: Removing redundant top directory [{}] from [{}]".format( self._as_info( dirs[0] ), self._as_info( path ) )
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
            print "cuppa: location: Extracting [{}] into [{}]".format( self._as_info( filename ), self._as_info( target_dir ) )
            try:
                with tarfile.TarFile( filename ) as tf:
                    tf.extractall( target_dir )
            except tarfile.ReadError:
                command = "tar -xf {filename}".format( filename=filename )
                if subprocess.call( shlex.split( command ), cwd=target_dir ) != 0:
                    raise LocationException( "Could not untar downloaded file from [{}]".format( filename ) )

        if zipfile.is_zipfile( filename ):
            print "cuppa: location: extracting [{}] into [{}]".format( self._as_info( filename ), self._as_info( target_dir ) )
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
            return '#'.join( [ url.scheme, url.netloc, urllib.unquote( url.path ) ] )

        def short_name_from_url( url ):
            return re.sub( r'[\\/+:() ]', r'#', urllib.unquote( url.path ) )

        def name_from_path( path ):
            folder_name = os.path.splitext( path_leaf( path ) )[0]
            name, ext = os.path.splitext( folder_name )
            if ext == ".tar":
                folder_name = name
            return folder_name

        local_folder = is_url( path ) and name_from_url( path ) or name_from_path( path )
        local_folder = re.sub( r'[\\/+:() ]', r'#', local_folder )

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


    def get_local_directory( self, env, location, sub_dir, branch, full_url ):

        local_directory = None

        base = env['download_root']
        if not os.path.isabs( base ):
            base = os.path.join( env['working_dir'], base )

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
                print "cuppa: location: [{}] is an archive download".format( self._as_info( location ) )

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
                cached_archive = self.get_cached_archive( env['cache_root'], local_folder )
                if cached_archive:
                    print "cuppa: location: Cached archive [{}] found for [{}]".format( self._as_info( cached_archive ), self._as_info( location ) )
                    self.extract( cached_archive, local_dir_with_sub_dir )
                else:
                    print "cuppa: location: downloading [{}]...".format( self._as_info( location ) )
                    filename, headers = urllib.urlretrieve( location )
                    name, extension = os.path.splitext( filename )
                    print "cuppa: location: [{}] successfully downloaded to [{}]".format( self._as_info( location ), self._as_info( filename ) )
                    self.extract( filename, local_dir_with_sub_dir )
                    if env['cache_root']:
                        cached_archive = os.path.join( env['cache_root'], local_folder )
                        print "cuppa: location: caching downloaded file as [{}]".format( self._as_info( cached_archive ) )
                        shutil.copyfile( filename, cached_archive )

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
                        print "cuppa: location: updating [{}] in [{}]{} at [{}]".format(
                                self._as_info( location ),
                                self._as_notice( local_dir_with_sub_dir ),
                                ( rev_options and  " on {}".format( self._as_notice( str(rev_options) ) ) or "" ),
                                self._as_info( version )
                        )
                        try:
                            vcs_backend.update( local_dir_with_sub_dir, rev_options )
                            print "cuppa: location: successfully updated [{}]".format( self._as_info( location ) )
                        except pip.exceptions.InstallationError as error:
                            print "cuppa: {}: location: could not update [{}] in [{}]{} due to error [{}]".format(
                                    self._as_warning_label( " warning " ),
                                    self._as_warning_text( location ),
                                    self._as_warning_text( local_dir_with_sub_dir ),
                                    ( rev_options and  " at {}".format( self._as_warning_text( str(rev_options) ) ) or "" ),
                                    self._as_warning_text( str(error) )
                            )
                    else:
                        action = "cloning"
                        if vc_type == "svn":
                            action = "checking out"
                        print "cuppa: location: {} [{}] into [{}]".format( action, self._as_info( location ), self._as_info( local_dir_with_sub_dir ) )
                        try:
                            vcs_backend.obtain( local_dir_with_sub_dir )
                            print "cuppa: location: successfully retrieved [{}]".format( self._as_info( location ) )
                        except pip.exceptions.InstallationError as error:
                            print "cuppa: {}: location: could not retrieve [{}] into [{}]{} due to error [{}]".format(
                                    self._as_error_label( " error " ),
                                    self._as_error_text( location ),
                                    self._as_error_text( local_dir_with_sub_dir ),
                                    ( rev_options and  " to {}".format( self._as_error_text(  str(rev_options) ) ) or ""),
                                    self._as_error_text( str( error ) )
                            )
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


    def _as_error_label( self, text ):
        return self._colouriser.highlight( 'error', text )


    def _as_error_text( self, text ):
        return self._colouriser.as_error( text )


    def _as_warning_label( self, text ):
        return self._colouriser.highlight( 'warning', text )


    def _as_warning_text( self, text ):
        return self._colouriser.as_warning( text )


    def _as_info( self, text ):
        return self._colouriser.as_info( text )


    def _as_notice( self, text ):
        return self._colouriser.as_notice( text )


    def __init__( self, env, location, branch=None, extra_sub_path=None, name_hint=None ):

        self._colouriser = env['colouriser']
        self._location   = location
        self._full_url   = urlparse.urlparse( location )
        self._sub_dir    = ""
        self._name_hint  = name_hint

        if extra_sub_path:
            if os.path.isabs( extra_sub_path ):
                raise LocationException()
            else:
                self._sub_dir = os.path.normpath( extra_sub_path )

        ## Get the location for the source dependency. If the location is a URL or an Archive we'll need to
        ## retrieve the URL and extract the archive. get_local_directory() returns the location of the source
        ## once this is done
        local_directory, use_sub_dir = self.get_local_directory( env, location, self._sub_dir, branch, self._full_url )

        self._base_local_directory = local_directory
        self._local_directory = use_sub_dir and os.path.join( local_directory, self._sub_dir ) or local_directory

        ## Now that we have a locally accessible version of the dependency we can try to collate some information
        ## about it to allow us to specify what we are building with.
        self._url, self._repository, self._branch, self._revision = self.get_info( self._location, self._local_directory, self._full_url )
        self._version, self._revision = self.ver_rev_summary( self._branch, self._revision, self._full_url.path )

        print "cuppa: location: using [{}]{} at [{}] stored in [{}]".format(
                self._as_info( location ),
                ( branch and  ":[{}]".format( self._as_info(  str(branch) ) ) or "" ),
                self._as_info( self._version ),
                self._as_notice( self._local_directory )
        )


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


