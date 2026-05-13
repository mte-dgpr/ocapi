#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
import logging
import tempfile
import unittest
from pathlib import Path

import pytest
from bs4 import Tag

from ocapi.types import (
    ArticleHistory,
    ArticleVersion,
    ErrorCode,
    FileType,
    NodeId,
    Operation,
    OperationType,
)
from ocapi.utils.io_utils import (
    InputOutputError,
    article_history_to_json_dict,
    filter_and_deduplicate_arrete_files,
    initialize_arrete_files,
    load_document_contexts,
    load_html_files,
    load_operations,
    save_history,
    save_operations,
    save_tagged_html_file,
)
from ocapi.utils.testing import make_testing_arrete, make_testing_op

# Minimal valid Arrêtify HTML (version 0.2.0)
_VALID_HTML = '<html><body data-arretify_version="0.2.0"><p>Content</p></body></html>'
# HTML without data-arretify_version attribute
_HTML_NO_VERSION = "<html><body><p>Content without version</p></body></html>"
# HTML with unsupported Arrêtify version
_HTML_UNSUPPORTED_VERSION = '<html><body data-arretify_version="0.1.0"><p>Content</p></body></html>'


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


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


class TestLoadDocumentContexts:
    def test_loads_pairs_with_shared_soup(self, tmp_path: Path) -> None:
        _write(tmp_path / "2021-06-15_ap prescriptions complémentaires_foo.html", _VALID_HTML)

        result = load_document_contexts(tmp_path, aiot="0001234567")

        assert len(result) == 1
        arrete_file, document_context = result[0]
        assert arrete_file.id == "2021-06-15"
        assert arrete_file.file_type == FileType.AP_COMPLEMENTAIRE
        assert arrete_file.soup is document_context.soup
        assert document_context.soup.find("body") is not None

    def test_skips_unsupported_arretify_version(self, tmp_path: Path) -> None:
        _write(tmp_path / "2020-01-01.html", _HTML_UNSUPPORTED_VERSION)

        result = load_document_contexts(tmp_path, aiot="0001234567")

        assert result == []


class TestSaveTaggedHtmlFile:
    def test_writes_prettified_soup(self, tmp_path: Path) -> None:
        _write(tmp_path / "2021-06-15_ap prescriptions complémentaires_foo.html", _VALID_HTML)
        pairs = load_document_contexts(tmp_path, aiot="0001234567")
        _, document_context = pairs[0]

        output_path = tmp_path / "out" / "tagged.html"
        save_tagged_html_file(document_context, output_path)

        assert output_path.exists()
        assert "<p>" in output_path.read_text(encoding="utf-8")

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        _write(tmp_path / "2021-06-15_ap prescriptions complémentaires_foo.html", _VALID_HTML)
        pairs = load_document_contexts(tmp_path, aiot="0001234567")
        _, document_context = pairs[0]

        nested = tmp_path / "deep" / "nested" / "path" / "tagged.html"
        save_tagged_html_file(document_context, nested)

        assert nested.exists()


