
#          Copyright Jamie Allsop 2011-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   BuildMethod
#-------------------------------------------------------------------------------

import cuppa.progress
import os.path

from SCons.Script import Flatten

from cuppa.colourise import as_notice
from cuppa.log import logger


class BuildMethod:

    @classmethod
    def build(
            cls,
            env,
            target,
            source,
            final_dir=None,
            append_variant=False,
            depends_on=None,
            LIBS=[],
            SHAREDLIBS=[],
            DYNAMICLIBS=[],
            STATICLIBS=[],
            stage_package_libraries=None,
            **kwargs
    ):
        if final_dir == None:
            final_dir = env['abs_final_dir']
        exe = os.path.join( final_dir, target )
        if append_variant and env['variant'].name() != 'rel':
            exe += '_' + env['variant']

        env.AppendUnique( DYNAMICLIBS = env['LIBS'] )

        if 'SHAREDLIBS' in env:
            env.AppendUnique( DYNAMICLIBS = env['SHAREDLIBS'] )

        all_libs = env['DYNAMICLIBS'] + env['STATICLIBS'] + LIBS + DYNAMICLIBS + SHAREDLIBS + STATICLIBS

        logger.trace( "Building [{}] from [{}] which depends on [{}] and links against [{}]".format(
                as_notice( str(target) ),
                as_notice( str(source) ),
                as_notice( str(depends_on) ),
                as_notice( str( [str(l) for l in Flatten(all_libs) ] ) )
        ) )

        from cuppa.package_managers.stage_package_libraries import (
                ensure_package_runtime_rpath,
                package_shared_library_files,
                should_stage_package_libraries,
                stage_package_libraries_for_programs,
        )

        do_stage = should_stage_package_libraries(
                env, stage_package_libraries=stage_package_libraries,
        )
        stage_sources = package_shared_library_files( env ) if do_stage else []
        if stage_sources:
            # RPATH on the construction env so Program picks it up at link time.
            ensure_package_runtime_rpath( env )

        objects = Flatten( [ env.Compile( source, depends_on=depends_on ) ] )
        # Objects from prior env.Module(...) calls in this sconscript.
        objects.extend( Flatten( [ env.get( '_cuppa_module_objects', [] ) ] ) )

        program = env.Program( exe,
                               objects,
                               LIBS = all_libs,
                               DYNAMICLIBS = env['DYNAMICLIBS'] + LIBS + DYNAMICLIBS + SHAREDLIBS,
                               STATICLIBS = env['STATICLIBS'] + STATICLIBS,
                               **kwargs )

        if stage_sources:
            # apply_rpath=False: already ensured on env before Program.
            staged = stage_package_libraries_for_programs(
                    env, program, apply_rpath=False,
            )
            if staged:
                cuppa.progress.label_terse_action(
                        staged, "copy", paths="transfer",
                )

        cuppa.progress.NotifyProgress.add( env, program )

        return program


    def __call__( self, env, target, source, final_dir = None, append_variant = False, **kwargs ):
        return self.build( env, target, source, final_dir=final_dir, append_variant=append_variant, **kwargs )


    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( "Build", cls() )


