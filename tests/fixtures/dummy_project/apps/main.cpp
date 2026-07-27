#include <cstdlib>
#include "dummy/hello.hpp"

int main()
{
    return dummy_answer() == 42 ? EXIT_SUCCESS : EXIT_FAILURE;
}
