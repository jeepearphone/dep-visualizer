"""Тесты описания графа на Graphviz, рендера и ASCII-дерева."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.graph import DependencyGraph, build_graph
from src.graph_file import load_graph_file, make_dependency_getter
from src.render import (
    RenderError,
    ascii_tree,
    open_image,
    quote_id,
    render_image,
    safe_file_name,
    save_dot,
    to_dot,
)

DATA_DIR = Path(__file__).parent / "data"
PNG_SIGNATURE = b"\x89PNG"


def graph_from(file_name, filter_substring=""):
    """Построить граф с корнем A из тестового файла."""
    graph = load_graph_file(DATA_DIR / file_name)
    return build_graph("A", make_dependency_getter(graph), filter_substring)


class ToDotTest(unittest.TestCase):
    """Проверки текстового описания на языке Graphviz."""

    def test_structure(self):
        """Описание — ориентированный граф со всеми рёбрами."""
        dot = to_dot(graph_from("diamond.txt"))
        self.assertTrue(dot.startswith("digraph dependencies {"))
        self.assertTrue(dot.rstrip().endswith("}"))
        for edge in ('"A" -> "B";', '"A" -> "C";', '"B" -> "D";',
                     '"C" -> "D";'):
            self.assertIn(edge, dot)

    def test_root_highlighted(self):
        """Корень выделяется заливкой."""
        dot = to_dot(graph_from("diamond.txt"))
        self.assertIn('"A" [style="rounded,filled"', dot)

    def test_cycle_edge_red(self):
        """Ребро, замыкающее цикл, красное, остальные — обычные."""
        dot = to_dot(graph_from("cycle.txt"))
        self.assertIn('"C" -> "A" [color=red', dot)
        self.assertIn('"A" -> "B";', dot)

    def test_single_node(self):
        """Пакет без зависимостей всё равно попадает в описание."""
        dot = to_dot(DependencyGraph("ms", {"ms": []}))
        self.assertIn('"ms"', dot)
        self.assertNotIn("->", dot)

    def test_filtered_not_shown(self):
        """Пакеты, исключённые фильтром, на графе отсутствуют."""
        self.assertNotIn('"F"', to_dot(graph_from("complex.txt", "F")))

    def test_quote_id(self):
        """Имена scoped-пакетов и спецсимволы экранируются."""
        self.assertEqual(quote_id("@babel/core"), '"@babel/core"')
        self.assertEqual(quote_id('a"b'), '"a\\"b"')


class AsciiTreeTest(unittest.TestCase):
    """Проверки ASCII-дерева."""

    def test_diamond(self):
        """Общая зависимость раскрывается один раз, дальше — повтор."""
        self.assertEqual(ascii_tree(graph_from("diamond.txt")), [
            "A",
            "+-- B",
            "|   `-- D",
            "`-- C",
            "    `-- D (повтор)",
        ])

    def test_cycle(self):
        """Пакет, уже стоящий на пути от корня, помечается циклом."""
        self.assertEqual(ascii_tree(graph_from("cycle.txt")), [
            "A",
            "`-- B",
            "    `-- C",
            "        `-- A (цикл)",
        ])

    def test_self_loop(self):
        """Самопетля — цикл длины один."""
        self.assertEqual(
            ascii_tree(graph_from("self_loop.txt")),
            ["A", "+-- A (цикл)", "`-- B"],
        )

    def test_single_node(self):
        """Дерево из одного корня."""
        self.assertEqual(ascii_tree(DependencyGraph("ms", {"ms": []})), ["ms"])

    def test_matches_graph(self):
        """Каждое ребро графа встречается в дереве ровно один раз."""
        graph = graph_from("complex.txt")
        lines = ascii_tree(graph)
        edges = sum(len(deps) for deps in graph.edges.values())
        self.assertEqual(len(lines), edges + len([graph.root]))


class FilesTest(unittest.TestCase):
    """Проверки сохранения, рендера и открытия файлов."""

    def test_safe_file_name(self):
        """Слеш и @ в имени scoped-пакета заменяются."""
        self.assertEqual(safe_file_name("@babel/core"), "_babel_core")
        self.assertEqual(safe_file_name("lodash.merge"), "lodash.merge")

    def test_save_dot(self):
        """DOT-файл сохраняется в указанную папку, папка создаётся."""
        with tempfile.TemporaryDirectory() as directory:
            path = save_dot("digraph {}\n", Path(directory) / "new", "@a/b")
            self.assertEqual(path.name, "_a_b.dot")
            self.assertEqual(path.read_text(encoding="utf-8"), "digraph {}\n")

    @patch("src.render.subprocess.run")
    def test_render_command(self, run):
        """Вызывается dot с выводом в PNG рядом с DOT-файлом."""
        image = render_image(Path("out") / "A.dot")
        self.assertEqual(image, Path("out") / "A.png")
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["dot", "-Tpng"])

    @patch("src.render.subprocess.run", side_effect=FileNotFoundError)
    def test_dot_not_installed(self, _):
        """Graphviz не установлен."""
        with self.assertRaisesRegex(RenderError, "Graphviz"):
            render_image(Path("A.dot"))

    @patch("src.render.subprocess.run")
    def test_dot_failed(self, run):
        """dot завершился с ошибкой."""
        run.side_effect = subprocess.CalledProcessError(
            1, ["dot"], stderr="syntax error"
        )
        with self.assertRaisesRegex(RenderError, "syntax error"):
            render_image(Path("A.dot"))

    @patch("src.render.sys.platform", "linux")
    @patch("src.render.subprocess.Popen", side_effect=FileNotFoundError)
    def test_open_failed(self, _):
        """Нет программы для открытия изображения."""
        with self.assertRaisesRegex(RenderError, "не удалось открыть"):
            open_image(Path("A.png"))

    @unittest.skipUnless(shutil.which("dot"), "Graphviz не установлен")
    def test_real_render(self):
        """Настоящий вызов dot создаёт PNG-файл."""
        with tempfile.TemporaryDirectory() as directory:
            dot_path = save_dot(to_dot(graph_from("cycle.txt")), directory, "A")
            image = render_image(dot_path)
            self.assertEqual(image.read_bytes()[:4], PNG_SIGNATURE)


if __name__ == "__main__":
    unittest.main()
