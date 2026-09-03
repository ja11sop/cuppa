#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Render Antora listing samples through Cuppa's real formatters.

Run from the repository root:

    python -m scripts.generate_doc_samples

Writes plain-text and semantic HTML samples under
``docs/modules/ROOT/partials/samples/``. AsciiDoc pages include text files inside
``[source,text]`` blocks and HTML fragments inside passthrough blocks.

Generate and preview the first semantic recipe with:

    python -m scripts.generate_doc_samples list-builds --preview

Relative ages use a fixed reference instant (:data:`NOW`, 2026-08-09) via
:class:`frozen_now`, including when unit tests call individual ``sample_*``
generators — do not refresh partials from live ``cuppa --list-*`` output.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import time
from pathlib import Path

import cuppa.colourise
from cuppa.colourise_html import HtmlColouriser
from cuppa.core import (
        dependency_downloads,
        dependency_removal,
        dependency_tree,
        storage_actions,
        toolchain_actions,
)
from cuppa.core.dependency_actions import (
        _format_age_epoch,
        apply_list_scope,
        write_list_dependencies_report,
        write_list_downloads_report,
)
from cuppa.develop import Copy, list_payload as develop_list_payload
from cuppa.develop import report as develop_report
from cuppa.utility import storage


class _FakeEnv( dict ):
    def get_option( self, name, default=None ):
        return self.get( name, default )


ROOT = Path( __file__ ).resolve().parents[1]
SAMPLES = ROOT / 'docs' / 'modules' / 'ROOT' / 'partials' / 'samples'
PREVIEWS = ROOT / '_docs_build' / 'samples'

# Freeze "today" / "yesterday" / "11 days ago" / "2 months ago" relative ages.
NOW = time.mktime( time.strptime( '2026-08-09 12:00:00', '%Y-%m-%d %H:%M:%S' ) )
DAY = 86400.0


class frozen_now( object ):
    """Context manager: pin ``time.time()`` to :data:`NOW` for stable LAST USED columns."""

    def __enter__( self ):
        self._real_time = time.time
        time.time = lambda: NOW
        return self

    def __exit__( self, exc_type, exc, tb ):
        time.time = self._real_time
        return False


def _frozen_now( fn ):
    """Decorator: run a sample generator under :class:`frozen_now`."""
    def wrapped( *args, **kwargs ):
        with frozen_now():
            return fn( *args, **kwargs )
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


def _strip_ansi( text ):
    return re.sub( r'\x1b\[[0-9;]*m', '', text )


def _clean( text ):
    lines = [ line.rstrip() for line in _strip_ansi( text ).splitlines() ]
    while lines and not lines[0]:
        lines.pop( 0 )
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join( lines ) + '\n'


def _rewrite_abs_build_root( text, abs_build_root ):
    """Prefer the project-relative `_build` readers see in real reports."""
    abs_build_root = os.path.normpath( abs_build_root )
    text = text.replace( abs_build_root, '_build' )
    displayed = storage.display_path( abs_build_root )
    if displayed != abs_build_root:
        text = text.replace( displayed, '_build' )
    return text


def _doc_toolchain_download_prefix( work_root ):
    """Map temp registered roots to the illustrative `~/_cuppa/_download/toolchains` path."""
    return str( Path( work_root ) / 'toolchains' ), '~/_cuppa/_download/toolchains'


def _write_sample( name, text ):
    SAMPLES.mkdir( parents=True, exist_ok=True )
    path = SAMPLES / name
    path.write_text( _clean( text ), encoding='utf-8' )
    return path


def _assert_public_html( text ):
    """Refuse HTML fragments containing machine-specific absolute paths."""
    forbidden = ( '/home/', '/Users/', '/tmp/' )
    found = next( ( prefix for prefix in forbidden if prefix in text ), None )
    if found:
        raise ValueError(
                "refusing documentation sample containing absolute path [{}]".format(
                    found
                )
        )


def _capture_html( invoke ):
    """Run ``invoke( out )`` under the HTML colouriser.

    Returns the assembled text and the colouriser holding the semantic
    operations, so a recipe can still rewrite machine paths in both before
    rendering.
    """
    colouriser = HtmlColouriser()
    out = io.StringIO()
    with cuppa.colourise.using_colouriser( colouriser ):
        invoke( out )
    return out.getvalue(), colouriser


def _write_html_sample( name, text, colouriser ):
    SAMPLES.mkdir( parents=True, exist_ok=True )
    rendered = colouriser.render( text )
    _assert_public_html( rendered )
    path = SAMPLES / name
    path.write_text( rendered, encoding='utf-8' )
    return path


def _write_preview( fragment ):
    """Write a standalone preview using the same palette and sample CSS as Antora."""
    palette = (
        ROOT / 'docs' / 'supplemental-ui' / 'css'
        / 'cuppa-palette-cup-of-tea.css'
    ).read_text( encoding='utf-8' )
    output_css = (
        ROOT / 'docs' / 'supplemental-ui' / 'css' / 'cuppa-output.css'
    ).read_text( encoding='utf-8' )
    body = fragment.read_text( encoding='utf-8' )
    preview = (
        '<!doctype html>\n'
        '<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>Cuppa {} sample</title>\n'
        '<style>{}</style><style>{}</style>\n'
        '</head><body style="background:var(--cuppa-page);'
        'color:var(--cuppa-text);margin:2rem">{}\n'
        '</body></html>\n'
    ).format( fragment.stem, palette, output_css, body )
    _assert_public_html( preview )
    PREVIEWS.mkdir( parents=True, exist_ok=True )
    path = PREVIEWS / '{}.preview.html'.format( fragment.stem )
    path.write_text( preview, encoding='utf-8' )
    return path


def _touch_dir( path, mtime ):
    path = Path( path )
    path.mkdir( parents=True, exist_ok=True )
    keep = path / '.keep'
    keep.write_text( 'x', encoding='utf-8' )
    os.utime( path, ( mtime, mtime ) )
    os.utime( keep, ( mtime, mtime ) )
    return str( path )


def _work_root( name ):
    root = Path( '/tmp' ) / 'cuppa_doc_samples' / name
    if root.exists():
        shutil.rmtree( root )
    root.mkdir( parents=True )
    return root


