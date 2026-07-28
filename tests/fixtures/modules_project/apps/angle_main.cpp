import <span>;

int main()
{
    int values[3]{ 1, 2, 3 };
    std::span<int> view( values );
    return view.size() == 3 ? 0 : 1;
}
