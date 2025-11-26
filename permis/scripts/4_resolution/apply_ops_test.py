import unittest
from unittest import mock
import networkx as nx
from apply_ops import build_subgraph, apply_subgraph_operations, apply_all_operations, build_initial_articles_content_map
from build_op_graph import add_edge, add_node
from permis.scripts.types import Operation
from bs4 import BeautifulSoup

class TestBuildSubgraph(unittest.TestCase):
    def test_build_subgraph(self):
        G = nx.MultiDiGraph()
        G.add_node("arreteA::node1")
        G.add_node("arreteB::node2")
        G.add_node("arreteB::node3")
        G.add_node("arreteC::node4")
        add_edge(G, Operation(id="op1", source_uid="arreteB::node2", target_uid="arreteA::node1", op_type="REPLACE", operand="very new content"))
        add_edge(G, Operation(id="op2", source_uid="arreteB::node3", target_uid="arreteA::node1", op_type="ADD", operand="additional content"))
        add_edge(G, Operation(id="op3", source_uid="arreteC::node4", target_uid="arreteA::node1", op_type="REPLACE", operand="very new content"))
        subG = build_subgraph(G, "arreteB")

        assert set(subG.nodes) == {"arreteB::node2", "arreteB::node3", "arreteA::node1"}
        assert set(subG.edges) == {("arreteB::node2", "arreteA::node1", 0), ("arreteB::node3", "arreteA::node1", 0)}


class TestApplySubgraphOperations(unittest.TestCase):

    @mock.patch('apply_ops.apply_replace')
    @mock.patch('apply_ops.apply_remove')
    @mock.patch('apply_ops.apply_add')
    def test_apply_subgraph_operations(self, mock_add, mock_remove, mock_replace):
        mock_add.return_value = "new content after add"
        mock_remove.return_value = ""
        mock_replace.return_value = "new content after replace"
        G = nx.MultiDiGraph()

        add_node(G, "arreteA::node1")
        add_node(G, "arreteB::node2")
        add_node(G, "arreteB::node3")
        add_edge(G, Operation(id="op1", source_uid="arreteB::node2", target_uid="arreteA::node1", op_type="REPLACE", operand="very new content"))
        add_edge(G, Operation(id="op2", source_uid="arreteB::node3", target_uid="arreteA::node1", op_type="ADD", operand="additional content"))
        articles_content_map = {"arreteA::node1": "old content"}
        output_content_map = apply_subgraph_operations(G, articles_content_map)

        assert output_content_map["arreteA::node1"] == "new content after add"

class TestApplyOpsFunctions(unittest.TestCase):
    @mock.patch('apply_ops.apply_replace')
    @mock.patch('apply_ops.apply_remove')
    @mock.patch('apply_ops.apply_add')
    def test_apply_all_operations(self, mock_add, mock_remove, mock_replace):
        mock_add.return_value = "new content after add"
        mock_remove.return_value = ""
        mock_replace.return_value = "new content after replace"

        G = nx.MultiDiGraph()
        add_node(G, "arreteA::1.2")
        add_node(G, "arreteB::node2")
        add_node(G, "arreteB::node3")
        add_node(G, "arreteC::node4")
        add_edge(G, Operation(id="op1", source_uid="arreteB::node2", target_uid="arreteA::1.2", op_type="REPLACE", operand="very new content"))
        add_edge(G, Operation(id="op2", source_uid="arreteB::node3", target_uid="arreteA::1.2", op_type="ADD", operand="additional content"))
        add_edge(G, Operation(id="op3", source_uid="arreteC::node4", target_uid="arreteA::1.2", op_type="REPLACE", operand="very new content"))
        arrete_list = ["arreteB", "arreteC"]
        initial_articles_content_map = {"arreteA::1.2": "old content"}
        versions = apply_all_operations(G, arrete_list, initial_articles_content_map)

        assert versions[1]["arreteA::1.2"] == "new content after add"
        assert versions[2]["arreteA::1.2"] == "new content after replace"
    
class TestBuildInitialArticlesContentMap(unittest.TestCase):
    def test_build_initial_articles_content_map(self):

        G = nx.MultiDiGraph()
        add_node(G, "arreteA::1.2")
        add_node(G, "arreteB::1.3")
        add_edge(G, Operation(id="op1", source_uid="arreteB::1.3", target_uid="arreteA::1.2", op_type="REPLACE", operand="very new content"))

        soups = {
            "arreteA": BeautifulSoup('<section class="arretify-section" data-num="1.2">Content A1</section>', 'html.parser'),
            "arreteB": BeautifulSoup('<section class="arretify-section" data-num="1.3">Content B2</section>', 'html.parser'),
        }

        articles_content_map = build_initial_articles_content_map(G, soups)

        assert articles_content_map["arreteA::1.2"] == '<section class="arretify-section" data-num="1.2">Content A1</section>'