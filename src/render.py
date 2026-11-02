"""Визуализация графа: описание на Graphviz (DOT), картинка, ASCII-дерево."""

import os
import re
import subprocess
import sys
from pathlib import Path

from src.graph import find_cycle_edges

DOT_COMMAND = "dot"
IMAGE_FORMAT = "png"
UNSAFE_FILE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
ROOT_ATTRS = '[style="rounded,filled", fillcolor=lightblue]'
CYCLE_ATTRS = " [color=red, penwidth=2]"
TREE_BRANCH = "+-- "
TREE_LAST = "`-- "
TREE_PIPE = "|   "
TREE_SPACE = "    "
MARK_CYCLE = " (цикл)"
MARK_REPEAT = " (повтор)"


class RenderError(Exception):
    """Ошибка построения или показа изображения графа."""


def quote_id(name):
    """Записать имя пакета как идентификатор DOT в двойных кавычках."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def to_dot(graph):
    """Сформировать описание графа на языке Graphviz.

    Корневой пакет выделяется заливкой, рёбра, замыкающие циклы, —
    красным цветом.
    """
    cycle_edges = set(find_cycle_edges(graph))
    lines = [
        "digraph dependencies {",
        "    rankdir=LR;",
        "    node [shape=box, style=rounded, fontname=Helvetica];",
        f"    {quote_id(graph.root)} {ROOT_ATTRS};",
    ]
    for name, deps in graph.edges.items():
        for dep in deps:
            attrs = CYCLE_ATTRS if (name, dep) in cycle_edges else ""
            lines.append(f"    {quote_id(name)} -> {quote_id(dep)}{attrs};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def ascii_tree(graph):
    """Построить ASCII-дерево зависимостей обходом в глубину без рекурсии.

    Пакет раскрывается только при первой встрече; повторные встречи
    помечаются «(повтор)», а пакеты, уже стоящие на пути от корня, —
    «(цикл)».
    """
    lines = [graph.root]
    expanded = {graph.root}
    stack = _tree_children(graph, graph.root, "", (graph.root,))
    while stack:
        name, prefix, is_last, path = stack.pop()
        mark = _tree_mark(name, path, expanded)
        connector = TREE_LAST if is_last else TREE_BRANCH
        lines.append(f"{prefix}{connector}{name}{mark}")
        if not mark:
            expanded.add(name)
            child_prefix = prefix + (TREE_SPACE if is_last else TREE_PIPE)
            stack.extend(
                _tree_children(graph, name, child_prefix, path + (name,))
            )
    return lines


def safe_file_name(name):
    """Превратить имя пакета в имя файла (@scope/name → _scope_name)."""
    return UNSAFE_FILE_CHARS.sub("_", name)


def save_dot(dot_text, output_dir, name):
    """Сохранить описание графа в файл <output_dir>/<name>.dot."""
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        dot_path = output_dir / f"{safe_file_name(name)}.dot"
        dot_path.write_text(dot_text, encoding="utf-8")
    except OSError as error:
        raise RenderError(f"не удалось сохранить DOT-файл: {error}") from None
    return dot_path


def render_image(dot_path):
    """Отрисовать DOT-файл утилитой Graphviz dot и вернуть путь к PNG."""
    image_path = dot_path.with_suffix(f".{IMAGE_FORMAT}")
    command = [
        DOT_COMMAND, f"-T{IMAGE_FORMAT}", str(dot_path), "-o", str(image_path)
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise RenderError(
            "утилита dot не найдена: установите Graphviz "
            "(https://graphviz.org/download/) и добавьте его в PATH"
        ) from None
    except subprocess.CalledProcessError as error:
        raise RenderError(
            f"dot завершился с ошибкой: {error.stderr.strip()}"
        ) from None
    return image_path


def open_image(path):
    """Открыть изображение в программе просмотра по умолчанию."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as error:
        raise RenderError(f"не удалось открыть {path}: {error}") from None


def _tree_children(graph, name, prefix, path):
    """Вернуть элементы стека для зависимостей пакета.

    Элементы идут в обратном порядке, чтобы первой со стека снималась
    первая зависимость; последняя зависимость помечается is_last.
    """
    items = []
    for dep in reversed(graph.edges.get(name, [])):
        items.append((dep, prefix, not items, path))
    return items


def _tree_mark(name, path, expanded):
    """Пометка узла дерева: цикл, повтор или пустая строка."""
    if name in path:
        return MARK_CYCLE
    if name in expanded:
        return MARK_REPEAT
    return ""
