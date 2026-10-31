#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ "$1" = "test" ]; then
    exec python3 -m unittest discover -s tests -v
fi
exec python3 -m src.main "$@"
