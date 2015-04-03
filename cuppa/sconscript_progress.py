
#          Copyright Jamie Allsop 2013-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   SconscriptProgress
#-------------------------------------------------------------------------------


class SconscriptProgress:

#    callbacks = []
    started   = {}
    finished  = {}

    @classmethod
    def register_callback( cls, env, callback ):
        cls._callbacks( env ).add( callback )


#    @classmethod
#    def unregister_callback( cls, env, callback ):
#        cls.callbacks( env ).remove( callback )


    @classmethod
    def _callbacks( cls, env ):
        if not 'sconscript_progress_callbacks' in env:
            env['sconscript_progress_callbacks'] = set()
        return env['sconscript_progress_callbacks']


    @classmethod
    def _sconscript( cls, env ):
        return env['build_dir']


    @classmethod
    def Started( cls, target, source, env ):
        for callback in cls._callbacks( env ):
            callback( 'started', env, cls._sconscript(env), target, source )

        del cls.started[cls._sconscript(env)]


    @classmethod
    def Finished( cls, target, source, env ):
        for callback in cls._callbacks( env ):
            callback( 'finished', env, cls._sconscript(env), target, source )

        del cls.finished[cls._sconscript(env)]


    @classmethod
    def add( cls, env, target ):
        sconscript = cls._sconscript(env)
        if sconscript not in cls.started:
            cls.started[sconscript] = env.Command( 'Started', [], cls.Started )
        if sconscript not in cls.finished:
            cls.finished[sconscript] = env.Command( 'Finished', [], cls.Finished )
        env.Requires( target, cls.started[sconscript] )
        env.Depends( cls.finished[sconscript], target )

