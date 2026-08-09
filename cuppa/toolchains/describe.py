#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Toolchain describe — dialects and default invocations for --list-toolchains
#-------------------------------------------------------------------------------

"""Build a stable ``describe()`` payload from toolchain instances.

Default dialect tokens, usable-feature shorthand, and stdlib choices come from
the toolchain classes (``default_dialect()``, ``usable_features()``,
``Clang.stdlib_choices()``, ``Cl.available_dialects()``). This module owns the
GNU alias catalog for “available dialects”, usable-feature formatting helpers,
and joining ``self.values`` flag lists into invocation templates.
"""

from __future__ import annotations

# Newest generation first. Within a generation Cuppa lists the working-draft
# token first (e.g. ``c++2c`` before ``c++26``): that is what Cuppa passes by
# default so builds can pick up post-freeze draft features, not only the frozen
# ISO dialect. Then the ISO alias. Sourced from GCC C-Dialect-Options and Clang
# ``-std=`` lists. No ``c++latest`` on GNU-style drivers.
#
# Default token selection lives on Gcc/Clang.default_dialect() — keep those
# tokens present in some generation below so expand-from-default stays correct.
_GNU_DIALECT_GENERATIONS = (
    ( 'c++2c', 'c++26' ),
    ( 'c++2b', 'c++23' ),
    ( 'c++2a', 'c++20' ),
    ( 'c++1z', 'c++17' ),
    ( 'c++1y', 'c++14' ),
    ( 'c++11', 'c++0x' ),
    ( 'c++03', ),
    ( 'c++98', ),
)

_GCC_VARIANT_KEYS = {
    'dbg': ( 'debug_cxx_flags', 'debug_c_flags', 'debug_link_cxx_flags' ),
    'rel': ( 'release_cxx_flags', 'release_c_flags', 'release_link_cxx_flags' ),
    'cov': ( 'coverage_cxx_flags', 'coverage_c_flags', 'coverage_link_cxx_flags' ),
}

_CLANG_VARIANT_KEYS = {
    'dbg': ( 'debug_cxx_flags', 'debug_c_flags', 'debug_link_cxx_flags' ),
    'rel': ( 'release_cxx_flags', 'release_c_flags', 'release_link_cxx_flags' ),
    'cov': ( 'coverage_cxx_flags', None, 'coverage_link_flags' ),
}

_MSVC_VARIANT_KEYS = {
    'dbg': ( 'dbg_cxx_flags', None, 'dbg_link_flags' ),
    'rel': ( 'rel_cxx_flags', None, 'rel_link_flags' ),
}

_COMPILE_PLACEHOLDER = '<sources>'
_STATIC_LIBS = '<static_libs>'
_DYNAMIC_LIBS = '<dynamic_libs>'
_OBJECTS = '<objects>'


def join_flag_tokens( tokens ):
    """Join flag tokens into one display string (split embedded spaces)."""
    parts = []
    for token in tokens or []:
        if token is None:
            continue
        text = str( token )
        if not text:
            continue
        if text.startswith( '<' ) and text.endswith( '>' ):
            parts.append( text )
        elif ' ' in text:
            parts.extend( piece for piece in text.split() if piece )
        else:
            parts.append( text )
    return ' '.join( parts )


def dialect_display_items( dialects, default_dialect ):
    """Plain items newest-first; Cuppa default marked with `` (default)``."""
    items = []
    for dialect in dialects or []:
        if dialect == default_dialect:
            items.append( '{} (default)'.format( dialect ) )
        else:
            items.append( dialect )
    return items


def format_dialects_line( dialects, default_dialect ):
    """Plain ``c++2c (default), c++26, …`` (for tests / uncoloured display)."""
    return ', '.join( dialect_display_items( dialects, default_dialect ) )


def stdlib_display_items( choices, default_stdlib ):
    """Ordered stdlib names with default first when known."""
    if not choices:
        return []
    ordered = []
    if default_stdlib and default_stdlib in choices:
        ordered.append( default_stdlib )
    for choice in choices:
        if choice not in ordered:
            ordered.append( choice )
    return dialect_display_items( ordered, default_stdlib )


def format_stdlib_line( choices, default_stdlib ):
    """Plain ``libstdc++ (default), libc++``."""
    return ', '.join( stdlib_display_items( choices, default_stdlib ) )


