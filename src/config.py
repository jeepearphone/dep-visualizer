"""Загрузка и проверка конфигурационного файла в формате TOML."""

import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

FIELD_TYPES = {
    "package": str,
    "repository": str,
    "test_mode": bool,
    "ascii_tree": bool,
    "filter_substring": str,
    "reverse_for": str,
}

TYPE_NAMES = {
    str: "строка",
    bool: "логическое значение (true или false)",
}

URL_SCHEMES = ("http", "https")
MAX_NAME_LENGTH = 214
NPM_NAME_PATTERN = re.compile(
    r"^(@[a-z0-9~-][a-z0-9._~-]*/)?[a-z0-9~-][a-z0-9._~-]*$"
)
TEST_NAME_PATTERN = re.compile(r"^[A-Z]+$")


class ConfigError(Exception):
    """Ошибка конфигурации; каждый аргумент — отдельное сообщение."""

    def __str__(self):
        """Вернуть все сообщения об ошибках, по одному на строку."""
        return "\n".join(self.args)


@dataclass(frozen=True)
class Config:
    """Параметры, которые пользователь задаёт в конфигурационном файле."""

    package: str
    repository: str
    test_mode: bool
    ascii_tree: bool
    filter_substring: str
    reverse_for: str

    def items(self):
        """Вернуть пары (ключ, значение) в порядке объявления полей."""
        return asdict(self).items()


def load_config(path):
    """Прочитать TOML-файл, проверить параметры и вернуть Config.

    Относительный путь к тестовому репозиторию отсчитывается от папки,
    в которой лежит конфигурационный файл. При любой ошибке выбрасывается
    ConfigError со списком всех найденных проблем.
    """
    path = Path(path)
    data = _read_toml(path)
    errors = _check_keys(data) + _check_types(data)
    if not errors:
        errors = _check_values(data, path.parent)
    if errors:
        raise ConfigError(*errors)
    if data["test_mode"]:
        data["repository"] = (path.parent / data["repository"]).as_posix()
    return Config(**data)


def _read_toml(path):
    """Прочитать файл и разобрать его как TOML."""
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError:
        raise ConfigError(f"файл конфигурации не найден: {path}") from None
    except OSError as error:
        raise ConfigError(
            f"не удалось открыть файл конфигурации {path}: {error}"
        ) from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"некорректный TOML в {path}: {error}") from None


def _check_keys(data):
    """Найти отсутствующие и неизвестные параметры."""
    errors = [
        f"{key}: параметр отсутствует"
        for key in FIELD_TYPES
        if key not in data
    ]
    errors += [
        f"{key}: неизвестный параметр"
        for key in sorted(set(data) - set(FIELD_TYPES))
    ]
    return errors


def _check_types(data):
    """Проверить, что у каждого параметра правильный тип."""
    errors = []
    for key, expected in FIELD_TYPES.items():
        if key in data and not isinstance(data[key], expected):
            errors.append(
                f"{key}: ожидается {TYPE_NAMES[expected]}, "
                f"получено {json.dumps(data[key], ensure_ascii=False)}"
            )
    return errors


def _check_values(data, base_dir):
    """Проверить значения параметров с учётом режима работы."""
    test_mode = data["test_mode"]
    filter_substring = data["filter_substring"]
    return (
        _check_name("package", data["package"], test_mode)
        + _check_repository(data["repository"], test_mode, base_dir)
        + _check_filter(filter_substring, data["package"])
        + _check_reverse(data["reverse_for"], test_mode, filter_substring)
    )


def _check_name(key, name, test_mode):
    """Проверить имя пакета: npm-имя или заглавные буквы в тестовом режиме."""
    if not name:
        return [f"{key}: имя пакета не может быть пустым"]
    if len(name) > MAX_NAME_LENGTH:
        return [f"{key}: имя длиннее {MAX_NAME_LENGTH} символов"]
    if test_mode and not TEST_NAME_PATTERN.match(name):
        return [
            f"{key}: в тестовом режиме имя пакета состоит из заглавных "
            f"латинских букв, получено {name!r}"
        ]
    if not test_mode and not NPM_NAME_PATTERN.match(name):
        return [f"{key}: недопустимое имя npm-пакета {name!r}"]
    return []


def _check_reverse(name, test_mode, filter_substring):
    """Проверить пакет для обратных зависимостей: "" отключает режим."""
    if not name:
        return []
    errors = _check_name("reverse_for", name, test_mode)
    if not errors and filter_substring and filter_substring in name:
        errors.append(
            f"reverse_for: пакет {name!r} исключается фильтром "
            f"{filter_substring!r}"
        )
    return errors


def _check_repository(value, test_mode, base_dir):
    """Проверить URL репозитория или путь к файлу тестового репозитория."""
    if not value:
        return ["repository: значение не может быть пустым"]
    if test_mode:
        if not (base_dir / value).is_file():
            return [
                f"repository: файл тестового репозитория не найден: "
                f"{base_dir / value}"
            ]
        return []
    url = urlparse(value)
    if url.scheme not in URL_SCHEMES or not url.netloc:
        return [
            f"repository: ожидается URL вида http(s)://хост, "
            f"получено {value!r}"
        ]
    return []


def _check_filter(value, package):
    """Проверить подстроку фильтра: пустая строка отключает фильтрацию."""
    if any(char.isspace() for char in value):
        return [
            f"filter_substring: имена пакетов не содержат пробелов, "
            f"получено {value!r}"
        ]
    if value and value in package:
        return [
            f"filter_substring: подстрока {value!r} содержится в имени "
            f"анализируемого пакета {package!r}"
        ]
    return []
