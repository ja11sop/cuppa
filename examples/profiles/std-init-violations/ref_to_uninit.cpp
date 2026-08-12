// -----------------------------------------------------------------------------
//   std::init rule: ref_to_uninit
// -----------------------------------------------------------------------------
//
//   Pointer and reference bindings must be consistent with [[ref_to_uninit]]
//   marking: unmarked bindings to uninitialized storage are rejected, and marked
//   bindings to initialized storage are rejected.
//
// -----------------------------------------------------------------------------

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace ref_to_uninit {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

void take_initialized( int* Pointer )
{
    (void)Pointer;
}

void bind_unmarked_pointer_to_uninit()
{
    int Storage [[uninit]];
    // Violation: unmarked pointer binds to uninitialized storage.
    int* Pointer = &Storage;
    (void)Pointer;
}

void bind_marked_pointer_to_initialized()
{
    int Initialized = 7;
    // Violation: [[ref_to_uninit]] pointer binds to initialized storage.
    int* Pointer [[ref_to_uninit]] = &Initialized;
    (void)Pointer;
}

void call_with_unmarked_from_uninit()
{
    int Storage [[uninit]];
    int* Pointer [[ref_to_uninit]] = &Storage;
    // Violation: passing marked pointer to unmarked parameter.
    take_initialized( Pointer );
}

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace ref_to_uninit
} // end namespace std_init_violations
} // end namespace profiles
