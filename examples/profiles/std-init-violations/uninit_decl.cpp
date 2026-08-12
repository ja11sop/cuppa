// -----------------------------------------------------------------------------
//   std::init rule: uninit_decl
// -----------------------------------------------------------------------------
//
//   Variables left (partially) uninitialized must be initialized or marked
//   [[uninit]]. Covers automatic scalars, aggregates, and unions.
//
// -----------------------------------------------------------------------------

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace uninit_decl {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

struct aggregate_s {
    int x;
};

union scalar_union {
    int i;
    float f;
};

void automatic_uninitialized()
{
    // Violation: automatic int with no initializer and no [[uninit]] marker.
    int Automatic;
    (void)Automatic;
}

void aggregate_member_uninitialized()
{
    // Violation: aggregate member 'x' has indeterminate value.
    aggregate_s Object;
    (void)Object;
}

void union_uninitialized()
{
    // Violation: union objects must be initialized (active member not set).
    scalar_union Object;
    (void)Object;
}

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace uninit_decl
} // end namespace std_init_violations
} // end namespace profiles
