"""Тесты чтения файла тестового репозитория."""

import unittest
from pathlib import Path

from src.graph_file import (
    GraphFileError,
    load_graph_file,
    make_dependency_getter,
)

DATA_DIR = Path(__file__).parent / "data"


class LoadGraphFileTest(unittest.TestCase):
    """Проверки разбора формата «ИМЯ: ЗАВИСИМОСТИ»."""

    def test_linear(self):
        """Пакет, упомянутый только как зависимость, становится листом."""
        graph = load_graph_file(DATA_DIR / "linear.txt")
        self.assertEqual(
            graph, {"A": ["B"], "B": ["C"], "C": ["D"], "D": []}
        )

    def test_empty_dependency_list(self):
        """Строка «B:» без зависимостей допустима."""
        graph = load_graph_file(DATA_DIR / "self_loop.txt")
        self.assertEqual(graph, {"A": ["A", "B"], "B": []})

    def test_missing_file(self):
        """Файл не существует."""
        with self.assertRaisesRegex(GraphFileError, "не удалось прочитать"):
            load_graph_file(DATA_DIR / "no_such_graph.txt")

    def test_no_separator(self):
        """Строка без двоеточия."""
        with self.assertRaisesRegex(GraphFileError, "строка 2"):
            load_graph_file(DATA_DIR / "bad_graph_syntax.txt")

    def test_bad_name(self):
        """Имя пакета не из заглавных латинских букв."""
        with self.assertRaisesRegex(GraphFileError, "заглавных"):
            load_graph_file(DATA_DIR / "bad_graph_name.txt")

    def test_duplicate_package(self):
        """Пакет описан дважды."""
        with self.assertRaisesRegex(GraphFileError, "описан повторно"):
            load_graph_file(DATA_DIR / "bad_graph_duplicate.txt")


class DependencyGetterTest(unittest.TestCase):
    """Проверки функции get_deps для тестового репозитория."""

    def test_known_package(self):
        """Зависимости известного пакета."""
        get_deps = make_dependency_getter({"A": ["B"], "B": []})
        self.assertEqual(get_deps("A"), ["B"])

    def test_unknown_package(self):
        """Пакета нет в репозитории."""
        get_deps = make_dependency_getter({"A": []})
        with self.assertRaisesRegex(GraphFileError, "не найден"):
            get_deps("Z")


if __name__ == "__main__":
    unittest.main()
