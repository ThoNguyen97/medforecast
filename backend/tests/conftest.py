"""Fixture dùng chung: khôi phục app.dependency_overrides sau mỗi test để
override CSDL của module này không lọt sang module khác.
"""

import pytest

from app.main import app


@pytest.fixture(autouse=True)
def _isolate_db_override():
    """Lưu và khôi phục app.dependency_overrides quanh mỗi test."""
    saved = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
