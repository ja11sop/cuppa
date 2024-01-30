
#          Copyright Jamie Allsop 2023-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   File Types
#-------------------------------------------------------------------------------

import os.path


_asciidoc_extensions = set([
        ".adoc",
        ".asciidoc",
])


_yml_extensions = set([
        ".yaml",
        ".yml",
])


_jinja_extensions = set([
    ".j2",
    ".jinja2",
    ".jinja"
])


def is_json_ext( ext ):
    if ext:
        return ext.lower() == ".json"
    return False


def is_html_ext( ext ):
    if ext:
        return ext.lower() == ".html"
    return False


def is_asciidoc_ext( ext ):
    if ext:
        return ext.lower() in _asciidoc_extensions
    return False


def is_yaml_ext( ext ):
    if ext:
        return ext.lower() in _yml_extensions
    return False


def is_j2_ext( ext ):
    if ext:
        return ext.lower() in _jinja_extensions
    return False


def is_json( file_path ):
    return is_json_ext( os.path.splitext( file_path )[1] )


def is_yaml( file_path ):
    return is_yaml_ext(  os.path.splitext( file_path )[1] )


def is_asciidoc( file_path ):
    return is_asciidoc_ext(  os.path.splitext( str(file_path) )[1] )


def is_html( file_path ):
    return is_html_ext(  os.path.splitext( file_path )[1] )


def is_j2_template( path ):
    inner_path, outer_extension = os.path.splitext( str(path) )
    file_path, inner_extension = os.path.splitext( inner_path )
    return is_j2_ext( outer_extension ) or is_j2_ext( inner_extension )

