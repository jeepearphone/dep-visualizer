"""Тесты получения прямых зависимостей из npm registry без сети."""

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.registry import (
    RegistryError,
    fetch_direct_deps,
    fetch_manifest,
    manifest_url,
    real_package_name,
)

BASE_URL = "https://registry.npmjs.org"
EXPRESS_MANIFEST = {
    "name": "express",
    "version": "5.1.0",
    "dependencies": {"debug": "^4.4.0", "accepts": "^2.0.0"},
    "devDependencies": {"mocha": "^10.0.0"},
}


def json_response(data):
    """Подделать ответ urlopen с JSON-телом."""
    return io.BytesIO(json.dumps(data).encode("utf-8"))


def http_error(code):
    """Создать HTTPError с заданным кодом."""
    return HTTPError(BASE_URL, code, "error", {}, None)


class ManifestUrlTest(unittest.TestCase):
    """Проверки построения URL манифеста."""

    def test_plain_package(self):
        """Обычное имя пакета."""
        self.assertEqual(
            manifest_url(BASE_URL, "express"),
            "https://registry.npmjs.org/express/latest",
        )

    def test_scoped_package(self):
        """Слеш в scoped-имени кодируется, @ остаётся."""
        self.assertEqual(
            manifest_url(BASE_URL, "@types/node"),
            "https://registry.npmjs.org/@types%2Fnode/latest",
        )

    def test_trailing_slash(self):
        """Слеш в конце базового URL не удваивается."""
        self.assertEqual(
            manifest_url(BASE_URL + "/", "express"),
            "https://registry.npmjs.org/express/latest",
        )


@patch("src.registry.urlopen")
class FetchManifestTest(unittest.TestCase):
    """Проверки загрузки и разбора манифеста."""

    def test_dependencies_sorted(self, urlopen):
        """Зависимости берутся из dependencies и сортируются по имени."""
        urlopen.return_value = json_response(EXPRESS_MANIFEST)
        manifest = fetch_manifest(BASE_URL, "express")
        self.assertEqual(manifest.version, "5.1.0")
        self.assertEqual(list(manifest.dependencies), ["accepts", "debug"])

    def test_dev_dependencies_ignored(self, urlopen):
        """devDependencies не считаются зависимостями пакета."""
        urlopen.return_value = json_response(EXPRESS_MANIFEST)
        self.assertNotIn("mocha", fetch_direct_deps(BASE_URL, "express"))

    def test_no_dependencies(self, urlopen):
        """Пакет без поля dependencies даёт пустой список."""
        urlopen.return_value = json_response({"name": "a", "version": "1"})
        self.assertEqual(fetch_direct_deps(BASE_URL, "a"), [])

    def test_request_url(self, urlopen):
        """Запрос уходит на URL манифеста последней версии."""
        urlopen.return_value = json_response(EXPRESS_MANIFEST)
        fetch_manifest(BASE_URL, "express")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, manifest_url(BASE_URL, "express"))

    def test_not_found(self, urlopen):
        """Код 404 означает, что пакета нет."""
        urlopen.side_effect = http_error(404)
        with self.assertRaisesRegex(RegistryError, "не найден"):
            fetch_manifest(BASE_URL, "no-such-package")

    def test_server_error(self, urlopen):
        """Другие HTTP-ошибки сообщают код ответа."""
        urlopen.side_effect = http_error(500)
        with self.assertRaisesRegex(RegistryError, "HTTP 500"):
            fetch_manifest(BASE_URL, "express")

    def test_connection_error(self, urlopen):
        """Ошибка соединения (нет сети, неверный хост)."""
        urlopen.side_effect = URLError("getaddrinfo failed")
        with self.assertRaisesRegex(RegistryError, "не удалось подключиться"):
            fetch_manifest(BASE_URL, "express")

    def test_connect_timeout(self, urlopen):
        """Таймаут при установке соединения."""
        urlopen.side_effect = URLError(TimeoutError())
        with self.assertRaisesRegex(RegistryError, "время ожидания"):
            fetch_manifest(BASE_URL, "express")

    def test_read_timeout(self, urlopen):
        """Таймаут при чтении ответа."""
        urlopen.side_effect = TimeoutError()
        with self.assertRaisesRegex(RegistryError, "время ожидания"):
            fetch_manifest(BASE_URL, "express")

    def test_not_json(self, urlopen):
        """Ответ, который не является JSON."""
        urlopen.return_value = io.BytesIO(b"<html>oops</html>")
        with self.assertRaisesRegex(RegistryError, "не JSON"):
            fetch_manifest(BASE_URL, "express")

    def test_not_object(self, urlopen):
        """JSON, который не является объектом."""
        urlopen.return_value = json_response("Not Found")
        with self.assertRaisesRegex(RegistryError, "не является объектом"):
            fetch_manifest(BASE_URL, "express")

    def test_bad_dependencies_type(self, urlopen):
        """Поле dependencies не словарь."""
        urlopen.return_value = json_response({"dependencies": ["a"]})
        with self.assertRaisesRegex(RegistryError, "неверный тип"):
            fetch_manifest(BASE_URL, "express")

    def test_aliases_resolved(self, urlopen):
        """Алиасы npm:имя@версия заменяются настоящими именами."""
        urlopen.return_value = json_response({"dependencies": {
            "string-width": "^5.1.2",
            "string-width-cjs": "npm:string-width@^4.2.0",
            "types-node": "npm:@types/node@^20.0.0",
        }})
        self.assertEqual(
            fetch_direct_deps(BASE_URL, "cliui"),
            ["string-width", "@types/node"],
        )


class RealPackageNameTest(unittest.TestCase):
    """Проверки разбора алиасов."""

    def test_plain_range(self):
        """Обычный диапазон версий не меняет имя."""
        self.assertEqual(real_package_name("debug", "^4.0.0"), "debug")

    def test_alias_without_version(self):
        """Алиас без версии."""
        self.assertEqual(
            real_package_name("x", "npm:@scope/pkg"), "@scope/pkg"
        )


if __name__ == "__main__":
    unittest.main()
