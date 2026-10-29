"""Teste de propriedade do round-trip de pet do PataSegura.

Feature: patasegura, Property 2: Round-trip de pet
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
    tmpdir = tempfile.mkdtemp(prefix="patasegura_pet_rt_")
    caminho = os.path.join(tmpdir, "pet_roundtrip.db")
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


datas_validas = st.dates(min_value=date(1900, 1, 1), max_value=date.today())

pet_valido = st.fixed_dictionaries(
    {
        "nome": texto(100),
        "especie": st.one_of(st.sampled_from(["Cachorro", "Gato", "Pássaro"]), texto(50)),
        "descricao": texto(500),
        "contato": texto(100),
        "lat": st.one_of(
            st.sampled_from([-90.0, 90.0, 0.0]),
            st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        ),
        "lng": st.one_of(
            st.sampled_from([-180.0, 180.0, 0.0]),
            st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
        ),
        "data_desaparecimento": st.one_of(datas_validas, datas_validas.map(date.isoformat)),
    },
    # Um "status" arbitrário na entrada nunca deve substituir o status inicial.
    optional={"status": st.sampled_from(["encontrado", "adotado", "", "qualquer"])},
)


def ler_pet(pet_id: int) -> dict:
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def iso(valor) -> str:
    return valor.isoformat() if isinstance(valor, date) else valor


@settings(max_examples=100, deadline=None)
@given(pets=st.lists(pet_valido, min_size=1, max_size=5))
def test_round_trip_de_pet(pets):
    """Feature: patasegura, Property 2: Round-trip de pet

    **Validates: Requirements 1.5, 3.1**
    """
    with banco_temporario():
        ids = []
        for dados in pets:
            assert db.validar_pet(dados) == [], dados
            pet_id = db.inserir_pet(dados)
            ids.append(pet_id)

            lido = ler_pet(pet_id)
            assert lido is not None
            assert lido["id"] == pet_id
            assert lido["status"] == "desaparecido"
            for campo in ("nome", "especie", "descricao", "contato"):
                assert lido[campo] == dados[campo], campo
            assert lido["lat"] == float(dados["lat"])
            assert lido["lng"] == float(dados["lng"])
            assert lido["data_desaparecimento"] == iso(dados["data_desaparecimento"])

        assert len(set(ids)) == len(ids)
