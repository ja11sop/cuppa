#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   coverage_by_source — union coverage across gcovr JSON (preferred) or HTML
#-------------------------------------------------------------------------------

from __future__ import print_function

import json
import os
import re
from collections import defaultdict

from cuppa.colourise import as_notice, as_warning
from cuppa.log import logger


RANK = {
    "covered": 4,
    "partial": 3,
    "uncovered": 2,
    "other": 1,
    "absent": 0,
}

DETAIL_NAME_RE = re.compile(
    r"(?:^|/)(?:test\.)?(?:gcc|clang)\d*\.coverage\.[^./]+\.(.+)\.[0-9a-f]{32}\.html$",
    re.I,
)
DETAIL_NAME_RE_LOOSE = re.compile(
    r"\.coverage\.[^./]+\.(.+)\.[0-9a-f]{32}\.html$",
    re.I,
)

LINE_STATUS_RE = re.compile(
    r'class="lineno"[^>]*>.*?>(\d+)</a>.*?'
    r'class="linecount\s+([^"]*)"[^>]*>',
    re.S,
)


def basename_from_detail_name( name ):
    for regex in ( DETAIL_NAME_RE, DETAIL_NAME_RE_LOOSE ):
        match = regex.search( name )
        if match:
            return match.group( 1 )
    return None


def merge_kind( current, new ):
    if current is None:
        return new
    return new if RANK.get( new, 0 ) > RANK.get( current, 0 ) else current


def parse_detail_lines( html ):
    """Map lineno -> covered|partial|uncovered|other from a gcovr detail HTML page."""
    lines = {}
    for match in LINE_STATUS_RE.finditer( html ):
        lineno = int( match.group( 1 ) )
        cls = match.group( 2 )
        if "uncoveredLine" in cls:
            kind = "uncovered"
        elif "partialCoveredLine" in cls:
            kind = "partial"
        elif "coveredLine" in cls:
            kind = "covered"
        else:
            kind = "other"
        lines[lineno] = kind
    return lines


def default_source_roots( repo_root ):
    candidates = [
        os.path.join( repo_root, "include" ),
        os.path.join( repo_root, "src" ),
        os.path.join( repo_root, "source" ),
        os.path.join( repo_root, "lib" ),
    ]
    roots = [ path for path in candidates if os.path.isdir( path ) ]
    return roots if roots else [ repo_root ]


def normalize_repo_path( repo_root, file_path ):
    """Return a repo-relative POSIX path for a gcovr file entry when possible."""
    if not file_path:
        return None
    path = file_path.replace( "\\", "/" )
    if os.path.isabs( path ):
        try:
            return os.path.relpath( path, repo_root ).replace( "\\", "/" )
        except ValueError:
            return path
    abs_path = os.path.normpath( os.path.join( repo_root, path ) )
    try:
        return os.path.relpath( abs_path, repo_root ).replace( "\\", "/" )
    except ValueError:
        return path


def resolve_source_path( repo_root, fname, source_roots ):
    """Map a detail-page basename to a repo-relative path."""
    if "/" in fname or os.sep in fname:
        rel = fname.replace( "\\", "/" )
        abs_path = os.path.join( repo_root, rel )
        if os.path.isfile( abs_path ):
            return rel
        for root in source_roots:
            if os.path.isfile( os.path.join( root, rel ) ):
                try:
                    return os.path.relpath( os.path.join( root, rel ), repo_root ).replace( "\\", "/" )
                except ValueError:
                    return rel
        return rel

    matches = []
    for root in source_roots:
        for dirpath, _dirnames, filenames in os.walk( root ):
            if fname in filenames:
                matches.append( os.path.join( dirpath, fname ) )

    if not matches:
        return None

    rels = []
    for match_path in matches:
        try:
            rel = os.path.relpath( match_path, repo_root ).replace( "\\", "/" )
        except ValueError:
            continue
        if any( part in ( "_build", "_artifacts", ".git", "node_modules" ) for part in rel.split( "/" ) ):
            continue
        rels.append( rel )

    if not rels:
        return None

    def rank( rel ):
        if rel.startswith( "include/" ):
            bucket = 0
        elif rel.startswith( "src/" ) or rel.startswith( "source/" ):
            bucket = 1
        else:
            bucket = 2
        return ( bucket, rel.count( "/" ), rel )

    rels.sort( key=rank )
    return rels[0]


