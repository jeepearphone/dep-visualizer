"""Тесты загрузки и проверки конфигурационного файла."""

import unittest
from pathlib import Path

from src.config import Config, ConfigError, load_config

DATA_DIR = Path(__file__).parent / "data"


class LoadConfigTest(unittest.TestCase):
    """Проверки функции load_config на корректных и ошибочных файлах."""

    def assert_error(self, file_name, *fragments):
        """Убедиться, что файл отклонён и сообщение содержит фрагменты."""
        with self.assertRaises(ConfigError) as context:
            load_config(DATA_DIR / file_name)
        message = str(context.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)

    def test_good_npm_config(self):
        """Корректный конфиг для npm загружается полностью."""
        config = load_config(DATA_DIR / "good_npm.toml")
        expected = Config(
            package="express",
            repository="https://registry.npmjs.org",
            test_mode=False,
            ascii_tree=True,
            filter_substring="debug",
            reverse_for="",
        )
        self.assertEqual(config, expected)

    def test_good_reverse_config(self):
        """Корректный конфиг с режимом обратных зависимостей."""
        config = load_config(DATA_DIR / "reverse_diamond.toml")
        self.assertEqual(config.reverse_for, "D")

    def test_good_test_mode_resolves_path(self):
        """В тестовом режиме путь считается от папки конфига."""
        config = load_config(DATA_DIR / "good_test_mode.toml")
        self.assertTrue(config.test_mode)
        self.assertEqual(Path(config.repository), DATA_DIR / "diamond.txt")

    def test_file_not_found(self):
        """Несуществующий файл конфигурации."""
        self.assert_error("no_such_file.toml", "не найден")

    def test_directory_instead_of_file(self):
        """Вместо файла указана папка."""
        with self.assertRaises(ConfigError):
            load_config(DATA_DIR)

    def test_bad_syntax(self):
        """Файл не является корректным TOML."""
        self.assert_error("bad_syntax.toml", "некорректный TOML")

    def test_missing_keys(self):
        """Отсутствующие параметры перечислены все."""
        self.assert_error(
            "bad_missing_keys.toml",
            "repository: параметр отсутствует",
            "ascii_tree: параметр отсутствует",
            "filter_substring: параметр отсутствует",
            "reverse_for: параметр отсутствует",
        )

    def test_unknown_key(self):
        """Лишний параметр считается ошибкой."""
        self.assert_error("bad_unknown_key.toml", "version: неизвестный")

    def test_wrong_types(self):
        """Ошибки типа выводятся для каждого параметра."""
        self.assert_error(
            "bad_types.toml",
            "package: ожидается строка",
            "test_mode: ожидается логическое",
            "ascii_tree: ожидается логическое",
            "filter_substring: ожидается строка",
            "reverse_for: ожидается строка",
        )

    def test_empty_package(self):
        """Пустое имя пакета."""
        self.assert_error("bad_empty_package.toml", "не может быть пустым")

    def test_invalid_package_name(self):
        """Имя с пробелами и заглавными буквами недопустимо в npm."""
        self.assert_error("bad_package_name.toml", "недопустимое имя")

    def test_bad_url_scheme(self):
        """URL репозитория должен начинаться с http:// или https://."""
        self.assert_error("bad_url.toml", "ожидается URL")

    def test_missing_test_repository(self):
        """Файл тестового репозитория не существует."""
        self.assert_error("bad_test_file.toml", "не найден")

    def test_test_mode_package_name(self):
        """В тестовом режиме пакеты называются заглавными буквами."""
        self.assert_error("bad_test_package.toml", "заглавных")

    def test_filter_with_spaces(self):
        """Подстрока фильтра с пробелом никогда не совпадёт с именем."""
        self.assert_error("bad_filter.toml", "filter_substring")

    def test_filter_matches_root(self):
        """Фильтр, исключающий сам анализируемый пакет."""
        self.assert_error("bad_filter_root.toml", "анализируемого пакета")

    def test_reverse_bad_name(self):
        """Имя для обратных зависимостей проверяется как имя пакета."""
        self.assert_error("bad_reverse_name.toml", "reverse_for: в тестовом")

    def test_reverse_filtered(self):
        """Пакет для обратных зависимостей исключён фильтром."""
        self.assert_error("bad_reverse_filtered.toml", "исключается фильтром")


if __name__ == "__main__":
    unittest.main()
