"""Testes de propriedade do Registro de Denúncias do PataSegura.

Feature: patasegura, Property 4: Round-trip de denúncia
Feature: patasegura, Property 12: Denúncia persiste apenas campos permitidos (anonimato)
Feature: patasegura, Property 13: Data de denúncia preenchida na persistência
Feature: patasegura, Property 14: Validação de denúncia rejeita entradas inválidas
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

COLUNAS_PERMITIDAS = {"id", "tipo", "descricao", "lat", "lng", "data", "distrito"}
CAMPOS_IDENTIFICAVEIS = ("nome", "email", "telefone", "ip", "user_id")
PII_PREFIXO = "PII-"


@contextlib.contextmanager
def banco_temporario():
    """Aponta db.DB_PATH para um banco novo (com schema) e restaura ao sair."""
    original = db.DB_PATH
    tmpdir = tempfile.mkdtemp(prefix="patasegura_denuncia_")
    caminho = os.path.join(tmpdir, "denuncia.db")
    db.DB_PATH = caminho
    try:
        db.init_db()
        yield caminho
    finally:
        db.DB_PATH = original
        with contextlib.suppress(OSError):
            os.remove(caminho)
            os.rmdir(tmpdir)


def ler_denuncia(denuncia_id: int) -> dict | None:
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM denuncias WHERE id = ?", (denuncia_id,)).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def contar_denuncias() -> int:
    conn = db.get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM denuncias").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Geradores
# ---------------------------------------------------------------------------

def texto(min_size: int, max_size: int):
    """Texto com Unicode (sem surrogates nem NUL), não vazio após strip e sem o prefixo PII."""
    return st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
        min_size=min_size,
        max_size=max_size,
    ).filter(lambda s: s.strip() and PII_PREFIXO not in s)


descricao_limite_st = st.sampled_from(["d", "é" * db.MAX_DESCRICAO_DENUNCIA])
lat_st = st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)
lng_st = st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)

denuncia_valida_st = st.fixed_dictionaries(
    {
        "tipo": st.one_of(st.sampled_from(["abandono", "agressão", "negligência"]), texto(1, 50)),
        "descricao": st.one_of(texto(1, 300), descricao_limite_st),
        "lat": st.one_of(lat_st, st.sampled_from([-90.0, 90.0, 0.0])),
        "lng": st.one_of(lng_st, st.sampled_from([-180.0, 180.0, 0.0])),
        "distrito": st.one_of(st.sampled_from(list(db.DISTRITOS_SP)), texto(1, 40)),
    }
)

valor_pii_st = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    max_size=30,
).map(lambda s: PII_PREFIXO + s)

chave_extra_st = st.text(
    alphabet=st.characters(min_codepoint=ord("a"), max_codepoint=ord("z")),
    min_size=1,
    max_size=12,
).filter(lambda k: k not in COLUNAS_PERMITIDAS)

extras_st = st.fixed_dictionaries(
    {campo: valor_pii_st for campo in CAMPOS_IDENTIFICAVEIS},
    optional={
        "id": st.integers(min_value=2, max_value=10**9),
        "data": st.one_of(valor_pii_st, st.just("1999-01-01T00:00:00")),
    },
).flatmap(
    lambda base: st.dictionaries(
        chave_extra_st, st.one_of(valor_pii_st, st.integers()), max_size=5
    ).map(lambda aleatorios: {**aleatorios, **base})
)


# ---------------------------------------------------------------------------
# Property 4: Round-trip de denúncia
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(dados=denuncia_valida_st)
def test_round_trip_denuncia(dados):
    """Feature: patasegura, Property 4: Round-trip de denúncia

    **Validates: Requirements 1.7, 5.1**
    """
    with banco_temporario():
        assert db.validar_denuncia(dados) == []
        denuncia_id = db.inserir_denuncia(dados)
        row = ler_denuncia(denuncia_id)

        assert row is not None
        assert set(row.keys()) == COLUNAS_PERMITIDAS
        assert row["id"] == denuncia_id
        assert row["tipo"] == dados["tipo"]
        assert row["descricao"] == dados["descricao"]
        assert row["distrito"] == dados["distrito"]
        assert row["lat"] == float(dados["lat"])
        assert row["lng"] == float(dados["lng"])
        assert row["data"] is not None


# ---------------------------------------------------------------------------
# Property 12: Anonimato — apenas campos permitidos são persistidos
# ---------------------------------------------------------------------------

def test_schema_denuncias_sem_colunas_identificaveis():
    """Feature: patasegura, Property 12: Denúncia persiste apenas campos permitidos (anonimato)

    **Validates: Requirements 5.3, 5.4**
    """
    with banco_temporario():
        conn = db.get_conn()
        try:
            colunas = {r["name"] for r in conn.execute("PRAGMA table_info(denuncias)")}
        finally:
            conn.close()
        assert colunas == COLUNAS_PERMITIDAS
        assert not colunas & set(CAMPOS_IDENTIFICAVEIS)


@settings(max_examples=100, deadline=None)
@given(dados=denuncia_valida_st, extras=extras_st)
def test_denuncia_persiste_apenas_campos_permitidos(dados, extras):
    """Feature: patasegura, Property 12: Denúncia persiste apenas campos permitidos (anonimato)

    **Validates: Requirements 5.3, 5.4**
    """
    payload = {**extras, **dados}
    with banco_temporario():
        denuncia_id = db.inserir_denuncia(payload)
        row = ler_denuncia(denuncia_id)

        assert row is not None
        assert set(row.keys()) == COLUNAS_PERMITIDAS

        # id e data não são controlados pelo chamador.
        if "id" in extras:
            assert row["id"] != extras["id"]
        if "data" in extras:
            assert row["data"] != extras["data"]

        # Nenhum valor identificável (marcado com PII-) aparece no registro.
        for valor in row.values():
            assert PII_PREFIXO not in str(valor)

        # Os campos permitidos continuam iguais ao enviado.
        for campo in ("tipo", "descricao", "distrito"):
            assert row[campo] == dados[campo]


# ---------------------------------------------------------------------------
# Property 13: data preenchida no momento da persistência
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(dados=denuncia_valida_st)
def test_data_preenchida_na_persistencia(dados):
    """Feature: patasegura, Property 13: Data de denúncia preenchida na persistência

    **Validates: Requirements 5.2**
    """
    with banco_temporario():
        antes = datetime.now()
        denuncia_id = db.inserir_denuncia(dados)
        depois = datetime.now()
        row = ler_denuncia(denuncia_id)

        assert row["data"] is not None
        assert antes <= datetime.fromisoformat(row["data"]) <= depois


# ---------------------------------------------------------------------------
# Property 14: validação rejeita entradas inválidas sem persistir
# ---------------------------------------------------------------------------

AUSENTE = object()  # sentinela: remove a chave do payload

texto_invalido_st = st.one_of(
    st.just(AUSENTE),
    st.just(None),
    st.just(""),
    st.text(alphabet=" \t\n\r", min_size=1, max_size=5),
)

descricao_invalida_st = st.one_of(
    st.just(AUSENTE),
    st.just(None),
    st.just(""),
    st.text(alphabet=" \t\n", min_size=1, max_size=5),
    st.integers(min_value=db.MAX_DESCRICAO_DENUNCIA + 1, max_value=db.MAX_DESCRICAO_DENUNCIA + 500)
    .flatmap(lambda n: st.sampled_from(["a", "ç", "🐾"]).map(lambda c: c * n)),
)


def coordenada_invalida_st(limite: float):
    fora = st.one_of(
        st.floats(min_value=limite, exclude_min=True, allow_nan=False, allow_infinity=False),
        st.floats(max_value=-limite, exclude_max=True, allow_nan=False, allow_infinity=False),
        st.integers(min_value=int(limite) + 1, max_value=10**6),
        st.integers(min_value=-(10**6), max_value=-int(limite) - 1),
    )
    return st.one_of(
        st.just(AUSENTE),
        st.just(None),
        st.just(""),
        fora,
        st.sampled_from([math.nan, math.inf, -math.inf]),
        st.sampled_from(["abc", "12,5", [1.0], {"v": 1}, True, False]),
    )


MUTACOES = {
    "tipo": texto_invalido_st,
    "distrito": texto_invalido_st,
    "descricao": descricao_invalida_st,
    "lat": coordenada_invalida_st(90),
    "lng": coordenada_invalida_st(180),
}


@st.composite
def denuncia_invalida_st(draw):
    dados = dict(draw(denuncia_valida_st))
    campos = draw(
        st.lists(st.sampled_from(sorted(MUTACOES)), min_size=1, max_size=5, unique=True)
    )
    for campo in campos:
        valor = draw(MUTACOES[campo])
        if valor is AUSENTE:
            dados.pop(campo, None)
        else:
            dados[campo] = valor
    return dados, set(campos)


@settings(max_examples=100, deadline=None)
@given(caso=denuncia_invalida_st(), existentes=st.lists(denuncia_valida_st, max_size=3))
def test_validacao_denuncia_rejeita_invalidas(caso, existentes):
    """Feature: patasegura, Property 14: Validação de denúncia rejeita entradas inválidas

    **Validates: Requirements 5.5, 5.6, 5.7, 5.8, 5.9**
    """
    dados, campos_mutados = caso
    with banco_temporario():
        for valida in existentes:
            db.inserir_denuncia(valida)
        antes = contar_denuncias()

        erros = db.validar_denuncia(dados)
        assert {e.split(":", 1)[0] for e in erros} == campos_mutados

        with pytest.raises(ValueError):
            db.inserir_denuncia(dados)

        assert contar_denuncias() == antes == len(existentes)