def sanitized_source_filename( source_path ):
    return source_path.replace( "\\", "/" ).replace( "/", "--" ) + ".html"


def sanitized_toolchain_dirname( toolchain_label ):
    """Turn 'gcc153/cov/x86_64/cxx2c' into a single path segment."""
    return (
        toolchain_label.replace( "\\", "/" )
        .strip( "/" )
        .replace( "/", "_" )
        .replace( " ", "_" )
    )


def iter_coverage_json_paths( search_roots ):
    seen_paths = set()
    seen_names = set()
    for root in search_roots:
        if not root or not os.path.isdir( root ):
            continue
        for dirpath, _dirnames, filenames in os.walk( root ):
            for filename in filenames:
                if not ( filename.startswith( "coverage--" ) and filename.endswith( ".json" ) ):
                    continue
                path = os.path.join( dirpath, filename )
                if path in seen_paths or filename in seen_names:
                    continue
                seen_paths.add( path )
                seen_names.add( filename )
                yield path


def iter_detail_html_paths( search_roots ):
    seen_paths = set()
    seen_names = set()
    for root in search_roots:
        if not root or not os.path.isdir( root ):
            continue
        for dirpath, _dirnames, filenames in os.walk( root ):
            for filename in filenames:
                if ".coverage." not in filename or not filename.endswith( ".html" ):
                    continue
                if filename.endswith( "functions.html" ) or filename.startswith( "coverage--" ):
                    continue
                if filename.startswith( "coverage-index" ):
                    continue
                path = os.path.join( dirpath, filename )
                if path in seen_paths or filename in seen_names:
                    continue
                if not basename_from_detail_name( filename ):
                    continue
                seen_paths.add( path )
                seen_names.add( filename )
                yield path


def progress_lines_status( percent ):
    percent = float( percent )
    if percent < 75.0:
        return "bg-danger"
    if percent < 90.0:
        return "bg-warning"
    return "bg-success"


def lines_status( percent ):
    percent = float( percent )
    if percent < 75.0:
        return "alert-danger"
    if percent < 90.0:
        return "alert-warning"
    return "alert-success"


def progress_branches_status( percent ):
    percent = float( percent )
    if percent < 40.0:
        return "bg-danger"
    if percent < 50.0:
        return "bg-warning"
    return "bg-success"


def branches_status( percent ):
    percent = float( percent )
    if percent < 40.0:
        return "alert-danger"
    if percent < 50.0:
        return "alert-warning"
    return "alert-success"


def branch_key( lineno, branch ):
    branchno = branch.get( "branchno", branch.get( "branch_number" ) )
    source_block = branch.get( "source_block_id" )
    dest_block = branch.get( "destination_block_id" )
    return ( int( lineno ), branchno, source_block, dest_block )


def load_source_text( repo_root, source_path, source_text_cache ):
    if source_path in source_text_cache:
        return
    abs_source = os.path.join( repo_root, source_path )
    if os.path.isfile( abs_source ):
        try:
            with open( abs_source, "r", encoding="utf-8", errors="replace" ) as source_file:
                source_text_cache[source_path] = source_file.read().splitlines()
        except ( IOError, UnicodeDecodeError ):
            source_text_cache[source_path] = []
    else:
        source_text_cache[source_path] = []


