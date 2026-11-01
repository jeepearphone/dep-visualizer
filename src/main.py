"""Точка входа CLI-приложения dep-visualizer."""

import argparse
import sys

from src.config import ConfigError, load_config
from src.registry import RegistryError, fetch_manifest

DEFAULT_CONFIG = "config.toml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_REGISTRY_ERROR = 2


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


def print_manifest(manifest):
    """Вывести прямые зависимости пакета с диапазонами версий."""
    print(f"Прямые зависимости {manifest.name}@{manifest.version}:")
    if not manifest.dependencies:
        print("  (нет зависимостей)")
    for name, version_range in manifest.dependencies.items():
        print(f"  {name} {version_range}")


def main(argv=None):
    """Загрузить конфигурацию и вывести прямые зависимости пакета."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации:\n{error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    if config.test_mode:
        print("Тестовый режим пока не поддерживается", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    try:
        manifest = fetch_manifest(config.repository, config.package)
    except RegistryError as error:
        print(f"Ошибка получения данных: {error}", file=sys.stderr)
        return EXIT_REGISTRY_ERROR
    print_manifest(manifest)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