def _download_rows_for_list_samples():
    """Shared rows for `--list-downloads` text and JSON samples."""
    now = NOW
    return [
        dict(
            type='archive', dependency='boost', short_name='boost',
            qualifier='1.91.0', state='referenced',
            size_bytes=142 * 1024 * 1024, last_used_epoch=now,
            path='/home/user/.cuppa/downloads/boost_1_91_0.tar.bz2',
            label='boost_1_91_0.tar.bz2', kind='archive', role='archive',
        ),
        dict(
            type='archive', dependency='boost', short_name='boost',
            qualifier='1.91.0', state='referenced',
            size_bytes=int( 2.1 * 1024 ** 3 ), last_used_epoch=now,
            path='/home/user/.cuppa/dependencies/boost_1_91_0.tar.bz2',
            label='[E] boost/1.91.0', kind='product', role='product',
        ),
        dict(
            type='gitlab', dependency='boost_package', short_name='boost_package',
            qualifier='1.91', tool_variant='gcc153_rel_x86_64_cxx2c',
            state='referenced', size_bytes=38 * 1024 * 1024, last_used_epoch=now,
            path='/home/user/.cuppa/downloads/boost_pkg_gcc153_rel_x86_64_cxx2c.tar.gz',
            label='boost_…_gcc153_rel_….tar.gz', kind='archive', role='archive',
        ),
        dict(
            type='gitlab', dependency='boost_package', short_name='boost_package',
            qualifier='1.91', tool_variant='gcc153_rel_x86_64_cxx2c',
            state='referenced', size_bytes=int( 299.3 * 1024 * 1024 ),
            last_used_epoch=now,
            path='/home/user/.cuppa/dependencies/boost/1.91/gcc153_rel_x86_64_cxx2c',
            label='[E] gcc153_rel_x86_64_cxx2c', kind='product', role='product',
        ),
        dict(
            type='gitlab', dependency='fmt_package', short_name='fmt_package',
            qualifier='11.1.4', tool_variant='clang211_rel_x86_64_cxx2c',
            state='unreferenced', size_bytes=36 * 1024 * 1024, last_used_epoch=now,
            path='/home/user/.cuppa/downloads/fmt_…_clang211_rel_….tar.gz',
            label='fmt_…_clang211_rel_….tar.gz', kind='archive', role='archive',
        ),
    ]


def _list_downloads_env():
    env = _FakeEnv()
    env['default_dependencies'] = [ 'boost', 'boost_package' ]
    return env


def _list_downloads_data():
    rows = _download_rows_for_list_samples()
    data = {
        'rows': rows,
        'downloads_root': str( Path.home() / '.cuppa' / 'downloads' ),
        'skips': [],
        'estimated': False,
    }
    return apply_list_scope(
            data, 'all', tree_builder=dependency_downloads.build_downloads_tree,
    )


def _rewrite_sample_home( text, colouriser=None ):
    """Map planted ``/home/user`` paths to ``~`` for public samples."""
    planted = '/home/user'
    if colouriser is not None:
        colouriser.replace( planted, '~' )
    return text.replace( planted, '~' )


def _run_dependency_removal( out, env, plan, purge_plan=None ):
    """Run the real removal report against a deterministic collected plan."""
    real_collect = dependency_removal.collect_removal_plan
    real_collect_purge = dependency_removal.collect_purge_downloads
    real_dry_run = dependency_removal.dry_run
    dependency_removal.collect_removal_plan = (
        lambda construct, cuppa_env, names, wipe=False: plan
    )
    dependency_removal.dry_run = (
        lambda cuppa_env: bool( cuppa_env.get_option( 'no_exec' ) )
    )
    if purge_plan is not None:
        dependency_removal.collect_purge_downloads = (
            lambda construct, cuppa_env, names, owned=None: purge_plan
        )
    try:
        return dependency_removal.remove_dependencies( object(), env, out=out )
    finally:
        dependency_removal.collect_removal_plan = real_collect
        dependency_removal.collect_purge_downloads = real_collect_purge
        dependency_removal.dry_run = real_dry_run


def _rewrite_removal_roots( text, colouriser, roots ):
    """Replace planted storage roots in text and semantic operation values."""
    for root, public in roots:
        if colouriser is not None:
            colouriser.replace( str( root ), public )
        text = text.replace( str( root ), public )
    return text


def sample_list_downloads():
    """`--list-downloads` hierarchical text (gitlab before source archives)."""
    out = io.StringIO()
    write_list_downloads_report(
            out, _list_downloads_data(), _list_downloads_env(),
    )
    return _write_sample(
            'list-downloads.txt', _rewrite_sample_home( out.getvalue() ),
    )


def sample_list_downloads_html():
    """Semantic HTML form of the `--list-downloads` report."""
    def invoke( out ):
        write_list_downloads_report(
                out, _list_downloads_data(), _list_downloads_env(),
        )

    text, colouriser = _capture_html( invoke )
    text = _rewrite_sample_home( text, colouriser )
    return _write_html_sample( 'list-downloads.html', text, colouriser )


def _remove_gitlab_fixture( name ):
    root = _work_root( name )
    deps = root / 'dependencies'
    p_gcc153 = _touch_dir( deps / 'boost' / '1.91' / 'gcc153_rel_x86_64_cxx2c', NOW - DAY )
    p_clang = _touch_dir(
            deps / 'boost' / '1.91' / 'clang211_rel_x86_64_cxx2c', NOW - 11 * DAY
    )
    p_gcc152 = _touch_dir(
            deps / 'boost' / '1.91' / 'gcc152_rel_x86_64_cxx2c', NOW - 60 * DAY
    )
    env = _FakeEnv(
            remove_dependencies='boost_package',
            default_dependencies=[ 'boost_package' ],
            dependencies_root=str( deps ),
            sconstruct_dir=str( root ),
            no_exec=True,
    )
    plan = {
        'targets': [
                dependency_removal.RemovalTarget(
                        dependency='boost_package',
                        path=p_gcc153,
                        qualifier='1.91',
                        tool_variant='gcc153_rel_x86_64_cxx2c',
                        storage_type='gitlab',
                        size_bytes=166 * 1024 * 1024,
                        label='gcc153_rel_x86_64_cxx2c/boost/1.91',
                        extra_paths=(),
                ),
        ],
        'leftovers': [
                dependency_removal.Leftover(
                        dependency='boost_package',
                        path=p_clang,
                        qualifier='1.91',
                        tool_variant='clang211_rel_x86_64_cxx2c',
                        size_bytes=294 * 1024 * 1024,
                        label='clang211_rel_x86_64_cxx2c/boost/1.91',
                        storage_type='gitlab',
                ),
                dependency_removal.Leftover(
                        dependency='boost_package',
                        path=p_gcc152,
                        qualifier='1.91',
                        tool_variant='gcc152_rel_x86_64_cxx2c',
                        size_bytes=int( 297.8 * 1024 * 1024 ),
                        label='gcc152_rel_x86_64_cxx2c/boost/1.91',
                        storage_type='gitlab',
                ),
        ],
        'archives': [],
        'develop_skips': [],
        'owned': [],
    }
    return env, plan, deps


def _render_remove_gitlab( name, colouriser=None ):
    env, plan, deps = _remove_gitlab_fixture( name )
    out = io.StringIO()
    _run_dependency_removal( out, env, plan )
    return _rewrite_removal_roots(
            out.getvalue(), colouriser,
            [ ( deps, '~/.cuppa/dependencies' ) ],
    )


def sample_remove_gitlab_dry_run():
    """`--remove-dependencies` dry-run for a selected GitLab toolchain leaf."""
    return _write_sample(
            'remove-gitlab-dry-run.txt',
            _render_remove_gitlab( 'remove-gitlab-text' ),
    )


def sample_remove_gitlab_dry_run_html():
    """Semantic HTML form of the selected GitLab removal dry run."""
    colouriser = HtmlColouriser()
    with cuppa.colourise.using_colouriser( colouriser ):
        text = _render_remove_gitlab( 'remove-gitlab-html', colouriser )
    return _write_html_sample( 'remove-gitlab-dry-run.html', text, colouriser )


