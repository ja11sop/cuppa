export module geo;

export import :point;

export int origin_distance( Point p )
{
    return manhattan( p );
}