def format_usable_feature_items(
        dialect, gated=(), experimental=(), dialect_inclusive=True,
):
    """Build ``usable features:`` display items.

    * Older toolchains where features are only behind ``-f*`` gates and not yet
      part of the default dialect list those names directly
      (e.g. ``concepts``).
    * Newer toolchains use dialect-inclusive shorthand
      (``all c++2c``, ``all c++2a, coroutines``).
    * Opt-in experimental support is tagged
      (``all c++2c, modules (experimental)``).
    """
    extras = [ name for name in list( gated ) + list( experimental ) if name ]
    if not dialect_inclusive:
        return extras
    items = []
    if dialect:
        items.append( 'all {}'.format( dialect ) )
    items.extend( extras )
    return items


def format_usable_features_line(
        dialect, gated=(), experimental=(), dialect_inclusive=True,
):
    """Plain usable-features summary for tests / uncoloured display."""
    return ', '.join( format_usable_feature_items(
            dialect, gated=gated, experimental=experimental,
            dialect_inclusive=dialect_inclusive,
    ) )


def _dialects_from_default( generations, default_token ):
    """Flatten generations from the one containing ``default_token`` downward."""
    if not default_token:
        return []
    start = None
    for index, generation in enumerate( generations ):
        if default_token in generation:
            start = index
            break
    if start is None:
        return [ default_token ]
    result = []
    for generation in generations[start:]:
        if default_token in generation:
            ordered = [ default_token ] + [
                    token for token in generation if token != default_token
            ]
            result.extend( ordered )
        else:
            result.extend( generation )
    return result


def _compile_tokens( flags ):
    tokens = list( flags or [] )
    tokens.append( _COMPILE_PLACEHOLDER )
    return tokens


def _default_lib_flags( libraries ):
    """Turn Cuppa default library names into normal ``-l`` tokens for display."""
    flags = []
    for name in libraries or []:
        if not name:
            continue
        text = str( name )
        if text.startswith( '-l' ):
            flags.append( text )
        else:
            flags.append( '-l{}'.format( text ) )
    return flags


def _link_tokens( link_flags, values, with_lib_placeholders=False ):
    tokens = [ _OBJECTS ]
    tokens.extend( link_flags or [] )
    if with_lib_placeholders:
        static_link = values.get( 'static_link' ) or '-Xlinker -Bstatic'
        dynamic_link = values.get( 'dynamic_link' ) or '-Xlinker -Bdynamic'
        # Show Cuppa's default STATICLIBS / DYNAMICLIBS before the open slots so
        # readers see pthread/rt (and Clang libc++ extras) without hiding that
        # more libraries can still be injected at the placeholders.
        tokens.extend( [ static_link ] )
        tokens.extend( _default_lib_flags( values.get( 'static_libraries' ) ) )
        tokens.append( _STATIC_LIBS )
        tokens.extend( [ dynamic_link ] )
        tokens.extend( _default_lib_flags( values.get( 'dynamic_libraries' ) ) )
        tokens.append( _DYNAMIC_LIBS )
    return tokens


def _variant_block(
        values, cxx_key, c_key, link_key,
        coverage_base_key=None, with_lib_placeholders=False,
):
    block = {}
    cxx_flags = list( values.get( cxx_key ) or [] )
    if coverage_base_key:
        base = list( values.get( coverage_base_key ) or [] )
        cxx_flags = base + [ flag for flag in cxx_flags if flag not in base ]
    if cxx_flags:
        block['c++'] = join_flag_tokens( _compile_tokens( cxx_flags ) )
    if c_key:
        c_flags = list( values.get( c_key ) or [] )
        if coverage_base_key and not c_flags:
            c_flags = list( values.get( coverage_base_key ) or [] )
        if c_flags:
            block['c'] = join_flag_tokens( _compile_tokens( c_flags ) )
    link_flags = values.get( link_key )
    if link_flags is not None:
        block['link'] = join_flag_tokens( _link_tokens(
                link_flags, values, with_lib_placeholders=with_lib_placeholders
        ) )
    return block


def _variants_from_keys(
        values, key_map, supports_coverage,
        clang_cov=False, with_lib_placeholders=False,
):
    variants = {}
    for variant, keys in key_map.items():
        if variant == 'cov' and not supports_coverage:
            continue
        cxx_key, c_key, link_key = keys
        coverage_base = 'coverage_flags' if ( clang_cov and variant == 'cov' ) else None
        block = _variant_block(
                values, cxx_key, c_key, link_key,
                coverage_base_key=coverage_base,
                with_lib_placeholders=with_lib_placeholders,
        )
        if block:
            variants[variant] = block
    return variants


