#          Copyright Jamie Allsop 2014-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   dependency
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

import pip.vcs
import pip.download

import scms.subversion
import scms.git


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


    def remove_common_top_directory_under( self, path ):
        dirs = os.listdir( path )
        top_dir = os.path.join( path, dirs[0] )
        if len(dirs) == 1 and os.path.isdir( top_dir ):
            print "cuppa: removing redundant top directory [{}] from [{}]".format( self._as_warning( dirs[0] ), self._as_warning( path ) )
            # we have a single top-level directory
            branch = dirs[0]
            move_dirs = os.listdir( top_dir )
            for d in move_dirs:
                shutil.move( os.path.join( top_dir, d ), os.path.join( path, d ) )
            shutil.rmtree( top_dir )


    def extract( self, filename, target_dir ):

        os.makedirs( target_dir )

        if tarfile.is_tarfile( filename ):
            print "cuppa: extracting [{}] into [{}]".format( self._as_warning( filename ), self._as_warning( target_dir ) )
            try:
                with tarfile.TarFile( filename ) as tf:
                    tf.extractall( target_dir )
            except tarfile.ReadError:
                command = "tar -xf {filename}".format( filename=filename )
                if subprocess.call( shlex.split( command ), cwd=target_dir ) != 0:
                    raise LocationException( "Could not untar downloaded file from [{}]".format( filename ) )

            self.remove_common_top_directory_under( target_dir )

        if zipfile.is_zipfile( filename ):
            print "cuppa: extracting [{}] into [{}]".format( self._as_warning( filename ), self._as_warning( target_dir ) )
            with zipfile.ZipFile( filename ) as zf:
                zf.extractall( target_dir )

        self.remove_common_top_directory_under( target_dir )


    def get_local_directory( self, env, location, branch, full_url ):

        local_directory = None

        base = os.path.join( env['working_dir'], '.cuppa' )

        if location.startswith( 'file:' ):
            location = pip.download.url_to_path( location )

        if not pip.download.is_url( location ):

            if pip.download.is_archive_file( location ):

                local_directory = os.path.splitext( path_leaf( location ) )[0]
                name, ext = os.path.splitext( local_directory )
                if ext == ".tar":
                    local_directory = name
                local_directory = re.sub( r'[\\/+:() ]', r'#', local_directory )
                local_directory = os.path.join( base, local_directory )

                if os.path.exists( local_directory ):
                    try:
                        os.rmdir( local_directory )
                    except:
                        return local_directory

                self.extract( location, local_directory )
            else:
                local_directory = branch and os.path.join( location, branch ) or location
                return local_directory
        else:

            local_directory = '#'.join( [ full_url.scheme, full_url.netloc, urllib.unquote( full_url.path ) ] )
            local_directory = re.sub( r'[\\/+:() ]', r'#', local_directory )
            local_directory = os.path.join( base, local_directory )

            if full_url.scheme.startswith( 'http' ) and pip.download.is_archive_file( full_url.path ):

                if os.path.exists( local_directory ):
                    try:
                        os.rmdir( local_directory )
                    except:
                        return local_directory

                print "cuppa: downloading [{}]...".format( self._as_warning( location ) )
                filename, headers = urllib.urlretrieve( location )
                print "cuppa: [{}] successfully downloaded to [{}]".format( self._as_warning( location ), self._as_warning( filename ) )
                self.extract( filename, local_directory )

            elif '+' in full_url.scheme:
                vc_type = location.split('+', 1)[0]
                backend = pip.vcs.vcs.get_backend( vc_type )
                if backend:
                    vcs_backend = backend( location )
                    if os.path.exists( local_directory ):
                        print "cuppa: updating [{}] in [{}]".format( self._as_warning( location ), self._as_warning( local_directory ) )
                        vcs_backend.update( local_directory, [] )
                    else:
                        action = "cloning"
                        if vc_type == "svn":
                            action = "checking out"
                        print "cuppa: {} [{}] into [{}]".format( action, self._as_warning( location ), self._as_warning( local_directory ) )
                        vcs_backend.obtain( local_directory )

            return local_directory


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

        return info


    def _as_error( self, text ):
        return self._colouriser.colour( 'error', text )


    def _as_warning( self, text ):
        return self._colouriser.colour( 'warning', text )


    def _as_notice( self, text ):
        return self._colouriser.colour( 'notice', text )


    def __init__( self, env, location, branch=None ):

        self._colouriser = env['colouriser']
        self._location = location
        self._full_url = urlparse.urlparse( location )

        ## Get the location for the source dependency. If the location is a URL or an Archive we'll need to
        ## retrieve the URL and extract the archive. get_local_directory() returns the location of the source
        ## once this is done
        self._local_directory = self.get_local_directory( env, location, branch, self._full_url )

        ## Now that we have a locally accessible version of the dependency we can try to collate some information
        ## about it to allow us to specify what we are building with.
        self._url, self._repository, self._branch, self._revision = self.get_info( self._location, self._local_directory, self._full_url )

        if self._branch and self._revision:
            self._version = ' rev. '.join( [ str(self._branch), str(self._revision) ] )
        elif branch and self._revision:
            self._version = ' rev. '.join( [ str(branch), str(self._revision) ] )
        else:
            version = os.path.splitext( path_leaf( urllib.unquote( self._full_url.path ) ) )[0]
            name, ext = os.path.splitext( version )
            if ext == ".tar":
                version = name
            self._version = version
            self._revision = "not under version control"


    def local( self ):
        return self._local_directory


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


