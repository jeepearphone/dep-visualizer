"""Тесты построения графа зависимостей и поиска циклов."""

import unittest
from pathlib import Path

from src.graph import build_graph, find_cycle_edges
from src.graph_file import load_graph_file, make_dependency_getter

DATA_DIR = Path(__file__).parent / "data"


def getter_for(file_name, calls=None):
    """Вернуть get_deps для тестового файла; calls собирает вызовы."""
    get_deps = make_dependency_getter(load_graph_file(DATA_DIR / file_name))

    def counting_get_deps(name):
        """Запомнить запрошенный пакет и вернуть его зависимости."""
        if calls is not None:
            calls.append(name)
        return get_deps(name)
    return counting_get_deps


class BuildGraphTest(unittest.TestCase):
    """Проверки обхода в глубину на тестовых репозиториях."""

    def test_linear(self):
        """Линейная цепочка A -> B -> C -> D."""
        graph = build_graph("A", getter_for("linear.txt"))
        self.assertEqual(
            graph.edges, {"A": ["B"], "B": ["C"], "C": ["D"], "D": []}
        )

    def test_diamond_requests_shared_once(self):
        """Общая зависимость D запрашивается один раз."""
        calls = []
        graph = build_graph("A", getter_for("diamond.txt", calls))
        self.assertEqual(graph.edges["B"], ["D"])
        self.assertEqual(graph.edges["C"], ["D"])
        self.assertEqual(calls.count("D"), 1)

    def test_dfs_order(self):
        """Пакеты обходятся в глубину в порядке перечисления."""
        graph = build_graph("A", getter_for("complex.txt"))
        self.assertEqual(
            list(graph.edges), ["A", "B", "E", "F", "H", "C", "G", "D"]
        )

    def test_cycle_terminates_and_keeps_edge(self):
        """Цикл A -> B -> C -> A не зацикливает обход, ребро C -> A есть."""
        calls = []
        graph = build_graph("A", getter_for("cycle.txt", calls))
        self.assertEqual(graph.edges["C"], ["A"])
        self.assertEqual(calls, ["A", "B", "C"])

    def test_self_loop(self):
        """Пакет, зависящий от самого себя."""
        graph = build_graph("A", getter_for("self_loop.txt"))
        self.assertEqual(graph.edges, {"A": ["A", "B"], "B": []})

    def test_filter_excludes_and_skips(self):
        """Пакет с подстрокой не попадает в граф и не обходится."""
        calls = []
        graph = build_graph("A", getter_for("complex.txt", calls), "F")
        self.assertNotIn("F", graph.edges)
        self.assertNotIn("F", calls)
        self.assertEqual(graph.excluded, {"F"})
        self.assertEqual(graph.edges["B"], ["E"])

    def test_filter_keeps_other_paths(self):
        """Пакет, доступный в обход отфильтрованного, остаётся в графе."""
        graph = build_graph("A", getter_for("complex.txt"), "F")
        self.assertIn("H", graph.edges)

    def test_from_middle(self):
        """Корнем может быть любой пакет репозитория."""
        graph = build_graph("C", getter_for("complex.txt"))
        self.assertEqual(graph.root, "C")
        self.assertIn("A", graph.edges)


class FindCycleEdgesTest(unittest.TestCase):
    """Проверки поиска рёбер, замыкающих циклы."""

    def cycles_of(self, file_name):
        """Построить граф из файла и найти циклы."""
        return find_cycle_edges(build_graph("A", getter_for(file_name)))

    def test_no_cycles(self):
        """В ромбе нет циклов, хотя D достижим двумя путями."""
        self.assertEqual(self.cycles_of("diamond.txt"), [])

    def test_cycle(self):
        """Цикл из трёх пакетов."""
        self.assertEqual(self.cycles_of("cycle.txt"), [("C", "A")])

    def test_self_loop(self):
        """Самопетля — цикл длины один."""
        self.assertEqual(self.cycles_of("self_loop.txt"), [("A", "A")])

    def test_complex(self):
        """Цикл A -> C -> G -> A в большом графе."""
        self.assertEqual(self.cycles_of("complex.txt"), [("G", "A")])


if __name__ == "__main__":
    unittest.main()
