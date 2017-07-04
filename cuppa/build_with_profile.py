#          Copyright Jamie Allsop 2017-2017
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   build_with_profile
#-------------------------------------------------------------------------------


class base_profile(object):

    _name = None

    @classmethod
    def add_options( cls, add_option ):
        pass


    @classmethod
    def add_to_env( cls, env, add_profile  ):
        add_profile( cls._name, cls.create )


    @classmethod
    def create( cls, env ):
        return cls()


    @classmethod
    def name( cls ):
        return cls._name


def profile( name ):
    return type( 'BuildProfile' + name.title(), ( base_profile, ), { '_name': name } )



