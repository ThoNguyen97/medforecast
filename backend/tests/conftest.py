"""Fixture dùng chung cho bộ test.

Các module test cùng dùng singleton `app` và ghi đè `app.dependency_overrides[get_db]`
theo CSDL riêng; fixture ở đây khôi phục trạng thái ghi đè sau mỗi test để một
override còn sót (ví dụ CSDL file của test_auth.py) không ảnh hưởng test sau.
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
