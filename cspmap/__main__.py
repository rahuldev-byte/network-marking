"""Module entry point: python3 -m cspmap."""

from .cli import arguments, main, nonnegative, positive, run

__all__ = ["arguments", "main", "nonnegative", "positive", "run"]

if __name__ == "__main__":
    raise SystemExit(main())