class TestSaveOperations:
    def test_creates_operations_json(self, tmp_path: Path) -> None:
        save_operations([make_testing_op(OperationType.REPLACE)], tmp_path)
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
        op = make_testing_op(
            OperationType.REPLACE, operation_id="op-xyz", operand="<p>new content</p>"
        )
        save_operations([op], tmp_path)
        data = json.loads((tmp_path / "operations.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["id"] == "op-xyz"
        assert data[0]["operation_type"] == "REPLACE"
        assert data[0]["operand"] == "<p>new content</p>"

    def test_multiple_operations_are_saved(self, tmp_path: Path) -> None:
        ops = [
            make_testing_op(OperationType.REPLACE, operation_id="op1"),
            make_testing_op(OperationType.REPLACE, operation_id="op2"),
            make_testing_op(OperationType.REPLACE, operation_id="op3"),
        ]
        save_operations(ops, tmp_path)
        data = json.loads((tmp_path / "operations.json").read_text(encoding="utf-8"))
        assert len(data) == 3
        assert [d["id"] for d in data] == ["op1", "op2", "op3"]


class TestLoadOperations:
    def test_loads_previously_saved_operations(self, tmp_path: Path) -> None:
        ops = [make_testing_op(OperationType.REPLACE, operation_id="op1")]
        save_operations(ops, tmp_path)
        loaded = load_operations(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].id == "op1"

    def test_raises_input_output_error_if_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(InputOutputError, match="introuvable"):
            load_operations(tmp_path)

    def test_raises_input_output_error_on_invalid_operation_item(self, tmp_path: Path) -> None:
        (tmp_path / "operations.json").write_text(
            json.dumps([{"id": "bad", "not_a_valid_operation": True}]),
            encoding="utf-8",
        )
        with pytest.raises(InputOutputError, match="Cannot parse operations file"):
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
        ops = [make_testing_op(OperationType.REPLACE, operation_id=f"op{i}") for i in range(5)]
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
                ArticleVersion(version=0, title="", content="<p>original</p>", operation_id=None),
                ArticleVersion(version=1, title="", content="<p>modified</p>", operation_id="op1"),
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
                ArticleVersion(version=0, title="", content="A", operation_id=None)
            ],
            NodeId(arrete_id="2020-01-01", article_id="2"): [
                ArticleVersion(version=0, title="", content="B", operation_id=None)
            ],
        }
        save_history(history, tmp_path)
        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert "2020-01-01#1" in data
        assert "2020-01-01#2" in data

    def test_error_codes_is_serialized_as_sorted_list(self, tmp_path: Path) -> None:
        node_id = NodeId(arrete_id="2020-01-01", article_id="1")
        history: ArticleHistory = {
            node_id: [
                ArticleVersion(
                    version=0,
                    title="",
                    content="<p>x</p>",
                    operation_id=None,
                    error_codes=frozenset(
                        {
                            ErrorCode.ERROR_EXTRACTING_OPERAND,
                            ErrorCode.PROPAGATED_ERROR,
                        }
                    ),
                )
            ]
        }
        save_history(history, tmp_path)
        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert data["2020-01-01#1"][0]["error_codes"] == [
            "error_extracting_operand",
            "propagated_error",
        ]


