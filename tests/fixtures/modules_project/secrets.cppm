export module secrets;

export int public_answer();

module :private;

static int hidden = 7;

int public_answer()
{
    return hidden;
}