def _remove_boost_fixture( name ):
    root = _work_root( name )
    deps = root / 'dependencies'
    extract = deps / 'boost_1_91_0'
    stage = extract / 'clean' / 'build.c++2c' / 'gcc153' / 'debug' / 'x86_64'
    bindir = extract / 'clean' / 'bin.c++2c' / 'boost' / 'bin.v2'
    _touch_dir( stage, NOW - DAY )
    _touch_dir( bindir, NOW - DAY )
    _touch_dir( extract / 'clean' / 'boost', NOW - DAY )

    archives = [ {
        'dependency': 'boost',
        'extract': str( extract ),
        'extract_bytes': int( 2.1 * 1024 ** 3 ),
        'source_bytes': int( 1.7 * 1024 ** 3 ),
        'qualifier': '1.91.0',
        'storage_type': 'archive',
        'age_text': 'yesterday',
        'age_epoch': NOW - DAY,
    } ]
    targets = [
        dependency_removal.RemovalTarget(
                dependency='boost',
                path=str( stage ),
                qualifier='1.91.0',
                tool_variant='gcc153/debug/x86_64',
                storage_type='archive',
                size_bytes=int( 298.4 * 1024 * 1024 ),
                label='clean/build.c++2c [gcc153/debug/x86_64]',
                extra_paths=(),
        ),
        dependency_removal.RemovalTarget(
                dependency='boost',
                path=str( bindir ),
                qualifier='1.91.0',
                tool_variant='gcc-15*/debug',
                storage_type='archive',
                size_bytes=int( 113.9 * 1024 * 1024 ),
                label='clean/bin.c++2c [gcc-15*/debug]',
                extra_paths=(),
        ),
    ]
    env = _FakeEnv(
            remove_dependencies='boost',
            default_dependencies=[ 'boost' ],
            dependencies_root=str( deps ),
            sconstruct_dir=str( root ),
            no_exec=False,
    )
    plan = {
        'targets': targets,
        'leftovers': [],
        'archives': archives,
        'develop_skips': [],
        'owned': [],
    }
    return env, plan, deps


def _render_remove_boost( name, colouriser=None ):
    env, plan, deps = _remove_boost_fixture( name )
    out = io.StringIO()
    _run_dependency_removal( out, env, plan )
    return _rewrite_removal_roots(
            out.getvalue(), colouriser,
            [ ( deps, '~/.cuppa/dependencies' ) ],
    )


def sample_remove_boost_product_clean():
    """`--remove-dependencies=boost` product-clean report (extract stays)."""
    return _write_sample(
            'remove-boost-product-clean.txt',
            _render_remove_boost( 'remove-boost-text' ),
    )


def sample_remove_boost_product_clean_html():
    """Semantic HTML form of the source Boost product-clean report."""
    colouriser = HtmlColouriser()
    with cuppa.colourise.using_colouriser( colouriser ):
        text = _render_remove_boost( 'remove-boost-html', colouriser )
    return _write_html_sample( 'remove-boost-product-clean.html', text, colouriser )


def _purge_gitlab_fixture( name ):
    root = _work_root( name )
    deps = root / 'dependencies'
    downloads = root / 'downloads'
    downloads.mkdir( parents=True )
    p_gcc = _touch_dir( deps / 'boost' / '1.91' / 'gcc153_rel_x86_64_cxx2c', NOW - DAY )
    p_clang = _touch_dir(
            deps / 'boost' / '1.91' / 'clang211_rel_x86_64_cxx2c', NOW - 11 * DAY
    )
    a_gcc = downloads / 'boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz'
    a_clang = downloads / 'boost_debian_clang211_rel_x86_64_cxx2c.tar.gz'
    a_gcc.write_bytes( b'x' * int( 1.2 * 1024 * 1024 ) )
    a_clang.write_bytes( b'x' * int( 1.1 * 1024 * 1024 ) )
    os.utime( a_gcc, ( NOW - DAY, NOW - DAY ) )
    os.utime( a_clang, ( NOW - 11 * DAY, NOW - 11 * DAY ) )

    targets = [
        dependency_removal.RemovalTarget(
                dependency='boost_package',
                path=p_gcc,
                qualifier='1.91',
                tool_variant='gcc153_rel_x86_64_cxx2c',
                storage_type='gitlab',
                size_bytes=166 * 1024 * 1024,
                label='gcc153_rel_x86_64_cxx2c/boost/1.91',
                extra_paths=(),
        ),
    ]
    leftovers = [
        dependency_removal.Leftover(
                dependency='boost_package',
                path=p_clang,
                qualifier='1.91',
                tool_variant='clang211_rel_x86_64_cxx2c',
                size_bytes=294 * 1024 * 1024,
                label='clang211_rel_x86_64_cxx2c/boost/1.91',
                storage_type='gitlab',
        ),
    ]
    download_targets = [
        dependency_removal.DownloadTarget(
                dependency='boost_package',
                path=str( a_gcc ),
                qualifier='1.91',
                tool_variant='gcc153_rel_x86_64_cxx2c',
                storage_type='gitlab',
                size_bytes=int( 1.2 * 1024 * 1024 ),
                label=a_gcc.name,
                missing=False,
        ),
    ]
    download_leftovers = [
        dependency_removal.DownloadTarget(
                dependency='boost_package',
                path=str( a_clang ),
                qualifier='1.91',
                tool_variant='clang211_rel_x86_64_cxx2c',
                storage_type='gitlab',
                size_bytes=int( 1.1 * 1024 * 1024 ),
                label=a_clang.name,
                missing=False,
        ),
    ]
    env = _FakeEnv(
            purge_dependencies='boost_package',
            default_dependencies=[ 'boost_package' ],
            dependencies_root=str( deps ),
            downloads_root=str( downloads ),
            sconstruct_dir=str( root ),
            no_exec=False,
    )
    plan = {
        'targets': targets,
        'leftovers': leftovers,
        'archives': [],
        'develop_skips': [],
        'owned': [],
    }
    purge_plan = ( download_targets, download_leftovers, str( downloads ) )
    return env, plan, purge_plan, deps, downloads


def _render_purge_gitlab( name, colouriser=None ):
    env, plan, purge_plan, deps, downloads = _purge_gitlab_fixture( name )
    out = io.StringIO()
    _run_dependency_removal( out, env, plan, purge_plan=purge_plan )
    return _rewrite_removal_roots(
            out.getvalue(), colouriser,
            [
                ( deps, '~/.cuppa/dependencies' ),
                ( downloads, '~/.cuppa/downloads' ),
            ],
    )


def sample_purge_gitlab():
    """`--purge-dependencies` selected GitLab archive + extract."""
    return _write_sample(
            'purge-gitlab.txt',
            _render_purge_gitlab( 'purge-gitlab-text' ),
    )


def sample_purge_gitlab_html():
    """Semantic HTML form of the selected GitLab purge report."""
    colouriser = HtmlColouriser()
    with cuppa.colourise.using_colouriser( colouriser ):
        text = _render_purge_gitlab( 'purge-gitlab-html', colouriser )
    return _write_html_sample( 'purge-gitlab.html', text, colouriser )


