"""Построение графа зависимостей обходом в глубину без рекурсии."""

from dataclasses import dataclass, field

IN_PROGRESS = "in_progress"
FINISHED = "finished"


class GraphError(Exception):
    """Ошибка операции над графом зависимостей."""


@dataclass
class DependencyGraph:
    """Граф зависимостей, достижимых из корневого пакета.

    edges хранит для каждого пакета список его зависимостей в порядке
    обхода; excluded — пакеты, отброшенные фильтром.
    """

    root: str
    edges: dict = field(default_factory=dict)
    excluded: set = field(default_factory=set)


def is_excluded(name, filter_substring):
    """Проверить, отбрасывается ли пакет фильтром по подстроке."""
    return bool(filter_substring) and filter_substring in name


def build_graph(root, get_deps, filter_substring=""):
    """Построить граф обходом в глубину с явным стеком.

    get_deps(name) возвращает прямые зависимости пакета. Каждый пакет
    запрашивается один раз: повторно встреченный пакет (общая
    зависимость или цикл) не обходится заново, но ребро к нему
    сохраняется. Пакеты, содержащие filter_substring, не попадают в
    граф и не обходятся.
    """
    graph = DependencyGraph(root)
    stack = [root]
    while stack:
        name = stack.pop()
        if name in graph.edges:
            continue
        deps = []
        for dep in get_deps(name):
            if is_excluded(dep, filter_substring):
                graph.excluded.add(dep)
            else:
                deps.append(dep)
        graph.edges[name] = deps
        stack.extend(reversed(deps))
    return graph


def find_cycle_edges(graph):
    """Найти рёбра, замыкающие циклы (обратные рёбра DFS).

    Обход в глубину без рекурсии: на стеке лежат пары (пакет, итератор
    по его зависимостям). Ребро в пакет, который ещё находится на
    стеке, замыкает цикл.
    """
    state = {graph.root: IN_PROGRESS}
    stack = [(graph.root, iter(graph.edges.get(graph.root, [])))]
    cycle_edges = []
    while stack:
        name, deps = stack[-1]
        dep = next(deps, None)
        if dep is None:
            state[name] = FINISHED
            stack.pop()
        elif state.get(dep) == IN_PROGRESS:
            cycle_edges.append((name, dep))
        elif dep not in state:
            state[dep] = IN_PROGRESS
            stack.append((dep, iter(graph.edges.get(dep, []))))
    return cycle_edges


def reverse_edges(edges):
    """Развернуть рёбра: для каждого пакета — кто от него зависит."""
    reversed_edges = {name: [] for name in edges}
    for name, deps in edges.items():
        for dep in deps:
            reversed_edges.setdefault(dep, []).append(name)
    return reversed_edges


def find_dependents(graph, target):
    """Найти пакеты графа, которые прямо или транзитивно зависят от target.

    Рёбра графа разворачиваются, и по ним выполняется тот же обход в
    глубину build_graph, что и при построении графа. Результат —
    граф обратных зависимостей с корнем target.
    """
    if target not in graph.edges:
        raise GraphError(
            f"пакет {target} не входит в граф зависимостей {graph.root}"
        )
    reversed_edges = reverse_edges(graph.edges)
    return build_graph(target, reversed_edges.__getitem__)


def dependents_of(reverse_graph):
    """Вернуть отсортированный список пакетов, зависящих от корня."""
    return sorted(
        name for name in reverse_graph.edges if name != reverse_graph.root
    )


def depends_on_itself(reverse_graph):
    """Проверить, зависит ли корень от самого себя через цикл."""
    return any(
        reverse_graph.root in deps for deps in reverse_graph.edges.values()
    )
