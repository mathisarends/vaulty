"""Backward-compatible module entry point for ``python -m vaulty.main``."""

from vaulty.cli import main

if __name__ == "__main__":
    main()
