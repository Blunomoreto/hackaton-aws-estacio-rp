"""Testes de propriedade do registro de avistamentos do PataSegura.

Feature: patasegura, Property 3: Round-trip e integridade referencial de avistamento
Feature: patasegura, Property 9: Ordenação decrescente de avistamentos
Feature: patasegura, Property 10: Status do pet inalterado após avistamento
Feature: patasegura, Property 11: Validação de avistamento rejeita entradas inválidas
"""

import contextlib
import math
import os
import tempfile
from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import db


@contextlib.contextmanager
def banco_temporario():
    """Aponta db.DB_PATH para um banco novo (com schema) e restaura ao sair."""
    original = db.DB_PATH
    tmpdir = tempfile.mkdtemp(prefix="patasegura_avist_")
    caminho = os.path.join(tmpdir, "avist.db")
    db.DB_PATH = caminho
    try:
        db.init_db()
        yield caminho
    finally:
        db.DB_PATH = original
        with contextlib.suppress(OSError):
            os.remove(caminho)
            os.rmdir(tmpdir)


def inserir_pet_sql(status: str = "desaparecido") -> int:
    conn = db.get_conn()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO pets (nome, especie, descricao, lat, lng, "
                "data_desaparecimento, status, contato) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("Rex", "Cachorro", "desc", -23.55, -46.63, "2024-01-01", status, "11 9999"),
            )
            return cur.lastrowid
    finally:
        conn.close()


def contar_avistamentos() -> int:
    conn = db.get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM avistamentos").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Geradores
# ---------------------------------------------------------------------------

ALFABETO = st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00")

lat_valida = st.one_of(
    st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
    st.integers(min_value=-90, max_value=90),
    st.sampled_from([-90.0, 90.0, 0.0]),
)
lng_valida = st.one_of(
    st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
    st.integers(min_value=-180, max_value=180),
    st.sampled_from([-180.0, 180.0, 0.0]),
)
observacao_valida = st.one_of(
    st.none(),
    st.text(alphabet=ALFABETO, min_size=0, max_size=db.MAX_OBSERVACAO),
    st.text(alphabet=ALFABETO, min_size=db.MAX_OBSERVACAO, max_size=db.MAX_OBSERVACAO),
)

STATUS = ["desaparecido", "encontrado", "adotado"]

# Datas passadas (ano de 4 dígitos), com e sem microssegundos.
datas_passadas = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2023, 12, 31, 23, 59, 59)
).flatmap(
    lambda d: st.sampled_from([d, d.replace(microsecond=0)])
)


# ---------------------------------------------------------------------------
# Property 3
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(lat=lat_valida, lng=lng_valida, observacao=observacao_valida)
def test_round_trip_e_integridade_referencial(lat, lng, observacao):
    """Feature: patasegura, Property 3: Round-trip e integridade referencial de avistamento

    **Validates: Requirements 1.6, 4.1**
    """
    with banco_temporario():
        pet_id = inserir_pet_sql()
        dados = {"pet_id": pet_id, "lat": lat, "lng": lng, "observacao": observacao}

        assert db.validar_avistamento(dados) == []
        av_id = db.inserir_avistamento(dados)

        conn = db.get_conn()
        try:
            row = conn.execute("SELECT * FROM avistamentos WHERE id = ?", (av_id,)).fetchone()
            pet = conn.execute(
                "SELECT id FROM pets WHERE id = ?", (row["pet_id"],)
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        assert row["pet_id"] == pet_id
        assert pet is not None  # integridade referencial
        assert row["lat"] == float(lat)
        assert row["lng"] == float(lng)
        assert row["observacao"] == observacao
        assert row["data"] is not None
        datetime.fromisoformat(row["data"])


# ---------------------------------------------------------------------------
# Property 9
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    entradas=st.lists(
        st.one_of(
            st.just(None),  # None -> via inserir_avistamento (data = agora)
            datas_passadas,
        ),
        min_size=1,
        max_size=8,
    ),
    repetir=st.booleans(),
    outros=st.integers(min_value=0, max_value=3),
)
def test_ordenacao_decrescente_de_avistamentos(entradas, repetir, outros):
    """Feature: patasegura, Property 9: Ordenação decrescente de avistamentos

    **Validates: Requirements 4.3**
    """
    if repetir and len(entradas) >= 2 and entradas[0] is not None:
        entradas = entradas + [entradas[0]]  # força empate de data

    with banco_temporario():
        pet_id = inserir_pet_sql()
        outro_pet = inserir_pet_sql()
        ids_esperados = set()

        for d in entradas:
            if d is None:
                ids_esperados.add(
                    db.inserir_avistamento({"pet_id": pet_id, "lat": -23.5, "lng": -46.6})
                )
            else:
                conn = db.get_conn()
                try:
                    with conn:
                        cur = conn.execute(
                            "INSERT INTO avistamentos (pet_id, lat, lng, data, observacao) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (pet_id, -23.5, -46.6, d.isoformat(), None),
                        )
                        ids_esperados.add(cur.lastrowid)
                finally:
                    conn.close()

        for _ in range(outros):
            db.inserir_avistamento({"pet_id": outro_pet, "lat": 0, "lng": 0})

        resultado = db.listar_avistamentos(pet_id)

        assert {r["id"] for r in resultado} == ids_esperados
        assert all(r["pet_id"] == pet_id for r in resultado)
        datas = [datetime.fromisoformat(r["data"]) for r in resultado]
        assert all(a >= b for a, b in zip(datas, datas[1:]))