def _linux_lib_placeholders():
    try:
        import cuppa.build_platform
        return cuppa.build_platform.name() == 'Linux'
    except Exception:
        return False


def _toolchain_default_dialect( toolchain ):
    """Prefer instance ``default_dialect()``; never re-derive version tables here."""
    default_dialect = getattr( toolchain, 'default_dialect', None )
    if callable( default_dialect ):
        return default_dialect()
    return None


def _toolchain_usable_features( toolchain ):
    """Prefer instance ``usable_features()``; returns a list of display items."""
    usable = getattr( toolchain, 'usable_features', None )
    if callable( usable ):
        items = usable()
        if items:
            return list( items )
    return []


def _with_usable_features( payload, toolchain ):
    items = _toolchain_usable_features( toolchain )
    if items:
        payload['usable_features'] = items
    return payload


def describe_toolchain( toolchain ):
    """Return a describe dict for ``toolchain``, or ``None`` if unsupported."""
    try:
        family = toolchain.family()
    except Exception:
        family = None
    if not family:
        return None
    values = getattr( toolchain, 'values', None )
    if not isinstance( values, dict ):
        return None

    family = str( family ).lower()
    supports_coverage = False
    try:
        supports_coverage = bool( toolchain.supports_coverage() )
    except Exception:
        supports_coverage = False

    if family == 'gcc':
        default_dialect = _toolchain_default_dialect( toolchain )
        dialects = _dialects_from_default( _GNU_DIALECT_GENERATIONS, default_dialect )
        variants = _variants_from_keys(
                values, _GCC_VARIANT_KEYS, supports_coverage, clang_cov=False,
                with_lib_placeholders=_linux_lib_placeholders(),
        )
        return _with_usable_features( {
            'dialects': dialects,
            'default_dialect': default_dialect,
            'variants': variants,
        }, toolchain )

    if family == 'clang':
        default_dialect = _toolchain_default_dialect( toolchain )
        dialects = _dialects_from_default( _GNU_DIALECT_GENERATIONS, default_dialect )
        variants = _variants_from_keys(
                values, _CLANG_VARIANT_KEYS, supports_coverage, clang_cov=True,
                with_lib_placeholders=_linux_lib_placeholders(),
        )
        payload = {
            'dialects': dialects,
            'default_dialect': default_dialect,
            'variants': variants,
        }
        choices_fn = getattr( type( toolchain ), 'stdlib_choices', None )
        if callable( choices_fn ):
            choices = list( choices_fn() )
        else:
            choices = list( getattr( type( toolchain ), '_stdlib_choices', () ) )
        if not choices:
            choices = [ 'libstdc++', 'libc++' ]
        stdlib = getattr( toolchain, '_stdlib', None )
        if stdlib and stdlib not in choices:
            choices = [ stdlib ] + choices
        payload['stdlib_choices'] = choices
        payload['default_stdlib'] = stdlib or choices[0]
        return _with_usable_features( payload, toolchain )

    if family in ( 'vc', 'cl', 'msvc' ):
        default_dialect = _toolchain_default_dialect( toolchain )
        available_fn = getattr( type( toolchain ), 'available_dialects', None )
        if callable( available_fn ):
            dialects = list( available_fn() )
        else:
            dialects = list( getattr( type( toolchain ), '_available_dialects', () ) )
        if not dialects and default_dialect:
            dialects = [ default_dialect ]
        dialect_flag = getattr( type( toolchain ), '_default_dialect_flag', None )
        if not dialect_flag and default_dialect:
            dialect_flag = '-std:{}'.format( default_dialect )
        variants = _variants_from_keys(
                values, _MSVC_VARIANT_KEYS, supports_coverage=False, clang_cov=False
        )
        if dialect_flag:
            for block in variants.values():
                cxx = block.get( 'c++' ) or ''
                if '-std:' in cxx or '-std=' in cxx:
                    continue
                parts = cxx.split()
                if parts and parts[-1] == _COMPILE_PLACEHOLDER:
                    parts = parts[:-1] + [ dialect_flag, _COMPILE_PLACEHOLDER ]
                else:
                    parts = parts + [ dialect_flag, _COMPILE_PLACEHOLDER ]
                block['c++'] = ' '.join( parts )
        return _with_usable_features( {
            'dialects': dialects,
            'default_dialect': default_dialect,
            'variants': variants,
        }, toolchain )

    return None
