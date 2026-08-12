// -----------------------------------------------------------------------------
//   std::init rule: static_runtime_init
// -----------------------------------------------------------------------------
//
//   Non-local variables with runtime initializers require constant initialization
//   unless another rule applies.
//
// -----------------------------------------------------------------------------

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {
namespace static_runtime_init {
// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n

int seed();

// Violation: runtime call in a non-local initializer.
int runtime_global = seed();

} // end namespace static_runtime_init
} // end namespace std_init_violations
} // end namespace profiles

int profiles::std_init_violations::static_runtime_init::seed()
{
    return 42;
}
