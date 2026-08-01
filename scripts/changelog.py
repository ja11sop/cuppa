"""Reading and updating `cuppa/VERSION` and `CHANGELOG.md`.

The release cycle these helpers assume:

- `cuppa/VERSION` holds `X.Y.Z.dev` while `X.Y.Z` is being assembled, and `X.Y.Z` once released.
- `CHANGELOG.md` has exactly one in-progress section, headed `## [X.Y.Z] - unreleased`, above the
  dated sections. Entries are written into it as the work happens.
- Releasing drops the `.dev`, dates the section, and closes its compare link.

`problems()` is the single description of what "consistent" means; the unit test and the CI gates
both use it so they cannot disagree.
"""

import datetime
import os
import re

from packaging.version import InvalidVersion, Version


ROOT = os.path.dirname( os.path.dirname( os.path.abspath( __file__ ) ) )
VERSION_FILE = os.path.join( ROOT, 'cuppa', 'VERSION' )
CHANGELOG_FILE = os.path.join( ROOT, 'CHANGELOG.md' )

UNRELEASED = 'unreleased'
COMPARE_URL = 'https://github.com/ja11sop/cuppa/compare/v{previous}...{target}'

# Compare links were not maintained before this version and the matching tags do not exist.
LINKS_REQUIRED_FROM = Version( '1.4.0' )

IMPACTS = ( 'none', 'patch', 'minor', 'major' )

_SECTION = re.compile( r'^## \[(?P<version>[^\]]+)\](?:\s+-\s+(?P<when>.+?))?\s*$' )
_SUBSECTION = re.compile( r'^### (?P<name>.+?)\s*$' )
_LINK = re.compile( r'^\[(?P<version>[^\]]+)\]:\s*(?P<url>\S+)\s*$' )
_DATE = re.compile( r'^\d{4}-\d{2}-\d{2}$' )


class Section( object ):
    """One `## [version] - when` block of the changelog."""

    def __init__( self, name, when, start ):
        self.name = name
        self.when = when
        self.start = start
        self.end = None

    @property
    def released( self ):
        return bool( self.when ) and bool( _DATE.match( self.when ) )

    @property
    def version( self ):
        try:
            return Version( self.name )
        except InvalidVersion:
            return None

    def __repr__( self ):
        return "Section({}, {})".format( self.name, self.when )


def read_version( path=VERSION_FILE ):
    with open( path ) as version_file:
        return version_file.read().strip()


def write_version( version, path=VERSION_FILE ):
    with open( path, 'w' ) as version_file:
        version_file.write( "{}\n".format( version ) )


def read_changelog( path=CHANGELOG_FILE ):
    with open( path ) as changelog_file:
        return changelog_file.read()


def write_changelog( text, path=CHANGELOG_FILE ):
    with open( path, 'w' ) as changelog_file:
        changelog_file.write( text )


def is_development( version ):
    return Version( version ).is_devrelease


def release_version( version ):
    """The version being assembled: `1.4.0.dev` and `1.4.0` both give `1.4.0`."""
    return Version( Version( version ).base_version )


def development_version( version ):
    return "{}.dev".format( Version( version ).base_version )


def expected_version( last_released, impact ):
    """The smallest version an `impact` change may target on top of `last_released`."""
    if impact == 'major':
        return Version( "{}.0.0".format( last_released.major + 1 ) )
    if impact == 'minor':
        return Version( "{}.{}.0".format( last_released.major, last_released.minor + 1 ) )
    if impact == 'patch':
        return Version( "{}.{}.{}".format(
            last_released.major, last_released.minor, last_released.micro + 1
        ) )
    return last_released


def parse_sections( text ):
    lines = text.splitlines()
    sections = []
    for index, line in enumerate( lines ):
        match = _SECTION.match( line )
        if match:
            if sections:
                sections[-1].end = index
            sections.append( Section( match.group( 'version' ), match.group( 'when' ), index ) )
        elif _LINK.match( line ) and sections and sections[-1].end is None:
            sections[-1].end = index
    if sections and sections[-1].end is None:
        sections[-1].end = len( lines )
    return sections


def parse_links( text ):
    links = {}
    for line in text.splitlines():
        match = _LINK.match( line )
        if match:
            links[ match.group( 'version' ) ] = match.group( 'url' )
    return links


