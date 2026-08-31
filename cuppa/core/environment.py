#          Copyright Jamie Allsop 2018-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CuppaEnvironment
#-------------------------------------------------------------------------------

# Python Standard
import six

# Scons
import SCons.Script
import SCons.Node

# Custom
import cuppa.progress
from cuppa.colourise import colouriser, as_info, as_info_label, as_notice
from cuppa.log import logger
from cuppa.utility.python2to3 import MutableMapping


class MethodWithProgress(object):

    def __init__( self, env, name, method ):
        self._env = env
        self._name = name
        self._method = method

    @staticmethod
    def _nodes_for_progress( nodes ):
        """Return a sequence of SCons nodes suitable for NotifyProgress, or None.

        Engine builders return a plain ``list`` (for example ``Install``) or a
        ``NodeList`` (for example ``Program`` / ``Object``). ``NodeList`` is not a
        ``list`` subclass, so a strict ``type(nodes) is list`` check misses most
        builders. A single ``Node`` is also accepted.
        """
        if nodes is None:
            return None
        if isinstance( nodes, SCons.Node.Node ):
            return [ nodes ]
        try:
            if len( nodes ) < 1:
                return None
            first = nodes[0]
        except ( TypeError, IndexError, KeyError ):
            return None
        if isinstance( first, SCons.Node.Node ):
            return nodes
        return None

    def __call__( self, *args, **kwargs ):
        logger.trace( "calling [{}] with args [{}] and kwargs [{}]".format( as_info(self._name), as_notice(str(args)), as_notice(str(kwargs)) ) )
        nodes = self._method( *args, **kwargs )
        progress_nodes = self._nodes_for_progress( nodes )
        if progress_nodes is not None:
            cuppa.progress.NotifyProgress.add( self._env, progress_nodes )
        return nodes


class EnvironmentMethods(object):

    # Public SCons builders and builder-like methods that emit action nodes.
    # ``add_progress_tracking`` skips names absent on a given env (``hasattr``).
    # Keep aligned with:
    # - SCons ``Environment`` ``BUILDERS`` keys that do not start with ``_``
    # - ``Command`` / ``Install*`` / ``Jar`` / ``Java`` (not always ``BUILDERS`` entries)
    # - tool method aliases documented as builders (Docbook*, gettext PO*/Translate, Ninja)
    # Synced against SCons 4.10; ``tests/unit/test_scons_progress_wrap_list.py`` guards drift.
    _scons_methods_and_builders = [
        'CFile',
        'CXXFile',
        'Command',
        'CompilationDatabase',
        'CopyAs',
        'CopyTo',
        'DVI',
        'DocbookEpub',
        'DocbookHtml',
        'DocbookHtmlChunked',
        'DocbookHtmlhelp',
        'DocbookMan',
        'DocbookPdf',
        'DocbookSlidesHtml',
        'DocbookSlidesPdf',
        'DocbookXInclude',
        'DocbookXslt',
        'Gs',
        'Install',
        'InstallAs',
        'InstallVersionedLib',
        'Ipkg',
        'Jar',
        'JarFile',
        'Java',
        'JavaClassDir',
        'JavaClassFile',
        'JavaFile',
        'JavaH',
        'Library',
        'LoadableModule',
        'M4',
        'MOFiles',
        'MSVSProject',
        'MSVSSolution',
        'Ninja',
        'Object',
        'PCH',
        'PDF',
        'POInit',
        'POTUpdate',
        'POUpdate',
        'Package',
        'PostScript',
        'Program',
        'ProgramAllAtOnce',
        'RES',
        'RMIC',
        'RPCGenClient',
        'RPCGenHeader',
        'RPCGenService',
        'RPCGenXDR',
        'Rpm',
        'SharedLibrary',
        'SharedObject',
        'StaticLibrary',
        'StaticObject',
        'Substfile',
        'Tag',
        'Tar',
        'Textfile',
        'Translate',
        'TypeLibrary',
        'Zip',
    ]

    @classmethod
    def add_progress_tracking( cls, env ):
        for name in cls._scons_methods_and_builders:
            if hasattr( env, name ):
                setattr( env, "_"+name, getattr( env, name ) )
                method = getattr( env, "_"+name )
                setattr( env, name, MethodWithProgress( env, name, method ) )


