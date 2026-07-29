export module math;

// MSVC: DLL builds need __declspec(dllexport) so the linker emits an import
// library. Only enable when MATH_DLL_EXPORT is defined (shared-lib tests);
// always-on dllexport leaves .exp/.lib next to executables that --clean misses.
#if defined(_MSC_VER) && defined(MATH_DLL_EXPORT)
#define MATH_API __declspec(dllexport)
#else
#define MATH_API
#endif

export MATH_API int add( int a, int b )
{
    return a + b;
}
