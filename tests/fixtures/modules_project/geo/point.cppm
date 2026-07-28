export module geo:point;

export struct Point
{
    int x;
    int y;
};

export int manhattan( Point p )
{
    int ax = p.x < 0 ? -p.x : p.x;
    int ay = p.y < 0 ? -p.y : p.y;
    return ax + ay;
}
