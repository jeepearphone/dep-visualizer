"""Точка входа CLI-приложения dep-visualizer."""

import argparse
import json
import sys

from src.config import ConfigError, load_config

DEFAULT_CONFIG = "config.toml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1


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


def format_value(value):
    """Представить значение так же, как оно записывается в TOML."""
    return json.dumps(value, ensure_ascii=False)


def main(argv=None):
    """Загрузить конфигурацию и вывести параметры в виде ключ = значение."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Ошибка конфигурации:\n{error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    for key, value in config.items():
        print(f"{key} = {format_value(value)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
