// -----------------------------------------------------------------------------
//   std::init violation fixture — link anchor
// -----------------------------------------------------------------------------
//
//   Calls each deliberate violation so every translation unit is linked into the
//   example binary. The build is expected to fail during compilation.
//
// -----------------------------------------------------------------------------

// n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n n
namespace profiles {
namespace std_init_violations {

namespace uninit_decl {
void automatic_uninitialized();
void aggregate_member_uninitialized();
void union_uninitialized();
}

namespace static_runtime_init {
extern int runtime_global;
}

namespace ctor_uninit_member {
struct with_member;
struct with_base;
}

namespace ref_to_uninit {
void bind_unmarked_pointer_to_uninit();
void bind_marked_pointer_to_initialized();
void call_with_unmarked_from_uninit();
}

namespace uninit_read {
void read_uninit_local();
void read_uninit_member();
int read_through_ref( int* Pointer );
}

namespace uninit_write {
void write_member_of_uninit_object();
void write_member_through_ref_at_call_site();
}

namespace marker_rules {
void pointer_marker_violation();
void union_marker_violation();
extern int static_storage;
void written_initializer_with_marker();
void default_init_contradicts_marker();
}

namespace destroy_rules {
void destroy_through_ref_never_stored();
void destroy_after_uncredited_fill();
void destroy_twice();
}

} // end namespace std_init_violations
} // end namespace profiles

int main()
{
    using namespace profiles::std_init_violations;

    uninit_decl::automatic_uninitialized();
    uninit_decl::aggregate_member_uninitialized();
    uninit_decl::union_uninitialized();
    (void)static_runtime_init::runtime_global;

    ctor_uninit_member::with_member member;
    (void)member;
    ctor_uninit_member::with_base derived;
    (void)derived;

    ref_to_uninit::bind_unmarked_pointer_to_uninit();
    ref_to_uninit::bind_marked_pointer_to_initialized();
    ref_to_uninit::call_with_unmarked_from_uninit();

    uninit_read::read_uninit_local();
    uninit_read::read_uninit_member();

    uninit_write::write_member_of_uninit_object();
    uninit_write::write_member_through_ref_at_call_site();

    marker_rules::pointer_marker_violation();
    marker_rules::union_marker_violation();
    (void)marker_rules::static_storage;
    marker_rules::written_initializer_with_marker();
    marker_rules::default_init_contradicts_marker();

    destroy_rules::destroy_through_ref_never_stored();
    destroy_rules::destroy_after_uncredited_fill();
    destroy_rules::destroy_twice();

    return 0;
}