def collect_union_coverage_from_json( search_roots, repo_root ):
    """Union line/branch coverage from coverage--*.json files."""
    source_roots = default_source_roots( repo_root )
    # source_path -> lineno -> executed(bool); False means seen but never executed
    line_executed = defaultdict( dict )
    # source_path -> branch_key -> taken(bool)
    union_branches = defaultdict( dict )
    json_counts = defaultdict( int )
    source_text_cache = {}
    found_any = False

    for json_path in sorted( iter_coverage_json_paths( search_roots ) ):
        try:
            with open( json_path, "r", encoding="utf-8" ) as json_file:
                payload = json.load( json_file )
        except ( IOError, ValueError, TypeError ) as exc:
            logger.warn(
                "Failed reading coverage JSON [{}]: {}".format(
                    as_notice( json_path ), as_warning( str( exc ) )
                )
            )
            continue

        files = payload.get( "files" )
        if not isinstance( files, list ):
            continue
        found_any = True

        for file_entry in files:
            raw_path = file_entry.get( "file" ) or file_entry.get( "filename" ) or ""
            source_path = normalize_repo_path( repo_root, raw_path )
            if not source_path:
                continue
            if "/" not in source_path:
                resolved = resolve_source_path( repo_root, source_path, source_roots )
                if resolved:
                    source_path = resolved
            if any( part in ( "_build", "_artifacts", ".git", "node_modules" ) for part in source_path.split( "/" ) ):
                continue

            json_counts[source_path] += 1
            load_source_text( repo_root, source_path, source_text_cache )

            for line_entry in file_entry.get( "lines" ) or []:
                if line_entry.get( "gcovr/excluded" ) or line_entry.get( "excluded" ):
                    continue
                lineno = line_entry.get( "line_number", line_entry.get( "line" ) )
                if lineno is None:
                    continue
                lineno = int( lineno )
                count = line_entry.get( "count" )
                if count is None:
                    continue
                executed = int( count ) > 0
                line_executed[source_path][lineno] = bool(
                    line_executed[source_path].get( lineno )
                ) or executed

                for branch in line_entry.get( "branches" ) or []:
                    if branch.get( "gcovr/excluded" ) or branch.get( "excluded" ):
                        continue
                    key = branch_key( lineno, branch )
                    taken = int( branch.get( "count", 0 ) or 0 ) > 0
                    union_branches[source_path][key] = bool(
                        union_branches[source_path].get( key )
                    ) or taken

    if not found_any:
        return None

    union_lines = defaultdict( dict )
    for source_path, linenos in line_executed.items():
        branch_map = union_branches.get( source_path, {} )
        for lineno, executed in linenos.items():
            line_branch_keys = [ key for key in branch_map if key[0] == lineno ]
            if line_branch_keys:
                taken = sum( 1 for key in line_branch_keys if branch_map.get( key ) )
                total = len( line_branch_keys )
                if not executed and taken == 0:
                    kind = "uncovered"
                elif taken < total:
                    kind = "partial"
                else:
                    kind = "covered"
            else:
                kind = "covered" if executed else "uncovered"
            union_lines[source_path][lineno] = kind

    return union_lines, union_branches, json_counts, source_text_cache


def collect_union_coverage_from_html( search_roots, repo_root ):
    """Fallback: union line status from gcovr HTML detail pages (no branches)."""
    source_roots = default_source_roots( repo_root )
    union = defaultdict( dict )
    detail_counts = defaultdict( int )
    source_text_cache = {}

    for html_path in sorted( iter_detail_html_paths( search_roots ) ):
        fname = basename_from_detail_name( os.path.basename( html_path ) )
        if not fname:
            continue
        source_path = resolve_source_path( repo_root, fname, source_roots )
        if not source_path:
            logger.trace(
                "Skipping coverage detail [{}]: could not resolve source for [{}]".format(
                    as_notice( html_path ), as_warning( fname )
                )
            )
            continue
        try:
            with open( html_path, "r", encoding="utf-8" ) as html_file:
                html = html_file.read()
        except IOError as exc:
            logger.warn(
                "Failed reading coverage detail [{}]: {}".format(
                    as_notice( html_path ), as_warning( str( exc ) )
                )
            )
            continue

        detail_counts[source_path] += 1
        for lineno, kind in parse_detail_lines( html ).items():
            union[source_path][lineno] = merge_kind( union[source_path].get( lineno ), kind )

        load_source_text( repo_root, source_path, source_text_cache )

    return union, {}, detail_counts, source_text_cache


def collect_union_coverage( search_roots, repo_root ):
    """Return (line_union, branch_union, source_counts, source_text_cache, used_json)."""
    json_result = collect_union_coverage_from_json( search_roots, repo_root )
    if json_result is not None:
        union_lines, union_branches, counts, source_text_cache = json_result
        return union_lines, union_branches, counts, source_text_cache, True
    union_lines, union_branches, counts, source_text_cache = collect_union_coverage_from_html(
        search_roots, repo_root
    )
    return union_lines, union_branches, counts, source_text_cache, False


