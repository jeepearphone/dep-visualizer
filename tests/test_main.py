"""Тесты вывода и кодов возврата CLI."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.main import (
    EXIT_CONFIG_ERROR,
    EXIT_OK,
    EXIT_REGISTRY_ERROR,
    main,
)
from src.registry import Manifest, RegistryError

DATA_DIR = Path(__file__).parent / "data"
NPM_CONFIG = str(DATA_DIR / "good_npm.toml")


def run_main(config_path):
    """Запустить main и вернуть код возврата, stdout и stderr."""
    output, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        code = main(["--config", config_path])
    return code, output.getvalue(), errors.getvalue()


@patch("src.main.fetch_manifest")
class MainTest(unittest.TestCase):
    """Проверки сценариев запуска приложения."""

    def test_prints_direct_dependencies(self, fetch_manifest):
        """Выводятся имя, версия и все прямые зависимости."""
        fetch_manifest.return_value = Manifest(
            "express", "5.1.0", {"accepts": "^2.0.0", "debug": "^4.4.0"}
        )
        code, output, _ = run_main(NPM_CONFIG)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("express@5.1.0", output)
        self.assertIn("accepts ^2.0.0", output)
        self.assertIn("debug ^4.4.0", output)
        fetch_manifest.assert_called_once_with(
            "https://registry.npmjs.org", "express"
        )

    def test_no_dependencies(self, fetch_manifest):
        """Пакет без зависимостей."""
        fetch_manifest.return_value = Manifest("express", "1.0.0", {})
        _, output, _ = run_main(NPM_CONFIG)
        self.assertIn("нет зависимостей", output)

    def test_registry_error(self, fetch_manifest):
        """Ошибка registry уходит в stderr со своим кодом возврата."""
        fetch_manifest.side_effect = RegistryError("пакет не найден")
        code, _, errors = run_main(NPM_CONFIG)
        self.assertEqual(code, EXIT_REGISTRY_ERROR)
        self.assertIn("пакет не найден", errors)

    def test_config_error(self, fetch_manifest):
        """При ошибке конфигурации registry не запрашивается."""
        code, _, errors = run_main(str(DATA_DIR / "bad_url.toml"))
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Ошибка конфигурации", errors)
        fetch_manifest.assert_not_called()

    def test_test_mode_not_supported(self, fetch_manifest):
        """Тестовый режим пока не поддерживается и сообщает об этом."""
        code, _, errors = run_main(str(DATA_DIR / "good_test_mode.toml"))
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Тестовый режим", errors)
        fetch_manifest.assert_not_called()


if __name__ == "__main__":
    unittest.main()
