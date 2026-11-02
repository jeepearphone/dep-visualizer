"""Точка входа CLI-приложения dep-visualizer."""

import argparse
import sys
from functools import partial

from src.config import ConfigError, load_config
from src.graph import build_graph, find_cycle_edges
from src.graph_file import (
    GraphFileError,
    load_graph_file,
    make_dependency_getter,
)
from src.registry import RegistryError, fetch_direct_deps

DEFAULT_CONFIG = "config.toml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_DATA_ERROR = 2


def parse_args(argv=None):
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="dep-visualizer",
        description="Визуализатор графа зависимостей npm-пакетов.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG,
        help=f"путь к конфигурационному файлу (по умолчанию {DEFAULT_CONFIG})",
    )
    return parser.parse_args(argv)


def make_get_deps(config):
    """Выбрать источник зависимостей: тестовый файл или npm registry."""
    if config.test_mode:
        return make_dependency_getter(load_graph_file(config.repository))
    return with_progress(partial(fetch_direct_deps, config.repository))


def with_progress(get_deps):
    """Обернуть get_deps выводом числа загруженных пакетов в stderr."""
    loaded = []

    def get_deps_with_progress(name):
        """Загрузить зависимости и обновить счётчик."""
        deps = get_deps(name)
        loaded.append(name)
        print(
            f"\rЗагружено пакетов: {len(loaded)}",
            end="",
            file=sys.stderr,
            flush=True,
        )
        return deps
    return get_deps_with_progress


def end_progress(config):
    """Завершить строку счётчика загрузки (только в режиме registry)."""
    if not config.test_mode:
        print(file=sys.stderr)


def print_graph(graph):
    """Вывести рёбра графа, циклы и пакеты, исключённые фильтром."""
    print(f"Граф зависимостей {graph.root} (пакетов: {len(graph.edges)}):")
    for name, deps in graph.edges.items():
        print(f"  {name} -> {', '.join(deps) if deps else '(нет)'}")
    cycles = find_cycle_edges(graph)
    if cycles:
        print("Циклические зависимости (ребро, замыкающее цикл):")
        for name, dep in cycles:
            print(f"  {name} -> {dep}")
    else:
        print("Циклических зависимостей нет")
    if graph.excluded:
        print(f"Исключены фильтром: {', '.join(sorted(graph.excluded))}")


def main(argv=None):
    """Загрузить конфигурацию, построить граф зависимостей и вывести его."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации:\n{error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    try:
        graph = build_graph(
            config.package, make_get_deps(config), config.filter_substring
        )
    except (RegistryError, GraphFileError) as error:
        end_progress(config)
        print(f"Ошибка получения данных: {error}", file=sys.stderr)
        return EXIT_DATA_ERROR
    end_progress(config)
    print_graph(graph)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
