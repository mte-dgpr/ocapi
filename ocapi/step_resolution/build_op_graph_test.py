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

from bs4 import BeautifulSoup

from ocapi.types import ArreteFile, NodeId, Operation, OperationType, SubTarget, SubTargetType

from .build_op_graph import build_graph


class TestBuildOpGraph(unittest.TestCase):

    def test_build_graph(self) -> None:
        # Create mock HTML content with the required articles
        html_1980 = """
        <section data-spec="section" data-number="2">Article 2 content</section>
        <section data-spec="section" data-number="3">Article 3 content</section>
        """
        html_1981 = """
        <section data-spec="section" data-number="1">Article 1 content</section>
        <section data-spec="section" data-number="2">Article 2 content</section>
        """

        arrete_files = [
            ArreteFile(
                id="1980-01-01",
                aiot="aiot1",
                filename="1980-01-01.html",
                soup=BeautifulSoup(html_1980, "html.parser"),
            ),
            ArreteFile(
                id="1981-01-01",
                aiot="aiot2",
                filename="1981-01-01.html",
                soup=BeautifulSoup(html_1981, "html.parser"),
            ),
        ]

        operations = [
            Operation(
                id="1",
                source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
                operation_type=OperationType.REPLACE,
                operand="article",
                sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
            ),
            Operation(
                id="2",
                source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
                target_id=NodeId(arrete_id="1980-01-01", article_id="3"),
                operation_type=OperationType.REMOVE,
            ),
        ]
        G, updated_arrete_files, skipped_ops = build_graph(operations, arrete_files)

        assert len(G.nodes) == 4
        assert len(G.edges) == 2
        assert len(skipped_ops) == 0

        # Les clés des noeuds sont maintenant des objets NodeId
        node1 = NodeId(arrete_id="1980-01-01", article_id="2")
        node2 = NodeId(arrete_id="1980-01-01", article_id="3")
        node3 = NodeId(arrete_id="1981-01-01", article_id="1")
        node4 = NodeId(arrete_id="1981-01-01", article_id="2")

        assert G.has_edge(node3, node1) is True
        assert G.has_edge(node4, node2) is True

        edge_data_1 = G.get_edge_data(node3, node1, 0)
        assert edge_data_1 == {
            "id": "1",
            "operation_type": "REPLACE",
            "operand": "article",
            "sub_target": {"type": "FULL_SECTION"},
        }

        edge_data_2 = G.get_edge_data(node4, node2, 0)
        assert edge_data_2 == {"id": "2", "operation_type": "REMOVE"}
