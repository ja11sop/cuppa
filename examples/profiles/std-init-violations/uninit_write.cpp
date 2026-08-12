// -----------------------------------------------------------------------------
//   std::init rule: uninit_write
// -----------------------------------------------------------------------------
//
//   Writing a proper subobject of [[uninit]] storage (or through
//   [[ref_to_uninit]]) does not initialize the whole object.
//
// -----------------------------------------------------------------------------

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace uninit_write {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

struct point {
    int x;
    int y;
};

void write_member_through_ref( point* Pointer [[ref_to_uninit]] )
{
    // Violation when Pointer refers to [[uninit]] storage (see call site below).
    Pointer->x = 1;
}

void write_member_of_uninit_object()
{
    point object [[uninit]];
    // Violation: member assignment does not initialize the whole struct.
    object.x = 1;
}

void write_member_through_ref_at_call_site()
{
    point object [[uninit]];
    point* pointer [[ref_to_uninit]] = &object;
    write_member_through_ref( pointer );
}

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace uninit_write
} // end namespace std_init_violations
} // end namespace profiles
