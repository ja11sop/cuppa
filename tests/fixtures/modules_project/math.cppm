export module math;

// MSVC: module symbols used from a DLL need an explicit export so the linker
// produces an import library (.lib). Harmless for static libs / executables.
#ifdef _MSC_VER
#define MATH_API __declspec(dllexport)
#else
#define MATH_API
#endif

export MATH_API int add( int a, int b )
{
    return a + b;
}
