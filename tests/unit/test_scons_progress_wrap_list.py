#          Copyright Jamie Allsop 2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Keep MethodWithProgress wrap list aligned with public SCons builders."""

import pkgutil

import pytest
from SCons.Environment import Environment

import SCons.Tool as scons_tool
from cuppa.core.environment import EnvironmentMethods


pytestmark = pytest.mark.unit


# Methods / aliases that emit action nodes but are not always ``BUILDERS`` keys.
_ALWAYS_WRAP = frozenset( {
    'Command',
    'Install',
    'InstallAs',
    'InstallVersionedLib',
    'Jar',
    'Java',
} )

# Tool method aliases documented as builders in the SCons man page.
_TOOL_METHOD_ALIASES = {
    'docbook': (
        'DocbookEpub',
        'DocbookHtml',
        'DocbookHtmlChunked',
        'DocbookHtmlhelp',
        'DocbookMan',
        'DocbookPdf',
        'DocbookSlidesHtml',
        'DocbookSlidesPdf',
        'DocbookXInclude',
        'DocbookXslt',
    ),
    'gettext_tool': (
        'POInit',
        'POTUpdate',
        'POUpdate',
        'Translate',
    ),
}


def _public_builders_across_tools():
    names = set()
    for module in pkgutil.iter_modules( scons_tool.__path__ ):
        try:
            env = Environment( tools=[ module.name ] )
        except Exception:
            continue
        names |= set( env[ 'BUILDERS' ].keys() )
    return { name for name in names if not name.startswith( '_' ) }


def test_progress_wrap_list_covers_public_scons_builders():
    wrap = set( EnvironmentMethods._scons_methods_and_builders )
    missing = _public_builders_across_tools() - wrap
    assert not missing, (
        "Add these public SCons builders to "
        "EnvironmentMethods._scons_methods_and_builders: {!r}".format(
            sorted( missing )
        )
    )


def test_progress_wrap_list_includes_install_and_command_aliases():
    wrap = set( EnvironmentMethods._scons_methods_and_builders )
    assert _ALWAYS_WRAP <= wrap


def test_progress_wrap_list_includes_tool_method_aliases():
    wrap = set( EnvironmentMethods._scons_methods_and_builders )
    for tool, aliases in _TOOL_METHOD_ALIASES.items():
        try:
            env = Environment( tools=[ tool ] )
        except Exception as exc:
            pytest.skip( "SCons tool {!r} unavailable: {}".format( tool, exc ) )
        present = [ name for name in aliases if hasattr( env, name ) ]
        assert present, "expected aliases on tool {!r}".format( tool )
        missing = set( present ) - wrap
        assert not missing, (
            "Add these {!r} method aliases to the wrap list: {!r}".format(
                tool, sorted( missing )
            )
        )


def test_progress_wrap_list_is_sorted_and_unique():
    names = EnvironmentMethods._scons_methods_and_builders
    assert names == sorted( names )
    assert len( names ) == len( set( names ) )
