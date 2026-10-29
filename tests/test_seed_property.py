"""Testes do seed idempotente do PataSegura.

Feature: patasegura, Property 1: Idempotência do seed
"""

import contextlib
import os
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

import db

TABELAS = ("pets", "avistamentos", "denuncias")


@contextlib.contextmanager
def banco_temporario():
    """Aponta db.DB_PATH para um arquivo novo e restaura o valor original ao sair."""
    original = db.DB_PATH
    tmpdir = tempfile.mkdtemp(prefix="patasegura_seed_")
    db.DB_PATH = os.path.join(tmpdir, "seed_test.db")
    try:
        yield db.DB_PATH
    finally:
        db.DB_PATH = original
        with contextlib.suppress(OSError):
            os.remove(os.path.join(tmpdir, "seed_test.db"))
            os.rmdir(tmpdir)


def contagens() -> dict[str, int]:
    conn = db.get_conn()
    try:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABELAS}
    finally:
        conn.close()


def inserir_pets_manuais(n: int, n_denuncias: int) -> None:
    conn = db.get_conn()
    try:
        with conn:
            for i in range(n):
                conn.execute(
                    "INSERT INTO pets (nome, especie, descricao, lat, lng, "
                    "data_desaparecimento, status, contato) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"Pet{i}", "Gato", "desc", -23.55, -46.63, "2024-01-01",
                     "desaparecido", "(11) 90000-0000"),
                )
            for _ in range(n_denuncias):
                conn.execute(
                    "INSERT INTO denuncias (tipo, descricao, lat, lng, data, distrito) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    ("Abandono", "desc", -23.55, -46.63, "2024-01-01T00:00:00", "Sé"),
                )
    finally:
        conn.close()


# Estado inicial com pets não vazia: ("seed", 0, 0) = banco já populado pelo seed;
# ("manual", n_pets, n_denuncias) = pets inseridos à mão, avistamentos vazios.
estado_inicial = st.one_of(
    st.just(("seed", 0, 0)),
    st.tuples(
        st.just("manual"),
        st.integers(min_value=1, max_value=5),
        st.integers(min_value=0, max_value=3),
    ),
)


@settings(max_examples=100, deadline=None)
@given(estado=estado_inicial, chamadas_extras=st.integers(min_value=1, max_value=5))
def test_seed_idempotente_com_pets_nao_vazia(estado, chamadas_extras):
    """Feature: patasegura, Property 1: Idempotência do seed

    **Validates: Requirements 1.3, 1.4**
    """
    modo, n_pets, n_denuncias = estado
    with banco_temporario():
        if modo == "seed":
            db.bootstrap()
        else:
            db.init_db()
            inserir_pets_manuais(n_pets, n_denuncias)

        antes = contagens()
        assert antes["pets"] >= 1

        for _ in range(chamadas_extras):
            db.seed()

        assert contagens() == antes


def test_seed_em_banco_vazio_popula_as_tres_tabelas(tmp_db):
    """Req 1.3: com pets vazia, seed insere registros em pets, avistamentos e denuncias."""
    db.init_db()
    assert contagens() == {t: 0 for t in TABELAS}

    db.seed()

    resultado = contagens()
    for tabela in TABELAS:
        assert resultado[tabela] >= 1, tabela
