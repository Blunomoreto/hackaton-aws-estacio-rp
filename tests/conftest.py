"""Fixtures compartilhadas dos testes do PataSegura."""

import os
import sys

import pytest

# Garante que a raiz do workspace (onde ficam app.py, db.py, maps.py) é importável,
# mesmo se o pytest for executado sem o pytest.ini.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import db  # noqa: E402

APP_PATH = os.path.join(ROOT, "app.py")


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Aponta db.DB_PATH para um arquivo temporário, isolando o patasegura.db real."""
    path = tmp_path / "patasegura_test.db"
    monkeypatch.setattr(db, "DB_PATH", str(path))
    return path


@pytest.fixture
def app_path():
    """Caminho absoluto do entrypoint Streamlit."""
    return APP_PATH