def _dependency_rows_for_list_samples():
    """Shared leaf rows for compact and verbose `--list-dependencies` samples."""
    return [
        {
            'type': 'gitlab',
            'dependency': 'boost_package',
            'short_name': 'boost_package',
            'qualifier': '1.91',
            'tool_variant': 'gcc153_rel_x86_64_cxx2c',
            'state': 'referenced',
            'size_bytes': int( 299.3 * 1024 * 1024 ),
            'last_used_epoch': NOW,
            'path': '/home/user/.cuppa/dependencies/boost/1.91/gcc153_rel_x86_64_cxx2c',
            'remote_location': 'https://gitlab.example/api/v4/projects/1/boost/1.91',
            'package_archive': 'boost_debian_gcc153_rel_x86_64_cxx2c.tar.gz',
            'has_download': True,
        },
        {
            'type': 'archive',
            'dependency': 'boost',
            'short_name': 'boost',
            'qualifier': '1.91.0',
            'tool_variant': '',
            'state': 'unreferenced',
            'size_bytes': int( 2.9 * 1024 * 1024 ),
            'last_used_epoch': NOW,
            'path': '/home/user/.cuppa/dependencies/boost/1.91.0',
            'source_url': (
                'https://archives.boost.io/release/1.91.0/source/boost_1_91_0.tar.gz'
            ),
            'remote_location': None,
            'has_download': True,
        },
        {
            'type': 'archive',
            'dependency': 'fmt',
            'short_name': 'github.com/fmtlib/fmt',
            'qualifier': '11.1.4',
            'tool_variant': '',
            'state': 'unreferenced',
            'size_bytes': int( 1.4 * 1024 * 1024 ),
            'last_used_epoch': NOW,
            'path': '/home/user/.cuppa/dependencies/github.com/fmtlib/fmt/11.1.4',
            'source_url': 'https://github.com/fmtlib/fmt/archive/refs/tags/11.1.4.zip',
            'remote_location': None,
            'has_download': True,
        },
        {
            'type': 'archive',
            'dependency': 'fmt',
            'short_name': 'github.com/fmtlib/fmt',
            'qualifier': '12.2.0',
            'tool_variant': '',
            'state': 'unreferenced',
            'size_bytes': int( 1.5 * 1024 * 1024 ),
            'last_used_epoch': NOW,
            'path': '/home/user/.cuppa/dependencies/github.com/fmtlib/fmt/12.2.0',
            'source_url': 'https://github.com/fmtlib/fmt/archive/refs/tags/12.2.0.zip',
            'remote_location': None,
            'has_download': False,
        },
    ]


def _list_dependencies_env():
    env = _FakeEnv()
    env['default_dependencies'] = [ 'boost_package' ]
    env['downloads_root'] = str( Path.home() / '.cuppa' / 'downloads' )
    return env


def _list_dependencies_data():
    data = {
        'rows': _dependency_rows_for_list_samples(),
        'dependencies_root': str( Path.home() / '.cuppa' / 'dependencies' ),
        'downloads_root': str( Path.home() / '.cuppa' / 'downloads' ),
        'skips': [],
        'estimated': False,
        'unqualified_duplicate_tokens': [],
    }
    return apply_list_scope(
            data, 'all', tree_builder=dependency_tree.build_tree,
    )


def sample_list_dependencies():
    """`--list-dependencies` hierarchical text (non-verbose)."""
    out = io.StringIO()
    write_list_dependencies_report(
            out, _list_dependencies_data(), _list_dependencies_env(),
    )
    return _write_sample(
            'list-dependencies.txt', _rewrite_sample_home( out.getvalue() ),
    )


def sample_list_dependencies_html():
    """Semantic HTML form of the `--list-dependencies` report."""
    def invoke( out ):
        write_list_dependencies_report(
                out, _list_dependencies_data(), _list_dependencies_env(),
        )

    text, colouriser = _capture_html( invoke )
    text = _rewrite_sample_home( text, colouriser )
    return _write_html_sample( 'list-dependencies.html', text, colouriser )


def sample_list_dependencies_verbose():
    """`--list-dependencies --list-format=verbose` with LOCATION / `[D]`."""
    out = io.StringIO()
    write_list_dependencies_report(
            out, _list_dependencies_data(), _list_dependencies_env(),
            verbose=True,
    )
    return _write_sample(
            'list-dependencies-verbose.txt',
            _rewrite_sample_home( out.getvalue() ),
    )


def sample_list_dependencies_verbose_html():
    """Semantic HTML form of verbose `--list-dependencies`."""
    def invoke( out ):
        write_list_dependencies_report(
                out, _list_dependencies_data(), _list_dependencies_env(),
                verbose=True,
        )

    text, colouriser = _capture_html( invoke )
    text = _rewrite_sample_home( text, colouriser )
    return _write_html_sample(
            'list-dependencies-verbose.html', text, colouriser,
    )


def _develop_copies_for_samples():
    """Shared develop copies for text and JSON `--list-develop` samples."""
    home = Path.home()
    return [
        Copy(
                name='flange',
                path=str( home / 'coding' / 'flange' ),
                exists=True,
                is_working_copy=True,
                scm='git',
                branch='spike_cache',
                detached=False,
                upstream='origin/spike_cache',
                ahead=0,
                behind=2,
                modified=False,
        ),
        Copy(
                name='gadget',
                path=str( home / 'coding' / 'gadget' ),
                exists=True,
                is_working_copy=True,
                scm='git',
                branch='master',
                detached=False,
                upstream='origin/master',
                ahead=0,
                behind=0,
                modified=False,
        ),
        Copy(
                name='gizmo',
                path=str( home / 'coding' / 'gizmo' ),
                exists=False,
                is_working_copy=True,
                scm='git',
                branch=None,
                detached=False,
                upstream=None,
                ahead=0,
                behind=0,
                modified=False,
        ),
        Copy(
                name='widget',
                path=str( home / 'coding' / 'widget' ),
                exists=True,
                is_working_copy=True,
                scm='git',
                branch='feature_orders',
                detached=False,
                upstream=None,
                ahead=0,
                behind=0,
                modified=True,
        ),
    ]


def _anonymise_home_paths( text ):
    """Stable doc paths: replace this machine's home with ``/home/user``."""
    home = str( Path.home() )
    text = text.replace( home, '/home/user' )
    # JSON may escape path separators on some platforms; keep a belt-and-braces pass.
    return text.replace( home.replace( '\\', '\\\\' ), '/home/user' )


def sample_list_develop():
    """`--list-develop` table + judgement tree."""
    lines = []

    def out( text='' ):
        lines.append( text )

    develop_report(
            _develop_copies_for_samples(),
            without_develop=[ 'boost' ],
            current_branch='feature_orders',
            default_branch='master',
            develop_active=False,
            out=out,
            suggest_update=True,
    )
    return _write_sample( 'list-develop.txt', '\n'.join( lines ) + '\n' )


