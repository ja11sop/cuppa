#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Module method — sugar for interface (+ optional implementation) sources
#-------------------------------------------------------------------------------

from SCons.Script import Flatten


class ModuleMethod:
    """
    Compile a named module's interface (and optional implementation units).

    BMIs are registered on the current env so a later Build/Compile in the same
    sconscript can import the module. Compiled objects are retained on the env
    and linked into subsequent Build() programs. BuildLib also installs BMIs under
    final/modules/ (module-map.json) for ImportModules / package consumers.
    """

    def __call__( self, env, name, interface=None, implementation=None, **kwargs ):
        sources = []
        if interface:
            sources.append( interface )
        if implementation:
            sources.extend( Flatten( [ implementation ] ) )
        if not sources:
            return []
        # No direct NotifyProgress call here: Module() is orchestration sugar.
        # Progress wiring is owned by env.Compile()/compile_with_modules(),
        # which NotifyProgress the BMIs/objects they produce.
        objects = env.Compile( sources, **kwargs )
        pending = env.setdefault( '_cuppa_module_objects', [] )
        for obj in Flatten( [ objects ] ):
            if obj not in pending:
                pending.append( obj )
        return objects

    @classmethod
    def add_to_env( cls, cuppa_env ):
        cuppa_env.add_method( 'Module', cls() )
