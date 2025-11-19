import unittest
import networkx as nx
from apply_ops import get_next_ops


class TestGetNextOps(unittest.TestCase):

    def test_get_next_ops_no_conflicts(self):
        G = nx.MultiDiGraph()
        G.add_edge("A", "B", operation_id="op1")
        G.add_edge("B", "C", operation_id="op2")

        next_ops = get_next_ops(G)
        assert next_ops == {("A", "B", 0)}

        G.remove_node("A")
        next_ops = get_next_ops(G)
        print(next_ops)
        assert next_ops == {("B", "C", 0)}

    def test_get_next_ops_with_conflicts(self):
        G = nx.MultiDiGraph()
        G.add_edge("A1", "B", operation_id="op1")
        G.add_edge("A2", "B", operation_id="op2")
        G.add_edge("B", "C", operation_id="op3")

        next_ops = get_next_ops(G)
        assert next_ops == {("A1", "B", 0), ("A2", "B", 0)}

        G.remove_node("A1")
        G.remove_node("A2")
        next_ops = get_next_ops(G)
        assert next_ops == {("B", "C", 0)}

    def test_get_next_ops_with_both(self):
        G = nx.MultiDiGraph()
        G.add_edge("A", "B", operation_id="op1")
        G.add_edge("B","D", operation_id="op2")
        G.add_edge("C", "D", operation_id="op3")

        next_ops = get_next_ops(G)
        assert next_ops == {("A", "B", 0)}

        G.remove_node("A")
        next_ops = get_next_ops(G)
        assert next_ops == {("B", "D", 0), ("C", "D", 0)}