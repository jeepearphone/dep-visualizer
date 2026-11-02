"""Тесты построения графа зависимостей и поиска циклов."""

import unittest
from pathlib import Path

from src.graph import (
    GraphError,
    build_graph,
    dependents_of,
    depends_on_itself,
    find_cycle_edges,
    find_dependents,
    reverse_edges,
)
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


class ReverseEdgesTest(unittest.TestCase):
    """Проверки разворота рёбер графа."""

    def test_diamond(self):
        """В ромбе от D зависят B и C, от B и C — A."""
        graph = build_graph("A", getter_for("diamond.txt"))
        self.assertEqual(
            reverse_edges(graph.edges),
            {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]},
        )


class FindDependentsTest(unittest.TestCase):
    """Проверки поиска обратных зависимостей."""

    def reverse_of(self, file_name, target, filter_substring=""):
        """Построить граф из файла и найти обратные зависимости target."""
        graph = build_graph("A", getter_for(file_name), filter_substring)
        return find_dependents(graph, target)

    def test_diamond_transitive(self):
        """От D зависят B и C напрямую и A транзитивно."""
        reverse_graph = self.reverse_of("diamond.txt", "D")
        self.assertEqual(reverse_graph.root, "D")
        self.assertEqual(dependents_of(reverse_graph), ["A", "B", "C"])

    def test_linear(self):
        """В цепочке от C зависят все предыдущие пакеты."""
        reverse_graph = self.reverse_of("linear.txt", "C")
        self.assertEqual(dependents_of(reverse_graph), ["A", "B"])

    def test_root_has_no_dependents(self):
        """От корня без циклов никто не зависит."""
        reverse_graph = self.reverse_of("linear.txt", "A")
        self.assertEqual(dependents_of(reverse_graph), [])
        self.assertFalse(depends_on_itself(reverse_graph))

    def test_cycle(self):
        """В цикле пакет зависит от всех остальных и от самого себя."""
        reverse_graph = self.reverse_of("cycle.txt", "A")
        self.assertEqual(dependents_of(reverse_graph), ["B", "C"])
        self.assertTrue(depends_on_itself(reverse_graph))

    def test_self_loop(self):
        """Самопетля: A зависит от себя, от B зависит A."""
        self_graph = self.reverse_of("self_loop.txt", "A")
        self.assertTrue(depends_on_itself(self_graph))
        reverse_graph = self.reverse_of("self_loop.txt", "B")
        self.assertEqual(dependents_of(reverse_graph), ["A"])
        self.assertFalse(depends_on_itself(reverse_graph))

    def test_complex_uses_dfs(self):
        """Обратный граф строится тем же DFS: порядок обхода в глубину."""
        reverse_graph = self.reverse_of("complex.txt", "E")
        self.assertEqual(
            list(reverse_graph.edges),
            ["E", "B", "A", "G", "C", "H", "F", "D"],
        )

    def test_filter_removes_paths(self):
        """С фильтром F путей H <- F <- B и H <- F <- C нет."""
        reverse_graph = self.reverse_of("complex.txt", "H", "F")
        self.assertEqual(dependents_of(reverse_graph), ["A", "C", "D", "G"])

    def test_missing_target(self):
        """Пакета нет в графе."""
        graph = build_graph("A", getter_for("diamond.txt"))
        with self.assertRaisesRegex(GraphError, "не входит в граф"):
            find_dependents(graph, "Z")


if __name__ == "__main__":
    unittest.main()
