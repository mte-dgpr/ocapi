#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Tests for I/O utilities: load_html_files, initialize_arrete_files,
save_operations, load_operations, save_history.
"""
import json
import tempfile
import unittest
from pathlib import Path

import pytest

from ocapi.types import (
    ArticleHistory,
    ArticleVersion,
    FileType,
    NodeId,
    Operation,
    OperationType,
    StatusCode,
)
from ocapi.utils.io_utils import (
    InputOutputError,
    article_history_to_json_dict,
    initialize_arrete_files,
    load_html_files,
    load_operations,
    save_history,
    save_operations,
)

# Minimal valid Arrêtify HTML (version 0.1.0)
_VALID_HTML = '<html><body data-arretify_version="0.1.0"><p>Content</p></body></html>'
# HTML without data-arretify_version attribute
_HTML_NO_VERSION = "<html><body><p>Content without version</p></body></html>"
# HTML with unsupported Arrêtify version
_HTML_UNSUPPORTED_VERSION = '<html><body data-arretify_version="0.2.0"><p>Content</p></body></html>'


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _make_operation(op_id: str = "op1") -> Operation:
    return Operation(
        id=op_id,
        source_id=NodeId(arrete_id="2021-06-15", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<p>new content</p>",
    )


class TestLoadHtmlFiles(unittest.TestCase):
    """Tests for load_html_files."""

    def test_raises_if_directory_does_not_exist(self) -> None:
        with self.assertRaises(InputOutputError) as ctx:
            load_html_files(Path("/tmp/nonexistent_ocapi_dir"))
        assert "does not exist" in str(ctx.exception)

    def test_raises_if_path_is_a_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".html") as f:
            with self.assertRaises(InputOutputError) as ctx:
                load_html_files(Path(f.name))
        assert "not a directory" in str(ctx.exception)

    def test_raises_if_no_html_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "readme.txt").write_text("text", encoding="utf-8")
            with self.assertRaises(InputOutputError) as ctx:
                load_html_files(Path(d))
        assert "No HTML files found" in str(ctx.exception)

    def test_returns_sorted_html_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root / "2023-01-01.html", _VALID_HTML)
            _write(root / "2021-06-15.html", _VALID_HTML)
            _write(root / "2025-12-31.html", _VALID_HTML)
            _write(root / "not_html.txt", "ignored")

            result = load_html_files(root)

        assert [p.name for p in result] == [
            "2021-06-15.html",
            "2023-01-01.html",
            "2025-12-31.html",
        ]

    def test_ignores_non_html_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root / "2023-01-01.html", _VALID_HTML)
            _write(root / "document.pdf", "pdf")
            _write(root / "notes.txt", "txt")

            result = load_html_files(root)

        assert len(result) == 1
        assert result[0].name == "2023-01-01.html"


class TestInitializeArreteFiles(unittest.TestCase):
    """Tests for initialize_arrete_files."""

    def test_loads_legacy_format_with_type(self) -> None:
        """A YYYY-MM-DD_type_desc.html file is loaded correctly."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root / "2020-04-30_ap prescriptions complémentaires_desc.html", _VALID_HTML)

            result = initialize_arrete_files(
                [root / "2020-04-30_ap prescriptions complémentaires_desc.html"],
                aiot="0001234567",
            )

        assert len(result) == 1
        assert result[0].id == "2020-04-30"
        assert result[0].file_type == FileType.AP_COMPLEMENTAIRE

    def test_skips_file_with_invalid_name(self) -> None:
        """A file with an invalid name is skipped without raising."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write(root / "invalid_name.html", _VALID_HTML)

            result = initialize_arrete_files([root / "invalid_name.html"], aiot="0001234567")

        assert result == []

    def test_empty_list_returns_empty(self) -> None:
        """An empty input list returns an empty list without error."""
        result = initialize_arrete_files([], aiot="0001234567")
        assert result == []


class TestSaveOperations:
    def test_creates_operations_json(self, tmp_path: Path) -> None:
        save_operations([_make_operation()], tmp_path)
        assert (tmp_path / "operations.json").exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        save_operations([], nested)
        assert (nested / "operations.json").exists()

    def test_empty_list_saves_empty_array(self, tmp_path: Path) -> None:
        save_operations([], tmp_path)
        data = json.loads((tmp_path / "operations.json").read_text(encoding="utf-8"))
        assert data == []

    def test_saved_json_contains_operation_fields(self, tmp_path: Path) -> None:
        op = _make_operation("op-xyz")
        save_operations([op], tmp_path)
        data = json.loads((tmp_path / "operations.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["id"] == "op-xyz"
        assert data[0]["operation_type"] == "REPLACE"
        assert data[0]["operand"] == "<p>new content</p>"

    def test_multiple_operations_are_saved(self, tmp_path: Path) -> None:
        ops = [_make_operation("op1"), _make_operation("op2"), _make_operation("op3")]
        save_operations(ops, tmp_path)
        data = json.loads((tmp_path / "operations.json").read_text(encoding="utf-8"))
        assert len(data) == 3
        assert [d["id"] for d in data] == ["op1", "op2", "op3"]


class TestLoadOperations:
    def test_loads_previously_saved_operations(self, tmp_path: Path) -> None:
        ops = [_make_operation("op1")]
        save_operations(ops, tmp_path)
        loaded = load_operations(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].id == "op1"

    def test_raises_input_output_error_if_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(InputOutputError, match="introuvable"):
            load_operations(tmp_path)

    def test_roundtrip_preserves_source_and_target(self, tmp_path: Path) -> None:
        op = Operation(
            id="op-rt",
            source_id=NodeId(arrete_id="2022-03-10", article_id="3.1"),
            target_id=NodeId(arrete_id="2021-01-01", article_id="ALL"),
            operation_type=OperationType.REMOVE,
        )
        save_operations([op], tmp_path)
        loaded = load_operations(tmp_path)
        assert loaded[0].source_id.arrete_id == "2022-03-10"
        assert loaded[0].source_id.article_id == "3.1"
        assert loaded[0].target_id.article_id == "ALL"
        assert loaded[0].operand is None

    def test_roundtrip_preserves_operation_type(self, tmp_path: Path) -> None:
        for op_type in (OperationType.ADD, OperationType.REMOVE, OperationType.REPLACE):
            op = Operation(
                id=f"op-{op_type.value}",
                source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
                target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
                operation_type=op_type,
            )
            save_operations([op], tmp_path)
            loaded = load_operations(tmp_path)
            assert loaded[0].operation_type == op_type

    def test_loads_multiple_operations(self, tmp_path: Path) -> None:
        ops = [_make_operation(f"op{i}") for i in range(5)]
        save_operations(ops, tmp_path)
        loaded = load_operations(tmp_path)
        assert len(loaded) == 5
        assert [o.id for o in loaded] == [f"op{i}" for i in range(5)]


class TestSaveHistory:
    def test_creates_history_json(self, tmp_path: Path) -> None:
        save_history({}, tmp_path)
        assert (tmp_path / "history.json").exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "x" / "y"
        save_history({}, nested)
        assert (nested / "history.json").exists()

    def test_empty_history_saves_empty_object(self, tmp_path: Path) -> None:
        save_history({}, tmp_path)
        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert data == {}

    def test_node_id_serialized_as_string_key(self, tmp_path: Path) -> None:
        node_id = NodeId(arrete_id="2020-01-01", article_id="1")
        history: ArticleHistory = {node_id: []}
        save_history(history, tmp_path)
        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert "2020-01-01#1" in data

    def test_versions_content_is_preserved(self, tmp_path: Path) -> None:
        node_id = NodeId(arrete_id="2020-01-01", article_id="1")
        history: ArticleHistory = {
            node_id: [
                ArticleVersion(version=0, content="<p>original</p>", operation_id=None),
                ArticleVersion(version=1, content="<p>modified</p>", operation_id="op1"),
            ]
        }
        save_history(history, tmp_path)
        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        versions = data["2020-01-01#1"]
        assert len(versions) == 2
        assert versions[0]["content"] == "<p>original</p>"
        assert versions[0]["operation_id"] is None
        assert versions[1]["content"] == "<p>modified</p>"
        assert versions[1]["operation_id"] == "op1"

    def test_multiple_articles_are_all_saved(self, tmp_path: Path) -> None:
        history: ArticleHistory = {
            NodeId(arrete_id="2020-01-01", article_id="1"): [
                ArticleVersion(version=0, content="A", operation_id=None)
            ],
            NodeId(arrete_id="2020-01-01", article_id="2"): [
                ArticleVersion(version=0, content="B", operation_id=None)
            ],
        }
        save_history(history, tmp_path)
        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert "2020-01-01#1" in data
        assert "2020-01-01#2" in data

    def test_status_code_is_serialized_as_string_value(self, tmp_path: Path) -> None:
        node_id = NodeId(arrete_id="2020-01-01", article_id="1")
        history: ArticleHistory = {
            node_id: [
                ArticleVersion(
                    version=0,
                    content="<p>x</p>",
                    operation_id=None,
                    status_code=StatusCode.ERROR_EXTRACTING_OPERAND,
                )
            ]
        }
        save_history(history, tmp_path)
        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert data["2020-01-01#1"][0]["status_code"] == "error_extracting_operand"


def test_article_history_to_json_dict_matches_save_history_shape() -> None:
    node_id = NodeId(arrete_id="2020-01-01", article_id="1")
    v: ArticleVersion = {
        "version": 0,
        "content": "c",
        "operation_id": None,
        "status_code": StatusCode.RESOLVED,
    }
    assert article_history_to_json_dict({node_id: [v]}) == {
        "2020-01-01#1": [
            {"version": 0, "content": "c", "operation_id": None, "status_code": "resolved"}
        ]
    }
