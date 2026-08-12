// -----------------------------------------------------------------------------
//   std::init rule: ctor_uninit_member
// -----------------------------------------------------------------------------
//
//   User-provided constructors must initialize every member and non-virtual base
//   subobject (written initializer, default member initializer, or [[uninit]]).
//
// -----------------------------------------------------------------------------

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace ctor_uninit_member {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

struct with_member {
    int value_;
    // Violation: member 'value_' is not initialized in the member-initializer list.
    with_member() {}
};

struct base {
    int base_;
};

struct with_base : base {
    // Violation: direct base 'base' is not initialized.
    with_base() {}
};

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace ctor_uninit_member
} // end namespace std_init_violations
} // end namespace profiles