def sample_list_develop_html():
    """Semantic HTML form of the `--list-develop` table and judgement tree."""
    def invoke( stream ):
        develop_report(
                _develop_copies_for_samples(),
                without_develop=[ 'boost' ],
                current_branch='feature_orders',
                default_branch='master',
                develop_active=False,
                out=lambda text='': stream.write( text + '\n' ),
                suggest_update=True,
        )

    text, colouriser = _capture_html( invoke )
    home = str( Path.home() )
    colouriser.replace( home, '~' )
    text = text.replace( home, '~' )
    return _write_html_sample( 'list-develop.html', text, colouriser )


class _FakePlatform( object ):
    def default_toolchain( self ):
        return 'gcc'


class _FakeToolchain( object ):
    def __init__(
            self, name, family, version, binary, storage_path=None, describe=None,
    ):
        self._name = name
        self._family = family
        self._version = version
        self.values = { 'CXX': binary }
        self._describe = describe
        if storage_path:
            self._toolchain_dep_root = storage_path

    def name( self ):
        return self._name

    def family( self ):
        return self._family

    def version( self ):
        return self._version

    def binary( self ):
        return self.values['CXX']

    def describe( self ):
        return self._describe


def _gcc_describe():
    return {
        'dialects': [
            'c++2c', 'c++26', 'c++2b', 'c++23', 'c++2a', 'c++20',
            'c++1z', 'c++17', 'c++1y', 'c++14', 'c++11', 'c++0x', 'c++03', 'c++98',
        ],
        'default_dialect': 'c++2c',
        'usable_features': [ 'all c++2c', 'modules (experimental)' ],
        'variants': {
            'dbg': {
                'c++': '-Wall -fexceptions -g -std=c++2c <sources>',
                'c': '-Wall -g <sources>',
                'link': (
                    '<objects> -rdynamic -Wl,-rpath=. -Xlinker -Bstatic <static_libs> '
                    '-Xlinker -Bdynamic -lpthread -lrt <dynamic_libs>'
                ),
            },
            'cov': {
                'c++': '-Wall -fexceptions -g -std=c++2c --coverage <sources>',
                'c': '-Wall -g --coverage <sources>',
                'link': (
                    '<objects> -rdynamic -Wl,-rpath=. --coverage -Xlinker -Bstatic '
                    '<static_libs> -Xlinker -Bdynamic -lpthread -lrt <dynamic_libs>'
                ),
            },
            'rel': {
                'c++': '-Wall -fexceptions -g -std=c++2c -O3 -DNDEBUG -flto=auto <sources>',
                'c': '-Wall -g -O3 -DNDEBUG <sources>',
                'link': (
                    '<objects> -rdynamic -Wl,-rpath=. -flto=auto -Xlinker -Bstatic '
                    '<static_libs> -Xlinker -Bdynamic -lpthread -lrt <dynamic_libs>'
                ),
            },
        },
    }


