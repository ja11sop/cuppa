#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Semantic HTML backend for :mod:`cuppa.colourise`.

The backend returns opaque placeholders while report formatters assemble their
ordinary strings. Rendering resolves those placeholders after escaping all
literal text, so nested calls such as ``as_emphasised( as_info( value ) )``
retain both meanings without trusting report data as HTML.
"""

import html
import re


_TOKEN = re.compile( r'\x00cuppa-html-(\d+)\x00' )


class HtmlColouriser(object):
    """Collect semantic operations and render an escaped HTML fragment."""

    def __init__( self ):
        self._operations = []

    def enable( self ):
        """Match the ANSI backend API; semantic output is always enabled."""

    def _token( self, operation, classes=None, text=None ):
        index = len( self._operations )
        self._operations.append( ( operation, classes, text ) )
        return '\x00cuppa-html-{}\x00'.format( index )

    @staticmethod
    def _meaning_class( meaning ):
        return 'cuppa-' + str( meaning ).replace( '_', '-' )

    def colour( self, meaning, text ):
        if meaning == 'message':
            return text
        return (
            self._token( 'start', ( self._meaning_class( meaning ), ) )
            + text
            + self._token( 'reset' )
        )

    def highlight( self, meaning, text ):
        return (
            self._token(
                    'start',
                    ( self._meaning_class( meaning ), 'cuppa-label' ),
            )
            + text
            + self._token( 'reset' )
        )

    def emphasise( self, text ):
        return (
            self._token( 'start', ( 'cuppa-emphasised', ) )
            + text
            + self._token( 'reset' )
        )

    def subdue( self, text ):
        return (
            self._token( 'start', ( 'cuppa-subdued', ) )
            + text
            + self._token( 'reset' )
        )

    def start_subdued( self ):
        return self._token( 'start', ( 'cuppa-subdued', ) )

    def start_colour( self, meaning ):
        if meaning == 'message':
            return ''
        return self._token( 'start', ( self._meaning_class( meaning ), ) )

    def start_highlight( self, meaning ):
        return self._token(
                'start',
                ( self._meaning_class( meaning ), 'cuppa-label' ),
        )

    def reset( self ):
        return self._token( 'reset' )

    def emphasise_time_by_group( self, time_text ):
        elements = re.findall( r'[0-9]+[:.,]?', time_text )
        empty = re.compile( r'00[:.]|000[,]?' )
        parts = []
        found = False
        for element in elements:
            if not found and not empty.match( element ):
                found = True
            classes = [ 'cuppa-time' ]
            if found:
                classes.append( 'cuppa-label' )
            parts.append(
                    self._token( 'start', tuple( classes ) )
                    + element
                    + self._token( 'reset' )
            )
        return ''.join( parts )

    def emphasise_time_by_digit(
            self,
            time_text,
            start_colour=None,
            start_highlight=None,
            end_highlight=None,
    ):
        start_colour = start_colour or self.start_colour( 'time' )
        start_highlight = start_highlight or self.start_highlight( 'time' )
        end_highlight = end_highlight or self.reset()
        found = False
        parts = [ start_colour ]
        for character in time_text:
            if not found and character.isdigit() and int( character ) > 0:
                found = True
                parts.append( start_highlight )
            parts.append( character )
        parts.append( end_highlight )
        return ''.join( parts )

    def render( self, text, wrap=True ):
        """Escape ``text`` and replace collected operations with semantic spans."""
        rendered = self._render_text( str( text ) )
        if not wrap:
            return rendered
        return '<pre class="cuppa-output"><code>{}</code></pre>\n'.format( rendered )

    def replace( self, old, new ):
        """Rewrite display text held inside semantic operations."""
        rewritten = []
        for operation, classes, value in self._operations:
            if value is not None:
                value = str( value ).replace( old, new )
            rewritten.append( ( operation, classes, value ) )
        self._operations = rewritten

    def _render_text( self, text ):
        output = []
        open_spans = 0
        position = 0
        for match in _TOKEN.finditer( text ):
            output.append( html.escape( text[position:match.start()] ) )
            index = int( match.group( 1 ) )
            if index >= len( self._operations ):
                output.append( html.escape( match.group( 0 ) ) )
                position = match.end()
                continue
            operation, classes, value = self._operations[index]
            if operation == 'wrap':
                inner = self._render_text( str( value ) )
                if classes:
                    output.append(
                            '<span class="{}">{}</span>'.format(
                                ' '.join( classes ),
                                inner,
                            )
                    )
                else:
                    output.append( inner )
            elif operation == 'start':
                output.append( '<span class="{}">'.format( ' '.join( classes ) ) )
                open_spans += 1
            elif operation == 'reset':
                output.append( '</span>' * open_spans )
                open_spans = 0
            position = match.end()
        output.append( html.escape( text[position:] ) )
        if open_spans:
            output.append( '</span>' * open_spans )
        return ''.join( output )
