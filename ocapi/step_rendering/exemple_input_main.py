from ocapi.types import NodeId, ArticlesContentMap
import networkx as nx


op_graph_exemple: nx.MultiDiGraph = nx.MultiDiGraph()
op_graph_exemple.add_node(NodeId(arrete_id="AP-auto", article_id="1"))
op_graph_exemple.add_node(NodeId(arrete_id="AP-auto", article_id="2.1"))
op_graph_exemple.add_node(NodeId(arrete_id="AP-auto", article_id="3.4"))
op_graph_exemple.add_node(NodeId(arrete_id="AP-auto", article_id="8"))
op_graph_exemple.add_node(NodeId(arrete_id="APC1", article_id="3"))
op_graph_exemple.add_node(NodeId(arrete_id="APC2", article_id="2.2.1"))
op_graph_exemple.add_node(NodeId(arrete_id="APC3", article_id="1"))

op_graph_exemple.add_edge(NodeId(arrete_id="APC1", article_id="3"),
                          NodeId(arrete_id="AP-auto", article_id="2.1"),    
                          id="op1",
                          operation_type="REPLACE",
                          operand="<p>Les déchets doivent être triés à la source selon les catégories suivantes: plastique, verre, carton.</p>",
                          sub_target=None
                    )                        
op_graph_exemple.add_edge(NodeId(arrete_id="APC2", article_id="2.2.1"),
                            NodeId(arrete_id="AP-auto", article_id="3.4"),
                            id="op2",
                            operation_type="ADD",
                            operand="Elles doivent être vidées régulièrement pour éviter tout débordement.",
                            sub_target=None)
op_graph_exemple.add_edge(NodeId(arrete_id="APC3", article_id="1"),
                          NodeId(arrete_id="AP-auto", article_id="8"),
                            id="op3",
                            operation_type="ADD",
                            operand="<p>Un registre des déchets doit être tenu à jour.</p>",
                            sub_target=None)


# Exemple 1: Évolution simple d'un arrêté avec 3 versions
versions_exemple_1: list[ArticlesContentMap] = [
    # Version 0 : contenu initial de tous les articles target
    {
        NodeId(arrete_id="AP-auto", article_id="1"): "<p>L'exploitant doit respecter les prescriptions générales.</p>",
        NodeId(arrete_id="AP-auto", article_id="2.1"): "<p>Les déchets doivent être triés à la source.</p>",
        NodeId(arrete_id="AP-auto", article_id="3.4"): "<p>Les bennes doivent être étanches.</p>",
        NodeId(arrete_id="AP-auto", article_id="8"): "",

    },
    # Version 1: Resolution de l'APC 1
    {
        NodeId(arrete_id="AP-auto", article_id="1"): "<p>L'exploitant doit respecter les prescriptions générales.</p>",
        NodeId(arrete_id="AP-auto", article_id="2.1"): "<p>Les déchets doivent être triés à la source selon les catégories suivantes: plastique, verre, carton.</p>",
        NodeId(arrete_id="AP-auto", article_id="3.4"): "<p>Les bennes doivent être étanches.</p>",
        NodeId(arrete_id="AP-auto", article_id="8"): "",
    },
    
    # Version 2: Resolution de l'APC 2
    {
        NodeId(arrete_id="AP-auto", article_id="1"): "<p>L'exploitant doit respecter les prescriptions générales.</p>",
        NodeId(arrete_id="AP-auto", article_id="2.1"): "<p>Les déchets doivent être triés à la source selon les catégories suivantes: plastique, verre, carton.</p>",
        NodeId(arrete_id="AP-auto", article_id="3.4"): "<p>Les bennes doivent être étanches. Elles doivent être vidées régulièrement pour éviter tout débordement.</p>",
        NodeId(arrete_id="AP-auto", article_id="8"): "",
    },
    
    # Version 3: Resolution de l'APC 3
    {
        NodeId(arrete_id="AP-auto", article_id="1"): "<p>L'exploitant doit respecter les prescriptions générales.</p>",
        NodeId(arrete_id="AP-auto", article_id="2.1"): "<p>Les déchets doivent être triés à la source selon les catégories suivantes: plastique, verre, carton.</p>",
        NodeId(arrete_id="AP-auto", article_id="3.3"): "<p>Les bennes doivent être étanches. Elles doivent être vidées régulièrement pour éviter tout débordement.</p>",
        NodeId(arrete_id="AP-auto", article_id="8"): "<p>Un registre des déchets doit être tenu à jour.</p>",
    },
]