class source_coverage_entry(object):

    def __init__(
        self,
        source_path,
        line_kinds,
        branch_taken=None,
        detail_count=0,
        used_json=False,
        by_source_subdir=None,
        toolchain_label=None,
    ):
        self.coverage_name = source_path
        self.toolchain_label = toolchain_label or ""
        label = "JSON report" if used_json else "detail page"
        self.coverage_context = "{} {}{}".format(
            detail_count, label, "" if detail_count == 1 else "s"
        )
        parts = [ "by-source" ]
        if by_source_subdir:
            parts.append( by_source_subdir )
        parts.append( sanitized_source_filename( source_path ) )
        self.coverage_file = os.path.join( *parts )
        self.line_kinds = dict( line_kinds )
        self.branch_taken = dict( branch_taken or {} )
        self.detail_count = detail_count
        self.line_branch_stats = {}

        for key, taken in self.branch_taken.items():
            lineno = key[0]
            stats = self.line_branch_stats.setdefault( lineno, { "taken": 0, "total": 0 } )
            stats["total"] += 1
            if taken:
                stats["taken"] += 1

        executable = [
            ( lineno, kind )
            for lineno, kind in self.line_kinds.items()
            if kind in ( "covered", "partial", "uncovered" )
        ]
        self.lines_total = len( executable )
        self.lines_covered = sum( 1 for _ln, kind in executable if kind in ( "covered", "partial" ) )
        if self.lines_total:
            self.lines_percent = "{:.1f}".format(
                100.0 * float( self.lines_covered ) / float( self.lines_total )
            )
        else:
            self.lines_percent = "0.0"

        self.branches_total = len( self.branch_taken )
        self.branches_covered = sum( 1 for taken in self.branch_taken.values() if taken )
        if self.branches_total:
            self.branches_percent = "{:.1f}".format(
                100.0 * float( self.branches_covered ) / float( self.branches_total )
            )
            self.progress_branches_status = progress_branches_status( self.branches_percent )
            self.branches_status = branches_status( self.branches_percent )
        else:
            self.branches_percent = "n/a"
            self.progress_branches_status = ""
            self.branches_status = "text-secondary"

        self.progress_lines_status = progress_lines_status( self.lines_percent )
        self.lines_status = lines_status( self.lines_percent )


class source_coverage_summary(object):

    def __init__( self, title, context, entries ):
        self.coverage_file = title
        self.coverage_context = context
        self.entries = list( entries )
        self.lines_covered = sum( entry.lines_covered for entry in self.entries )
        self.lines_total = sum( entry.lines_total for entry in self.entries )
        if self.lines_total:
            self.lines_percent = "{:.1f}".format(
                100.0 * float( self.lines_covered ) / float( self.lines_total )
            )
        else:
            self.lines_percent = "0.0"
        self.branches_covered = sum( entry.branches_covered for entry in self.entries )
        self.branches_total = sum( entry.branches_total for entry in self.entries )
        if self.branches_total:
            self.branches_percent = "{:.1f}".format(
                100.0 * float( self.branches_covered ) / float( self.branches_total )
            )
            self.progress_branches_status = progress_branches_status( self.branches_percent )
            self.branches_status = branches_status( self.branches_percent )
        else:
            self.branches_percent = "n/a"
            self.progress_branches_status = ""
            self.branches_status = "text-secondary"
        self.progress_lines_status = progress_lines_status( self.lines_percent )
        self.lines_status = lines_status( self.lines_percent )


def build_source_entries( union_lines, union_branches, detail_counts, used_json, by_source_subdir=None, toolchain_label=None ):
    entries = []
    for source_path in sorted( union_lines.keys() ):
        entries.append(
            source_coverage_entry(
                source_path,
                union_lines[source_path],
                branch_taken=union_branches.get( source_path ),
                detail_count=detail_counts.get( source_path, 0 ),
                used_json=used_json,
                by_source_subdir=by_source_subdir,
                toolchain_label=toolchain_label,
            )
        )
    entries.sort( key=lambda entry: ( float( entry.lines_percent ), entry.coverage_name ) )
    return entries