def in_progress_section( sections ):
    for section in sections:
        if not section.released:
            return section
    return None


def released_sections( sections ):
    return [ section for section in sections if section.released ]


def last_released_version( sections ):
    releases = [ section.version for section in released_sections( sections ) if section.version ]
    return max( releases ) if releases else None


def section_body( text, section ):
    lines = text.splitlines()
    return lines[ section.start + 1 : section.end ]


def section_has_entries( text, section ):
    return any( line.startswith( '- ' ) for line in section_body( text, section ) )


def problems( version=None, text=None ):
    """Every way the version file and the changelog can disagree. Empty means consistent."""
    version = version if version is not None else read_version()
    text = text if text is not None else read_changelog()
    found = []

    try:
        current = Version( version )
    except InvalidVersion:
        return [ "cuppa/VERSION [{}] is not a valid version".format( version ) ]

    sections = parse_sections( text )
    if not sections:
        return [ "CHANGELOG.md has no version sections" ]

    for section in sections:
        if section.version is None:
            found.append( "CHANGELOG.md section [{}] is not a valid version".format( section.name ) )
        elif not section.when:
            found.append( "CHANGELOG.md section [{}] has no date and is not marked "
                          "'{}'".format( section.name, UNRELEASED ) )
        elif not section.released and section.when != UNRELEASED:
            found.append( "CHANGELOG.md section [{}] is dated [{}], which is neither a date nor "
                          "'{}'".format( section.name, section.when, UNRELEASED ) )

    unreleased = [ section for section in sections if not section.released ]
    if len( unreleased ) > 1:
        found.append( "CHANGELOG.md has {} unreleased sections [{}]; there should be at most "
                      "one".format( len( unreleased ),
                                    ", ".join( s.name for s in unreleased ) ) )
    if unreleased and unreleased[0] is not sections[0]:
        found.append( "CHANGELOG.md section [{}] is unreleased but is not at the "
                      "top".format( unreleased[0].name ) )

    versions = [ section.version for section in sections if section.version ]
    for previous, following in zip( versions, versions[1:] ):
        if not previous > following:
            found.append( "CHANGELOG.md sections are out of order: [{}] is listed above "
                          "[{}]".format( previous, following ) )

    top = sections[0]
    if top.version and top.version != release_version( version ):
        found.append( "cuppa/VERSION is [{}] but the top CHANGELOG.md section is "
                      "[{}]".format( version, top.name ) )
    if current.is_devrelease and top.released:
        found.append( "cuppa/VERSION [{}] is a development version but CHANGELOG.md section [{}] "
                      "is already dated".format( version, top.name ) )
    if not current.is_devrelease and not top.released:
        found.append( "cuppa/VERSION [{}] is a release version but CHANGELOG.md section [{}] is "
                      "still marked '{}'".format( version, top.name, UNRELEASED ) )

    links = parse_links( text )
    for section in sections:
        if section.version and section.version >= LINKS_REQUIRED_FROM:
            if section.name not in links:
                found.append( "CHANGELOG.md has no compare link for [{}]".format( section.name ) )

    return found


def compare_link( target, previous, released ):
    return COMPARE_URL.format(
        previous = previous,
        target = "v{}".format( target ) if released else 'HEAD'
    )


def set_link( text, name, url ):
    lines = text.splitlines()
    replacement = "[{}]: {}".format( name, url )
    for index, line in enumerate( lines ):
        match = _LINK.match( line )
        if match and match.group( 'version' ) == name:
            lines[index] = replacement
            return "\n".join( lines ) + "\n"

    for index, line in enumerate( lines ):
        if _LINK.match( line ):
            lines.insert( index, replacement )
            return "\n".join( lines ) + "\n"

    lines.extend( [ '', replacement ] )
    return "\n".join( lines ) + "\n"


def rename_link( text, old_name, new_name ):
    lines = text.splitlines()
    for index, line in enumerate( lines ):
        match = _LINK.match( line )
        if match and match.group( 'version' ) == old_name:
            lines[index] = "[{}]: {}".format( new_name, match.group( 'url' ) )
            break
    return "\n".join( lines ) + "\n"


def today():
    return datetime.date.today().isoformat()
