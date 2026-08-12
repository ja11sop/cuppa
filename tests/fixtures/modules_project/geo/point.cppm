export module geo:point;

export struct point
{
    int x;
    int y;
};

export int manhattan( point Point )
{
    int Ax = Point.x < 0 ? -Point.x : Point.x;
    int Ay = Point.y < 0 ? -Point.y : Point.y;
    return Ax + Ay;
}
