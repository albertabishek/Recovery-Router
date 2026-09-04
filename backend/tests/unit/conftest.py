"""Fixtures for unit tests — no DB, no Redis, no HTTP."""
import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "/unit/" in str(item.fspath) or "\\unit\\" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
