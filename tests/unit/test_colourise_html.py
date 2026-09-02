#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

import cuppa.colourise as colourise
from cuppa.colourise_html import HtmlColouriser


pytestmark = pytest.mark.unit


def test_html_colouriser_escapes_literal_text_and_semantic_values():
    backend = HtmlColouriser()
    with colourise.using_colouriser( backend ):
        text = 'plain <tag> {}'.format( colourise.as_info( 'A&B' ) )

    assert backend.render( text ) == (
        '<pre class="cuppa-output"><code>'
        'plain &lt;tag&gt; <span class="cuppa-info">A&amp;B</span>'
        '</code></pre>\n'
    )


def test_html_colouriser_preserves_nested_semantics():
    backend = HtmlColouriser()
    with colourise.using_colouriser( backend ):
        text = colourise.as_emphasised( colourise.as_info( '_build' ) )

    assert backend.render( text, wrap=False ) == (
        '<span class="cuppa-emphasised">'
        '<span class="cuppa-info">_build</span>'
        '</span>'
    )


def test_html_colouriser_renders_labels_and_subdued_text_as_docs_classes():
    backend = HtmlColouriser()
    with colourise.using_colouriser( backend ):
        text = '{} {}'.format(
                colourise.as_warning_label( 'Warning' ),
                colourise.as_subdued( 'not selected' ),
        )

    assert backend.render( text, wrap=False ) == (
        '<span class="cuppa-warning cuppa-label">Warning</span> '
        '<span class="cuppa-subdued">not selected</span>'
    )


def test_html_colouriser_supports_start_and_reset_helpers():
    backend = HtmlColouriser()
    with colourise.using_colouriser( backend ):
        text = '{}value{}'.format(
                colourise.start_colour( 'notice' ),
                colourise.colour_reset(),
        )

    assert backend.render( text, wrap=False ) == (
        '<span class="cuppa-notice">value</span>'
    )


def test_using_colouriser_restores_the_production_backend():
    original = colourise.colouriser
    with colourise.using_colouriser( HtmlColouriser() ):
        assert colourise.colouriser is not original
    assert colourise.colouriser is original
