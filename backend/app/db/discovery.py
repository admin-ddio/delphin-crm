"""Import every `models` module under `app` so Base.metadata is complete.

Used by Alembic and the test suite; new modules are picked up automatically.
"""

from __future__ import annotations

import importlib
import pkgutil

import app


def import_all_models() -> list[str]:
    imported: list[str] = []
    for module in pkgutil.walk_packages(app.__path__, prefix="app."):
        if module.name.endswith(".models"):
            importlib.import_module(module.name)
            imported.append(module.name)
    return imported
