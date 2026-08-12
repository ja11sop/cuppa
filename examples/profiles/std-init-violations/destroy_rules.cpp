// -----------------------------------------------------------------------------
//   std::init rules: destroy_uninit, double_destroy
// -----------------------------------------------------------------------------
//
//   [[now_uninit]] functions end object lifetimes. Destroying affirmatively
//   uninitialized storage, or destroying the same storage twice, is rejected.
//
//   Note: Alliance Clang profiles_2026_08_07_27 may still report ref_to_uninit
//   at these call sites until destroy analysis is complete in that snapshot.
//
// -----------------------------------------------------------------------------

// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I

// C++ Standard Library Includes
// None

// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace destroy_rules {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

template<typename T>
[[now_uninit]]
void destroy_at( T* Pointer )
{
    (void)Pointer;
}

void fill( int* Pointer [[ref_to_uninit]] )
{
    (void)Pointer;
}

void destroy_through_ref_never_stored()
{
    int Storage [[uninit]];
    int* Pointer [[ref_to_uninit]] = &Storage;
    // Expected (documented): destroy_uninit — destroy without prior store through marker.
    destroy_at( Pointer );
}

void destroy_after_uncredited_fill()
{
    int Storage [[uninit]];
    fill( &Storage );
    // Expected (documented): destroy_uninit — ordinary [[ref_to_uninit]] callee earns no credit.
    destroy_at( &Storage );
}

void destroy_twice()
{
    int Storage = 5;
    destroy_at( &Storage );
    // Expected (documented): double_destroy — second [[now_uninit]] on same storage.
    destroy_at( &Storage );
}

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace destroy_rules
} // end namespace std_init_violations
} // end namespace profiles
