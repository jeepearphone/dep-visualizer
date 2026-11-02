"""Чтение тестового репозитория: файла с описанием графа зависимостей.

Формат: каждая непустая строка имеет вид «ИМЯ: ЗАВИСИМОСТЬ ...», имена
пакетов состоят из заглавных латинских букв. Пакет, который упоминается
только как зависимость, считается пакетом без зависимостей.
"""

import re

NAME_PATTERN = re.compile(r"^[A-Z]+$")
SEPARATOR = ":"


class GraphFileError(Exception):
    """Ошибка чтения или формата файла тестового репозитория."""


def load_graph_file(path):
    """Прочитать файл и вернуть словарь «пакет → список зависимостей»."""
    graph = {}
    for number, line in enumerate(_read_lines(path), start=1):
        if not line.strip():
            continue
        name, deps = _parse_line(line, number)
        if name in graph:
            raise GraphFileError(
                f"строка {number}: пакет {name} описан повторно"
            )
        graph[name] = deps
    for dep in _all_dependencies(graph):
        graph.setdefault(dep, [])
    return graph


def make_dependency_getter(graph):
    """Вернуть функцию get_deps(name) для графа из тестового файла."""
    def get_deps(name):
        """Вернуть зависимости пакета из тестового репозитория."""
        if name not in graph:
            raise GraphFileError(
                f"пакет не найден в тестовом репозитории: {name}"
            )
        return graph[name]
    return get_deps


def _read_lines(path):
    """Прочитать строки файла в кодировке UTF-8."""
    try:
        with open(path, encoding="utf-8") as file:
            return file.read().splitlines()
    except OSError as error:
        raise GraphFileError(f"не удалось прочитать {path}: {error}") from None
    except UnicodeDecodeError:
        raise GraphFileError(f"файл {path} не в кодировке UTF-8") from None


def _parse_line(line, number):
    """Разобрать строку «ИМЯ: ЗАВИСИМОСТИ» и проверить имена."""
    name, separator, rest = line.partition(SEPARATOR)
    if not separator:
        raise GraphFileError(
            f"строка {number}: ожидается «ИМЯ: ЗАВИСИМОСТИ», "
            f"получено {line.strip()!r}"
        )
    name = name.strip()
    deps = rest.split()
    for item in [name, *deps]:
        if not NAME_PATTERN.match(item):
            raise GraphFileError(
                f"строка {number}: имя пакета должно состоять из заглавных "
                f"латинских букв, получено {item!r}"
            )
    if len(set(deps)) != len(deps):
        raise GraphFileError(f"строка {number}: зависимость указана дважды")
    return name, deps


def _all_dependencies(graph):
    """Вернуть множество всех пакетов, упомянутых как зависимости."""
    return {dep for deps in graph.values() for dep in deps}
