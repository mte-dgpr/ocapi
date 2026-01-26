import unittest
from unittest import mock
import networkx as nx
from ocapi.step_resolution.apply_ops import (
    build_subgraph,
    apply_subgraph_operations,
    apply_all_operations,
    build_initial_articles_content_map,
    apply_replace,
)
from ocapi.step_resolution.build_op_graph import add_edge, add_node
from ocapi.types import ArreteFile, ArticlesContentMap, NodeId, Operation, OperationType, SubTarget
from bs4 import BeautifulSoup

from ocapi.utils.utils import _assert_html_equal


class TestApplyReplace(unittest.TestCase):
    pass  # Tester LLM... éviter le parsing à la main ?


class TestBuildSubgraph(unittest.TestCase):
    def test_build_subgraph(self):
        G = nx.MultiDiGraph()
        add_node(G, NodeId(arrete_id="arreteA", article_id="1"))
        add_node(G, NodeId(arrete_id="arreteB", article_id="2"))
        add_node(G, NodeId(arrete_id="arreteB", article_id="3"))
        add_node(G, NodeId(arrete_id="arreteC", article_id="1"))
        add_edge(
            G,
            Operation(
                id="op1",
                source_id=NodeId(arrete_id="arreteB", article_id="2"),
                target_id=NodeId(arrete_id="arreteA", article_id="1"),
                operation_type="REPLACE",
                operand="very new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op2",
                source_id=NodeId(arrete_id="arreteB", article_id="3"),
                target_id=NodeId(arrete_id="arreteA", article_id="1"),
                operation_type="ADD",
                operand="additional content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op3",
                source_id=NodeId(arrete_id="arreteC", article_id="1"),
                target_id=NodeId(arrete_id="arreteA", article_id="1"),
                operation_type="REPLACE",
                operand="very new content",
            ),
        )
        subG = build_subgraph(G, arrete_id="arreteB")

        assert set(subG.nodes) == {
            NodeId(arrete_id="arreteA", article_id="1"),
            NodeId(arrete_id="arreteB", article_id="2"),
            NodeId(arrete_id="arreteB", article_id="3"),
        }
        assert set(subG.edges) == {
            (
                NodeId(arrete_id="arreteB", article_id="2"),
                NodeId(arrete_id="arreteA", article_id="1"),
                0,
            ),
            (
                NodeId(arrete_id="arreteB", article_id="3"),
                NodeId(arrete_id="arreteA", article_id="1"),
                0,
            ),
        }


class TestApplySubgraphOperations(unittest.TestCase):
    @mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_remove")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_add")
    def test_apply_subgraph_operations(self, mock_add, mock_remove, mock_replace):
        mock_add.return_value = "new content after add"
        mock_remove.return_value = ""
        mock_replace.return_value = "new content after replace"
        G = nx.MultiDiGraph()
        add_node(G, NodeId(arrete_id="arreteA", article_id="1"))
        add_node(G, NodeId(arrete_id="arreteA", article_id="2"))
        add_node(G, NodeId(arrete_id="arreteB", article_id="2"))
        add_node(G, NodeId(arrete_id="arreteB", article_id="3"))
        add_edge(
            G,
            Operation(
                id="op1",
                source_id=NodeId(arrete_id="arreteB", article_id="2"),
                target_id=NodeId(arrete_id="arreteA", article_id="1"),
                operation_type="REPLACE",
                operand="very new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op2",
                source_id=NodeId(arrete_id="arreteB", article_id="3"),
                target_id=NodeId(arrete_id="arreteA", article_id="2"),
                operation_type="ADD",
                operand="additional content",
            ),
        )
        articles_content_map: ArticlesContentMap = {
            NodeId(arrete_id="arreteA", article_id="1"): "original content",
            NodeId(arrete_id="arreteA", article_id="2"): "original content 2",
        }
        output_content_map = apply_subgraph_operations(G, articles_content_map)

        assert output_content_map == {
            NodeId(arrete_id="arreteA", article_id="1"): mock_replace.return_value,
            NodeId(arrete_id="arreteA", article_id="2"): mock_add.return_value,
        }


