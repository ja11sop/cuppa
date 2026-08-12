import <span>;

int main()
{
    int Values[3]{ 1, 2, 3 };
    std::span<int> View( Values );
    return View.size() == 3 ? 0 : 1;
}
