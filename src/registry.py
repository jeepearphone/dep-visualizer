"""Получение прямых зависимостей пакета из npm registry по HTTP."""

import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

TIMEOUT_SECONDS = 15
HTTP_NOT_FOUND = 404
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "dep-visualizer",
}
ALIAS_PATTERN = re.compile(r"^npm:(@?[^@]+)")


class RegistryError(Exception):
    """Ошибка получения или разбора данных из npm registry."""


@dataclass(frozen=True)
class Manifest:
    """Сведения о последней версии пакета, нужные для анализа."""

    name: str
    version: str
    dependencies: dict


def manifest_url(base_url, name):
    """Построить URL манифеста последней версии пакета.

    Слеш в имени scoped-пакета (@scope/name) кодируется как %2F.
    """
    return f"{base_url.rstrip('/')}/{quote(name, safe='@')}/latest"


def fetch_manifest(base_url, name):
    """Скачать манифест последней версии пакета и проверить его."""
    data = _fetch_json(manifest_url(base_url, name), name)
    if not isinstance(data, dict):
        raise RegistryError(f"{name}: ответ registry не является объектом")
    dependencies = data.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise RegistryError(f"{name}: поле dependencies имеет неверный тип")
    return Manifest(
        name=data.get("name", name),
        version=str(data.get("version", "?")),
        dependencies=dict(sorted(dependencies.items())),
    )


def real_package_name(name, version_range):
    """Вернуть настоящее имя пакета с учётом алиаса «npm:имя@версия»."""
    match = ALIAS_PATTERN.match(str(version_range))
    return match.group(1) if match else name


def fetch_direct_deps(base_url, name):
    """Вернуть имена прямых зависимостей пакета (поле dependencies).

    Алиасы заменяются настоящими именами пакетов, повторы убираются.
    """
    dependencies = fetch_manifest(base_url, name).dependencies
    names = (
        real_package_name(dep, version_range)
        for dep, version_range in dependencies.items()
    )
    return list(dict.fromkeys(names))


def _fetch_json(url, name):
    """Выполнить GET-запрос и разобрать ответ как JSON."""
    request = Request(url, headers=REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read()
    except HTTPError as error:
        raise RegistryError(_http_error_message(error, name)) from None
    except URLError as error:
        raise RegistryError(_url_error_message(error, url)) from None
    except TimeoutError:
        raise RegistryError(
            f"превышено время ожидания ответа от {url}"
        ) from None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RegistryError(f"{name}: registry вернул не JSON") from None


def _http_error_message(error, name):
    """Сформировать текст ошибки для HTTP-ответа с кодом ошибки."""
    if error.code == HTTP_NOT_FOUND:
        return f"пакет не найден в registry: {name}"
    return f"{name}: registry ответил HTTP {error.code} {error.reason}"


def _url_error_message(error, url):
    """Сформировать текст ошибки соединения."""
    if isinstance(error.reason, TimeoutError):
        return f"превышено время ожидания ответа от {url}"
    return f"не удалось подключиться к {url}: {error.reason}"
