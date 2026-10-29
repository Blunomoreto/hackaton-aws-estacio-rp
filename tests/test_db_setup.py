"""Testes de exemplo para criação do schema (Requirements 1.1, 8.6)."""

import os
import sqlite3

import db

EXPECTED_COLUMNS = {
    "pets": {
        "id",
        "nome",
        "especie",
        "descricao",
        "lat",
        "lng",
        "data_desaparecimento",
        "status",
        "contato",
    },
    "avistamentos": {"id", "pet_id", "lat", "lng", "data", "observacao"},
    "denuncias": {"id", "tipo", "descricao", "lat", "lng", "data", "distrito"},
}


def _tables(path) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


def _columns(path, table: str) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        conn.close()
    return {r[1] for r in rows}


def test_init_db_cria_arquivo_e_tres_tabelas(tmp_db):
    assert not os.path.exists(tmp_db)

    db.init_db()

    assert os.path.exists(tmp_db)
    assert {"pets", "avistamentos", "denuncias"} <= _tables(tmp_db)


def test_init_db_cria_colunas_do_schema(tmp_db):
    db.init_db()

    for table, expected in EXPECTED_COLUMNS.items():
        assert _columns(tmp_db, table) == expected, table


def test_init_db_e_reexecutavel(tmp_db):
    db.init_db()
    db.init_db()  # CREATE TABLE IF NOT EXISTS: não deve falhar

    assert {"pets", "avistamentos", "denuncias"} <= _tables(tmp_db)


def test_bootstrap_cria_tres_tabelas(tmp_db):
    db.bootstrap()

    assert {"pets", "avistamentos", "denuncias"} <= _tables(tmp_db)