class TestApplyOpsFunctions(unittest.TestCase):
    @mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_remove")
    @mock.patch("ocapi.step_resolution.apply_ops.apply_add")
    def test_apply_all_operations(self, mock_add, mock_remove, mock_replace):
        mock_add.return_value = "new content after add"
        mock_remove.return_value = ""
        mock_replace.return_value = "new content after replace"

        G = nx.MultiDiGraph()
        add_node(G, NodeId(arrete_id="arreteA", article_id="1"))
        add_node(G, NodeId(arrete_id="arreteA", article_id="2"))
        add_node(G, NodeId(arrete_id="arreteB", article_id="2"))
        add_node(G, NodeId(arrete_id="arreteB", article_id="3"))
        add_node(G, NodeId(arrete_id="arreteC", article_id="1"))
        add_edge(
            G,
            Operation(
                id="op1",
                source_id=NodeId(arrete_id="arreteB", article_id="2"),
                target_id=NodeId(arrete_id="arreteA", article_id="1"),
                operation_type=OperationType.REPLACE,
                operand="very new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op2",
                source_id=NodeId(arrete_id="arreteB", article_id="3"),
                target_id=NodeId(arrete_id="arreteA", article_id="2"),
                operation_type=OperationType.ADD,
                operand="additional content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op3",
                source_id=NodeId(arrete_id="arreteC", article_id="1"),
                target_id=NodeId(arrete_id="arreteA", article_id="1"),
                operation_type=OperationType.ADD,
                operand="new content",
            ),
        )
        add_edge(
            G,
            Operation(
                id="op4",
                source_id=NodeId(arrete_id="arreteC", article_id="1"),
                target_id=NodeId(arrete_id="arreteA", article_id="2"),
                operation_type=OperationType.REMOVE,
            ),
        )
        arrete_list = [
            ArreteFile(id="arreteA", aiot="aiotA", filename="a.html", soup=None),
            ArreteFile(id="arreteB", aiot="aiotB", filename="b.html", soup=None),
            ArreteFile(id="arreteC", aiot="aiotC", filename="c.html", soup=None),
        ]
        initial_articles_content_map = {
            NodeId(arrete_id="arreteA", article_id="1"): "old content",
            NodeId(arrete_id="arreteA", article_id="2"): "old content 2",
        }
        versions = apply_all_operations(G, arrete_list, initial_articles_content_map)

        assert versions == [
            {
                NodeId(arrete_id="arreteA", article_id="1"): "old content",
                NodeId(arrete_id="arreteA", article_id="2"): "old content 2",
            },
            {
                NodeId(arrete_id="arreteA", article_id="1"): "new content after replace",
                NodeId(arrete_id="arreteA", article_id="2"): "new content after add",
            },
            {
                NodeId(arrete_id="arreteA", article_id="1"): "new content after add",
                NodeId(arrete_id="arreteA", article_id="2"): "",
            },
        ]


class TestBuildInitialArticlesContentMap(unittest.TestCase):
    def test_build_initial_articles_content_map(self):

        G = nx.MultiDiGraph()
        add_node(G, NodeId(arrete_id="arreteA", article_id="1.2"))
        add_node(G, NodeId(arrete_id="arreteB", article_id="1.3"))
        add_edge(
            G,
            Operation(
                id="op1",
                source_id=NodeId(arrete_id="arreteB", article_id="1.3"),
                target_id=NodeId(arrete_id="arreteA", article_id="1.2"),
                operation_type="REPLACE",
                operand="very new content",
            ),
        )

        arreteA = ArreteFile(
            id="arreteA",
            aiot="aiotA",
            filename="a.html",
            soup=BeautifulSoup(
                '<section class="arretify-section" data-num="1.2">Content A1</section>',
                "html.parser",
            ),
        )
        arreteB = ArreteFile(
            id="arreteB",
            aiot="aiotB",
            filename="b.html",
            soup=BeautifulSoup(
                '<section class="arretify-section" data-num="1.3">Content B2</section>',
                "html.parser",
            ),
        )
        articles_content_map = build_initial_articles_content_map(G, [arreteA, arreteB])

        assert articles_content_map == {
            NodeId(
                arrete_id="arreteA", article_id="1.2"
            ): '<section class="arretify-section" data-num="1.2">Content A1</section>',
        }
