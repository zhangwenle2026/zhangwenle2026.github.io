#!/usr/bin/env python3
"""Compatibility wrapper for the kdata-fl CLI.

Use `kdata-fl` or `python3 scripts/kdata_fl.py ...` as the primary entrypoint.
"""

from __future__ import annotations

from kdata_fl import main


if __name__ == "__main__":
    main()