def _list_toolchains_fixture( work_name ):
    """Plant registered toolchain trees and return the env plus path rewrite."""
    root = _work_root( work_name )
    clang_reg = root / 'toolchains' / 'clang' / 'profiles_2026_08_07_27'
    gcc_reg = root / 'toolchains' / 'gcc' / 'gcc_snapshot_20260725_1_amd64'
    clang_bin = clang_reg / 'bin'
    gcc_bin = (
            gcc_reg / 'usr' / 'lib' / 'gcc-snapshot' / 'bin'
    )
    clang_bin.mkdir( parents=True )
    gcc_bin.mkdir( parents=True )
    ( clang_bin / 'clang++' ).write_text( 'x', encoding='utf-8' )
    ( gcc_bin / 'g++' ).write_text( 'x', encoding='utf-8' )
    # Inflate registered trees so SIZE cells are non-trivial (kept small for regen speed).
    ( clang_reg / 'pad.bin' ).write_bytes( b'x' * ( 2 * 1024 * 1024 ) )
    ( gcc_reg / 'pad.bin' ).write_bytes( b'x' * ( 8 * 1024 * 1024 ) )
    for path in ( clang_reg, gcc_reg, clang_bin, gcc_bin ):
        os.utime( path, ( NOW, NOW ) )

    env = {
        'list_format': 'text',
        'platform': _FakePlatform(),
        'toolchains': {
            'clang': _FakeToolchain(
                    'clang', 'clang', '21.1', '/usr/bin/clang++-21',
            ),
            'clang21': _FakeToolchain(
                    'clang21', 'clang', '21.1', '/usr/bin/clang++-21',
            ),
            'clang211': _FakeToolchain(
                    'clang211', 'clang', '21.1', '/usr/bin/clang++-21',
            ),
            'clang22': _FakeToolchain(
                    'clang22', 'clang', '22.1', '/usr/bin/clang++-22',
            ),
            'clang221': _FakeToolchain(
                    'clang221', 'clang', '22.1', '/usr/bin/clang++-22',
            ),
            'clang10': _FakeToolchain(
                    'clang10', 'clang', '10.0', '/usr/bin/clang++-10',
            ),
            'clang100': _FakeToolchain(
                    'clang100', 'clang', '10.0', '/usr/bin/clang++-10',
            ),
            'gcc': _FakeToolchain( 'gcc', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc15': _FakeToolchain( 'gcc15', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc153': _FakeToolchain( 'gcc153', 'gcc', '15.3', '/usr/bin/g++-15' ),
            'gcc16': _FakeToolchain( 'gcc16', 'gcc', '16.2', '/usr/bin/g++-16' ),
            'gcc162': _FakeToolchain( 'gcc162', 'gcc', '16.2', '/usr/bin/g++-16' ),
            'gcc161': _FakeToolchain( 'gcc161', 'gcc', '16.1', '/usr/bin/g++-16' ),
            'gcc9': _FakeToolchain( 'gcc9', 'gcc', '9.5', '/usr/bin/g++-9' ),
            'gcc95': _FakeToolchain( 'gcc95', 'gcc', '9.5', '/usr/bin/g++-9' ),
            'clang24_profiles_2026_08_07_27': _FakeToolchain(
                    'clang24_profiles_2026_08_07_27', 'clang', '24.0',
                    str( clang_bin / 'clang++' ),
                    storage_path=str( clang_reg ),
            ),
            'gcc17_gcc_snapshot_20260725_1_amd64': _FakeToolchain(
                    'gcc17_gcc_snapshot_20260725_1_amd64', 'gcc', '17.0',
                    str( gcc_bin / 'g++' ),
                    storage_path=str( gcc_reg ),
            ),
        },
    }
    return env, _doc_toolchain_download_prefix( root )


def sample_list_toolchains():
    """`--list-toolchains` discovered + registered tree."""
    env, ( temp_prefix, doc_prefix ) = _list_toolchains_fixture( 'list-toolchains' )
    out = io.StringIO()
    toolchain_actions.list_toolchains( env, out=out )
    text = out.getvalue().replace( temp_prefix, doc_prefix )
    return _write_sample( 'list-toolchains.txt', text )


def sample_list_toolchains_html():
    """Semantic HTML form of the `--list-toolchains` report."""
    env, ( temp_prefix, doc_prefix ) = _list_toolchains_fixture( 'list-toolchains-html' )

    def invoke( out ):
        toolchain_actions.list_toolchains( env, out=out )

    text, colouriser = _capture_html( invoke )
    colouriser.replace( temp_prefix, doc_prefix )
    text = text.replace( temp_prefix, doc_prefix )
    return _write_html_sample( 'list-toolchains.html', text, colouriser )


def _list_toolchains_verbose_env():
    """One discovered GCC with a full `describe` payload."""
    return {
        'list_format': 'verbose',
        'platform': _FakePlatform(),
        'toolchains': {
            'gcc': _FakeToolchain(
                    'gcc', 'gcc', '15.3', '/usr/bin/g++-15',
                    describe=_gcc_describe(),
            ),
            'gcc15': _FakeToolchain(
                    'gcc15', 'gcc', '15.3', '/usr/bin/g++-15',
                    describe=_gcc_describe(),
            ),
            'gcc153': _FakeToolchain(
                    'gcc153', 'gcc', '15.3', '/usr/bin/g++-15',
                    describe=_gcc_describe(),
            ),
        },
    }


def sample_list_toolchains_verbose():
    """`--list-toolchains --list-format=verbose` with one discovered GCC."""
    out = io.StringIO()
    toolchain_actions.list_toolchains( _list_toolchains_verbose_env(), out=out )
    return _write_sample( 'list-toolchains-verbose.txt', out.getvalue() )


def sample_list_toolchains_verbose_html():
    """Semantic HTML form of the verbose `--list-toolchains` report."""
    env = _list_toolchains_verbose_env()

    def invoke( out ):
        toolchain_actions.list_toolchains( env, out=out )

    text, colouriser = _capture_html( invoke )
    return _write_html_sample( 'list-toolchains-verbose.html', text, colouriser )


class _FakeBuildToolchain( object ):
    def __init__( self, name ):
        self._name = name

    def name( self ):
        return self._name


class _FakeConstruct( object ):
    def __init__( self, selections ):
        self.selections = selections

    def create_build_envs( self, toolchain, cuppa_env ):
        return [
            {
                'variant': variant,
                'target_arch': arch,
                'abi': abi,
            }
            for name, variant, arch, abi in self.selections
            if name == toolchain.name()
        ]


def _plant_variant( build_root, *parts, content=b'hello', mtime=None ):
    path = Path( build_root ).joinpath( *parts )
    working = path / 'working'
    working.mkdir( parents=True )
    blob = working / 'obj.o'
    blob.write_bytes( content )
    stamp = NOW if mtime is None else mtime
    for target in ( path, working, blob ):
        os.utime( target, ( stamp, stamp ) )
    return path


def _stamp_build_tree( build_root, mtime ):
    """Keep folder-summary ages stable (mkdir otherwise stamps the root as now)."""
    build_root = Path( build_root )
    os.utime( build_root, ( mtime, mtime ) )
    for path, _dirs, files in os.walk( build_root ):
        os.utime( path, ( mtime, mtime ) )
        for name in files:
            os.utime( os.path.join( path, name ), ( mtime, mtime ) )


def _build_env( project, **options ):
    build = project / '_build'
    build.mkdir( parents=True, exist_ok=True )
    env = _FakeEnv( options )
    env['build_root'] = '_build'
    env['abs_build_root'] = str( build )
    env['sconstruct_dir'] = str( project )
    env['list_format'] = options.get( 'list_format', 'text' )
    env['active_toolchains'] = [ _FakeBuildToolchain( 'gcc15' ) ]
    env['no_exec'] = bool( options.get( 'no_exec' ) )
    return env, build


def _plant_list_builds_fixture( build ):
    """lib dbg-only + test dbg/rel → 2 of 3 selected under `--dbg`."""
    age = NOW - 3 * DAY
    _plant_variant(
            build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c',
            content=b'x' * 20000, mtime=age,
    )
    _plant_variant(
            build, 'test', 'gcc15', 'dbg', 'x86_64', 'cxx2c',
            content=b'x' * 50000, mtime=age,
    )
    _plant_variant(
            build, 'test', 'gcc15', 'rel', 'x86_64', 'cxx2c',
            content=b'x' * 80000, mtime=age,
    )
    _stamp_build_tree( build, age )


def sample_list_builds():
    """`--list-builds` three-table report."""
    project = _work_root( 'list-builds' )
    env, build = _build_env( project, list_builds=True )
    _plant_list_builds_fixture( build )
    construct = _FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    out = io.StringIO()
    storage_actions.list_builds( construct, env, out=out )
    return _write_sample(
            'list-builds.txt',
            _rewrite_abs_build_root( out.getvalue(), str( build ) ),
    )


def sample_list_builds_html():
    """Semantic HTML form of the `--list-builds` report."""
    project = _work_root( 'list-builds-html' )
    env, build = _build_env( project, list_builds=True )
    _plant_list_builds_fixture( build )
    construct = _FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    def invoke( out ):
        storage_actions.list_builds( construct, env, out=out )

    text, colouriser = _capture_html( invoke )
    colouriser.replace( str( build ), '_build' )
    text = _rewrite_abs_build_root( text, str( build ) )
    return _write_html_sample( 'list-builds.html', text, colouriser )


def sample_remove_builds_dry_run():
    """`--remove-builds -n` dry-run tables."""
    project = _work_root( 'remove-builds-dry' )
    env, build = _build_env( project, remove_builds=True, no_exec=True )
    _plant_list_builds_fixture( build )
    construct = _FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    real_dry = storage_actions.dry_run
    storage_actions.dry_run = lambda cuppa_env: True
    try:
        out = io.StringIO()
        storage_actions.remove_builds( construct, env, out=out )
    finally:
        storage_actions.dry_run = real_dry
    return _write_sample(
            'remove-builds-dry-run.txt',
            _rewrite_abs_build_root( out.getvalue(), str( build ) ),
    )


def sample_remove_builds_dry_run_html():
    """Semantic HTML form of the `--remove-builds -n` report."""
    project = _work_root( 'remove-builds-dry-html' )
    env, build = _build_env( project, remove_builds=True, no_exec=True )
    _plant_list_builds_fixture( build )
    construct = _FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    def invoke( out ):
        real_dry = storage_actions.dry_run
        storage_actions.dry_run = lambda cuppa_env: True
        try:
            storage_actions.remove_builds( construct, env, out=out )
        finally:
            storage_actions.dry_run = real_dry

    text, colouriser = _capture_html( invoke )
    colouriser.replace( str( build ), '_build' )
    text = _rewrite_abs_build_root( text, str( build ) )
    return _write_html_sample(
            'remove-builds-dry-run.html',
            text,
            colouriser,
    )


def sample_remove_builds_error():
    """`--remove-builds` failure judgement tree (permission denied)."""
    project = _work_root( 'remove-builds-error' )
    env, build = _build_env( project, remove_builds=True )
    age = NOW - 3 * DAY
    _plant_variant(
            build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c',
            content=b'x' * 20000, mtime=age,
    )
    _stamp_build_tree( build, age )
    construct = _FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    def boom( target, dry_run=False ):
        raise OSError( 13, 'Permission denied', os.path.join( target, 'working' ) )

    real_remove = storage.remove_path
    storage.remove_path = boom
    try:
        out = io.StringIO()
        storage_actions.remove_builds( construct, env, out=out )
    finally:
        storage.remove_path = real_remove
    return _write_sample(
            'remove-builds-error.txt',
            _rewrite_abs_build_root( out.getvalue(), str( build ) ),
    )


def sample_remove_builds_error_html():
    """Semantic HTML form of a failed `--remove-builds` report."""
    project = _work_root( 'remove-builds-error-html' )
    env, build = _build_env( project, remove_builds=True )
    age = NOW - 3 * DAY
    _plant_variant(
            build, 'lib', 'gcc15', 'dbg', 'x86_64', 'cxx2c',
            content=b'x' * 20000, mtime=age,
    )
    _stamp_build_tree( build, age )
    construct = _FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )

    def boom( target, dry_run=False ):
        raise OSError( 13, 'Permission denied', os.path.join( target, 'working' ) )

    def invoke( out ):
        real_remove = storage.remove_path
        storage.remove_path = boom
        try:
            storage_actions.remove_builds( construct, env, out=out )
        finally:
            storage.remove_path = real_remove

    text, colouriser = _capture_html( invoke )
    colouriser.replace( str( build ), '_build' )
    text = _rewrite_abs_build_root( text, str( build ) )
    return _write_html_sample( 'remove-builds-error.html', text, colouriser )


