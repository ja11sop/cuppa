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
    int storage [[uninit]];
    // Violation: unmarked pointer binds to uninitialized storage.
    int* pointer = &storage;
    (void)pointer;
}

void bind_marked_pointer_to_initialized()
{
    int initialized = 7;
    // Violation: [[ref_to_uninit]] pointer binds to initialized storage.
    int* pointer [[ref_to_uninit]] = &initialized;
    (void)pointer;
}

void call_with_unmarked_from_uninit()
{
    int storage [[uninit]];
    int* pointer [[ref_to_uninit]] = &storage;
    // Violation: passing marked pointer to unmarked parameter.
    take_initialized( pointer );
}

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace ref_to_uninit
} // end namespace std_init_violations
} // end namespace profiles
