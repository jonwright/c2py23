"""Unit tests for c2py23.harvester: C2PY_BEGIN/END block extraction.

These exercises the Python-side block harvester that reads embedded
interface dicts out of C/C++ sources -- the path with the lowest line
coverage (harvester.py ~55%).

Python 2.7 - 3.15 compatible.  Pure Python; no extension build needed.
"""

from __future__ import print_function

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from c2py23.harvester import _extract_blocks, extract_from_file, extract_from_dir


def _c_text(body):
    return "/******************\n * C2PY_BEGIN\n" + body + "\n * C2PY_END\n ********************/\n"


def test_extract_single_block():
    text = _c_text(
        '{\n'
        '    "module": "m",\n'
        '    "source": ["m.c"],\n'
        '    "functions": [{"py_sig": "f(x: int) -> int"}],\n'
        '}'
    )
    blocks = list(_extract_blocks(text))
    assert len(blocks) == 1
    _, obj = blocks[0]
    assert obj["module"] == "m"
    assert obj["functions"][0]["py_sig"] == "f(x: int) -> int"


def test_extract_strips_leading_star_comment():
    text = "/**\n * C2PY_BEGIN\n * {\n * \"module\": \"m\"\n * }\n * C2PY_END\n */\n"
    _, obj = list(_extract_blocks(text))[0]
    assert obj["module"] == "m"


def test_extract_true_false_literals():
    text = _c_text(
        '{\n'
        '    "module": "m",\n'
        '    "timing": true,\n'
        '    "free_threading": false,\n'
        '    "functions": [],\n'
        '}'
    )
    _, obj = list(_extract_blocks(text))[0]
    assert obj["timing"] is True
    assert obj["free_threading"] is False


def test_extract_multiple_blocks():
    text = _c_text('{"module": "m", "functions": []}') + "\n\n" + _c_text('{"constants": {"A": 1}}')
    blocks = list(_extract_blocks(text))
    assert len(blocks) == 2


def test_extract_per_function_blocks():
    text = (
        _c_text('{"module": "m", "source": ["m.c"]}')
        + "\n\n"
        + _c_text('{"py_sig": "a(x: int) -> int"}')
        + "\n\n"
        + _c_text('{"py_sig": "b(y: float) -> float"}')
    )
    path = _write_tmp(text)
    merged = extract_from_file(path)
    assert merged["module"] == "m"
    assert [f["py_sig"] for f in merged["functions"]] == [
        "a(x: int) -> int",
        "b(y: float) -> float",
    ]


def _write_tmp(text, suffix=".c"):
    path = tempfile.mktemp(suffix=suffix)
    with open(path, "w") as f:
        f.write(text)
    return path


def test_extract_from_file_constants_override():
    path = _write_tmp(
        _c_text('{"module": "m", "constants": {"A": 1}}')
        + "\n\n"
        + _c_text('{"constants": {"A": 2, "B": 3}}')
    )
    merged = extract_from_file(path)
    assert merged["module"] == "m"
    assert merged["constants"] == {"A": 2, "B": 3}


def test_extract_from_file_malformed_raises():
    path = _write_tmp(_c_text("this is { not valid"))
    with pytest.raises(Exception):
        extract_from_file(path)


def test_extract_from_dir_merges_c_and_h():
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "a.c"), "w") as f:
        f.write(_c_text('{"module": "m", "functions": []}'))
    with open(os.path.join(d, "b.h"), "w") as f:
        f.write(_c_text('{"py_sig": "z(x: int) -> int"}'))
    # Only .c/.h touched; b.h contributes a function.
    merged = extract_from_dir(d)
    assert merged["module"] == "m"
    assert any(f["py_sig"] == "z(x: int) -> int" for f in merged.get("functions", []))


def test_extract_from_file_does_not_see_other_comments():
    text = "/* just a normal comment, no C2PY block */\n"
    blocks = list(_extract_blocks(text))
    assert blocks == []
