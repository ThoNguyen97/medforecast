"""
Shared fixtures and configuration for the test suite.

The existing API integration tests (test_supplies, test_inventory, etc.) each
override `app.dependency_overrides[get_db]` at module level with their own
in-memory SQLite engine.  When multiple modules are collected together, the
`autouse=True` `setup_database` fixture in one module calls
`Base.metadata.drop_all()` which removes tables needed by the other module,
because they all share the same `app` singleton and the same underlying
connection pool.

This conftest:
  1. Resets `app.dependency_overrides` after every test so a stale file-based
     DB override from `test_auth.py` cannot bleed into subsequent tests.
  2. The new `test_services_unit.py` does not use TestClient at all — it only
     mocks the DB, so no fixtures here are needed for it.
"""

import pytest

from app.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _isolate_db_override():
    """
    Save and restore app.dependency_overrides around each test.

    This prevents a file-based DB override set by test_auth.py from
    lingering into the in-memory DB modules (test_supplies, test_inventory…).
    """
    saved = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
