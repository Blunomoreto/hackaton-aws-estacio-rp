"""Testes de propriedade das métricas de topo e do índice de risco do PataSegura.

Feature: patasegura, Property 5: Métricas iguais às contagens reais
Feature: patasegura, Property 15: Índice de risco igual à contagem por distrito
"""

import contextlib
import os
import tempfile
from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

import db


@contextlib.contextmanager
def banco_temporario():
    """Aponta db.DB_PATH para um banco novo (com schema) e restaura ao sair."""
    original = db.DB_PATH
    tmpdir = tempfile.mkdtemp(prefix="patasegura_metricas_")
    caminho = os.path.join(tmpdir, "metricas.db")
    db.DB_PATH = caminho
    try:
        db.init_db()
        yield caminho
    finally:
        db.DB_PATH = original
        with contextlib.suppress(OSError):
            os.remove(caminho)
            os.rmdir(tmpdir)


def texto(max_size: int):
    """Texto não vazio após strip, com Unicode (sem surrogates nem NUL)."""
    return st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        min_size=1,
        max_size=max_size,
    ).filter(lambda s: s.strip())


STATUS = ["desaparecido", "encontrado", "adotado"]
DISTRITOS_POOL = list(db.DISTRITOS_SP)[:8]

distrito_st = st.one_of(st.sampled_from(DISTRITOS_POOL), texto(20))

lat_st = st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)
lng_st = st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)


def inserir_pets(conn, statuses: list[str]) -> list[int]:
    ids = []
    for i, status in enumerate(statuses):
        cur = conn.execute(
            "INSERT INTO pets (nome, especie, descricao, lat, lng, "
            "data_desaparecimento, status, contato) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"Pet {i}", "Cachorro", "desc", -23.55, -46.63, "2024-01-01", status, "11 9999"),
        )
        ids.append(cur.lastrowid)
    return ids


def inserir_avistamentos(conn, pet_ids: list[int], indices: list[int]) -> int:
    if not pet_ids:
        return 0
    for idx in indices:
        conn.execute(
            "INSERT INTO avistamentos (pet_id, lat, lng, data, observacao) "
            "VALUES (?, ?, ?, ?, ?)",
            (pet_ids[idx % len(pet_ids)], -23.55, -46.63, "2024-01-02T10:00:00", None),
        )
    return len(indices)


def inserir_denuncias(conn, distritos: list[str], coords=None) -> None:
    for i, distrito in enumerate(distritos):
        lat, lng = coords[i] if coords else (-23.55, -46.63)
        conn.execute(
            "INSERT INTO denuncias (tipo, descricao, lat, lng, data, distrito) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("abandono", "descricao", lat, lng, "2024-01-03T12:00:00", distrito),
        )


@settings(max_examples=100, deadline=None)
@given(
    statuses=st.lists(st.sampled_from(STATUS), min_size=0, max_size=15),
    avist_indices=st.lists(st.integers(min_value=0, max_value=1000), min_size=0, max_size=15),
    denuncias=st.lists(distrito_st, min_size=0, max_size=15),
)
def test_metricas_iguais_as_contagens_reais(statuses, avist_indices, denuncias):
    """Feature: patasegura, Property 5: Métricas iguais às contagens reais

    **Validates: Requirements 2.3, 2.4, 2.5**
    """
    with banco_temporario():
        conn = db.get_conn()
        try:
            with conn:
                pet_ids = inserir_pets(conn, statuses)
                total_avist = inserir_avistamentos(conn, pet_ids, avist_indices)
                inserir_denuncias(conn, denuncias)
        finally:
            conn.close()

        esperado = {
            "pets": sum(1 for s in statuses if s == "desaparecido"),
            "avistamentos": total_avist,
            "denuncias": len(denuncias),
        }

        assert db.contar_metricas() == esperado
        assert db.contar_pets() == esperado["pets"]
        assert db.contar_avistamentos() == esperado["avistamentos"]
        assert db.contar_denuncias() == esperado["denuncias"]


@settings(max_examples=100, deadline=None)
@given(
    denuncias=st.lists(
        st.tuples(distrito_st, lat_st, lng_st), min_size=0, max_size=25
    )
)
def test_indice_de_risco_igual_contagem_por_distrito(denuncias):
    """Feature: patasegura, Property 15: Índice de risco igual à contagem por distrito

    **Validates: Requirements 6.1**
    """
    with banco_temporario():
        distritos = [d for d, _, _ in denuncias]
        coords = [(lat, lng) for _, lat, lng in denuncias]
        conn = db.get_conn()
        try:
            with conn:
                inserir_denuncias(conn, distritos, coords)
        finally:
            conn.close()

        indice = db.indice_de_risco()

        assert indice == dict(Counter(distritos))
        assert all(v >= 1 for v in indice.values())
        if not denuncias:
            assert indice == {}