class TestFilterAndDeduplicateArreteFiles:
    """Tests for filter_and_deduplicate_arrete_files."""

    # --- excluded file types ---

    @pytest.mark.parametrize(
        "pattern",
        [
            "rapport",
            "rapport d'ap d'autorisation",
            "document de procédure",
            "fiche seveso",
            "inspection",
            "arrêté de mise en demeure",
            "ap mise en demeure",
            "ap levée de mise en demeure",
            "ap mesures conservatoires",
            "ap mesures d'urgence",
        ],
    )
    def test_excludes_various_non_ap_types(self, pattern: str) -> None:
        files = [
            make_testing_arrete(
                "2020-01-01",
                _VALID_HTML,
                filename=f"2020-01-01_{pattern}.html",
                file_type=FileType.AUTRE,
            ),
        ]
        assert filter_and_deduplicate_arrete_files(files) == []

    def test_keeps_ap_autorisation(self) -> None:
        files = [
            make_testing_arrete(
                "2020-01-01",
                _VALID_HTML,
                filename="2020-01-01_ap d'autorisation.html",
                file_type=FileType.AP_AUTORISATION,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].filename == "2020-01-01_ap d'autorisation.html"

    # --- same date + same type + identical checksum ---

    def test_dedup_same_date_type_identical_content(self, caplog: pytest.LogCaptureFixture) -> None:
        html = '<html><body data-arretify_version="0.2.0"><p>Same</p></body></html>'
        files = [
            make_testing_arrete(
                "2023-09-12",
                html,
                filename="2023-09-12_ap prescriptions complémentaires_a.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            ),
            make_testing_arrete(
                "2023-09-12",
                html,
                filename="2023-09-12_ap prescriptions complémentaires_b.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            ),
        ]
        with caplog.at_level(logging.INFO, logger="ocapi.utils.io_utils"):
            result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].filename == files[0].filename
        assert "AP doublon rencontré" in caplog.text
        assert "identique" in caplog.text

    # --- same date + same type + different checksum ---

    def test_dedup_same_date_type_different_content(self, caplog: pytest.LogCaptureFixture) -> None:
        html_a = '<html><body data-arretify_version="0.2.0"><p>Version A</p></body></html>'
        html_b = '<html><body data-arretify_version="0.2.0"><p>Version B</p></body></html>'
        files = [
            make_testing_arrete(
                "2023-09-12",
                html_a,
                filename="2023-09-12_ap prescriptions complémentaires_a.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            ),
            make_testing_arrete(
                "2023-09-12",
                html_b,
                filename="2023-09-12_ap prescriptions complémentaires_b.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].filename == files[0].filename
        assert "Deux documents différents rencontrés" in caplog.text

    # --- same date + different types → keep highest priority ---

    def test_dedup_same_date_different_types_keeps_highest_priority(self) -> None:
        files = [
            make_testing_arrete(
                "2020-11-03",
                _VALID_HTML,
                filename="2020-11-03_arrêté préfectoral_a.html",
                file_type=FileType.ARRETE_PREFECTORAL,
            ),
            make_testing_arrete(
                "2020-11-03",
                _VALID_HTML,
                filename="2020-11-03_ap prescriptions complémentaires_b.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].file_type == FileType.ARRETE_PREFECTORAL

    def test_dedup_ap_autorisation_wins_over_arrete_prefectoral(self) -> None:
        files = [
            make_testing_arrete(
                "2022-02-02",
                _VALID_HTML,
                filename="2022-02-02_ap prescriptions complémentaires.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            ),
            make_testing_arrete(
                "2022-02-02",
                _VALID_HTML,
                filename="2022-02-02_ap d'autorisation.html",
                file_type=FileType.AP_AUTORISATION,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].file_type == FileType.AP_AUTORISATION

    # --- mixed: excluded + duplicates ---

    def test_excludes_rapport_and_keeps_ap_on_same_date(self) -> None:
        files = [
            make_testing_arrete(
                "2017-09-22",
                _VALID_HTML,
                filename="2017-09-22_arrêté préfectoral.html",
                file_type=FileType.ARRETE_PREFECTORAL,
            ),
            make_testing_arrete(
                "2017-09-22",
                _VALID_HTML,
                filename="2017-09-22_rapport.html",
                file_type=FileType.AUTRE,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].file_type == FileType.ARRETE_PREFECTORAL

    def test_five_identical_duplicates_keeps_one(self) -> None:
        html = '<html><body data-arretify_version="0.2.0"><p>Same content</p></body></html>'
        files = [
            make_testing_arrete(
                "2024-01-17",
                html,
                filename=f"2024-01-17_ap prescriptions complémentaires_{i}.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            )
            for i in range(5)
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1

    def test_preserves_order_across_dates(self) -> None:
        files = [
            make_testing_arrete(
                "2020-01-01",
                _VALID_HTML,
                filename="2020-01-01_arrêté préfectoral.html",
                file_type=FileType.ARRETE_PREFECTORAL,
            ),
            make_testing_arrete(
                "2021-06-15",
                _VALID_HTML,
                filename="2021-06-15_ap prescriptions complémentaires.html",
                file_type=FileType.AP_COMPLEMENTAIRE,
            ),
            make_testing_arrete(
                "2023-12-01",
                _VALID_HTML,
                filename="2023-12-01_ap d'autorisation.html",
                file_type=FileType.AP_AUTORISATION,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert [af.id for af in result] == ["2020-01-01", "2021-06-15", "2023-12-01"]

    def test_empty_input(self) -> None:
        assert filter_and_deduplicate_arrete_files([]) == []

    def test_single_file_passes_through(self) -> None:
        files = [
            make_testing_arrete(
                "2020-01-01",
                _VALID_HTML,
                filename="2020-01-01_arrêté préfectoral.html",
                file_type=FileType.ARRETE_PREFECTORAL,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0] is files[0]

    # --- annexe handling (ticket #64) ---

    def test_annexes_merged_into_base_with_existing_appendix(self) -> None:
        base_html = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='base-main'>base</section></main>"
            "<footer data-spec=\"appendix\"><section id='orig-app'>orig</section></footer>"
            "</body></html>"
        )
        annexe_html = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='ann1'>annexe 1</section></main>"
            "</body></html>"
        )
        files = [
            make_testing_arrete(
                "2024-09-26",
                base_html,
                filename="2024-09-26_ap d'autorisation.html",
                file_type=FileType.AP_AUTORISATION,
            ),
            make_testing_arrete(
                "2024-09-26",
                annexe_html,
                filename="2024-09-26_ap d'autorisation_Annexe 1.html",
                file_type=FileType.AP_AUTORISATION,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].filename == "2024-09-26_ap d'autorisation.html"
        appendix = result[0].soup.find("footer", attrs={"data-spec": "appendix"})
        assert isinstance(appendix, Tag)
        section_ids = [s.get("id") for s in appendix.find_all("section")]
        assert section_ids == ["orig-app", "ann1"]

    def test_annexes_merged_creates_appendix_when_missing(self) -> None:
        base_html = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='base-main'>base</section></main>"
            "</body></html>"
        )
        annexe_a = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='ann2a'>2-a</section></main>"
            "</body></html>"
        )
        annexe_b = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='ann1'>1</section></main>"
            "</body></html>"
        )
        files = [
            make_testing_arrete(
                "2024-09-26",
                base_html,
                filename="2024-09-26_ap d'autorisation.html",
                file_type=FileType.AP_AUTORISATION,
            ),
            make_testing_arrete(
                "2024-09-26",
                annexe_a,
                filename="2024-09-26_ap d'autorisation_Annexe 2-a.html",
                file_type=FileType.AP_AUTORISATION,
            ),
            make_testing_arrete(
                "2024-09-26",
                annexe_b,
                filename="2024-09-26_ap d'autorisation_Annexe 1.html",
                file_type=FileType.AP_AUTORISATION,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].filename == "2024-09-26_ap d'autorisation.html"
        appendix = result[0].soup.find("footer", attrs={"data-spec": "appendix"})
        assert isinstance(appendix, Tag)
        section_ids = [s.get("id") for s in appendix.find_all("section")]
        assert section_ids == ["ann2a", "ann1"]

    def test_single_annexe_is_kept(self) -> None:
        annexe_html = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='ann2a'>2-a</section></main>"
            "</body></html>"
        )
        files = [
            make_testing_arrete(
                "2024-09-26",
                annexe_html,
                filename="2024-09-26_ap d'autorisation_Annexe 2-a.html",
                file_type=FileType.AP_AUTORISATION,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0] is files[0]

    def test_only_annexes_first_becomes_base(self) -> None:
        annexe_a = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='ann2a'>2-a</section></main>"
            "</body></html>"
        )
        annexe_b = (
            '<html><body data-arretify_version="0.2.0">'
            "<main data-spec=\"main\"><section id='ann1'>1</section></main>"
            "</body></html>"
        )
        files = [
            make_testing_arrete(
                "2024-09-26",
                annexe_a,
                filename="2024-09-26_ap d'autorisation_Annexe 2-a.html",
                file_type=FileType.AP_AUTORISATION,
            ),
            make_testing_arrete(
                "2024-09-26",
                annexe_b,
                filename="2024-09-26_ap d'autorisation_Annexe 1.html",
                file_type=FileType.AP_AUTORISATION,
            ),
        ]
        result = filter_and_deduplicate_arrete_files(files)
        assert len(result) == 1
        assert result[0].filename == "2024-09-26_ap d'autorisation_Annexe 2-a.html"
        appendix = result[0].soup.find("footer", attrs={"data-spec": "appendix"})
        assert isinstance(appendix, Tag)
        section_ids = [s.get("id") for s in appendix.find_all("section")]
        assert section_ids == ["ann1"]


def test_article_history_to_json_dict_matches_save_history_shape() -> None:
    node_id = NodeId(arrete_id="2020-01-01", article_id="1")
    v: ArticleVersion = {
        "version": 0,
        "title": "",
        "content": "c",
        "operation_id": None,
        "error_codes": frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}),
    }
    assert article_history_to_json_dict({node_id: [v]}) == {
        "2020-01-01#1": [
            {
                "version": 0,
                "title": "",
                "content": "c",
                "operation_id": None,
                "error_codes": ["error_extracting_operand"],
            }
        ]
    }