def sample_remove_all_builds_dry_run():
    """`--remove-all-builds -n` dry-run."""
    project = _work_root( 'remove-all-builds-dry' )
    env, build = _build_env( project, remove_all_builds=True, no_exec=True )
    _plant_list_builds_fixture( build )
    real_dry = storage_actions.dry_run
    storage_actions.dry_run = lambda cuppa_env: True
    try:
        out = io.StringIO()
        storage_actions.remove_all_builds( env, out=out )
    finally:
        storage_actions.dry_run = real_dry
    return _write_sample(
            'remove-all-builds-dry-run.txt',
            _rewrite_abs_build_root( out.getvalue(), str( build ) ),
    )


def sample_remove_all_builds_dry_run_html():
    """Semantic HTML form of the `--remove-all-builds -n` report."""
    project = _work_root( 'remove-all-builds-dry-html' )
    env, build = _build_env( project, remove_all_builds=True, no_exec=True )
    _plant_list_builds_fixture( build )

    def invoke( out ):
        real_dry = storage_actions.dry_run
        storage_actions.dry_run = lambda cuppa_env: True
        try:
            storage_actions.remove_all_builds( env, out=out )
        finally:
            storage_actions.dry_run = real_dry

    text, colouriser = _capture_html( invoke )
    colouriser.replace( str( build ), '_build' )
    text = _rewrite_abs_build_root( text, str( build ) )
    return _write_html_sample(
            'remove-all-builds-dry-run.html',
            text,
            colouriser,
    )


def _write_json_sample( name, payload ):
    """Serialize with the same Allman formatter the CLI uses."""
    return _write_sample( name, storage.render_json_payload( payload ) + '\n' )


def _enrich_dependency_rows_for_json( rows ):
    enriched = []
    for row in rows:
        size_bytes = int( row['size_bytes'] )
        item = dict( row )
        item.setdefault( 'tool_variant', '' )
        item['size'] = storage.human_size( size_bytes )
        item['size_bytes'] = size_bytes
        item['last_used'] = _format_age_epoch( row.get( 'last_used_epoch' ) )
        item['kind'] = row['type']
        item.setdefault( 'stem', None )
        item.setdefault(
                'location', row.get( 'remote_location' ) or row.get( 'source_url' )
        )
        item.setdefault( 'download_path', None )
        item.setdefault( 'toolchain_session_name', None )
        enriched.append( item )
    return enriched


def _dependencies_json_payload( rows ):
    """Payload shape matching ``dependency_actions.list_dependencies`` JSON mode."""
    tree = dependency_tree.build_tree( rows )
    total = sum( row['size_bytes'] for row in rows )
    unreferenced = sum(
            row['size_bytes'] for row in rows if row['state'] == 'unreferenced'
    )
    return {
        'dependencies_root': '/home/user/.cuppa/dependencies',
        'scope': 'all',
        'tree': dependency_tree.tree_to_json( tree ),
        'entries': [
            {
                'size': row['size'],
                'size_bytes': row['size_bytes'],
                'dependency': row['dependency'],
                'qualifier': row['qualifier'],
                'tool_variant': row['tool_variant'],
                'last_used': row['last_used'],
                'state': row['state'],
                'path': row['path'],
                'type': row['type'],
                'kind': row['kind'],
                'short_name': row.get( 'short_name' ),
                'stem': row.get( 'stem' ),
                'source_url': row.get( 'source_url' ),
                'remote_location': row.get( 'remote_location' ),
                'location': row.get( 'location' ),
                'has_download': bool( row.get( 'has_download' ) ),
                'download_path': row.get( 'download_path' ),
                'toolchain_session_name': row.get( 'toolchain_session_name' ),
            }
            for row in rows
        ],
        'total_bytes': total,
        'unreferenced_bytes': unreferenced,
        'missing_count': 0,
        'unqualified_duplicate_tokens': [],
        'skips': [],
    }


def _gcc_describe_short():
    """Compact describe for the JSON sample (still a real ``describe()`` shape)."""
    full = _gcc_describe()
    return {
        'dialects': full['dialects'][:4],
        'default_dialect': full['default_dialect'],
        'usable_features': full['usable_features'],
        'variants': { 'dbg': full['variants']['dbg'] },
    }


def sample_list_dependencies_json():
    """Short `--list-dependencies --list-format=json` sample (one used + one leftover)."""
    # Keep the gitlab leaf and a single unreferenced archive — enough to show both sections.
    source_rows = _dependency_rows_for_list_samples()
    rows = _enrich_dependency_rows_for_json( [ source_rows[0], source_rows[1] ] )
    return _write_json_sample(
            'list-dependencies.json',
            _dependencies_json_payload( rows ),
    )


def sample_list_downloads_json():
    """Short `--list-downloads --list-format=json` sample (one archive + extract)."""
    rows = _download_rows_for_list_samples()[:2]
    tree = dependency_downloads.build_downloads_tree( rows )
    archive_rows = [ row for row in rows if row.get( 'role' ) == 'archive' ]
    total = sum( int( row['size_bytes'] ) for row in archive_rows )
    payload = {
        'downloads_root': '/home/user/.cuppa/downloads',
        'dependencies_root': '/home/user/.cuppa/dependencies',
        'scope': 'all',
        'tree': dependency_tree.tree_to_json( tree ),
        'entries': [
            {
                'kind': row.get( 'role' ),
                'size': storage.human_size( int( row.get( 'size_bytes' ) or 0 ) ),
                'size_bytes': int( row.get( 'size_bytes' ) or 0 ),
                'dependency': row.get( 'dependency' ),
                'short_name': row.get( 'short_name' ),
                'qualifier': row.get( 'qualifier' ),
                'tool_variant': row.get( 'tool_variant' ),
                'state': row.get( 'state' ),
                'type': row.get( 'type' ),
                'path': row.get( 'path' ),
                'label': row.get( 'label' ),
                'location': row.get( 'location' ),
                'source_url': row.get( 'source_url' ),
                'remote_location': row.get( 'remote_location' ),
            }
            for row in rows
        ],
        'archive_count': len( archive_rows ),
        'total_bytes': total,
        'unreferenced_bytes': 0,
        'skips': [],
    }
    return _write_json_sample( 'list-downloads.json', payload )


