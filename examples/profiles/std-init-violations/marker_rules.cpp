// -----------------------------------------------------------------------------
//   std::init rules: pointer_marker, union_marker, static_marker,
//                    uninit_with_initializer
// -----------------------------------------------------------------------------
//
//   [[uninit]] cannot be applied to pointers, unions, or static/thread storage.
//   It also cannot contradict a written or default initializer.
//
// -----------------------------------------------------------------------------

// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I

// C++ Standard Library Includes
#include <string>

// I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I I

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace marker_rules {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

void pointer_marker_violation()
{
    // Violation: [[uninit]] on a pointer (use nullptr initialization instead).
    int* pointer [[uninit]];
    (void)pointer;
}

union scalar_union {
    int i;
    float f;
};

void union_marker_violation()
{
    // Violation: [[uninit]] on a union object.
    scalar_union value [[uninit]];
    (void)value;
}

// Violation: static storage is zero-initialized; [[uninit]] is not allowed.
int static_storage [[uninit]];

void written_initializer_with_marker()
{
    // Violation: [[uninit]] combined with a written initializer.
    int value [[uninit]] = 4;
    (void)value;
}

void default_init_contradicts_marker()
{
    // Violation: default construction of std::string contradicts [[uninit]].
    std::string value [[uninit]];
    (void)value;
}

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
} // end namespace marker_rules
} // end namespace std_init_violations
} // end namespace profiles