def language_for_source( source_path ):
    ext = os.path.splitext( source_path )[1].lower()
    if ext in ( ".c", ):
        return "c"
    if ext in ( ".hpp", ".h", ".hh", ".hxx", ".cpp", ".cc", ".cxx", ".inl", ".ipp", ".tpp" ):
        return "cpp"
    if ext in ( ".py", ):
        return "python"
    if ext in ( ".js", ".mjs", ):
        return "javascript"
    if ext in ( ".ts", ):
        return "typescript"
    if ext in ( ".rs", ):
        return "rust"
    if ext in ( ".go", ):
        return "go"
    return "cpp"


def write_source_detail_pages(
    output_dir,
    entries,
    source_text_cache,
    index_basename,
    get_template,
    LOC,
    by_source_subdir=None,
):
    by_source_dir = os.path.join( output_dir, "by-source" )
    if by_source_subdir:
        by_source_dir = os.path.join( by_source_dir, by_source_subdir )
    if not os.path.isdir( by_source_dir ):
        os.makedirs( by_source_dir )

    template = get_template()
    depth = 2 if by_source_subdir else 1
    index_href = "{}{}#by-source".format( "../" * depth, index_basename )
    written = []

    for entry in entries:
        lines = []
        source_lines = source_text_cache.get( entry.coverage_name, [] )
        if source_lines:
            for lineno, text in enumerate( source_lines, start=1 ):
                kind = entry.line_kinds.get( lineno, "none" )
                if kind not in ( "covered", "partial", "uncovered", "other", "none" ):
                    kind = "none"
                stats = entry.line_branch_stats.get( lineno )
                lines.append({
                    "lineno": lineno,
                    "kind": kind,
                    "text": text,
                    "branches_taken": stats["taken"] if stats else 0,
                    "branches_total": stats["total"] if stats else 0,
                })
        else:
            for lineno in sorted( entry.line_kinds.keys() ):
                kind = entry.line_kinds[lineno]
                if kind not in ( "covered", "partial", "uncovered", "other" ):
                    continue
                stats = entry.line_branch_stats.get( lineno )
                lines.append({
                    "lineno": lineno,
                    "kind": kind,
                    "text": "",
                    "branches_taken": stats["taken"] if stats else 0,
                    "branches_total": stats["total"] if stats else 0,
                })

        page_path = os.path.join( output_dir, entry.coverage_file )
        with open( page_path, "w", encoding="utf-8" ) as page_file:
            page_file.write(
                template.render(
                    source_entry=entry,
                    source_lines=lines,
                    index_href=index_href,
                    source_language=language_for_source( entry.coverage_name ),
                    LOC=LOC,
                )
            )
        written.append( page_path )

    return written


def generate_by_source_coverage(
    search_roots,
    output_dir,
    repo_root,
    index_basename,
    get_source_template,
    LOC,
    title="union",
    context="By source file (best line status across tests)",
    by_source_subdir=None,
    toolchain_label=None,
):
    """Build union coverage pages and return (summary, entries, show_tab, written_paths)."""
    union_lines, union_branches, detail_counts, source_text_cache, used_json = collect_union_coverage(
        search_roots, repo_root
    )
    if not union_lines:
        empty = source_coverage_summary( title, context, [] )
        return empty, [], False, []

    if used_json:
        context = context + " — JSON union (lines + branches)"
    else:
        context = context + " — HTML fallback (lines only)"

    entries = build_source_entries(
        union_lines,
        union_branches,
        detail_counts,
        used_json,
        by_source_subdir=by_source_subdir,
        toolchain_label=toolchain_label,
    )
    summary = source_coverage_summary( title, context, entries )
    if toolchain_label:
        summary.coverage_context = toolchain_label
        summary.toolchain_label = toolchain_label
    written = write_source_detail_pages(
        output_dir,
        entries,
        source_text_cache,
        index_basename,
        get_source_template,
        LOC,
        by_source_subdir=by_source_subdir,
    )
    return summary, entries, True, written
