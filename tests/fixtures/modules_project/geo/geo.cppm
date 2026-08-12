export module geo;

export import :point;

export int origin_distance( point Point )
{
    return manhattan( Point );
}
