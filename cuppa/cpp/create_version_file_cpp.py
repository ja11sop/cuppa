
#          Copyright Jamie Allsop 2011-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   CreateVersionFileCpp
#-------------------------------------------------------------------------------
import os
from os.path import splitext, relpath,  sep
from SCons.Script import File


import cuppa.location


def offset_path( path, env ):

    build_dir  = env['build_dir']
    offset_dir = env['offset_dir']

    return offset_dir + sep + relpath( path, build_dir)


def hpp_from_cpp( cpp_file ):
    return splitext( cpp_file )[0] + '.hpp'


def txt_from_cpp( cpp_file ):
    return splitext( cpp_file )[0] + '.txt'


class CreateVersionHeaderCpp:

    def __init__( self, env, namespaces, version, location ):
        self.__env = env
        self.__namespace_guard = "_".join( namespaces )
        self.__namespaces = namespaces
        self.__version = version
        self.__location = location

        self.__variant = self.__env['variant'].name()

        self.__working_dir = os.path.join( env['base_path'], env['build_dir'] )
        if not os.path.exists( self.__working_dir ):
            os.makedirs( self.__working_dir )


    def __call__( self, target, source, env ):

        cpp_file = offset_path( target[0].path, env )
        hpp_file = hpp_from_cpp( cpp_file )
        txt_file = txt_from_cpp( cpp_file )

        output_dir = os.path.split( hpp_file )[0]

        if output_dir:
            output_dir = os.path.join( self.__working_dir, output_dir )
            if not os.path.exists( output_dir ):
                os.makedirs( output_dir )

        version_hpp = open( os.path.join( self.__working_dir, hpp_file ), "w" )
        version_hpp.write( get_build_identity_header( self.__namespace_guard, self.__namespaces ) )
        version_hpp.close()

        version_txt = open( os.path.join( self.__working_dir, txt_file ), "w" )
        version_txt.write( get_build_identity_txt( self.__version, relpath( env['base_path'], self.__location), self.__namespaces ) )
        version_txt.close()

        target[0] = File( cpp_file )
        source.append( hpp_file )
        source.append( txt_file )
        return target, source


def get_build_identity_txt( version, location, namespaces ):
    lines = []
    lines += [ '// v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v\n'
               '// Version File for product version [ ' + version + ' ]\n'
               '// Location for dependency versions [ ' + location + ' ]\n'
               '// Namespace                        [ ' + "::".join( namespaces ) + ' ]\n'
               '// v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v v\n' ]
    return "\n".join( lines )


def get_build_identity_header( namespace_guard, namespaces ):
    lines = []
    lines += [ '// G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G\n'
               '#ifndef INCLUDED_' + namespace_guard.upper() + '_BUILD_GENERATED_VERSION_HPP\n'
               '#define INCLUDED_' + namespace_guard.upper() + '_BUILD_GENERATED_VERSION_HPP\n'
               '// G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G\n'
               '\n'
               '// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I\n'
               '#include <string>\n'
               '#include <vector>\n'
               '#include <map>\n'
               '// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I\n'
               '\n'
               '// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n' ]
    for namespace in namespaces:
        lines += [ 'namespace ' + namespace + ' {' ]
    lines += [ 'namespace build {\n'
               '// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n\n'
               '\n'
               'class identity\n'
               '{\n'
               'public:\n'
               '\n'
               '    typedef std::string                             string_t;\n'
               '    typedef std::vector< string_t >                 revisions_t;\n'
               '\n'
               'private:\n'
               '\n'
               '    struct dependency\n'
               '    {\n'
               '        dependency()\n'
               '        {\n'
               '        }\n'
               '\n'
               '        dependency( const string_t& Name,\n'
               '                    const string_t& Version,\n'
               '                    const string_t& Repository,\n'
               '                    const string_t& Branch,\n'
               '                    const revisions_t& Revisions )\n'
               '        : name       ( Name )\n'
               '        , version    ( Version )\n'
               '        , repository ( Repository )\n'
               '        , branch     ( Branch )\n'
               '        , revisions  ( Revisions )\n'
               '        {\n'
               '        }\n'
               '\n'
               '        string_t       name;\n'
               '        string_t       version;\n'
               '        string_t       repository;\n'
               '        string_t       branch;\n'
               '        revisions_t    revisions;\n'
               '    };\n'
               '\n'
               'public:\n'
               '\n'
               '    typedef dependency                              dependency_t;\n'
               '    typedef std::map< string_t, dependency >        dependencies_t;\n'
               '\n'
               'public:\n' ]
    lines += [ function_declaration_from_variable( 'product_version' ) ]
    lines += [ function_declaration_from_variable( 'product_repository' ) ]
    lines += [ function_declaration_from_variable( 'product_branch' ) ]
    lines += [ function_declaration_from_variable( 'product_revision' ) ]
    lines += [ function_declaration_from_variable( 'build_variant' ) ]
    lines += [ function_declaration_from_variable( 'build_time' ) ]
    lines += [ function_declaration_from_variable( 'build_user' ) ]
    lines += [ function_declaration_from_variable( 'build_host' ) ]
    lines += [ function_declaration_dependencies() ]
    lines += [ function_declaration_report() ]

    lines += [ '\nprivate:\n'
               '    static const dependencies_t Dependencies_;\n'
               '    static const string_t       Report_;\n'
               '};\n'
               '\n'
               '// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n\n'
               '} //end namespace build' ]
    for namespace in namespaces:
        lines += [ '} //end namespace ' + namespace ]
    lines += [ '// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n\n'
               '\n'
               '// G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G\n'
               '#endif\n'
               '// G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G G\n'
               '\n' ]

    return "\n".join( lines )


