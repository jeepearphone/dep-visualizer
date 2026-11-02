"""Тесты вывода и кодов возврата CLI."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.main import EXIT_CONFIG_ERROR, EXIT_DATA_ERROR, EXIT_OK, main
from src.registry import RegistryError

DATA_DIR = Path(__file__).parent / "data"
NPM_DEPS = {"express": ["accepts", "debug"], "accepts": [], "debug": []}


def run_main(file_name):
    """Запустить main с конфигом из tests/data и вернуть код и вывод."""
    output, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        code = main(["--config", str(DATA_DIR / file_name)])
    return code, output.getvalue(), errors.getvalue()


class TestModeTest(unittest.TestCase):
    """Запуск на тестовых репозиториях."""

    def test_diamond(self):
        """Ромб: все рёбра, циклов нет."""
        code, output, _ = run_main("good_test_mode.toml")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("A -> B, C", output)
        self.assertIn("D -> (нет)", output)
        self.assertIn("Циклических зависимостей нет", output)

    def test_cycle(self):
        """Цикл выводится отдельно."""
        _, output, _ = run_main("graph_cycle.toml")
        self.assertIn("Циклические зависимости", output)
        self.assertIn("C -> A", output)

    def test_filter(self):
        """Исключённые пакеты перечисляются."""
        _, output, _ = run_main("graph_complex_filter.toml")
        self.assertIn("Исключены фильтром: F", output)
        self.assertIn("B -> E\n", output)

    def test_missing_root(self):
        """Корневого пакета нет в тестовом репозитории."""
        code, _, errors = run_main("graph_missing_root.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("не найден", errors)

    def test_bad_graph_file(self):
        """Ошибка формата тестового файла."""
        code, _, errors = run_main("graph_bad_syntax.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("строка 2", errors)

    def test_reverse_diamond(self):
        """Режим обратных зависимостей вместо вывода графа."""
        code, output, _ = run_main("reverse_diamond.toml")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("D <- B, C", output)
        self.assertIn("Зависят от D (пакетов: 3): A, B, C", output)
        self.assertNotIn("Граф зависимостей", output)

    def test_reverse_cycle(self):
        """Пакет в цикле зависит сам от себя."""
        _, output, _ = run_main("reverse_cycle.toml")
        self.assertIn("A зависит сам от себя через цикл", output)

    def test_reverse_root(self):
        """От корня никто не зависит."""
        _, output, _ = run_main("reverse_root.toml")
        self.assertIn("не зависит ни один пакет", output)

    def test_reverse_missing(self):
        """Пакета для обратных зависимостей нет в графе."""
        code, _, errors = run_main("reverse_missing.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("не входит в граф", errors)

    def test_config_error(self):
        """Ошибка конфигурации."""
        code, _, errors = run_main("bad_url.toml")
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Ошибка конфигурации", errors)


@patch("src.main.fetch_direct_deps")
class RegistryModeTest(unittest.TestCase):
    """Запуск с npm registry (сеть подменена)."""

    def test_graph_with_filter(self, fetch_direct_deps):
        """Фильтр из good_npm.toml убирает debug."""
        fetch_direct_deps.side_effect = lambda url, name: NPM_DEPS[name]
        code, output, _ = run_main("good_npm.toml")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("express -> accepts", output)
        self.assertIn("Исключены фильтром: debug", output)

    def test_registry_error(self, fetch_direct_deps):
        """Ошибка registry уходит в stderr со своим кодом возврата."""
        fetch_direct_deps.side_effect = RegistryError("пакет не найден")
        code, _, errors = run_main("good_npm.toml")
        self.assertEqual(code, EXIT_DATA_ERROR)
        self.assertIn("пакет не найден", errors)


if __name__ == "__main__":
    unittest.main()
