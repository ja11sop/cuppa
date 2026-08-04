
#          Copyright Declan Traynor 2012
#          Copyright Jamie Allsop 2012-2022
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Colouriser
#-------------------------------------------------------------------------------

import os
import re


# Reduced intensity moves text towards the background, which only works when the background is
# the darker end. On a light console the default foreground is already black and dimming it can
# leave it looking untouched, so a grey foreground is used there instead.
GREY_256 = "\x1b[38;5;244m"
BRIGHT_BLACK = "\x1b[90m"

# The convention COLORFGBG reports: the last field is the background colour index, and 7 or 15
# means a light background. Anything else is treated as dark, which is the safe assumption.
LIGHT_BACKGROUNDS = ( 7, 15 )


def console_background():
    """`light`, `dark`, or `unknown` where the terminal does not say.

    `CUPPA_CONSOLE_BACKGROUND` settles it for terminals that report nothing, which is most of
    them; `COLORFGBG` is used where a terminal does set it.
    """
    declared = os.environ.get( 'CUPPA_CONSOLE_BACKGROUND', '' ).strip().lower()
    if declared in ( 'light', 'dark' ):
        return declared

    fields = os.environ.get( 'COLORFGBG', '' ).split( ';' )
    background = fields[-1].strip()
    if background.isdigit():
        return int( background ) in LIGHT_BACKGROUNDS and 'light' or 'dark'

    return 'unknown'


def supports_256_colours():
    term = os.environ.get( 'TERM', '' )
    return '256color' in term or bool( os.environ.get( 'COLORTERM', '' ) )


try:
    import colorama
    colorama_available = True
except ImportError:
    print( 'Output Colourisation disabled. To enabled, install colorama')
    colorama_available = False


class Colouriser(object):

    @classmethod
    def create( cls ):
        if colorama_available:
            colorama.init( strip=False )
        return cls()


    def __init__( self ):
        self.use_colour = False


    def enable( self ):
        self.use_colour = True


    def colour( self, meaning, text ):
        if not self.use_colour:
            return text
        else:
            return self.start_colour( meaning ) + text + colorama.Style.RESET_ALL


    def emphasise( self, text ):
        if not self.use_colour:
            return text
        else:
            return colorama.Style.BRIGHT + text + colorama.Style.RESET_ALL


    def subdue( self, text ):
        """Text that recedes: reduced intensity on a dark console, grey on a light one.

        Both move the text towards the background rather than towards a colour, so the meaning
        survives either console, and a terminal that ignores the sequence shows ordinary text.
        """
        if not self.use_colour:
            return text
        return self.start_subdued() + text + colorama.Style.RESET_ALL


    def start_subdued( self ):
        if not self.use_colour:
            return ''
        if console_background() == 'light':
            return supports_256_colours() and GREY_256 or BRIGHT_BLACK
        return colorama.Style.DIM


    def emphasise_time_by_group( self, time_text ):
        if not self.use_colour:
            return time_text
        else:
            time_elements = re.findall( r'[0-9]+[:.,]?', time_text )
            time_found = False
            emphasised = self.start_colour('time')
            empty = re.compile( r'00[:.]|000[,]?' )
            for element in time_elements:
                if not time_found and not empty.match( element ):
                    time_found = True
                    emphasised += self.start_highlight('time')
                emphasised += element

            emphasised += colorama.Style.RESET_ALL

            return emphasised


    def emphasise_time_by_digit( self, time_text, start_colour=None, start_highlight=None, end_highlight=None ):
        if not self.use_colour:
            return time_text
        else:
            if not start_colour:
                start_colour = self.start_colour('time')
            if not start_highlight:
                start_highlight = self.start_highlight('time')
            if not end_highlight:
                end_highlight = colorama.Style.RESET_ALL
            time_found = False
            emphasised = start_colour
            for char in time_text:
                if not time_found and char.isdigit() and int(char) > 0:
                    time_found = True
                    emphasised += start_highlight
                emphasised += char

            emphasised += end_highlight

            return emphasised


    def highlight( self, meaning, text ):
        if not self.use_colour:
            return text
        else:
            return self.start_highlight( meaning ) + text + colorama.Style.RESET_ALL


    def start_colour( self, meaning ):
        if self.use_colour:
            return self._start_colour( meaning )
        return ''


    def start_highlight( self, meaning ):
        if self.use_colour:
            return self._start_highlight( meaning )
        return ''


    def reset( self ):
        if self.use_colour:
            return self._reset()
        return ''


    def _reset( self ):
        return colorama.Style.RESET_ALL


    ## Make these functions into simple dictionary lookups

    def _start_colour( self, meaning ):
        if meaning == 'error':
            return colorama.Fore.RED
        elif meaning == 'remove_error':
            return colorama.Fore.RED
        elif meaning == 'warning':
            return colorama.Fore.MAGENTA
        elif meaning == 'remove_notice':
            return colorama.Fore.MAGENTA
        elif meaning == 'summary':
            return colorama.Fore.BLACK
        elif meaning == 'passed':
            return colorama.Fore.GREEN
        elif meaning == 'success':
            return colorama.Fore.GREEN
        elif meaning == 'unexpected_success':
            return colorama.Fore.GREEN
        elif meaning == 'expected_failure':
            return colorama.Fore.YELLOW
        elif meaning == 'failure':
            return colorama.Fore.RED
        elif meaning == 'failed':
            return colorama.Fore.RED
        elif meaning == 'aborted':
            return colorama.Fore.RED
        elif meaning == 'skipped':
            return colorama.Fore.BLACK
        elif meaning == 'notice':
            return colorama.Fore.YELLOW
        elif meaning == 'time':
            return colorama.Fore.BLUE
        elif meaning == 'info':
            return colorama.Fore.BLUE
        elif meaning == 'message':
            return ''

    def _start_highlight( self, meaning ):
        if meaning == 'error':
            return colorama.Style.BRIGHT + colorama.Back.RED + colorama.Fore.WHITE
        elif meaning == 'remove_error':
            return colorama.Style.BRIGHT + colorama.Back.RED + colorama.Fore.WHITE
        elif meaning == 'warning':
            return colorama.Style.BRIGHT + colorama.Back.MAGENTA + colorama.Fore.WHITE
        elif meaning == 'remove_notice':
            return colorama.Style.BRIGHT + colorama.Back.MAGENTA + colorama.Fore.WHITE
        elif meaning == 'summary':
            return colorama.Style.BRIGHT + colorama.Back.BLACK + colorama.Fore.WHITE
        elif meaning == 'success':
            return colorama.Style.BRIGHT + colorama.Back.GREEN + colorama.Fore.WHITE
        elif meaning == 'unexpected_success':
            return colorama.Style.BRIGHT + colorama.Back.GREEN + colorama.Fore.BLACK
        elif meaning == 'passed':
            return colorama.Style.BRIGHT + colorama.Back.GREEN + colorama.Fore.WHITE
        elif meaning == 'expected_failure':
            return colorama.Style.BRIGHT + colorama.Back.YELLOW + colorama.Fore.WHITE
        elif meaning == 'failure':
            return colorama.Style.BRIGHT + colorama.Back.RED + colorama.Fore.WHITE
        elif meaning == 'failed':
            return colorama.Style.BRIGHT + colorama.Back.RED + colorama.Fore.WHITE
        elif meaning == 'aborted':
            return colorama.Style.BRIGHT + colorama.Back.RED + colorama.Fore.BLACK
        elif meaning == 'skipped':
            return colorama.Style.BRIGHT + colorama.Back.BLACK + colorama.Fore.WHITE
        elif meaning == 'notice':
            return colorama.Style.BRIGHT + colorama.Back.YELLOW + colorama.Fore.WHITE
        elif meaning == 'time':
            return colorama.Style.BRIGHT + colorama.Back.BLUE + colorama.Fore.WHITE
        elif meaning == 'info':
            return colorama.Style.BRIGHT + colorama.Back.BLUE + colorama.Fore.WHITE
        elif meaning == 'message':
            return ''


