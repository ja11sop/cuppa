// -----------------------------------------------------------------------------
//   std::init rule: uninit_read
// -----------------------------------------------------------------------------
//
//   Reads of uninitialized objects, including members and reads through
//   [[ref_to_uninit]] pointers, are rejected.
//
// -----------------------------------------------------------------------------

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace uninit_read {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

struct buf {
    int n [[uninit]];
};

void read_uninit_local()
{
    int Value [[uninit]];
    // Violation: read of [[uninit]] local before any initialization.
    int Copy = Value;
    (void)Copy;
}

void read_uninit_member()
{
    buf Object;
    // Violation: read of member marked [[uninit]] before assignment.
    int Copy = Object.n;
    (void)Copy;
}

int read_through_ref( int* Pointer [[ref_to_uninit]] )
{
    // Violation: dereference through [[ref_to_uninit]] is always checked.
    return *Pointer;
}

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace uninit_read
} // end namespace std_init_violations
} // end namespace profiles
