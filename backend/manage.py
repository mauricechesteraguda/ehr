#!/usr/bin/env python3
"""type-10022026-Maurice: Django management entry point."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    """type-10022026-Maurice: Start Django management commands."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
