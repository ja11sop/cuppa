#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

import pytest

from cuppa.utility.dict_tools import args_from_dict


pytestmark = pytest.mark.unit


def test_args_from_dict_evaluates_callables():
    assert args_from_dict(None) == {}
    assert args_from_dict("x") == {}
    assert args_from_dict({"a": 1, "b": lambda: 2}) == {"a": 1, "b": 2}
