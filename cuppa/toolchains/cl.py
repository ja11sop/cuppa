
#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CL Toolchain
#-------------------------------------------------------------------------------

from exceptions import Exception

import SCons.Script

from cuppa.cpp.create_version_file_cpp import CreateVersionHeaderCpp, CreateVersionFileCpp
from cuppa.cpp.run_boost_test import RunBoostTestEmitter, RunBoostTest
from cuppa.cpp.run_patched_boost_test import RunPatchedBoostTestEmitter, RunPatchedBoostTest
from cuppa.cpp.run_process_test import RunProcessTestEmitter, RunProcessTest
from cuppa.output_processor import command_available



class ClException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


class Cl(object):


    @classmethod
    def default_version( cls ):
        return 'cl'


    @classmethod
    def supported_versions( cls ):
        return [
            "cl"
        ]


    @classmethod
    def available_versions( cls ):
        if not hasattr( cls, '_available_versions' ):
            cls._available_versions = []
            for version in cls.supported_versions():
                command = "cl"
                if command_available( command ):
                    cls._available_versions = [ "cl" ]
        return cls._available_versions


    @classmethod
    def add_options( cls, add_option ):
        pass


    @classmethod
    def add_to_env( cls, env, add_toolchain, add_to_supported ):
        for version in cls.supported_versions():
            add_to_supported( version )

        for version in cls.available_versions():
            add_toolchain( version, cls( version ) )


    @classmethod
    def default_variants( cls ):
        return [ 'dbg', 'rel' ]


    def __init__( self, version ):

        self.values = {}
        self._version = "cl"
        self.values['name'] = version

        env = SCons.Script.DefaultEnvironment()

        self.values['sys_inc_prefix'] = env['INCPREFIX']
        self.values['sys_inc_suffix'] = env['INCSUFFIX']

        SYSINCPATHS = '${_concat(\"' + self.values['sys_inc_prefix'] + '\", SYSINCPATH, \"'+ self.values['sys_inc_suffix'] + '\", __env__, RDirs, TARGET, SOURCE)}'

        self.values['_CPPINCFLAGS'] = '$( ' + SYSINCPATHS + ' ${_concat(INCPREFIX, INCPATH, INCSUFFIX, __env__, RDirs, TARGET, SOURCE)} $)'

	self._initialise_toolchain()


    def __getitem__( self, key ):
        return self.values.get( key )


    def name( self ):
        return self.values['name']


    def family( self ):
        return "cl"


    def version( self ):
        return self._version


    def cxx_version( self ):
        return self._version


    def binary( self ):
        return self.values['CXX']


    def initialise_env( self, env ):
        env['_CPPINCFLAGS'] = self.values['_CPPINCFLAGS']
        env['SYSINCPATH']   = []
        env['INCPATH']      = [ '#.', '.' ]
        env['LIBPATH']      = []
        env['CPPDEFINES']   = []
        env['LIBS']         = []
        env['STATICLIBS']   = []


    def variants( self ):
        pass


    def supports_coverage( self ):
        return False


    def version_file_builder( self, env, namespace, version, location ):
        return CreateVersionFileCpp( env, namespace, version, location )


    def version_file_emitter( self, env, namespace, version, location ):
        return CreateVersionHeaderCpp( env, namespace, version, location )


    def test_runner( self, tester, final_dir, expected ):
        if not tester or tester =='process':
            return RunProcessTest( expected ), RunProcessTestEmitter( final_dir )
        elif tester=='boost':
            return RunBoostTest( expected ), RunBoostTestEmitter( final_dir )
        elif tester=='patched_boost':
            return RunPatchedBoostTest( expected ), RunPatchedBoostTestEmitter( final_dir )


    def test_runners( self ):
        return [ 'process', 'boost', 'patched_boost' ]


    def coverage_runner( self, program, final_dir ):
        return None


    def update_variant( self, env, variant ):
        if variant == 'dbg':
            env.AppendUnique( CXXFLAGS = self.values['dbg_cxx_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['dbg_link_flags'] )
        elif variant == 'rel':
            env.AppendUnique( CXXFLAGS = self.values['rel_cxx_flags'] )
            env.AppendUnique( LINKFLAGS = self.values['rel_link_flags'] )
        elif variant == 'cov':
            pass


    def _initialise_toolchain( self ):

        CommonCxxFlags = [ '-W4', '-EHac', '-nologo', '-GR' ]

        self.values['dbg_cxx_flags'] = CommonCxxFlags + [ '-Zi', '-MDd' ]
        self.values['rel_cxx_flags'] = CommonCxxFlags + [ '-Ox', '-MD' ]

        CommonLinkFlags = [ '-OPT:REF']

        self.values['dbg_link_flags'] = CommonLinkFlags + []
        self.values['rel_link_flags'] = CommonLinkFlags + []


    def abi_flag( self, library ):
        return ""


    def stdcpp_flag_for( self, standard ):
        return ""


    def error_format( self ):
        return "{}({}): error: {}"


    @classmethod
    def output_interpretors( cls ):
        return [
        {
            'title'     : "Compiler Error",
            'regex'     : r"([][{}() \t#%$~\w&_:+\\/\.-]+)([(]([0-9]+)[)])([ ]:[ ]error [A-Z0-9]+:.*)",
            'meaning'   : 'error',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
        {
            'title'     : "Compiler Warning",
            'regex'     : r"([][{}() \t#%$~\w&_:+\\/\.-]+)([(]([0-9]+)[)])([ ]:[ ]warning [A-Z0-9]+:.*)",
            'meaning'   : 'warning',
            'highlight' : set( [ 1, 2 ] ),
            'display'   : [ 1, 2, 4 ],
            'file'      : 1,
            'line'      : None,
            'column'    : None,
        },
    ]