def function_declaration_from_variable( name ):
    lines = []
    lines += [ '    static const char*              ' + name + '();' ]
    return "\n".join( lines )


def function_declaration_dependencies():
    lines = []
    lines += [ '    static const dependencies_t&    dependencies();' ]
    return "\n".join( lines )


def function_declaration_report():
    lines = []
    lines += [ '    static const char*              report();' ]
    return "\n".join( lines )


class CreateVersionFileCpp:

    def __init__( self, env, namespaces, version, location ):
        self.__env = env
        self.__namespace_guard = "_".join( namespaces )
        self.__namespaces = namespaces
        self.__version = version
        self.__location = location

        location = cuppa.location.Location( env, location )

        self.__repository = location.repository()
        self.__branch     = location.branch()
        self.__revision   = location.revisions()[0]

        self.__variant = self.__env['variant'].name()


    def __call__( self, target, source, env ):
        cpp_file = target[0].path
        hpp_file = hpp_from_cpp( cpp_file )

        #print "Create CPP Version File at [" + cpp_file + "]"
        version_cpp = open( cpp_file, "w" )
        version_cpp.write( self.get_build_identity_source( env['BUILD_WITH'], hpp_file ) )
        version_cpp.close()

        return None


    def function_definition_from_variable( self, name, variable ):
        lines = []
        lines += [ '\nconst char*       identity::' + name + '()' ]
        lines += [ '{' ]
        lines += [ '    return "' + str( variable ) + '";' ]
        lines += [ '}\n' ]
        return "\n".join( lines )


    def function_definition_dependencies( self ):
        lines = []
        lines += [ '\nconst identity::dependencies_t& identity::dependencies()\n'
                   '{\n'
                   '    return Dependencies_;\n'
                   '}\n' ]
        return "\n".join( lines )


    def initialise_dependencies_definition( self, dependencies ):
        lines = []
        lines += [ '\nidentity::dependencies_t initialise_dependencies()\n'
                   '{\n'
                   '    typedef identity::dependencies_t dependencies_t;\n'
                   '    typedef identity::dependency_t   dependency_t;\n'
                   '    typedef identity::revisions_t    revisions_t;\n'
                   '    dependencies_t Dependencies;' ]
        for name in dependencies:
            if name in self.__env['dependencies']:
                dependency_factory = self.__env['dependencies'][name]
                dependency = dependency_factory( self.__env )

                lines += [ '    Dependencies[ "' +  name + '" ] = dependency_t( "'
                               + dependency.name() + '", "'
                               + dependency.version() + '", "'
                               + dependency.repository() + '", "'
                               + dependency.branch()
                               + '", revisions_t() );' ]
                try:
                    if callable( getattr( dependency, 'revisions' ) ):
                        revisions = dependency.revisions()
                        if revisions:
                            for revision in revisions:
                                lines += [ '    Dependencies[ "' +  name + '" ].revisions.push_back( "' + revision + '" );' ]
                except AttributeError:
                    pass
        lines += [ '    return Dependencies;\n'
                   '}\n'
                   '\n'
                   'const identity::dependencies_t identity::Dependencies_ = initialise_dependencies();\n' ]
        return "\n".join( lines )


    def function_definition_report( self ):
        lines = []
        lines += [ '\nconst char*       identity::report()' ]
        lines += [ '{' ]
        lines += [ '    return Report_.c_str();' ]
        lines += [ '}\n' ]
        return "\n".join( lines )


    def initialise_report_definition( self ):
        lines = []
        lines += [ '\nidentity::string_t initialise_report()\n'
                   '{\n'
                   '    std::ostringstream Report;\n'
                   '\n'
                   '    Report\n'
                   '        << "Product:\\n"\n'
                   '           "  |- Version    = " << identity::product_version()    << "\\n"\n'
                   '           "  |- Repository = " << identity::product_repository() << "\\n"\n'
                   '           "  |- Branch     = " << identity::product_branch()     << "\\n"\n'
                   '           "  +- Revision   = " << identity::product_revision()   << "\\n"\n'
                   '           "Build:\\n"\n'
                   '           "  |- Variant    = " << identity::build_variant()      << "\\n"\n'
                   '           "  |- Time       = " << identity::build_time()         << "\\n"\n'
                   '           "  |- User       = " << identity::build_user()         << "\\n"\n'
                   '           "  +- Host       = " << identity::build_host()         << "\\n";\n'
                   '\n'
                   '    if( !identity::dependencies().empty() )\n'
                   '    {\n'
                   '        Report << "Dependencies:\\n";\n'
                   '    }\n'
                   '\n'
                   '    identity::dependencies_t::const_iterator Dependency = identity::dependencies().begin();\n'
                   '    identity::dependencies_t::const_iterator End        = identity::dependencies().end();\n'
                   '\n'
                   '    for( ; Dependency != End; ++Dependency )\n'
                   '    {\n'
                   '        Report\n'
                   '            << " " << Dependency->second.name << "\\n"\n'
                   '            << "  |- Version    = " << Dependency->second.version << "\\n"\n'
                   '            << "  |- Repository = " << Dependency->second.repository << "\\n"\n'
                   '            << "  |- Branch     = " << Dependency->second.branch << "\\n";\n'
                   '\n'
                   '        identity::revisions_t::const_iterator Revision = Dependency->second.revisions.begin();\n'
                   '        identity::revisions_t::const_iterator End      = Dependency->second.revisions.end();\n'
                   '\n'
                   '        for( ; Revision != End; )\n'
                   '        {\n'
                   '            identity::string_t Value( *Revision );\n'
                   '            if( ++Revision != End )\n'
                   '            {\n'
                   '                Report << "  |";\n'
                   '            }\n'
                   '            else\n'
                   '            {\n'
                   '                Report << "  +";\n'
                   '            }\n'
                   '            Report << "- Revision   = " << Value << "\\n";\n'
                   '        }\n'
                   '    }\n'
                   '\n'
                   '    return Report.str();\n'
                   '}\n'
                   '\n'
                   'const identity::string_t identity::Report_ = initialise_report();' ]
        return "\n".join( lines )


    def get_build_identity_source( self, dependencies, header_file ):

        from datetime import datetime
        from getpass import getuser
        from socket import gethostname

        build_time = datetime.utcnow()
        build_user = getuser()
        build_host = gethostname()

        lines = []
        lines += [ '// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I\n'
                   '// Self Include' ]
        lines += [ '#include "' + header_file + '"' ]
        lines += [ ''
                   '// C++ Standard Includes\n'
                   '#include <sstream>\n'
                   '\n'
                   '// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I\n'
                   '\n'
                   '// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n' ]
        for namespace in self.__namespaces:
            lines += [ 'namespace ' + namespace + ' {' ]
        lines += [ 'namespace build {\n'
                   '// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n\n' ]

        lines += [ self.function_definition_from_variable( 'product_version',    self.__version ) ]
        lines += [ self.function_definition_from_variable( 'product_repository', self.__repository ) ]
        lines += [ self.function_definition_from_variable( 'product_branch',     self.__branch ) ]
        lines += [ self.function_definition_from_variable( 'product_revision',   self.__revision ) ]

        lines += [ self.function_definition_from_variable( 'build_variant', self.__variant ) ]
        lines += [ self.function_definition_from_variable( 'build_time', build_time ) ]
        lines += [ self.function_definition_from_variable( 'build_user', build_user ) ]
        lines += [ self.function_definition_from_variable( 'build_host', build_host ) ]

        lines += [ self.initialise_dependencies_definition( dependencies ) ]
        lines += [ self.function_definition_dependencies() ]

        lines += [ self.initialise_report_definition() ]
        lines += [ self.function_definition_report() ]

        lines += [ '\n// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n\n'
                   '} //end namespace build' ]
        for namespace in self.__namespaces:
            lines += [ '} //end namespace ' + namespace ]
        lines += [ '// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n\n'
                   '\n' ]

        return "\n".join( lines )
