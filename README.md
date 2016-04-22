# Cuppa

[![Downloads](https://img.shields.io/pypi/dm/cuppa.svg)](https://pypi.python.org/pypi/cuppa/) [![Latest Version](https://img.shields.io/pypi/v/cuppa.svg)](https://pypi.python.org/pypi/cuppa/) [![Boost License](https://img.shields.io/badge/license-Boost-blue.svg)](http://www.boost.org/LICENSE_1_0.txt)

A simple, extensible build system for use with [Scons](http://www.scons.org/). **Cuppa** is designed to leverage the capabilities of Scons, while allowing developers to focus on the task of describing what needs to be built. In general **cuppa** supports `make` like usage on the command-line. That is developers can simply write:

```sh
scons -D
```

and have Scons "do the right thing"; building targets for any `sconscript` files found in the current directory.

**Cuppa** can be installed as a normal python package or installed locally into a `site_scons` directory allowing it to be effortlessly integrated into any Scons setup.

> Note: `-D` tells `scons` to look for an `sconstruct` file in the current or parent directories and if it finds one execute the `sconscript` files as if called from the starting directory. This ensures everything works as expected. For more details refer to the [Scons documentation](http://www.scons.org/documentation.php)

## Table of Contents

  * [Quick Intro](#quick-intro)
  * [Design Principles](#design-principles)
  * [Installation and Dependencies](#installation-and-dependencies)
  * [Reference](#reference)
    * [Basic Structure](#basic-structure)
    * [Cuppa Command-line Reference](#construct-command-line-options)
    * [Where does Cuppa put my builds?](#where-does-construct-put-my-builds)
    * [Using `--xxxx-conf` to save command-line choices](#using---xxxx-conf-to-save-command-line-choices)
    * [Cuppa](#cuppa)
    * [Methods](#methods)
      * [env.Build](#envbuild)
      * [env.Test](#envtest)
      * [env.BuildTest](#envbuildtest)
      * [env.Compile](#envcompile)
      * [env.BuildWith](#envbuildwith)
      * [env.BuildProfile](#envbuildprofile)
      * [env.Use](#envuse)
      * [env.CreateVersion](#envcreateversion)
    * [Variants and Actions](#variants-and-actions)
      * [dbg - Debug](#dbg---debug)
      * [rel - Release](#rel---release)
      * [cov - Coverage](#cov---coverage)
      * [test - Test](#test---test)
    * [Toolchains](#toolchains)
    * [Platforms](#platforms)
  * [Supported Dependencies](#supported-dependencies)
    * [boost](#boost)
    * [Header-only Libraries](#header-only-libraries)
  * [Creating your own Dependencies](#creating-your-own-dependencies)
    * [Building dependencies on top of `cuppa.header_library_dependency()`](#building-dependencies-on-top-of-cuppaheader_library_dependency)
  * [Acknowledgements](#acknowledgements)

## Quick Intro

### Get **cuppa**

The simpest way to get **cuppa** is to `pip install` it using:

```
pip install cuppa
```

however there are a few approaches that can be used as described in the [Installation and Dependencies](#installation-and-dependencies) section.

### Sample `sconstruct` file

Let's look at a minimal `sconstruct` that makes use of **cuppa**. It could look like this:

```python
# Pull in all the Cuppa goodies..
import cuppa

# Call sconscripts to do the work
cuppa.run()
```

Calling the `run` method in the `cuppa` module starts the build process calling `sconscript` files.

### Sample `sconscript` file

Here is an example `sconscript` file that builds all *.cpp files in the directory where it resides:

```python
Import( 'env' )

# Build all *.cpp source files as executables
for Source in env.GlobFiles('*.cpp'):
    env.Build( str(Source)[:-4], Source )
```

The `env.Build()` method is provided by **cuppa** and does essentially what `env.Program()` does but in addition is both toolchain and variant aware, and further can provide notifications on progress.

> Note: Source[:-4] simply strips off the file extension `.cpp`, that is, the last 4 characters of the file name.

If our `sconscript` file was for a directory containing *.cpp files that are actually tests then we could instead write the `sconscript` file as:

```python
Import( 'env' )

# Build all *.cpp source files as executables to be run as tests
for Source in env.GlobFiles('*.cpp'):
    env.BuildTest( str(Source)[:-4], Source )
```

The `env.BuildTest()` method is provided by **cuppa** and builds the sources specified as `env.Build()` does.

However, in addition, passing `--test` on the command-line will also result in the executable produced being run by a **runner**. The default test runner simply treats each executable as a test case and each directory of executables as a test suite. If the process executes cleanly the test passed, if not it failed.

To run this on the command-line we would write:

```sh
scons -D --test
```

If we only want to build and test *debug* executables we can instead write this:

```sh
scons -D --dbg --test
```

Or for release only pass `--rel`.

**cuppa** also makes it easy to work with [dependencies](#supported-dependencies). For example, if [boost](http://www.boost.org/) was a default dependency for all your `sconscript` files you could write your sconstruct file as follows:

```python
import cuppa

cuppa.run(
    default_options = {
         'boost-location': '<Location of Boost>'
    },
    default_dependencies = [
        'boost'
    ]
)
```

This will automatically ensure that necessary includes and other compile options are set for the boost version that is found at `boost-location`.

> Note: **cuppa** will even attempt to retrieve the dependency if a version or URL is supplied. Including from source control assuming you have the necessary source control system installed on your machine.

If you need to link against specific boost libraries this can also be done in the sconscript file as follows:

```python
Import('env')

Test = 'my_complex_test'

Sources = [
    Test + '.cpp'
]

env.AppendUnique( STATICLIBS =
    env.BoostStaticLibs( [
        'system',
        'log',
        'thread',
        'timer',
        'chrono',
        'filesystem'
    ] )
)

env.BuildTest( Test, Sources )
```

The `BoostStaticLibs()` method ensures that the library is built in the correct build variant as required. If you preferred to use dynamic linking then that can also be achieved using `BoostSharedLibs()`.

The point is the complexities of using [boost](http://www.boost.org/) as a *dependency* are encapsulated and managed separately from the scontruct and sconscript files allowing developers to focus on intent, not method.

## Design Principles

**cuppa** has been written primarily to provide a clean and structured way to leverage the power of Scons without the usual problems of hugely complex `scontruct` files that diverge between projects. Key goals of **cuppa** are:

  * minimise the need for adding logic into `sconscript` files, keeping them as declarative as possible.
  * allow declarative `sconscript`s that are both much clearer and significantly simpler than the equivalent `make` file, without the need to learn a whole new scripting language like `make` or `cmake`.
  * provide a clear structure for extending the facilities offered by **cuppa**
  * provide a clear vocabulary for building projects ([dependencies, methods, profiles, runners, variants etc.](#basic-structure))
  * codify Scons best practices into **cuppa** itself so that users just need to call appropriate methods knowing that **cuppa** will do the right thing with their intent
  * provide a framework that allows experts to focus on providing facilities for others to use. Write once, use everywhere. For example one person who knows how best to make [boost](http://www.boost.org/) available as a dependency can manage and maintain that dependency and allow others to use it seamlessly.


## Installation and Dependencies

### Installation

**cuppa** can be made available as a normal python package and this is the preferred method of installation. It can be added directly to a `site_scons` folder, placed appropriately so Scons will find it. For global use add it to your home directory or for use with a specific project place it beside (or sym-link `site_scons` beside) the top-level `sconstruct` file. For more details on using a `site_scons` folder refer to the [Scons man page](http://www.scons.org/doc/production/HTML/scons-man.html).

The following sections summarise some of the ways you can get **cuppa**.

#### Method 1: Install it as a python package ####

Use `pip install` to get the latest:

```
pip install cuppa
```

#### Method 2: Install it locally in your project folder ####

Install locally in the same folder as your `sconstruct` file using:

```
pip install cuppa -t .
```

### Method 3: Bootstrap a local installation from your `sconstruct` file directly

Adding this to your `sconstruct` file would `pip install` **cuppa** if it was not found:

```python
try:
    import cuppa
except ImportError:
    print "Cuppa not found, installing..."
    import subprocess, shlex
    subprocess.call( shlex.split( 'pip install cuppa -t .' ) )
    import cuppa
```

### Dependencies

##### Coloured output

To make use of the colourisation **cuppa** uses the [colorama](https://pypi.python.org/pypi/colorama) package.

#### HTML coverage summaries

**cuppa** uses the [gcovr](https://github.com/gcovr/gcovr) python library to help post-process the coverage files that `gcov` produces (used by both the GCC and CLANG toolchains). This produces a nice `coverage.html` file in your final build folder that links to HTML files for all files for which coverage information was produced.


## Reference

### Basic Structure

**cuppa** uses the following terms to mean specific aspects of a build. Understanding these will remove ambiguity in understanding the facilities that **cuppa** provides.

| Term                 | Meaning   |
| -------------------- | --------- |
| Methods              | **cuppa** provides a number of build methods that can be called inside your `sconscript` files. Methods such as `Build()`, `BuildTest()`, `BuildWith()`, `Compile()` and so on. These are in addition to the methods already provided by Scons. A key difference between these methods and the basic Scons methods such as `Program()` and `Object()` is that these methods are aware of build variants, toolchains, progress notifications and so on. |
| Dependencies         | Projects can have an arbitrary number of *dependencies*, for example [boost](http://www.boost.org/) or [Qt](http://www.qt.io/). Typically a dependency requires compiler and linker flags to be updated, or in some cases pulled from a remote repository and built. Wrapping that complexity up into a dependency makes it easy for developers to re-use that effort cleanly across projects. |
| Profiles             | *Profiles* are a collection of build modifications that are commonly made to builds and might bring in one or more dependencies. Profiles provide an easy way to say, "I always do *this* with my builds" and make that available to others if you want to. |
| Variants and Actions | *Variants* and *Actions* allow the specification of a specific builds, such as debug and release builds. Actions allow additional actions to be taken for a build, such as executing tests and analysing code coverage. |
| Target Architecture  | The *Target Architecture* is the platform target of any build output. If none is specified a default for the current platform and toolchain is used. By tracking this information it allows multiple builds to be completed for different target architectures, such as `x86` and `amd64` on Windows. |
| Toolchains           | Toolchains allow custom build settings for different toolchains making it easy to build for any available toolchain on a specific platform, or even different versions of the same underlying toolchain. For example you might want to build and test against several versions of GCC and Clang at the same time. This allows you to do so. |

### Cuppa Command-line Options

```
  --show-conf                 Show the current values in the configuration
                                file if one exists
  --save-conf                 Save the current command-line a configuration
                                file
  --update-conf               Update the configuration file with the current
                                command-line
  --remove-settings=REMOVE_SETTINGS
                              Remove the listed settings from the
                                configuration file
  --clear-conf                Clear the configuration file
  --raw-output                Disable output processing like colourisation of
                                output
  --standard-output           Perform standard output processing but not
                                colourisation of output
  --minimal-output            Show only errors and warnings in the output
  --ignore-duplicates         Do not show repeated errors or warnings
  --projects=PROJECTS         Projects to build (alias for scripts)
  --scripts=SCRIPTS           Sconscripts to run
  --thirdparty=DIR            Thirdparty directory
  --build-root=BUILD_ROOT     The root directory for build output. If not
                                specified then .build is used
  --download-root=DOWNLOAD_ROOT
                              The root directory for downloading external
                                libraries to. If not specified then .cuppa is
                                used
  --runner=RUNNER             The test runner to use for executing tests. The
                                default is the process test runner
  --dump                      Dump the default environment and exit
  --parallel                  Enable parallel builds utilising the available
                                concurrency. Translates to -j N with N chosen
                                based on the current hardware
  --show-test-output          When executing tests display all outout to
                                stdout and stderr as appropriate
  --verbosity=VERBOSITY       The The verbosity level that you wish to run
                                cuppa at. The default level is "info".
                                VERBOSITY may be one of ('trace', 'debug',
                                'info', 'warn', 'error')
  --decider=DECIDER           The decider to use for determining if a
                                dependency has changed. Refer to the Scons
                                manual for more details. By default
                                "MD5-timestamp" is used. DECIDER may be one of
                                ('timestamp-newer', 'timestamp-match', 'MD5',
                                'MD5-timestamp')
  --stdcpp=STDCPP             Use this option to override the default language
                                compliance of your cpp compiler which by
                                dafault is the highest compliance available.
                                Value may be one of ('c++98', 'c++03',
                                'c++0x', 'c++11', 'c++1y', 'c++14')
  --cov                       Build an instrumented binary
  --dbg                       Build a debug binary
  --rel                       Build a release (optimised) binary
  --test                      Run the binary as a test
  --toolchains=TOOLCHAINS     The Toolchains you wish to build against
```

### Where does Cuppa put my builds?

**cuppa** places all builds outside of the source tree under the `BUILD_ROOT` which by default is the folder `_build` beside the `sconstruct` file used when Scons is executed. You can change this by specifying the `--build-root` option.

Build variants and the output from each `sconscript` is kept separate using the following convention:

`<build_root>/<sconscript_path>/<sconscript_name>/<toolchain>/<build_variant>/<target_arch>/final`

If `<sconscript_name>` is "sconscript" then it is omitted from the path. The assumption is that a single `sconscript` file is being used for the given folder and therefore the folder name is sufficient to differentiate from other `sconscript`s.

### Using `--xxxx-conf` to show, save and udpate command-line choices

**cuppa** allows you to save commonly used or local settings to a conf file so that they can be re-applied when you execute `scons` from anywhere in your Sconscript tree. The basic approach is to pass `--save-conf` along with the options you wish to save.

No builds will be performed at this time and your effective command-line will be dispalyed for you to review. Next time you simply execute `scons` (or more typically `scons -D`) your previous options will be applied automatically. For example, passing `--save-conf` alongside `--boost-home=~/boost/boost_1_55` would result in `--boost-home` being applied on subsequent builds.

In addition to `--save-conf` there are a few other options that allow, updating, removing, clearing and reviewing of options. All the options are summarised below:

| Option | Description |
| ------ | ----------- |
| `--save-conf` | Saves all the current command-line settings to the conf file - overwriting any that existed previously. |
| `--update-conf` | Passing `--update-conf` which will save any new settings passed and overwrite the values of existing settings. Other existing settings will remain unchanged. |
| `--clear-conf` | Removes the conf file - clearing all settings. |
| `--remove-settings` | `--remove-settings` takes a comma-separate list of settings to be removed from the currrent conf file. Non-existant settings are ignored. |
| `--show-conf` | Echoes the equivalent command-line that would result from the application of the existing conf file. |


### Cuppa

Calling the `run()` method of the `cuppa` module in your sconstruct file is used to start the build process. `run()` is defined as follows:

```python
run(    base_path            = os.path.abspath( '.' ),
        branch_root          = None,
        default_options      = {},
        default_projects     = [],
        default_variants     = [],
        default_dependencies = [],
        default_profiles     = [],
        default_runner       = None,
        configure_callback   = None,
        dependencies         = {},
        tools                = [] )
```

*Overview*: Starts the build process.

*Effects*: Executes the build using the defaults supplied. That is each `sconscript` file will be executed using the defaults specified in the `sconstruct` file. Passing options on the command-line will override any defaults specified here. If no `--scripts` or `--projects` are specified on the command-line **cuppa** attempts to find and run `sconscript`s present in the lauch directory from where Scons was executed.

| Argument | Usage |
| -------- | ----- |
| `base_path` | You may override this to force a different base path other than the path where the `sconstruct` is located. You might want to do this to compensate for situations were your `sconstruct` file resides beside your project files in the filesystem. |
| `branch_root` | In some project structures, for example those using subversion style folder branches, you may want to specify where your branch root is. The purpose of this would be to allow specification of full branch names when referencing other source code in your `sconstruct` files. For example, if you had project code that relied on a specific branch of shared code (using folder based branches as in subversion) you could refer to the branch explicitly in your `sconstrcut` file as an offset to the `branch_root`. |
| `default_options` | `default_options` expects a dictionary of options. The allowable options are the same as the command-line options with the leading `--`. For example changing the default `build_root` from `.build` to `/tmp/builds` could be achieved by writing `default_options = { 'build-root': '/tmp/builds' }` |
| `default_variants` | `default_variants` takes a list of variants, for example `[ 'dbg', 'rel', 'cov' ]`. By default the `dbg` and `rel` variants are built. If you only wanted to build release variants you might set `default_variants = ['rel']` for example. |
| `default_dependencies` | `default_dependencies` takes a list of dependencies you want to always apply to the build environment and ensures that they are already applied for each build. You may pass the name of a supported dependency, such as `'boost'` or a *callable* object taking `( env, toolchain, variant )` as parameters. |
| `default_profiles` | `default_profiles` takes a list of profiles you want to always apply to the build environment and ensures that they are already applied for each build. You may pass the name of a supported profile or a *callable* object taking `( env, toolchain, variant )` as parameters. |
| `default_runner` | By default the `runner` used is `'process'` however you my specify your own test runner or use one of the other runners provided, such as `'boost'`. |
| `configure_callback` | This allows you to specify a callback to be executed during part of a `configure` process. This callback should be any *callable* object that takes the following parameter `( configure_context )`. Refer to the [Scons Multi-Platform Configuration documentation](http://www.scons.org/doc/production/HTML/scons-user.html#chap-sconf) for details on how to make use of the `configure_context`. |
| `dependencies` | `dependencies` takes a dictionary of dependency classes as `"name":class_name` pairs. For example you might  |
| `tools` | `tools` takes a list of Scons Tools that should be added by default to all environments |


### Methods

#### env.`Build`

```python
env.Build(
        target,
        source,
        final_dir = None,
        append_variant = False )
```

*Overview*: `env.Build()` performs the same task as `env.Program()` but with the additional benefit of reporting progress and the ability to specify where the target is placed and named.

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
        runner = None,
        expected = 'passed' )
```

*Overview*: Uses the specified `runner` to execute `source` as a test using any `data` provided. The `runner` can report on the progress of the test with respect to the `expected` outcome.

*Example*:

```python
Import('env')
test_program = env.Build( 'my_program', [ 'main.cpp', 'utility.cpp' ] )
env.Test( test_program )
```

*Effects*: The `runner` will be used to execute the `source` program with any supplied `data` treated as a source dependency for the target test outcome from running the test. Any output from the test will be placed in `final_dir`.


#### env.`BuildTest`
```python
env.BuildTest(
       target,
       source,
       final_dir = None,
       data = None,
       append_variant = None,
       runner = None,
       expected = 'passed' )
```

*Overview*: Builds the target from the specified sources and allows it to be executed as a test.

*Effects*: As if:
```python
program = env.Build( target, sources )
env.Test( program )
```


#### env.`Compile`
```python
env.Compile( sources )
```

*Overview*: Compile the specified `sources` into object files.

*Effects*: Returns `objects` nodes that represent the outcome of compiling the specified `sources`. As if:
```python
objects = env.Object( sources, CPPPATH = env['SYSINCPATH'] + env['INCPATH'] )
```
Typically `env.Compile()` is not needed and instead you should directly use `env.Build()` to directly produce the required program or library being built. However in some cases, such as when using `env.CreateVersion()` you need to break dependency cycles and then `env.Compile()` is needed.


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
*Overview*: Updates the current `env` with specified `dependency`.

*Effects*: `env` will be updated as per the `dependency`.


#### env.`CreateVersion`
```python
env.CreateVersion( version_file, sources, namespaces, version, location )
```

*Overview*: Creates a version cpp and hpp file that can be included in other files in your project while ensuring dependencies between files are correctly handled and that the cpp file is built correctly.

*Effects*: Creates a `version_file` and a header file for the target file that depends on `sources`. The version file will have a class `identity` nested inside `namespaces` with an interface as follows:

```
#ifndef INCLUDED__FIRST__SECOND__N_BUILD_GENERATED_VERSION_HPP
#define INCLUDED__FIRST__SECOND__N_BUILD_GENERATED_VERSION_HPP

namespace _first {
namespace _second {
namespace _n {

class identity
{
public:

    typedef std::string                             string_t;
    typedef std::vector< string_t >                 revisions_t;

private:

    struct dependency
    {
        string_t       name;
        string_t       version;
        revisions_t    revisions;
    };

public:

    typedef dependency                              dependency_t;
    typedef std::map< string_t, dependency >        dependencies_t;

public:

    static const char* const        product_version();
    static const char* const        product_revision();
    static const char* const        build_variant();
    static const char* const        build_time();
    static const char* const        build_user();
    static const char* const        build_host();
    static const dependencies_t&    dependencies();
    static const char* const        report();
};

} // end namespace _n
} // end namespace _second
} // end namespace _first

#endif
```

The `version` provided is used to populate the result of `product_version()` method and the `location` is used to specify what directories should be read to determine revision information based on the source control method used. For example if the source under `location` is from a subversion repository the `revision()` method will return the revision number of the source code. In addition to details about the build system are also included as well as the time of the build and the build variant, such as debug or release. The `report()` method provide a single string containing all the information.

Typically `env.CreateVersion()` is used with the `env.Compile()` method to allow dependencie between intermediate objects to be established as shown in the example that follows.

*Example*:
```python
Import('env')

Version = "Product 00.01.00"

Sources = [
    'main.cpp',
]

# We add this intermediary step to get the nodes representing the objects
# after compilation so that we can make the version file depend on this.
# Otherwise we could pass the source files directly to the Build() method
ProductObjects = env.Compile( Sources )

# If anything in the application changes we want a new version file with
# new build times and so on. We therefore make the version file depend
# on the result of compiling all our sources apart from the version file
# itself. This ensures that changes that cause the source to recompile will
# also cause the version file to be recompiled.
VersionFile = env.CreateVersion(
    'version.cpp',              # The name of the version file. This will be
                                # in the current directory.
    ProductObjects,             # What the version file depends on.
    ['company', 'product'],     # The namespaces that should be used to nest
                                # the version info in.
    Version,                    # The product version string.
    env['base_path']            # The location below which all revision information
                                # should be gathered in this case basically all source
                                # from sconsctuct and below
)

# The program itself will depend on all objects and the version file
Objects = ProductObjects + VersionFile

env.Build( 'product_name', Objects )
```

### Variants and Actions

#### `dbg` - Debug

Specifies the creation of a debug variant of the build. Usually including debug symbols, no optimisations and so on. What exactly is done depends on the toolchain and normal settings for it.

#### `rel` - Release

Specifies the creation of a release variant of the build. Usually with full optimisations turned on. What exactly is done depends on the toolchain and normal settings for it.

#### `cov` - Coverage

Specifies the creation of an instrumented variant of the build which allows coverage metrics to be gathered when the program is run. Usually including debug symbols this typically produces a fully instrumented build so that metrics can be obtained. Depending on the toolchain and coverage summariser used HTML or XML coverage output can be produced.

In order for the coverage to be determined for a given build target the program must be executed and therefore specifying `--cov` implies `--test`. To indicated that a build target is executable it should be built with the `BuildTest()` method. If only `Build()` is used then intermediate instrumented files will be produced, but the target will not be executed and no coverage data will be generated.

#### `test` - Test

The `test` variant does not actually produce an output directly. Instead it executes any target build using the `BuildTest()` method. The `runner` specified in the call to `BuildTest()` (or the default if none is specified) is used to execute the target and interpret success or failure.

### Toolchains

The following toolchains are currently supported:

#### The GCC family

| Toolchain | Description |
| --------- | ----------- |
| `gcc34`   | g++ 3.4 |
| `gcc40`   | g++ 4.0 |
| `gcc41`   | g++ 4.1 |
| `gcc42`   | g++ 4.2 |
| `gcc43`   | g++ 4.3 |
| `gcc44`   | g++ 4.4 |
| `gcc45`   | g++ 4.5 |
| `gcc46`   | g++ 4.6 |
| `gcc47`   | g++ 4.7 |
| `gcc48`   | g++ 4.8 |
| `gcc49`   | g++ 4.9 |
| `gcc50`   | g++ 5.0 |
| `gcc51`   | g++ 5.1 |
| `gcc52`   | g++ 5.2 |
| `gcc53`   | g++ 5.3 |

#### The Clang family

| Toolchain | Description |
| --------- | ----------- |
| `clang32` | clang 3.2 |
| `clang33` | clang 3.3 |
| `clang34` | clang 3.4 |
| `clang35` | clang 3.5 |
| `clang36` | clang 3.6 |
| `clang37` | clang 3.7 |
| `clang38` | clang 3.8 |

#### The Visual C++ family

| Toolchain | Description |
| --------- | ----------- |
| `vc60`    | Visual C++ 6.0                                |
| `vc70`    | Visual C++ 7.0 (Visual C++ .NET 2002)         |
| `vc71`    | Visual C++ 7.1 (Visual C++ .NET 2003)         |
| `vc80e`   | Visual C++ 8.0 Express (Visual C++ 2005 Exp)  |
| `vc80`    | Visual C++ 8.0 (Visual C++ 2005)              |
| `vc90e`   | Visual C++ 9.0 Express (Visual C++ 2008 Exp)  |
| `vc90`    | Visual C++ 9.0 (Visual C++ 2008)              |
| `vc100e`  | Visual C++ 10.0 Express (Visual C++ 2010 Exp) |
| `vc100`   | Visual C++ 10.0 (Visual C++ 2010)             |
| `vc110e`  | Visual C++ 11.0 (Visual C++ 2012 Exp)         |
| `vc110`   | Visual C++ 11.0 (Visual C++ 2012)             |
| `vc120e`  | Visual C++ 12.0 (Visual C++ 2013 Exp)         |
| `vc120`   | Visual C++ 12.0 (Visual C++ 2013)             |
| `vc140e`  | Visual C++ 14.0 (Visual C++ 2015 Exp)         |
| `vc140`   | Visual C++ 14.0 (Visual C++ 2015)             |

#### Note

It is not necessary to specify a toolchain when building. If none is specified the default toolchain for the current platform will be used. However if more toolchains are available and you want to use one or more then pass the `--toolchains` option with a comma-separated list of toolchains from the list. For example to build with both GCC 4.9 and CLANG 3.4 you would add:

```
--toolchains=gcc49,clang35
```

to the command-line. It is not necessary to specify the versions of the toolchains if you just want the default version. For example you could write:

```
--toochains=gcc,clang
```
You can also use `*` as a wildcard so all available GCC toolchains would be:

```
--toolchains=gcc*
```

### Platforms

The following platforms are supported:

  * Linux
  * Darwin (Mac)

## Supported Dependencies

In order to make use of a dependency in your code it must both exist and be added to the current environment. Typically a dependency is created by indicating a version or location of the dependency. It is up to each dependency how they interpret this information. To then use the dependency you can either make it a default dependency by passing it as a list member to the `default_dependencies` argument to `cuppa.run` or by using the `BuildWith()` or `Use()` methods.

### `boost`

The `boost` dependency simplifies the use of the [Boost C++ Libraries](http://www.boost.org).

#### Options

The dependency provides the following options to specify which Boost source tree you wish to build against.

| Option | Description |
| -------| ------------|
| `--boost-home` | Use this option to specify the location of your Boost source tree which contains the Boost `boost` and `lib` folders. For example if you downloaded Boost 1.55 and extracted it to `~/boost/boost_1_55` so that `boost` and `lib` are in that folder then you can make boost available to your builds by specifying `--boost-home=~/boost/boost_1_55` on the command-line |
| `--boost-version` | If you specified a `--thirdparty` option then you can use `--boost-version` to indicate that you want to build with a particular version of boost under the `thirdparty` folder. The version should be in the format `major_minor` for example to specify using boost version 1.55 you would write `--boost-version=1_55`. The boost dependency then tries to find a matching version of Boost under the `thirdparty` folder. |
| `--boost-build-always` | By default `bjam` is only executed once to build each library once. That is, it is assumed that the sourec is static and will not change. If it is possible or likely that the the boost sources will be changed then specifying `--boost-build-always` will ensure that `bjam` is executed every time to check if the library needs rebuilt or not. |
| `--boost-verbose-build` | By default only warning and error messages are displayed when boost is being built and even then only the summary (file and location) of the warning or error is shown. Passing this flag will show full build output allowing problems to be diagnosed. |
| `--boost-verbose-config` | By default no boost configuration messages are shown, such as performance configuration checks or configuration file reading. Passing this flag will show all configuration output allowing problems to be diagnosed. |

#### Build Methods

This dependency provides the following additional build methods to make using Boost easier.

| Method | Description |
| ------ | ----------- |
| `BoostStaticLibs` | Specifies Boost libraries to lazily build for statically linking against. The libraries are specified using the libraries' names in a list. For example, to create a static version of the Boost.thread library for statically linking against you would write, `BoostStaticLibs( [ 'thread' ] )`. For more details see [BoostStaticLibs](#booststaticlibs). |
| `BoostSharedLibs` | Specifies Boost libraries to lazily build for dynamically linking against. The libraries are specified using the libraries' names in a list. For example, to create a shared (dynamic) version of the Boost.thread library for dynamically linking against you would write, `BoostSharedLibs( [ 'thread' ] )`. For more details see [BoostSharedLibs](#boostsharedlibs). |

It is important to note that these methods return a node representing the built libraries. To link against the libraries you need to append the library to the environment's `STATICLIBS` or `DYNAMICLIBS` as appropriate.

> Note: These methods will automatically add any required dependent libraries to the list of libraries built. For example if you want to link against Boost.Coroutine then these methods will also build Boost.Context and other libraries that Boost.Coroutine requires.

> Note: Calling either `BoostStaticLibs` or `BoostSharedLibs` will automatically imply `BuildWith( ['boost'] )` if `boost` has not already been added as a dependency.

##### `BoostStaticLibs`

Use this method to specify a Boost library that you want to link statically with your application. For example, if you want to use Boost.System and Boost.Thread you would add this to your `sconscript` file:

```python
env.AppendUnique( STATICLIBS =
    env.BoostStaticLibs( [
        'system',
        'thread'
    ] )
)
```

This is all that is required to ensure that the libraries are built correctly and linked with your target.

##### `BoostSharedLibs`

Use this method to specify a Boost library that you want to link statically with your application. For example, if you want to use Boost.Coroutine and Boost.Chrono you would add this to your `sconscript` file:

```python
env.AppendUnique( DYNAMICLIBS =
    env.BoostSharedLibs( [
        'system',
        'chrono',
        'coroutine'
    ] )
)
```

This is all that is required to ensure that the libraries are built correctly and linked with your target. It is important to note this will also "Do The Right Thing" in the presence of existing Boost installations. In other words this will pick up the correct shared library.

### Header only Libraries

**Cuppa** makes building with header only libraries easy if all you need to do add the libraries to your include path. To support this scenario **cuppa** provides the `cuppa.header_library_dependency()` factory. The remainder of this section describes how to use this class factory to define your own simple header library dependencies. For more sophisticated uses refer to the [Custom Header-only Dependencies](#custom-header-only-dependencies) section.

#### Using the `cuppa.header_library_dependency()` class factory

The `cuppa.header_library_dependency()` class factory takes one parameter, the name of the dependency and returns a class that can be given to **cuppa** for later use.

For example, let's consider adding the non-boost version of the [asio library](http://think-async.com/Asio) as a project dependency. We can download a release and put is somewhere convenient. Then we could write our `sconstruct` file as follows:

```python
# Specify where to find 'asio'
options['asio-location'] = "<location-of-asio>"
# Specify the include folder needed to allow compilation
options['asio-include']  = "asio/include"

cuppa.run(
    # Add 'asio' as a dependency
    dependencies = {
        'asio': cuppa.header_library_dependency( 'asio' )
    },
    # Ensure the options we've added for 'asio' are added to the defaults
    default_options = options,
    # Make this a default dependency in all sconscripts
    default_dependencies = [ 'asio' ]
)
```

Now we can compile against [asio](http://think-async.com/Asio) as expected by adding:

```cpp
#include <asio.hpp>
```

#### Version-controlled and remote locations supported

We are not limited to specifying location dependencies on local disk. It is also possible to specify remote locations. For example, again considering [asio](http://think-async.com/Asio), if we want to build against a specfic release tag of the source code directly from the source repository we could write `[asio-location]` as follows:

```python
[asio-location] = "git+https://github.com/chriskohlhoff/asio.git@asio-1-10-4"
```

Of course being an ordinary option we could override this on the command-line if we wanted to, for example, to try building against `master`. In that case we might write this while invoking `scons`:

```sh
scons -D --asio-location="git+https://github.com/chriskohlhoff/asio.git"
```

As you might expect building against a branch rather than a specific tag or archived release automatically updates as the branch is updated.

#### `cuppa.header_library_dependency()` in more detail

As shown perviously the `cuppa.header_library_dependency()` factory function takes a name (referred to as `<dependency-name>` below) for the dependency and returns a class that can be passed as a dependency to **cuppa**.

Classes created the factory function provide the following Scons options.

| Option | Description |
| -------| ------------|
| `--<dependency-name>-location` | Specify the location of the dependency. The location can be any local directory, or any URL to a remote directory or archive, as well any [version controlled location supported by pip](https://pip.pypa.io/en/latest/reference/pip_install.html#vcs-support). |
| `--<dependency-name>-include`  | This allows you to specify a subfolder which should be added to the `INCPATH` Scons variable. |
| `--<dependency-name>-branch`   | You may use the `--<dependency-name>-branch` option with local directories to specify that a subfolder (as a branch) is added to the location given. This follows the approach used with [Subversion](https://subversion.apache.org/) to allow branches to be specfied as folders. If you are using a remote location branch information is typically provided as part of the URL and so this option is not needed. The option also finds use for informational purpores if the given location is not under version control and branch or revision information is not available. |

Typically only `--name-location` and `--name-include` are needed when used with remote URLs.

##### What happens when a remote URL is specified?

When a remote URL is specified, and the files have not previously been obtained, then **cuppa** attemtps to either download, `checkout` or `pull` them. Once retrieved compressed archives are expanded into a suitable location.

##### Where does **cuppa** store retrieved files?

**Cuppa** stores any retrieved files under a sub-folder under `.cuppa`. The sub-folder name is derived from the URL so that it is unique for a given URL. That means different branches of the same repository will be checked out in to different folders.

##### What happens if the files are already present?

If the files are already present and they were not retrieved from version control then nothing is done. However, if the files were retrieved from version control then **cuppa** will attempt to update the files to the latest revision as allowed by the original URL specified.

## Creating your own Dependencies

It is possibly to create your own dependencies, like the `boost` dependency. As far as **cuppa** is concerned a dependency is any class that provides the following:

```python
import os
from cuppa.log import logger
from cuppa.colourise import as_notice, as_error


class <dependency>:

    _name = <dependency>
    _cached_locations = {}

    @classmethod
    def add_options( cls, add_option ):
        # Specify any options here
        location_name = cls._name + "-location"
        add_option( '--' + location_name,
                    dest=location_name,
                    type='string', nargs=1,
                    action='store',
                    help = cls._name + ' location to build against' )

    @classmethod
    def add_to_env( cls, env, add_dependency  ):
        add_dependency( cls._name, cls.create )

    @classmethod
    def _location_id( cls, env ):
        location = env.get_option( cls._name + "-location" )
        if not location and env['thirdparty']:
            location = os.path.join( env['thirdparty'], cls._name )
        if not location:
            logger.debug( "No location specified for dependency [{}]."
                          " Dependency not available."
                          .format( cls._name.title() ) )
            return None
        return location

    @classmethod
    def _get_location( cls, env ):
        location_id = cls._location_id( env )
        if not location_id:
            return None
        if location_id not in cls._cached_locations:
            try:
                cls._cached_locations[location_id] = cuppa.location.Location( env, location )
            except cuppa.location.LocationException as error:
                logger.error(
                        "Could not get location for [{}] at [{}]."
                        " Failed with error [{}]"
                        .format( as_notice( cls._name.title() ),
                                 as_notice( str(location) ),
                                 as_error( error ) )
                )
                return None
        return cls._cached_locations[location_id]

    @classmethod
    def create( cls, env ):
        location = cls._get_location( env )
        if not location:
            return None
        return cls( env, location )

    def __init__( self, env, location ):
        self._location = location

    def __call__( self, env, toolchain, variant ):
        # Update the environment
        pass

    def name( self ):
        return sel._name

    def version( self ):
        return str(self._location.version())

    def repository( self ):
        return self._location.repository()

    def branch( self ):
        return self._location.branch()

    def revisions( self ):
        return self._location.revisions()
```

Only `add_to_env()`, `create()`, `__call__` and `name()` are strictly required but it makes sense to provide the others as using `cuppa.location.Location` makes this trivial.

Once the basic dependency is written abitrarily complex relationships can be built by making use of Scons builders or other dependency related tools. It is worth looking at the `boost` dependency as an example of a complex dependency.

### Building dependencies on top of `cuppa.header_library_dependency()`

Most dependencies will be much more trivial than the `boost` dependency and many can be built directly on top of the `cuppa.header_library_dependency()` factory. For example, let's look again at using [asio](http://think-async.com/Asio) as a dependency. We've already seen how we can create a basic dependency by writing:

```python
asio_dependency = cuppa.header_library_dependency( 'asio' )

```

We can take this a step further and create our dependency by inheriting from the class returned by the factory and overriding the `__call__` method:

```python

# Specify where to find 'asio'
options['asio-location'] = "<location-of-asio>"


class asio( cuppa.header_library_dependency( 'asio' ) ):

    def __call__( self, env, toolchain, variant ):
        super(asio,self).__call__( env, toolchain, variant )
        # Update the environment as we need to, for example...

        # Save the user from having to specify this
        env.AppendUnique( SYSINCPATH = [
            'asio/include'
        ]
        # Perhaps we remove deprecated features
        env.AppendUnique( CPPDEFINES = [
            'ASIO_NO_DEPRECATED',
            ] )


cuppa.run(
    # Add 'asio' as a dependency
    dependencies = {
        'asio': asio
    },
    # Ensure the options we've added for 'asio' are added to the defaults
    default_options = options,
    # Make this a default dependency in all sconscripts
    default_dependencies = [ 'asio' ]
)

```

## Acknowledgements

This work is based on the build system used in [clearpool.io](http://www.clearpool.io) during development of its next generation exchange platform.



