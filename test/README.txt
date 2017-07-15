This directory serves to illustrate the problem and fix for building shared
libraries with cuppa. Two files, f1.cpp and f2.cpp, are compiled and linked
into a shared library, libfoo.so, which is then used by the executable, bar,
created from bar.cpp.

First build using scons alone and verify the executable works:
$ scons -f SConstruct_scons
$ LD_LIBRARY_PATH='.' ./bar

Notice the following:
- All generated files are dumped in this directory.
- The "-fPIC" option is passed to the compiler for f1.cpp and f2.cpp.
- The object file suffix is ".os" for f1.os and f2.os.
- The build works.
- The executable works.

Now clean up:
$ scons -f SConstruct_scons -c
$ rm .sconsign.dblite

Now try to build using cuppa:
$ scons

Notice the following:
- All the genereated files are under _build. (Nice!)
- THe "-fPIC" options is NOT passed to the compiler for f1.cpp and f2.cpp.
- The link of the shared library fails with a scons error message about
  static object files not being compatible with shared target:

    """
    scons: *** [_build/gcc54/dbg/x86_64/c++1z/final/libfoo.so] Source file:
     _build/gcc54/dbg/x86_64/c++1z/working/_build/gcc54/dbg/x86_64/c++1z/working/f1.o
     is static and is not compatible with shared target:
     _build/gcc54/dbg/x86_64/c++1z/final/libfoo.so
    scons: building terminated because of errors.
    """

This error comes from /usr/lib/scons/SCons/Defaults.py:120 in the function
SharedFlagChecker. I found StackOverflow suggestions to define
STATIC_AND_SHARED_OBJECTS_ARE_THE_SAME in the build environment, but that
really has a bad code smell. It is defined for the 'aix' platform, for
example, in /usr/lib/scons/SCons/Tool/g++.py:61 but that whole thing
looks like a kludge.

You can see that the SharedFlagChecker passes if the target has an attribute
'shared' which should be set by the SharedObjectEmitter defined at
/usr/lib/scons/SCons/Default.py:106 and added to the shared object builder at
/usr/lib/scons/SCons/Tool/c++.py:71. Yes, this file appears to be just for the
IBM VisualAge C++ compiler according to its comments, but it gets brought into
/usr/lib/scons/SCons/Tool/g++.py at line 45 and used at line 56.

The shared object builder is originally created in the function
createObjBuilders from /usr/lib/scons/SCons/Tool/__init__.py:720. This gets
called at /usr/lib/scons/SCons/Tool/g++.py:51 and again, unnecessarily, at
/usr/lib/scons/SCons/Tool/c++.py:65 via the call at g++.py:56.

So...

Clean up again:
$ rm .sconsign.dblite config.log
$ rm -rf _build .sconf_temp

and apply the fix to the following files:
- cuppa/methods/build_library.py
- cuppa/methods/compile.py
where ever your cuppa is installed.

Now build using cuppa:
$ scons
$ ./_build/gcc54/dbg/x86_64/c++1z/final/bar

Your path may differ depending on your toolset. (... as if you didn't know!)

Notice the following:
- All the genereated files are under _build. (Nice!)
- The "-fPIC" option IS passed to the compiler for f1.cpp and f2.cpp.
- The object file suffix is ".os" for f1.os and f2.os.
- The build works.
- The executable works.

I think this is a better fix than defining STATIC_AND_SHARED_OBJECTS_ARE_THE_SAME.
That prevents an important test from happening. This fix to cuppa passes the
corrent intention from cuppa to SCons; cuppa's BuildSharedLib method uses Scons'
SharedObject builder. It also means that if a user builds individual components
of a shared library manually using SCons' SharedObject builder that cuppa will
recognize them in the source list passed to BuildSharedLib. Without the fix,
the CompileMethod callable would not recognize such objects as SCons would give
them the SHOBJSUFFIX and cuppa would be testing against the OBJSUFFIX.

It is an entirely different discussion whether SCons should rely on the
SharedObjectEmitter and object attributes to determine if an object file is
relocatable or not. It could instead, and perhaps more reliably, use something
like the 'file' command on *nix operating systems, but then I suppose they
would have to track down the correct thing to do for all operating systems.

