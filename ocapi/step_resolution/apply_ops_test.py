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
import unittest
from unittest import mock

import networkx as nx
from bs4 import BeautifulSoup

from ocapi.step_resolution.apply_ops import (
    apply_all_ops,
    apply_subgraph_operations,
    build_next_subgraph,
)
from ocapi.step_resolution.build_op_graph import add_edge, add_node
from ocapi.types import ArreteFile, ArticleHistory, NodeId, Operation, OperationType


class TestApplyReplace(unittest.TestCase):
    pass  # Tester LLM... éviter le parsing à la main ?


class TestBuildSubgraph(unittest.TestCase):
    def test_build_subgraph(self) -> None:
        G = nx.MultiDiGraph()
        add_node(G, NodeId(arrete_id="1980-01-01", article_id="1"))
        add_node(G, NodeId(arrete_id="1981-01-01", article_id="2"))
        add_node(G, NodeId(arrete_id="1981-01-01", article_id="3"))
        add_node(G, NodeId(arrete_id="1982-01-01", article_id="1"))
        add_edge(
            G,
            Operation(
                id="op1",
                source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
                operation_type=OperationType.REPLACE,
                operand="very new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op2",
                source_id=NodeId(arrete_id="1981-01-01", article_id="3"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
                operation_type=OperationType.ADD,
                operand="additional content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op3",
                source_id=NodeId(arrete_id="1982-01-01", article_id="1"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
                operation_type=OperationType.REPLACE,
                operand="very new content",
            ),
        )
        history: ArticleHistory = {}
        subG = build_next_subgraph(G, history, arrete_id="1981-01-01")

        assert set(subG.nodes) == {
            NodeId(arrete_id="1980-01-01", article_id="1"),
            NodeId(arrete_id="1981-01-01", article_id="2"),
            NodeId(arrete_id="1981-01-01", article_id="3"),
        }
        assert set(subG.edges) == {
            (
                NodeId(arrete_id="1981-01-01", article_id="2"),
                NodeId(arrete_id="1980-01-01", article_id="1"),
                0,
            ),
            (
                NodeId(arrete_id="1981-01-01", article_id="3"),
                NodeId(arrete_id="1980-01-01", article_id="1"),
                0,
            ),
        }


class TestApplySubgraphOperations(unittest.TestCase):
    @mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_remove")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_add")
    def test_apply_subgraph_operations(
        self, mock_add: mock.Mock, mock_remove: mock.Mock, mock_replace: mock.Mock
    ) -> None:
        mock_add.return_value = "new content after add"
        mock_remove.return_value = ""
        mock_replace.return_value = "new content after replace"
        G = nx.MultiDiGraph()
        add_node(G, NodeId(arrete_id="1980-01-01", article_id="1"))
        add_node(G, NodeId(arrete_id="1980-01-01", article_id="2"))
        add_node(G, NodeId(arrete_id="1981-01-01", article_id="2"))
        add_node(G, NodeId(arrete_id="1981-01-01", article_id="3"))
        add_edge(
            G,
            Operation(
                id="op1",
                source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
                operation_type=OperationType.REPLACE,
                operand="very new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op2",
                source_id=NodeId(arrete_id="1981-01-01", article_id="3"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
                operation_type=OperationType.ADD,
                operand="additional content",
            ),
        )
        history: ArticleHistory = {
            NodeId(arrete_id="1980-01-01", article_id="1"): [
                {"version": 0, "content": "original content", "operation_id": None}
            ],
            NodeId(arrete_id="1980-01-01", article_id="2"): [
                {"version": 0, "content": "original content 2", "operation_id": None}
            ],
        }
        output_history, skipped_ops = apply_subgraph_operations(G, history)

        # Check that the last version of each article has the expected content
        assert (
            output_history[NodeId(arrete_id="1980-01-01", article_id="1")][-1]["content"]
            == mock_replace.return_value
        )
        assert (
            output_history[NodeId(arrete_id="1980-01-01", article_id="2")][-1]["content"]
            == mock_add.return_value
        )


class TestApplyOpsFunctions(unittest.TestCase):
    @mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_remove")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_add")
    def test_apply_all_operations(
        self, mock_add: mock.Mock, mock_remove: mock.Mock, mock_replace: mock.Mock
    ) -> None:
        mock_add.return_value = "new content after add"
        mock_remove.return_value = ""
        mock_replace.return_value = "new content after replace"

        G = nx.MultiDiGraph()
        add_node(G, NodeId(arrete_id="1980-01-01", article_id="1"))
        add_node(G, NodeId(arrete_id="1980-01-01", article_id="2"))
        add_node(G, NodeId(arrete_id="1981-01-01", article_id="2"))
        add_node(G, NodeId(arrete_id="1981-01-01", article_id="3"))
        add_node(G, NodeId(arrete_id="1982-01-01", article_id="1"))
        add_edge(
            G,
            Operation(
                id="op1",
                source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
                operation_type=OperationType.REPLACE,
                operand="very new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op2",
                source_id=NodeId(arrete_id="1981-01-01", article_id="3"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
                operation_type=OperationType.ADD,
                operand="additional content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op3",
                source_id=NodeId(arrete_id="1982-01-01", article_id="1"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
                operation_type=OperationType.ADD,
                operand="new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op4",
                source_id=NodeId(arrete_id="1982-01-01", article_id="1"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
                operation_type=OperationType.REMOVE,
            ),
        )
        arrete_list = [
            ArreteFile(
                id="1980-01-01",
                aiot="aiotA",
                filename="a.html",
                soup=BeautifulSoup("<section/>", "html.parser"),
            ),
            ArreteFile(
                id="1981-01-01",
                aiot="aiotB",
                filename="b.html",
                soup=BeautifulSoup("<section/>", "html.parser"),
            ),
            ArreteFile(
                id="1982-01-01",
                aiot="aiotC",
                filename="c.html",
                soup=BeautifulSoup("<section/>", "html.parser"),
            ),
        ]
        history, skipped_ops = apply_all_ops(G, arrete_list)

        # Verify the history contains the expected articles
        assert NodeId(arrete_id="1980-01-01", article_id="1") in history
        assert NodeId(arrete_id="1980-01-01", article_id="2") in history

        # Check that operations were applied by verifying multiple versions exist
        assert len(history[NodeId(arrete_id="1980-01-01", article_id="1")]) > 1
        assert len(history[NodeId(arrete_id="1980-01-01", article_id="2")]) > 1


class TestBuildInitialArticlesContentMap(unittest.TestCase):
    def test_build_initial_articles_content_map(self) -> None:
        # This test is disabled as build_initial_articles_content_map is no longer part of the API
        # The initialization is now handled internally by apply_subgraph_operations
        pass
