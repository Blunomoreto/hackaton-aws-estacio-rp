"""Testes de propriedade da listagem de pets do PataSegura.

Feature: patasegura, Property 7: Listagem retorna apenas pets desaparecidos
Feature: patasegura, Property 8: Filtro por espécie
"""

import contextlib
import os
import tempfile
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

import db


@contextlib.contextmanager
def banco_temporario():
    """Aponta db.DB_PATH para um banco novo (com schema) e restaura ao sair."""
    original = db.DB_PATH
    tmpdir = tempfile.mkdtemp(prefix="patasegura_pet_list_")
    caminho = os.path.join(tmpdir, "pet_listagem.db")
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


ESPECIES = ["Cachorro", "Gato", "Pássaro"]
STATUS = ["desaparecido", "encontrado", "adotado"]

especie_st = st.one_of(st.sampled_from(ESPECIES), texto(20))

pet_st = st.fixed_dictionaries(
    {
        "nome": texto(30),
        "especie": especie_st,
        "descricao": texto(50),
        "contato": texto(30),
        "lat": st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        "lng": st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
        "data_desaparecimento": st.dates(
            min_value=date(2000, 1, 1), max_value=date.today()
        ).map(date.isoformat),
        "status": st.sampled_from(STATUS),
    }
)


def inserir_direto(pets: list[dict]) -> list[int]:
    """Insere pets via SQL (permite status arbitrário); retorna ids na ordem."""
    conn = db.get_conn()
    try:
        with conn:
            ids = []
            for p in pets:
                cur = conn.execute(
                    "INSERT INTO pets (nome, especie, descricao, lat, lng, "
                    "data_desaparecimento, status, contato) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        p["nome"],
                        p["especie"],
                        p["descricao"],
                        p["lat"],
                        p["lng"],
                        p["data_desaparecimento"],
                        p["status"],
                        p["contato"],
                    ),
                )
                ids.append(cur.lastrowid)
            return ids
    finally:
        conn.close()


@settings(max_examples=100, deadline=None)
@given(pets=st.lists(pet_st, min_size=0, max_size=12))
def test_listagem_retorna_apenas_desaparecidos(pets):
    """Feature: patasegura, Property 7: Listagem retorna apenas pets desaparecidos

    **Validates: Requirements 3.5**
    """
    with banco_temporario():
        ids = inserir_direto(pets)
        esperados = {i for i, p in zip(ids, pets) if p["status"] == "desaparecido"}

        resultado = db.listar_pets()

        assert all(r["status"] == "desaparecido" for r in resultado)
        ids_resultado = [r["id"] for r in resultado]
        assert len(ids_resultado) == len(set(ids_resultado))
        assert set(ids_resultado) == esperados


@settings(max_examples=100, deadline=None)
@given(
    pets=st.lists(pet_st, min_size=0, max_size=12),
    filtro=especie_st,
)
def test_filtro_por_especie(pets, filtro):
    """Feature: patasegura, Property 8: Filtro por espécie

    **Validates: Requirements 3.6**
    """
    with banco_temporario():
        ids = inserir_direto(pets)
        esperados = {
            i
            for i, p in zip(ids, pets)
            if p["status"] == "desaparecido" and p["especie"] == filtro
        }

        resultado = db.listar_pets(filtro)

        assert all(r["especie"] == filtro for r in resultado)
        assert all(r["status"] == "desaparecido" for r in resultado)
        assert {r["id"] for r in resultado} == esperados
