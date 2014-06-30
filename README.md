# construct

A simple, extensible build system packaged as a *site_scons* site directory for [Scons](http://www.scons.org/). **construct** is designed to leverage the capabilities of Scons while allowing developers to focus on the task of describing what needs to be built. In general **construct** supports `make` like usage on the command-line. That is developers can simply write:

```sh
scons -D
```

and have Scons "do the right thing"; building targets for any `sconscript` files found in the current directory.

**construct** is distributed as a `site_scons` directory allowing it to be effortlessly integrated into any Scons setup.

> Note: `-D` tells `scons` to look for an `sconstruct` file in the current or in parent directories and if it finds one execute the `sconscript` files as if called from that directory. This ensures everything works as expected. For more details refer to the [Scons documentation](http://www.scons.org/documentation.php)

## Table of Contents

  * [Quick Intro](#quick-intro)
  * [Installation and Dependencies](#installation-and-dependencies)
  * [Design Principles](#design-principles)
  * [Reference](#reference)
    * [Basic Structure](#basic-structure)
    * [Construct Command-line Reference](#construct-command-line-options)
    * [Construct](#construct)
    * [Methods](#methods)
      * [env.Build](#envbuild)
      * [env.Test](#envtest)
      * [env.BuildTest](#envbuildtest)
      * [env.BuildWith](#envbuildwith)
      * [env.BuildProfile](#envbuildprofile)
      * [env.Use](#envuse)
      * [env.CreateVersion](#envcreateversion)
    * [Variants](#variants)
      * [dbg - Debug](#dbg---debug)
      * [rel - Rlease](#rel---release)
      * [cov - Coverage](#cov---coverage)
    * [Toolchains](#toolchains)
    * [Platforms](#platforms)
  * [Supported Dependencies](#supported-dependencies)
    * [boost](#boost)
  * [Tutorial](#tutorial)

## Quick Intro

### Sample `sconstruct` file

A minimal `sconstruct` file using **construct** would look like this:

```python
# Pull in all the Construct goodies..
from construct import Construct

# Call sconscripts to do the work
Construct()
```

Creating the `Construct` instance starts the build process calling `sconscript` files.

### Sample `sconscript` file

Here is an example `sconscript` file that builds all *.cpp files in the directory where it resides:

```python
Import( 'env' )

# Build all *.cpp source files as executables
for Source in env.GlobFiles('*.cpp'):
    env.Build( Source[:-4], Source )
```

The `env.Build()` method is provided by **construct** and does essentially what `env.Program()` does but in addition is both toolchain and variant aware, and further can provide notifications on progress.

If our `sconscript` file was for a directory containing *.cpp files that are actually tests then we could instead write the `sconscript` file as:

```python
Import( 'env' )

# Build all *.cpp source files as executables to be run as tests
for Source in env.GlobFiles('*.cpp'):
    env.BuildTest( Source[:-4], Source )
```

The `env.BuildTest()` method is provided by **construct** and builds the sources specified as `env.Build()` does. However, in addition, passing `--test` on the command-line will also result in the executable produced being run by a **test_runner**. The default test runner simply treats each executable as a test case and each directory or executables as a test suite. If the process executes cleanly the test passed, if not it failed.

To run this on the command-line we would write:

```sh
scons -D --test
```

If we only want to build and test *debug* executables we can instead write this:

```sh
scons -D --dbg --test
```

Or for release only pass `--rel`.

**construct** also makes it easy to work with dependencies. For example, if [boost](http://www.boost.org/) was a default dependency for all your sconscipt files you could write your sconstruct file as follows:

```python
from construct import Construct

Construct(
    default_options = {
         'boost-home': '<Location of Boost>'
    },
    default_dependencies = [ 
        'boost' 
    ]
)
```

This will automatically ensure that necessary includes and other compile options are set for the boost version that is found at `boost-home`. If you need to link against specific boost libraries this can also be done in the sconscript file as follows:

```python
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
```

The `BoostStaticLibrary()` method ensures that the library is built in the correct build variant as required. If you preferred to use dynamic linking then that can also be achieved using `BoostSharedLibrary()`.

The point is the complexities of using [boost](http://www.boost.org/) as a dependency are encapsulated and managed separately from the scontruct and sconscript files allowing developers to focus on intent not method.


## Installation and Dependencies

No installation is required to use **construct**: simple download or pull a branch of the `site_scons` folder and place it appropriately so Scons will find it. For global use add it to your home directory or for use with a specific project place it beside (or sym-link `site_scons` beside) the top-level `sconstruct` file. For more details on using `site_scons` refer to the [Scons man page](http://www.scons.org/doc/production/HTML/scons-man.html).

There are no dependencies for **construct** other than Scons itself, however if you want to make use of the colourisation you should install the python package [colorama](https://pypi.python.org/pypi/colorama). For example you might do:

```
pip install colorama
```

## Design Principles

**construct** has been written primarily to provide a clean and structured way to leverage the power of Scons without the usual problems of hugely complex `scontruct` files that diverge between projects. Key goals of **construct** are:

  * minimise the need for adding logic into `sconscript` files, keeping them as declarative as possible. 
  * allow declarative `sconscript`s that are both much clearer and significantly simpler than the equivalent `make` file, without the need to learn a whole new scripting language like `make` or `cmake`.
  * provide a clear structure for extending the facilities offered by **construct**
  * provide a clear vocabulary for building projects
  * codify Scons best practices into **construct** itself so that users just need to call appropriate methods knowing that **construct** will do the right thing with their intent
  * provide a framework that allows experts to focus on providing facilities for others to use. Write once, use everywhere. For example one person who knows how best to make [boost](http://www.boost.org/) available as a dependency can manage that dependency and allow others to use it seamlessly.


## Reference

### Basic Structure

**construct** uses the following terms to mean specific aspects of a build. Understanding these will remove ambiguity in understanding the facilities that **construct** provides.

| Term                 | Meaning   |
| -------------------- | --------- |
| Methods              | **construct** provides a number of build methods that can be called inside your `sconscript` files. Methods such as `Build()`, `BuildTest()`, `BuildWith()` and so on. These are in addition to the methods already provided by Scons. |
| Dependencies         | Projects can have an arbitrary number of dependencies, for example [boost](http://www.boost.org/). Typically a dependency requires compiler and linker flags to be updated, or in some cases pulled from a remote repository and built. Wrapping that complexity up into a dependency makes it easy for developers to re-use that effort cleanly across projects. |
| Profiles             | Profiles are a collection of build modifications that are commonly made to builds and might bring in one or more dependencies. Profiles provide an easy way to say, "I always do *this* with my builds" and make that available to others if you want to. |
| Variants and Actions | Variants and Actions allow the specification of a specific builds, such as debug and release builds. Actions allow additional actions to be taken for a build, such as executing tests and analysing code coverage. |
| Toolchains           | Toolchains allow custom build settings for different toolchains making it easy to build for any available toolchain on a specific platform, or even different versions of the same underlying toolchain |

### Construct Command-line Options

```
  --raw-output                Disable output processing like colourisation of
                                output
  --standard-output           Perform standard output processing but not
                                colourisation of output
  --minimal-output            Show only errors and warnings in the output
  --ignore-duplicates         Do not show repeated errors or warnings
  --projects=PROJECTS         Projects to build (alias for scripts)
  --scripts=SCRIPTS           Sconscripts to run
  --configure                 Store the current passed custom options as
                                defaults in a configuration file
  --thirdparty=DIR            Thirdparty directory
  --build-root=BUILD_ROOT     The root directory for build output. If not
                                specified then .build is used
  --test-runner=TEST_RUNNER   The test runner to use for executing tests. The
                                default is the process test runner

  --cov                       Build an instrumented binary
  --dbg                       Build a debug binary
  --rel                       Build a release (optimised) binary
  --test                      Run the binary as a test
  --toolchain=TOOLCHAIN       The Toolchain we are using
  --scm=SCM                   The Source Control Management System we are
                                using
```

### Construct

Creation of the `Construct` instance in your sconstruct file is used to start the build process. `Construct` is defined as follows:

```python
Construct(
        base_path            = os.path.abspath( '.' ), 
        branch_root          = os.path.abspath( '.' ), 
        default_options      = None, 
        default_projects     = None, 
        default_variants     = None, 
        default_dependencies = None, 
        default_profiles     = None, 
        default_test_runner  = None,
        configure_callback   = None )
```

*Overview*: Constructs a `Construct` instance and starts the build process.

*Effects*: Executes the build using the defaults supplied. That is each `sconscript` file will be executed using the defaults specified in the `sconstruct` file. Passing options on the command-line will override any defaults specified here. If no `--scripts` or `--projects` are specified on the command-line `Construct` attempts to find and run `sconscript`s present in the lauch directory from where Scons was executed.

| Argument | Usage |
| ---------| ------|
| `base_path` | You may override this to force a different base path other than the path where the `sconstruct` is located. You might want to do this to compensate for situations were your `sconstruct` file resides beside your project files in the filesystem. |
| `branch_root` | In some project structures, for example those using subversion style folder branches, you may want to specify where your branch root is. The purpose of this would be to allow specification of full branch names when referencing other source code in your `sconstruct` files. For example, if you had project code that relied on a specific branch of shared code (using folder based branches as in subversion) you could refer to the branch explicitly in your `sconstrcut` file as an offset to the `branch_root`. |
| `default_options` | `default_options` expects a dictionary of options. The allowable options are the same as the command-line options with the leading `--`. For example changing the default `build_root` from `.build` to `/tmp/builds` could be achieved by writing `default_options = { 'build-root': '/tmp/builds' }` |
| `default_variants` | `default_variants` takes a list of variants, for example `[ 'dbg', 'rel', 'cov' ]`. By default the `dbg` and `rel` variants are built. If you only wanted to build release variants you might set `default_variants = ['rel']` for example. |
| `default_dependencies` | `default_dependencies` takes a list of dependencies you want to always apply to the build environment and ensures that they are already applied for each build. You may pass the name of a supported dependency, such as `'boost'` or a *callable* object taking `( env, toolchain, variant )` as parameters. |
| `default_profiles` | `default_profiles` takes a list of profiles you want to always apply to the build environment and ensures that they are already applied for each build. You may pass the name of a supported profile or a *callable* object taking `( env, toolchain, variant )` as parameters. |
| `default_test_runner` | By default the `test_runner` used is `'process'` however you my specify your own test runner or use one of the other runners provided, such as `'boost'`. |
| `configure_callback` | This allows you to specify a callback to be executed during part of a `configure` process. This callback should be any *callable* object that takes the following parameter `( configure_context )`. Refer to the [Scons Multi-Platform Configuration documentation](http://www.scons.org/doc/production/HTML/scons-user.html#chap-sconf) for details on how to make use of the `configure_context`. |


### Methods

#### env.`Build`

```python
env.Build( 
        target, 
        source, 
        final_dir = None, 
        append_variant = False )
```

*Overview*: `env.Build()` performs the same task as `env.Program()` but with the additional beenfit of reporting progress and the ability to specify where the target is placed and named. 

*Effects*: Builds the target from the sources specified writing the output as `target_name` where `target_name` is:

```python
target_name = os.path.join( 
         final_dir, 
         target, 
         ( ( append_variant and env['variant'] != 'rel' ) and '_' + env['variant'] or '' ) 
)
```
If `final_dir` is not specified then it is `../final`, relative to the working directory

In addition to adding dynamic libraries to the environment using:

```python
env.AppendUnique( DYNAMICLIBS = env['LIBS'] )
```

`env.Build()` essentially performs as:

```python
env.Program( 
        target_name, 
        source, 
        LIBS = env['DYNAMICLIBS'] + env['STATICLIBS'], 
        CPPPATH = env['SYSINCPATH'] + env['INCPATH'] 
)
```

It can do this because the build variants and toolchains have taken care to ensure that env is configured with the correct values in the variables referenced.


#### env.`Test`

```python
env.Test( 
        source, 
        final_dir = None, 
        data = None, 
        test_runner = None, 
        expected = 'success' )
```

*Overview*: Uses the specified `test_runner` to execute `source` as a test using any `data` provided. The `test_runner` can report on the progress of the test with respect to the `expected` outcome.

*Example*:

```python
Import('env')
test_program = env.Build( 'my_program', [ 'main.cpp', 'utility.cpp' ] )
env.Test( test_program )
```

*Effects*: The `test_runner` will be used to execute the `source` program with any supplied `data` treated as a source dependency for the target test outcome from running the test. Any output from the test will be placed in `final_dir`.


#### env.`BuildTest`
```python
env.BuildTest( 
       target, 
       source, 
       final_dir = None, 
       data = None, 
       append_variant = None, 
       test_runner = None, 
       expected = 'success' )
```

*Overview*: Builds the target from the specified sources and allows it to be executed as a test.

*Effects*: As if:
```python
program = env.Build( target, sources )
env.Test( program )
```


#### env.`BuildWith`
```python
env.BuildWith( dependencies )
```

*Overview*: Updates the current `env` with any modifications required to allow the build to work with the given `dependencies`.

*Effects*: `env` will be updated with all variable and method updates provided by each `dependency` in `dependencies`.

#### env.`BuildProfile`
```python
env.BuildProfile( profiles )
```
*Overview*: Updates the current `env` with any modifications specified in the `profiles` listed.

*Effects*: `env` will be updated as dictated by each `profile` in `profiles`.


#### env.`Use`
```python
env.Use( dependency )
```


#### env.`CreateVersion`
```python
env.CreateVersion( target, source, namespaces, version, location )
```


### Variants

#### `dbg` - Debug

#### `rel` - Release

#### `cov` - Coverage



### Toolchains


### Platforms


## Supported Dependencies


## Tutorial





