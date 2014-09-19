Cuppa
=====

A simple, extensible build system for use with
`Scons <http://www.scons.org/>`__. **Cuppa** is designed to leverage the
capabilities of Scons, while allowing developers to focus on the task of
describing what needs to be built. In general **cuppa** supports
``make`` like usage on the command-line. That is developers can simply
write:

.. code:: sh

    scons -D

and have Scons "do the right thing"; building targets for any
``sconscript`` files found in the current directory.

**Cuppa** can be installed as a normal python package or installed
locally into a ``site_scons`` directory allowing it to be effortlessly
integrated into any Scons setup.

    Note: ``-D`` tells ``scons`` to look for an ``sconstruct`` file in
    the current or in parent directories and if it finds one execute the
    ``sconscript`` files as if called from that directory. This ensures
    everything works as expected. For more details refer to the `Scons
    documentation <http://www.scons.org/documentation.php>`__


Quick Intro
-----------

Get **cuppa**
~~~~~~~~~~~~~

The simpest way to get **cuppa** is to ``pip install`` it using:

::

    pip install cuppa


Sample ``sconstruct`` file
~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's look at a minimal ``sconstruct`` that makes use of **cuppa**. It
could look like this:

.. code:: python

    # Pull in all the Cuppa goodies..
    import cuppa

    # Call sconscripts to do the work
    cuppa.run()

Calling the ``run`` method in the ``cuppa`` module starts the build
process calling ``sconscript`` files.

Sample ``sconscript`` file
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is an example ``sconscript`` file that builds all \*.cpp files in
the directory where it resides:

.. code:: python

    Import( 'env' )

    # Build all *.cpp source files as executables
    for Source in env.GlobFiles('*.cpp'):
        env.Build( Source[:-4], Source )

The ``env.Build()`` method is provided by **cuppa** and does essentially
what ``env.Program()`` does but in addition is both toolchain and
variant aware, and further can provide notifications on progress.

    Note: Source[:-4] simply strips off the file extension ``.cpp``,
    that is, the last 4 characters of the file name.

If our ``sconscript`` file was for a directory containing \*.cpp files
that are actually tests then we could instead write the ``sconscript``
file as:

.. code:: python

    Import( 'env' )

    # Build all *.cpp source files as executables to be run as tests
    for Source in env.GlobFiles('*.cpp'):
        env.BuildTest( Source[:-4], Source )

The ``env.BuildTest()`` method is provided by **cuppa** and builds the
sources specified as ``env.Build()`` does.

However, in addition, passing ``--test`` on the command-line will also
result in the executable produced being run by a **runner**. The default
test runner simply treats each executable as a test case and each
directory or executables as a test suite. If the process executes
cleanly the test passed, if not it failed.

To run this on the command-line we would write:

.. code:: sh

    scons -D --test

If we only want to build and test *debug* executables we can instead
write this:

.. code:: sh

    scons -D --dbg --test

Or for release only pass ``--rel``.

**cuppa** also makes it easy to work with dependencies. For example, if
`boost <http://www.boost.org/>`__ was a default dependency for all your
``sconscript`` files you could write your sconstruct file as follows:

.. code:: python

    import cuppa

    cuppa.run(
        default_options = {
             'boost-home': '<Location of Boost>'
        },
        default_dependencies = [
            'boost'
        ]
    )

This will automatically ensure that necessary includes and other compile
options are set for the boost version that is found at ``boost-home``.
If you need to link against specific boost libraries this can also be
done in the sconscript file as follows:

.. code:: python

    Import('env')

    Test = 'my_complex_test'

    Sources = [
        Test + '.cpp'
    ]

    env.AppendUnique( STATICLIBS = [
        env.BoostStaticLibrary( 'system' ),
        env.BoostStaticLibrary( 'log' ),
        env.BoostStaticLibrary( 'thread' ),
        env.BoostStaticLibrary( 'timer' ),
        env.BoostStaticLibrary( 'chrono' ),
        env.BoostStaticLibrary( 'filesystem' ),
    ] )

    env.BuildTest( Test, Sources )

The ``BoostStaticLibrary()`` method ensures that the library is built in
the correct build variant as required. If you preferred to use dynamic
linking then that can also be achieved using ``BoostSharedLibrary()``.

The point is the complexities of using `boost <http://www.boost.org/>`__
as a dependency are encapsulated and managed separately from the
scontruct and sconscript files allowing developers to focus on intent
not method.

Design Principles
-----------------

**cuppa** has been written primarily to provide a clean and structured
way to leverage the power of Scons without the usual problems of hugely
complex ``scontruct`` files that diverge between projects. Key goals of
**cuppa** are:

-  minimise the need for adding logic into ``sconscript`` files, keeping
   them as declarative as possible.
-  allow declarative ``sconscript``\ s that are both much clearer and
   significantly simpler than the equivalent ``make`` file, without the
   need to learn a whole new scripting language like ``make`` or
   ``cmake``.
-  provide a clear structure for extending the facilities offered by
   **cuppa**
-  provide a clear vocabulary for building projects
-  codify Scons best practices into **cuppa** itself so that users just
   need to call appropriate methods knowing that **cuppa** will do the
   right thing with their intent
-  provide a framework that allows experts to focus on providing
   facilities for others to use. Write once, use everywhere. For example
   one person who knows how best to make
   `boost <http://www.boost.org/>`__ available as a dependency can
   manage that dependency and allow others to use it seamlessly.

More Details
------------

For more details refer to the `project homepage <https://github.com/ja11sop/cuppa>`__.

Acknowledgements
----------------

This work is based on the build system used in
`clearpool.io <http://www.clearpool.io>`__ during development of its
next generation exchange platform.