def sample_list_develop_json():
    """Short `--list-develop --list-format=json` (warn + error rows)."""
    copies = [
            copy for copy in _develop_copies_for_samples()
            if copy.name in ( 'flange', 'gizmo' )
    ]
    payload = develop_list_payload(
            copies,
            without_develop=[ 'boost' ],
            current_branch='feature_orders',
            default_branch='master',
            develop_active=False,
    )
    text = storage.render_json_payload( payload ) + '\n'
    return _write_sample( 'list-develop.json', _anonymise_home_paths( text ) )


def sample_list_toolchains_json():
    """Short `--list-toolchains --list-format=json` (one driver + compact describe)."""
    describe = _gcc_describe_short()
    env = {
        'list_format': 'json',
        'platform': _FakePlatform(),
        'toolchains': {
            'gcc15': _FakeToolchain(
                    'gcc15', 'gcc', '15.3', '/usr/bin/g++-15',
                    describe=describe,
            ),
            'gcc': _FakeToolchain(
                    'gcc', 'gcc', '15.3', '/usr/bin/g++-15',
                    describe=describe,
            ),
        },
    }
    out = io.StringIO()
    toolchain_actions.list_toolchains( env, out=out )
    return _write_sample( 'list-toolchains.json', out.getvalue() )


def sample_list_builds_json():
    """Short `--list-builds --list-format=json` (one sconscript, dbg selected / rel not)."""
    project = _work_root( 'list-builds-json' )
    env, build = _build_env( project, list_builds=True, list_format='json' )
    age = NOW - 3 * DAY
    _plant_variant(
            build, 'test', 'gcc15', 'dbg', 'x86_64', 'cxx2c',
            content=b'x' * 50000, mtime=age,
    )
    _plant_variant(
            build, 'test', 'gcc15', 'rel', 'x86_64', 'cxx2c',
            content=b'x' * 80000, mtime=age,
    )
    _stamp_build_tree( build, age )
    construct = _FakeConstruct( [ ( 'gcc15', 'dbg', 'x86_64', 'cxx2c' ) ] )
    out = io.StringIO()
    storage_actions.list_builds( construct, env, out=out )
    return _write_sample(
            'list-builds.json',
            _rewrite_abs_build_root( out.getvalue(), str( build ) ),
    )


GENERATORS = tuple(
        _frozen_now( generator )
        for generator in (
                sample_list_downloads,
                sample_list_downloads_html,
                sample_list_downloads_json,
                sample_list_dependencies,
                sample_list_dependencies_html,
                sample_list_dependencies_verbose,
                sample_list_dependencies_verbose_html,
                sample_list_dependencies_json,
                sample_list_develop,
                sample_list_develop_html,
                sample_list_develop_json,
                sample_list_toolchains,
                sample_list_toolchains_html,
                sample_list_toolchains_verbose,
                sample_list_toolchains_verbose_html,
                sample_list_toolchains_json,
                sample_list_builds,
                sample_list_builds_html,
                sample_list_builds_json,
                sample_remove_builds_dry_run,
                sample_remove_builds_dry_run_html,
                sample_remove_builds_error,
                sample_remove_builds_error_html,
                sample_remove_all_builds_dry_run,
                sample_remove_all_builds_dry_run_html,
                sample_remove_gitlab_dry_run,
                sample_remove_gitlab_dry_run_html,
                sample_remove_boost_product_clean,
                sample_remove_boost_product_clean_html,
                sample_purge_gitlab,
                sample_purge_gitlab_html,
        )
)

# Re-bind names so unit tests and ad-hoc calls cannot write wall-clock ages into partials.
(
        sample_list_downloads,
        sample_list_downloads_html,
        sample_list_downloads_json,
        sample_list_dependencies,
        sample_list_dependencies_html,
        sample_list_dependencies_verbose,
        sample_list_dependencies_verbose_html,
        sample_list_dependencies_json,
        sample_list_develop,
        sample_list_develop_html,
        sample_list_develop_json,
        sample_list_toolchains,
        sample_list_toolchains_html,
        sample_list_toolchains_verbose,
        sample_list_toolchains_verbose_html,
        sample_list_toolchains_json,
        sample_list_builds,
        sample_list_builds_html,
        sample_list_builds_json,
        sample_remove_builds_dry_run,
        sample_remove_builds_dry_run_html,
        sample_remove_builds_error,
        sample_remove_builds_error_html,
        sample_remove_all_builds_dry_run,
        sample_remove_all_builds_dry_run_html,
        sample_remove_gitlab_dry_run,
        sample_remove_gitlab_dry_run_html,
        sample_remove_boost_product_clean,
        sample_remove_boost_product_clean_html,
        sample_purge_gitlab,
        sample_purge_gitlab_html,
) = GENERATORS


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument(
            'sample',
            nargs='*',
            choices=(
                    'list-builds',
                    'list-develop',
                    'list-downloads',
                    'list-dependencies',
                    'list-dependencies-verbose',
                    'list-toolchains',
                    'list-toolchains-verbose',
                    'remove-builds-dry-run',
                    'remove-builds-error',
                    'remove-all-builds-dry-run',
                    'remove-gitlab-dry-run',
                    'remove-boost-product-clean',
                    'purge-gitlab',
            ),
            help='generate one semantic HTML recipe (default: all checked-in samples)',
    )
    parser.add_argument(
            '--preview',
            action='store_true',
            help='also write a standalone HTML preview under _docs_build/samples',
    )
    arguments = parser.parse_args( argv )
    if arguments.sample:
        recipes = {
            'list-builds': sample_list_builds_html,
            'list-develop': sample_list_develop_html,
            'list-downloads': sample_list_downloads_html,
            'list-dependencies': sample_list_dependencies_html,
            'list-dependencies-verbose': sample_list_dependencies_verbose_html,
            'list-toolchains': sample_list_toolchains_html,
            'list-toolchains-verbose': sample_list_toolchains_verbose_html,
            'remove-builds-dry-run': sample_remove_builds_dry_run_html,
            'remove-builds-error': sample_remove_builds_error_html,
            'remove-all-builds-dry-run': sample_remove_all_builds_dry_run_html,
            'remove-gitlab-dry-run': sample_remove_gitlab_dry_run_html,
            'remove-boost-product-clean': sample_remove_boost_product_clean_html,
            'purge-gitlab': sample_purge_gitlab_html,
        }
        generators = [ recipes[name] for name in arguments.sample ]
    else:
        generators = GENERATORS
    written = [ generator() for generator in generators ]
    if arguments.preview:
        written.extend(
                _write_preview( path )
                for path in list( written )
                if path.suffix == '.html'
        )
    for path in written:
        print( path.relative_to( ROOT ) )
    return 0


if __name__ == '__main__':
    raise SystemExit( main() )
