import unittest

from app.agent.graph import graph


class AgentGraphTests(unittest.TestCase):
    def test_compiled_graph_contains_all_agent_nodes(self):
        node_names = set(graph.get_graph().nodes)

        self.assertTrue(
            {
                "extract_keywords",
                "recall_column",
                "recall_value",
                "recall_metric",
                "merge_retrieved_info",
                "filter_metric",
                "filter_table",
                "add_extra_context",
                "generate_sql",
                "validate_sql",
                "correct_sql",
                "execute_sql",
            }.issubset(node_names)
        )
