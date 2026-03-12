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
Tests pour run_pipeline : sélection des étapes et structure des dossiers de sortie.

Les fonctions de chaque étape (chunking, detection, resolution, rendering) sont
mockées pour ne pas dépendre des LLMs.
"""
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from ocapi.pipeline import _DETECTION_SUBDIR, _RENDERING_SUBDIR, _RESOLUTION_SUBDIR, run_pipeline
from ocapi.types import (
    ArreteFile,
    ArticleHistory,
    ArticleVersion,
    FileType,
    NodeId,
    Operation,
    OperationType,
    Permis,
)
from ocapi.utils.io_utils import InputOutputError, save_operations

AIOT = "0005804239"

_STEP_CHUNKING = "ocapi.pipeline.step_chunking"
_STEP_DETECTION = "ocapi.pipeline.step_detection"
_STEP_RESOLUTION = "ocapi.pipeline.step_resolution"
_STEP_RENDERING = "ocapi.pipeline.step_rendering"


@pytest.fixture
def arrete_files() -> list[ArreteFile]:
    soup = BeautifulSoup('<html><body data-arretify_version="0.1.0"></body></html>', "html.parser")
    return [
        ArreteFile(
            id="2020-01-01",
            aiot=AIOT,
            filename="2020-01-01_ap d'autorisation_test.html",
            soup=soup,
            file_type=FileType.AP_AUTORISATION,
        )
    ]


@pytest.fixture
def sample_operation() -> Operation:
    return Operation(
        id="op1",
        source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
        operand="<p>new content</p>",
    )


@pytest.fixture
def sample_history(arrete_files: list[ArreteFile]) -> ArticleHistory:
    node_id = NodeId(arrete_id="2020-01-01", article_id="1")
    return {node_id: [ArticleVersion(version=0, content="<p>content</p>", operation_id=None)]}


@pytest.fixture
def sample_permis() -> Permis:
    return Permis(header="<header>H</header>", contenu="<main>C</main>", other="")


def _mock_chunking(return_docs: list[Any] | None = None) -> MagicMock:
    """Retourne un mock pour step_chunking."""
    return MagicMock(return_value=(return_docs or [MagicMock()], {}))


def _mock_detection(operations: list[Operation]) -> MagicMock:
    """Retourne un mock pour step_detection."""
    return MagicMock(return_value=operations)


def _mock_resolution(history: ArticleHistory, arrete_files: list[ArreteFile]) -> MagicMock:
    """Retourne un mock pour step_resolution."""
    return MagicMock(return_value=(history, arrete_files))


def _mock_rendering(permis: Permis) -> MagicMock:
    """Retourne un mock pour step_rendering."""
    return MagicMock(return_value=permis)


@pytest.fixture
def multi_arrete_files() -> list[ArreteFile]:
    soup = BeautifulSoup('<html><body data-arretify_version="0.1.0"></body></html>', "html.parser")
    return [
        ArreteFile(
            id="2010-01-01",
            aiot=AIOT,
            filename="2010-01-01_ap d'autorisation_test.html",
            soup=soup,
            file_type=FileType.AP_AUTORISATION,
        ),
        ArreteFile(
            id="2015-06-15",
            aiot=AIOT,
            filename="2015-06-15_ap prescriptions complémentaires_test.html",
            soup=soup,
            file_type=FileType.AP_COMPLEMENTAIRE,
        ),
        ArreteFile(
            id="2020-03-20",
            aiot=AIOT,
            filename="2020-03-20_ap prescriptions complémentaires_test.html",
            soup=soup,
            file_type=FileType.AP_COMPLEMENTAIRE,
        ),
    ]


class TestStartDate:
    """Vérifie le comportement du filtre start_date lors de la détection."""

    def test_start_date_skips_earlier_arretes(
        self,
        tmp_path: Path,
        multi_arrete_files: list[ArreteFile],
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        """Les arrêtés dont l'id <= start_date sont ignorés en détection."""
        with (
            patch(_STEP_CHUNKING, _mock_chunking()) as mock_chunk,
            patch(_STEP_DETECTION, _mock_detection([])) as mock_det,
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, multi_arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(
                multi_arrete_files, aiot=AIOT, output_dir=tmp_path, start_date="2015-06-15"
            )

        assert mock_chunk.call_count == 1
        assert mock_det.call_count == 1
        called_arrete = mock_chunk.call_args[0][0]
        assert called_arrete.id == "2020-03-20"

    def test_start_date_none_defaults_to_first_arrete(
        self,
        tmp_path: Path,
        multi_arrete_files: list[ArreteFile],
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        """Sans start_date, tous les arrêtés sont traités sauf le premier."""
        with (
            patch(_STEP_CHUNKING, _mock_chunking()) as mock_chunk,
            patch(_STEP_DETECTION, _mock_detection([])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, multi_arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(multi_arrete_files, aiot=AIOT, output_dir=tmp_path)

        assert mock_chunk.call_count == 2
        first_call_arrete = mock_chunk.call_args_list[0][0][0]
        assert first_call_arrete.id == "2015-06-15"

    def test_start_date_after_all_arretes_processes_none(
        self,
        tmp_path: Path,
        multi_arrete_files: list[ArreteFile],
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        """Si start_date >= tous les arrêtés, aucun n'est traité en détection."""
        with (
            patch(_STEP_CHUNKING) as mock_chunk,
            patch(_STEP_DETECTION) as mock_det,
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, multi_arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(
                multi_arrete_files, aiot=AIOT, output_dir=tmp_path, start_date="2020-03-20"
            )

        mock_chunk.assert_not_called()
        mock_det.assert_not_called()

    def test_start_date_passes_all_arretes_to_resolution(
        self,
        tmp_path: Path,
        multi_arrete_files: list[ArreteFile],
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        """Tous les arrêtés (y compris ignorés) sont transmis à la résolution."""
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([])),
            patch(
                _STEP_RESOLUTION, _mock_resolution(sample_history, multi_arrete_files)
            ) as mock_res,
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(
                multi_arrete_files, aiot=AIOT, output_dir=tmp_path, start_date="2015-06-15"
            )

        _, res_arrete_files = mock_res.call_args[0]
        assert len(res_arrete_files) == 3

    def test_start_date_equal_to_first_arrete_skips_it(
        self,
        tmp_path: Path,
        multi_arrete_files: list[ArreteFile],
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        """Quand start_date == id du premier arrêté, le premier est ignoré."""
        with (
            patch(_STEP_CHUNKING, _mock_chunking()) as mock_chunk,
            patch(_STEP_DETECTION, _mock_detection([])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, multi_arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(
                multi_arrete_files, aiot=AIOT, output_dir=tmp_path, start_date="2010-01-01"
            )

        assert mock_chunk.call_count == 2
        first_call_arrete = mock_chunk.call_args_list[0][0][0]
        assert first_call_arrete.id == "2015-06-15"


class TestStepList:
    """Vérifie que les bonnes étapes sont exécutées selon les flags."""

    def test_full_pipeline_calls_all_steps(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])) as mock_det,
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)) as mock_res,
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)) as mock_ren,
        ):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path, start_date="2019-01-01")

        mock_det.assert_called_once()
        mock_res.assert_called_once()
        mock_ren.assert_called_once()

    def test_no_rendering_skips_rendering_step(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING) as mock_ren,
        ):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path, enable_rendering=False)

        mock_ren.assert_not_called()

    def test_no_detection_skips_chunking_and_detection(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        save_operations([sample_operation], tmp_path / _DETECTION_SUBDIR / AIOT)

        with (
            patch(_STEP_CHUNKING) as mock_chunk,
            patch(_STEP_DETECTION) as mock_det,
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path, enable_detection=False)

        mock_chunk.assert_not_called()
        mock_det.assert_not_called()

    def test_no_detection_no_rendering_only_runs_resolution(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
    ) -> None:
        save_operations([sample_operation], tmp_path / _DETECTION_SUBDIR / AIOT)

        with (
            patch(_STEP_CHUNKING) as mock_chunk,
            patch(_STEP_DETECTION) as mock_det,
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)) as mock_res,
            patch(_STEP_RENDERING) as mock_ren,
        ):
            run_pipeline(
                arrete_files,
                aiot=AIOT,
                output_dir=tmp_path,
                enable_detection=False,
                enable_rendering=False,
            )

        mock_chunk.assert_not_called()
        mock_det.assert_not_called()
        mock_res.assert_called_once()
        mock_ren.assert_not_called()


