// Deliberate std::init profile violations for capture and classifier golden tests.
// Build with a Profiles-capable Clang archive, --cxx-profiles-enforce=std::init, and
// --cxx-disable-error-limit. See README.md in this directory.

namespace uninit_decl {
int uninit_global;
}

namespace static_runtime_init {
const int runtime_value = [] { return 42; }();
}

struct CtorUninitMember {
    int value_;
    CtorUninitMember() {}
};

struct Base {
    int base_value_;
};

struct CtorUninitBase : Base {
    CtorUninitBase() {}
};

namespace ref_to_uninit {
void take_pointer( int* pointer ) {
    (void)pointer;
}

void emit_ref() {
    int local;
    take_pointer( &local );
}
}

int main() {
    (void)uninit_decl::uninit_global;
    (void)static_runtime_init::runtime_value;
    CtorUninitMember member;
    (void)member;
    CtorUninitBase derived;
    (void)derived;
    ref_to_uninit::emit_ref();
    return 0;
}