class CuppaEnvironment(MutableMapping):

    _tools = []
    _options = {}
    _cached_options = {}
    _methods = {}

    # Option Interface
    @classmethod
    def get_option( cls, option, default=None ):
        if option in cls._cached_options:
            return cls._cached_options[ option ]

        value = SCons.Script.GetOption( option )
        source = None
        default_options = cls._options.get( 'default_options' ) or {}
        if value == None or value == '':
            if default_options and option in default_options:
                value = default_options[ option ]
                source = "in the sconstruct file"
            elif default:
                value = default
                source = "using default"
        else:
            source = "on command-line"

        configured_options = cls._options.get( 'configured_options' ) or {}
        if option in configured_options:
            source = "using configure"

        if value:
            logger.debug( "option [{}] set {} as [{}]".format(
                        as_info( option ),
                        source,
                        as_info( str(value) ) )
            )
        cls._cached_options[option] = value
        return value


    @classmethod
    def _get_option_method( cls, env, option, default=None ):
        return cls.get_option( option, default )


    # Environment Interface
    @classmethod
    def default_env( cls ):
        if not hasattr( cls, '_default_env' ):
            cls._default_env = SCons.Script.Environment( tools=['default'] + cls._tools )
        return cls._default_env


    @classmethod
    def create_env( cls, **kwargs ):

        tools = ['default'] + cls._tools
        if 'tools' in kwargs:
            tools = tools + kwargs['tools']
            del kwargs['tools']

        tools = SCons.Script.Flatten( tools )

        env = SCons.Script.Environment(
                tools = tools,
                **kwargs
        )

        env['default_env'] = CuppaEnvironment.default_env()

        for key, option in six.iteritems(cls._options):
            env[key] = option
        for name, method in six.iteritems(cls._methods):
            env.AddMethod( method, name )
        env.AddMethod( cls._get_option_method, "get_option" )

        return env


    @classmethod
    def dump( cls ):
        import json

        def expand_node( node ):
            if isinstance( node, list ):
                return [ expand_node(i) for i in node ]
            elif isinstance( node, dict ):
                return { str(k): expand_node(v) for k,v in six.iteritems(node) }
            elif isinstance( node, set ):
                return [ expand_node(s) for s in node ]
            elif hasattr( node, "__dict__" ):
                return { str(k): expand_node(v) for k,v in six.iteritems(node.__dict__) }
            else:
                return str( node )

        logger.info( as_info_label( "Displaying Options" ) )
        options = json.dumps( expand_node(cls._options), sort_keys=True, indent=4 )
        logger.info( "\n" + options + "\n" )

        logger.info( as_info_label("Displaying Methods" ) )
        methods = json.dumps( expand_node(cls._methods), sort_keys=True, indent=4 )
        logger.info( "\n" + methods + "\n" )


    @classmethod
    def colouriser( cls ):
        return colouriser

    @classmethod
    def add_tools( cls, tools ):
        tools = SCons.Script.Flatten( tools )
        cls._tools.extend( tools )


    @classmethod
    def tools( cls ):
        return cls._tools

    @classmethod
    def add_method( cls, name, method ):
        cls._methods[name] = method

    @classmethod
    def add_variant( cls, name, variant ):
        if not 'variants' in  cls._options:
            cls._options['variants'] = {}
        cls._options['variants'][name] = variant

    @classmethod
    def add_action( cls, name, action ):
        if not 'actions' in  cls._options:
            cls._options['actions'] = {}
        cls._options['actions'][name] = action

    @classmethod
    def add_supported_toolchain( cls, name ):
        if not 'supported_toolchains' in  cls._options:
            cls._options['supported_toolchains'] = []
        cls._options['supported_toolchains'].append( name )

    @classmethod
    def add_available_toolchain( cls, name, toolchain ):
        if not 'toolchains' in  cls._options:
            cls._options['toolchains'] = {}
        cls._options['toolchains'][name] = toolchain

    @classmethod
    def add_project_generator( cls, name, project_generator ):
        if not 'project_generators' in  cls._options:
            cls._options['project_generators'] = {}
        cls._options['project_generators'][name] = project_generator

    @classmethod
    def add_profile( cls, name, profile ):
        if not 'profiles' in  cls._options:
            cls._options['profiles'] = {}
        cls._options['profiles'][name] = profile

    @classmethod
    def add_dependency( cls, name, dependency ):
        if not 'dependencies' in  cls._options:
            cls._options['dependencies'] = {}
        cls._options['dependencies'][name] = dependency

    # Dict Interface
    def __getitem__( self, key ):
        return self._options[key]

    def __setitem__( self, key, value ):
        self._options[key] = value

    def __delitem__( self, key ):
        del self._options[key]
        del self._cached_options[key]

    def __iter__( self ):
        return iter( self._options )

    def __len__( self ):
        return len( self._options )

    def __contains__( self, key ):
        return key in self._options

