# dep-visualizer

CLI-инструмент для построения и визуализации графа зависимостей
npm-пакетов (практическая работа №2, вариант 11). Данные о зависимостях
берутся напрямую из npm registry по HTTP, без менеджеров пакетов и
сторонних библиотек.

Требуется Python 3.11 или новее (используется встроенный модуль
`tomllib`). Сторонние зависимости не нужны.

## Структура

| Путь | Назначение |
|------|------------|
| `src/main.py` | точка входа, разбор аргументов командной строки |
| `src/config.py` | загрузка и проверка конфигурации TOML |
| `tests/` | модульные тесты (`unittest`) |
| `tests/data/` | примеры корректных и ошибочных конфигураций |
| `config.toml` | пример конфигурации |
| `run.bat`, `run.sh` | скрипты запуска приложения и тестов |

## Конфигурация

Параметры задаются в TOML-файле. Все параметры обязательны, лишние
параметры считаются ошибкой.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `package` | строка | имя анализируемого пакета |
| `repository` | строка | URL npm registry или путь к файлу тестового репозитория |
| `test_mode` | bool | `true` — работа с тестовым репозиторием из файла |
| `ascii_tree` | bool | `true` — выводить зависимости в виде ASCII-дерева |
| `filter_substring` | строка | пакеты, имя которых содержит подстроку, не учитываются; `""` — без фильтра |

Пример (`config.toml`):

```toml
package = "express"
repository = "https://registry.npmjs.org"
test_mode = false
ascii_tree = true
filter_substring = "debug"
```

### Проверки параметров

- файл конфигурации существует и является корректным TOML;
- присутствуют все параметры и нет неизвестных;
- `test_mode` и `ascii_tree` — логические значения, остальные — строки;
- `package` не пустой, не длиннее 214 символов; в обычном режиме —
  допустимое имя npm-пакета (в том числе `@scope/name`), в тестовом —
  заглавные латинские буквы (`A`, `B`, `AB`);
- `repository` в обычном режиме — URL со схемой `http` или `https`,
  в тестовом — существующий файл; относительный путь отсчитывается от
  папки, где лежит конфигурационный файл;
- `filter_substring` не содержит пробельных символов.

При ошибке все найденные проблемы выводятся в stderr, код возврата 1.

## Запуск

Windows:

```bat
run.bat
run.bat --config tests\data\good_test_mode.toml
```

Linux / macOS:

```sh
./run.sh --config tests/data/good_test_mode.toml
```

Напрямую: `python -m src.main --config config.toml`. Без `--config`
используется `config.toml` из текущей папки.

## Тесты

```sh
run.bat test
./run.sh test
python -m unittest discover -s tests -v
```

Проверка стиля (необязательно):

```sh
pip install -r requirements-dev.txt
flake8 --max-line-length 80 --max-complexity 10 src tests
```

## Примеры

Корректная конфигурация:

```
> run.bat
package = "express"
repository = "https://registry.npmjs.org"
test_mode = false
ascii_tree = true
filter_substring = "debug"
```

Ошибки типов (`tests/data/bad_types.toml`):

```
> run.bat --config tests\data\bad_types.toml
Ошибка конфигурации:
package: ожидается строка, получено 42
test_mode: ожидается логическое значение (true или false), получено "yes"
ascii_tree: ожидается логическое значение (true или false), получено 1
filter_substring: ожидается строка, получено false
```

Отсутствующие параметры (`tests/data/bad_missing_keys.toml`):

```
> run.bat --config tests\data\bad_missing_keys.toml
Ошибка конфигурации:
repository: параметр отсутствует
ascii_tree: параметр отсутствует
filter_substring: параметр отсутствует
```

Другие ошибочные конфигурации лежат в `tests/data/bad_*.toml`.
