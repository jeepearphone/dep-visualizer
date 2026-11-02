"""Точка входа CLI-приложения dep-visualizer."""

import argparse
import sys
from functools import partial

from src.config import ConfigError, load_config
from src.graph import (
    GraphError,
    build_graph,
    dependents_of,
    depends_on_itself,
    find_cycle_edges,
    find_dependents,
)
from src.graph_file import (
    GraphFileError,
    load_graph_file,
    make_dependency_getter,
)
from src.registry import RegistryError, fetch_direct_deps
from src.render import (
    RenderError,
    ascii_tree,
    open_image,
    render_image,
    save_dot,
    to_dot,
)

DEFAULT_CONFIG = "config.toml"
DEFAULT_OUTPUT_DIR = "out"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_DATA_ERROR = 2
EXIT_RENDER_ERROR = 3


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
    parser.add_argument(
        "-o",
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"папка для .dot и .png (по умолчанию {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="не открывать изображение графа после построения",
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


def visualize(graph, config, args):
    """Вывести описание на Graphviz и ASCII-дерево, показать картинку."""
    dot_text = to_dot(graph)
    dot_path = save_dot(dot_text, args.output_dir, graph.root)
    print(f"Описание графа на языке Graphviz ({dot_path.as_posix()}):")
    print(dot_text)
    if config.ascii_tree:
        print("ASCII-дерево зависимостей:")
        print("\n".join(ascii_tree(graph)))
        print()
    print_summary(graph)
    image_path = render_image(dot_path)
    print(f"Изображение графа: {image_path.as_posix()}")
    if not args.no_open:
        open_image(image_path)


def print_summary(graph):
    """Вывести число пакетов, циклы и пакеты, исключённые фильтром."""
    print(f"Пакетов в графе {graph.root}: {len(graph.edges)}")
    cycles = find_cycle_edges(graph)
    if cycles:
        print("Циклические зависимости (ребро, замыкающее цикл):")
        for name, dep in cycles:
            print(f"  {name} -> {dep}")
    else:
        print("Циклических зависимостей нет")
    if graph.excluded:
        print(f"Исключены фильтром: {', '.join(sorted(graph.excluded))}")


def print_dependents(graph, reverse_graph):
    """Вывести обратные зависимости: кто зависит от заданного пакета."""
    target = reverse_graph.root
    print(f"Обратные зависимости {target} в графе {graph.root}")
    print("(пакет <- пакеты, которые от него напрямую зависят):")
    for name, dependents in reverse_graph.edges.items():
        print(f"  {name} <- {', '.join(dependents) or '(нет)'}")
    dependents = dependents_of(reverse_graph)
    if dependents:
        print(
            f"Зависят от {target} (пакетов: {len(dependents)}): "
            f"{', '.join(dependents)}"
        )
    else:
        print(f"От {target} не зависит ни один пакет графа")
    if depends_on_itself(reverse_graph):
        print(f"{target} зависит сам от себя через цикл")


def show_result(graph, config, args):
    """Показать граф или обратные зависимости, если задан reverse_for."""
    if config.reverse_for:
        reverse_graph = find_dependents(graph, config.reverse_for)
        print_dependents(graph, reverse_graph)
    else:
        visualize(graph, config, args)


def main(argv=None):
    """Загрузить конфигурацию, построить граф и вывести результат."""
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
    try:
        show_result(graph, config, args)
    except GraphError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_DATA_ERROR
    except RenderError as error:
        print(f"Ошибка визуализации: {error}", file=sys.stderr)
        return EXIT_RENDER_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
