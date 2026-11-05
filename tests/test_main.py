"""Тесты вывода и кодов возврата CLI."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.main import (
    EXIT_CONFIG_ERROR,
    EXIT_DATA_ERROR,
    EXIT_OK,
    EXIT_RENDER_ERROR,
    main,
)
from src.registry import RegistryError
from src.render import RenderError

DATA_DIR = Path(__file__).parent / "data"
NPM_DEPS = {"express": ["accepts", "debug"], "accepts": [], "debug": []}


class MainTestCase(unittest.TestCase):
    """Общая подготовка: временная папка вывода, рендер и показ подменены."""

    def setup_tests(self):
        """Подменить вызов dot и открытие картинки, создать папку вывода."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output_dir = Path(directory.name)
        self.render = self.start_patch(
            "src.main.render_image",
            side_effect=lambda path: path.with_suffix(".png"),
        )
        self.open = self.start_patch("src.main.open_image")

    def start_patch(self, target, **kwargs):
        """Включить подмену на время теста."""
        patcher = patch(target, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def run_main(self, file_name, *extra):
        """Запустить main с конфигом из tests/data, вернуть код и вывод."""
        argv = [
            "--config", str(DATA_DIR / file_name),
            "--output-dir", str(self.output_dir),
            "--no-open", *extra,
        ]
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(argv)
        return code, output.getvalue(), errors.getvalue()


class VisualizeTest(MainTestCase):
    """Визуализация графа на тестовых репозиториях."""

    def test_diamond(self):
        """DOT-описание, ASCII-дерево и сводка."""
        self.setup_tests()
        code, output, _ = self.run_main("good_test_mode.toml")
        self.assertEqual(code, EXIT_OK)
        self.assertIn('"A" -> "B";', output)
        self.assertIn("    `-- D (повтор)", output)
        self.assertIn("Циклических зависимостей нет", output)
        self.assertIn("Изображение графа", output)

    def test_dot_file_saved_and_rendered(self):
        """DOT-файл сохраняется в папку вывода и передаётся в dot."""
        self.setup_tests()
        self.run_main("good_test_mode.toml")
        dot_path = self.output_dir / "A.dot"
        self.assertTrue(dot_path.is_file())
        self.render.assert_called_once_with(dot_path)

    def test_no_ascii_tree(self):
        """Без ascii_tree дерево не выводится."""
        self.setup_tests()
        _, output, _ = self.run_main("graph_no_tree.toml")
        self.assertNotIn("ASCII-дерево", output)
        self.assertIn('"A" -> "B";', output)

    def test_cycle(self):
        """Цикл: красное ребро, пометка в дереве и сводка."""
        self.setup_tests()
        _, output, _ = self.run_main("graph_cycle.toml")
        self.assertIn('"C" -> "A" [color=red', output)
        self.assertIn("`-- A (цикл)", output)
        self.assertIn("  C -> A", output)

    def test_filter(self):
        """Исключённые пакеты не показываются и перечисляются."""
        self.setup_tests()
        _, output, _ = self.run_main("graph_complex_filter.toml")
        self.assertIn("Исключены фильтром: F", output)
        self.assertNotIn('"F"', output)

    def test_image_opened(self):
        """Без --no-open картинка открывается."""
        self.setup_tests()
        argv = [
            "--config", str(DATA_DIR / "good_test_mode.toml"),
            "--output-dir", str(self.output_dir),
        ]
        with redirect_stdout(io.StringIO()):
            main(argv)
        self.open.assert_called_once_with(self.output_dir / "A.png")

    def test_render_error(self):
        """Ошибка Graphviz: свой код возврата, DOT-файл уже сохранён."""
        self.setup_tests()
        self.render.side_effect = RenderError("утилита dot не найдена")
        code, _, errors = self.run_main("good_test_mode.toml")
        self.assertEqual(code, EXIT_RENDER_ERROR)
        self.assertIn("утилита dot не найдена", errors)
        self.assertTrue((self.output_dir / "A.dot").is_file())


class ErrorsTest(MainTestCase):
    """Ошибки конфигурации и данных."""

    def test_missing_root(self):
        """Корневого пакета нет в тестовом репозитории."""
        self.setup_tests()
        code, _, errors = self.run_main("graph_missing_root.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("не найден", errors)

    def test_bad_graph_file(self):
        """Ошибка формата тестового файла."""
        self.setup_tests()
        code, _, errors = self.run_main("graph_bad_syntax.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("строка 2", errors)

    def test_config_error(self):
        """Ошибка конфигурации."""
        self.setup_tests()
        code, _, errors = self.run_main("bad_url.toml")
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Ошибка конфигурации", errors)
        self.render.assert_not_called()


class ReverseTest(MainTestCase):
    """Режим обратных зависимостей."""

    def test_reverse_diamond(self):
        """Вместо визуализации выводятся обратные зависимости."""
        self.setup_tests()
        code, output, _ = self.run_main("reverse_diamond.toml")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("D <- B, C", output)
        self.assertIn("Зависят от D (пакетов: 3): A, B, C", output)
        self.render.assert_not_called()

    def test_reverse_cycle(self):
        """Пакет в цикле зависит сам от себя."""
        self.setup_tests()
        _, output, _ = self.run_main("reverse_cycle.toml")
        self.assertIn("A зависит сам от себя через цикл", output)

    def test_reverse_root(self):
        """От корня никто не зависит."""
        self.setup_tests()
        _, output, _ = self.run_main("reverse_root.toml")
        self.assertIn("не зависит ни один пакет", output)

    def test_reverse_missing(self):
        """Пакета для обратных зависимостей нет в графе."""
        self.setup_tests()
        code, _, errors = self.run_main("reverse_missing.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("не входит в граф", errors)


class RegistryModeTest(MainTestCase):
    """Запуск с npm registry (сеть подменена)."""

    def setup_registry_tests(self):
        """Подменить загрузку зависимостей из registry."""
        self.setup_tests()
        self.fetch = self.start_patch("src.main.fetch_direct_deps")

    def test_graph_with_filter(self):
        """Фильтр из good_npm.toml убирает debug."""
        self.setup_registry_tests()
        self.fetch.side_effect = lambda url, name: NPM_DEPS[name]
        code, output, _ = self.run_main("good_npm.toml")
        self.assertEqual(code, EXIT_OK)
        self.assertIn('"express" -> "accepts";', output)
        self.assertIn("Исключены фильтром: debug", output)

    def test_registry_error(self):
        """Ошибка registry уходит в stderr со своим кодом возврата."""
        self.setup_registry_tests()
        self.fetch.side_effect = RegistryError("пакет не найден")
        code, _, errors = self.run_main("good_npm.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("пакет не найден", errors)


if __name__ == "__main__":
    unittest.main()
