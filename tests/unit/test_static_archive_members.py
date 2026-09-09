#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

"""Unit tests for static archive member uniquify helpers."""

import pytest

from cuppa.utility.static_archive_members import (
    archive_member_name,
    basenames_collide,
)


pytestmark = pytest.mark.unit


def test_archive_member_name_flattens_working_relative_path():
    assert archive_member_name( 'src/detail/except.o' ) == 'src_detail_except.o'
    assert archive_member_name( 'src/buffers/detail/except.o' ) == 'src_buffers_detail_except.o'
    assert archive_member_name( 'except.o' ) == 'except.o'


def test_basenames_collide_detects_duplicate_leaf_names():
    assert basenames_collide( [ 'a/except.o', 'b/except.o' ] ) is True
    assert basenames_collide( [ 'a/except.o', 'b/other.o' ] ) is False
    assert basenames_collide( [] ) is False
