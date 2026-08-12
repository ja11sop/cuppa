export module secrets;

export int public_answer();

module :private;

static int Hidden = 7;

int public_answer()
{
    return Hidden;
}