colouriser = Colouriser.create()


def as_colour( meaning, text ):
    return colouriser.colour( meaning, text )

def as_highlighted( meaning, text ):
    return colouriser.highlight( meaning, text )

def as_emphasised( text ):
    return colouriser.emphasise( text )

def as_subdued( text ):
    return colouriser.subdue( text )

def start_subdued():
    return colouriser.start_subdued()

def as_error( text ):
    return colouriser.colour( 'error', text )

def as_error_label( text ):
    return colouriser.highlight( 'error', text )

def as_remove_error( text ):
    """Removal attempt failed (permissions, missing path, and similar)."""
    return colouriser.colour( 'remove_error', text )

def as_remove_error_label( text ):
    return colouriser.highlight( 'remove_error', text )

def as_warning( text ):
    return colouriser.colour( 'warning', text )

def as_warning_label( text ):
    return colouriser.highlight( 'warning', text )

def as_remove_notice( text ):
    """Planned or successful removal highlight (warn / purple family)."""
    return colouriser.colour( 'remove_notice', text )

def as_remove_notice_label( text ):
    return colouriser.highlight( 'remove_notice', text )

def as_info( text ):
    return colouriser.colour( 'info', text )

def as_info_label( text ):
    return colouriser.highlight( 'info', text )

def as_message( text ):
    return colouriser.colour( 'message', text )

def as_notice( text ):
    return colouriser.colour( 'notice', text )

def start_colour( meaning ):
    return colouriser.start_colour( meaning )

def start_highlight( meaning ):
    return colouriser.start_highlight( meaning )

def colour_reset():
    return colouriser.reset()

def emphasise_time_by_group( time_text ):
    return colouriser.emphasise_time_by_group( time_text )

def emphasise_time_by_digit( time_text, start_colour=None, start_highlight=None, end_highlight=None ):
    return colouriser.emphasise_time_by_digit( time_text, start_colour, start_highlight, end_highlight )

def colour_items( items, colour_func=as_notice ):
    if isinstance( items, list ):
        return "'{}'".format( "', '".join( colour_func( item ) for item in items ) )
    elif isinstance( items, dict ):
        elements = []
        for k,v in list( items.items() ):
            elements.append( "'{}':'{}'".format( colour_func(str(k)), colour_func(str(v)) ) )
        return "', '".join( elements )

def is_error( meaning ):
    return meaning in ['error', 'failed', 'failure', 'aborted', 'remove_error']