class TestOutputDirectories:
    """Vérifie que chaque étape écrit dans le bon sous-dossier."""

    def test_detection_saves_operations_in_correct_dir(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path)

        ops_path = tmp_path / _DETECTION_SUBDIR / AIOT / "operations.json"
        assert ops_path.exists()

    def test_resolution_saves_history_in_correct_dir(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path)

        history_path = tmp_path / _RESOLUTION_SUBDIR / AIOT / "history.json"
        assert history_path.exists()

    def test_rendering_saves_permis_in_correct_dir(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path)

        permis_path = tmp_path / _RENDERING_SUBDIR / AIOT / "permis_consolidé.html"
        assert permis_path.exists()

    def test_no_rendering_does_not_create_rendering_dir(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING),
        ):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path, enable_rendering=False)

        rendering_dir = tmp_path / _RENDERING_SUBDIR / AIOT
        assert not rendering_dir.exists()

    def test_aiot_is_used_as_subdir(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        custom_aiot = "9999999999"
        for af in arrete_files:
            af.aiot = custom_aiot

        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            run_pipeline(arrete_files, aiot=custom_aiot, output_dir=tmp_path)

        assert (tmp_path / _DETECTION_SUBDIR / custom_aiot / "operations.json").exists()
        assert (tmp_path / _RESOLUTION_SUBDIR / custom_aiot / "history.json").exists()
        assert (tmp_path / _RENDERING_SUBDIR / custom_aiot / "permis_consolidé.html").exists()


class TestNoDetectionLoadsBehavior:
    """Vérifie le comportement de chargement des opérations existantes."""

    def test_no_detection_loads_operations_from_disk(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        save_operations([sample_operation], tmp_path / _DETECTION_SUBDIR / AIOT)

        with (
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)) as mock_res,
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            ops, _, _, _ = run_pipeline(
                arrete_files, aiot=AIOT, output_dir=tmp_path, enable_detection=False
            )

        loaded_ops = mock_res.call_args[0][0]
        assert len(loaded_ops) == 1
        assert loaded_ops[0].id == "op1"

    def test_no_detection_raises_if_operations_file_missing(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
    ) -> None:
        with pytest.raises(InputOutputError, match="introuvable"):
            run_pipeline(arrete_files, aiot=AIOT, output_dir=tmp_path, enable_detection=False)

    def test_full_pipeline_returns_detected_operations(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
        sample_permis: Permis,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING, _mock_rendering(sample_permis)),
        ):
            ops, history, _, permis = run_pipeline(
                arrete_files, aiot=AIOT, output_dir=tmp_path, start_date="2019-01-01"
            )

        assert len(ops) == 1
        assert ops[0].id == "op1"
        assert permis is not None

    def test_no_rendering_returns_none_permis(
        self,
        tmp_path: Path,
        arrete_files: list[ArreteFile],
        sample_operation: Operation,
        sample_history: ArticleHistory,
    ) -> None:
        with (
            patch(_STEP_CHUNKING, _mock_chunking()),
            patch(_STEP_DETECTION, _mock_detection([sample_operation])),
            patch(_STEP_RESOLUTION, _mock_resolution(sample_history, arrete_files)),
            patch(_STEP_RENDERING),
        ):
            _, _, _, permis = run_pipeline(
                arrete_files, aiot=AIOT, output_dir=tmp_path, enable_rendering=False
            )

        assert permis is None