# ---------------------------------------------------------------------------
# Property 10
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    status=st.sampled_from(STATUS),
    lat=lat_valida,
    lng=lng_valida,
    observacao=observacao_valida,
)
def test_status_do_pet_inalterado_apos_avistamento(status, lat, lng, observacao):
    """Feature: patasegura, Property 10: Status do pet inalterado após avistamento

    **Validates: Requirements 4.5**
    """
    with banco_temporario():
        pet_id = inserir_pet_sql(status)
        db.inserir_avistamento(
            {"pet_id": pet_id, "lat": lat, "lng": lng, "observacao": observacao}
        )

        conn = db.get_conn()
        try:
            atual = conn.execute("SELECT status FROM pets WHERE id = ?", (pet_id,)).fetchone()
        finally:
            conn.close()

        assert atual["status"] == status


# ---------------------------------------------------------------------------
# Property 11
# ---------------------------------------------------------------------------

lat_invalida = st.one_of(
    st.floats(min_value=90, exclude_min=True, allow_nan=False, allow_infinity=False),
    st.floats(max_value=-90, exclude_max=True, allow_nan=False, allow_infinity=False),
    st.sampled_from([math.nan, math.inf, -math.inf]),
)
lng_invalida = st.one_of(
    st.floats(min_value=180, exclude_min=True, allow_nan=False, allow_infinity=False),
    st.floats(max_value=-180, exclude_max=True, allow_nan=False, allow_infinity=False),
    st.sampled_from([math.nan, math.inf, -math.inf]),
)
observacao_invalida = st.text(
    alphabet=ALFABETO, min_size=db.MAX_OBSERVACAO + 1, max_size=db.MAX_OBSERVACAO + 50
)
# pet_id inexistente (o banco temporário terá apenas o pet de id 1) ou de tipo errado.
pet_id_invalido = st.one_of(
    st.integers(min_value=2, max_value=10**6),
    st.integers(max_value=0),
    st.sampled_from([True, False, 1.0, "1", "abc", [1]]),
)

MUTACOES = {
    "lat": lat_invalida,
    "lng": lng_invalida,
    "observacao": observacao_invalida,
    "pet_id": pet_id_invalido,
}


@st.composite
def avistamento_invalido(draw):
    campos = draw(
        st.lists(st.sampled_from(sorted(MUTACOES)), min_size=1, max_size=4, unique=True)
    )
    dados = {
        "lat": draw(lat_valida),
        "lng": draw(lng_valida),
        "observacao": draw(observacao_valida),
    }
    mutados = {c: draw(MUTACOES[c]) for c in campos}
    return dados, mutados


@settings(max_examples=100, deadline=None)
@given(caso=avistamento_invalido())
def test_validacao_de_avistamento_rejeita_entradas_invalidas(caso):
    """Feature: patasegura, Property 11: Validação de avistamento rejeita entradas inválidas

    **Validates: Requirements 4.2**
    """
    base, mutados = caso
    with banco_temporario():
        pet_id = inserir_pet_sql()
        assert pet_id == 1
        dados = {"pet_id": pet_id, **base, **mutados}

        erros = db.validar_avistamento(dados)
        campos_com_erro = {e.split(":", 1)[0] for e in erros}
        assert campos_com_erro == set(mutados)

        antes = contar_avistamentos()
        with pytest.raises(ValueError):
            db.inserir_avistamento(dados)
        assert contar_avistamentos() == antes
