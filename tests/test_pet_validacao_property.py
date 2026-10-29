"""Testes de propriedade da validação de pets do PataSegura.

Feature: patasegura, Property 6: Validação de pet rejeita entradas inválidas sem persistir
"""

import contextlib
import math
import os
import tempfile
from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import db

TABELAS = ("pets", "avistamentos", "denuncias")
CAMPOS = ("nome", "especie", "descricao", "contato", "lat", "lng", "data_desaparecimento")
LIMITES_TEXTO = {"nome": 100, "especie": None, "descricao": 500, "contato": 100}

# Texto sem surrogates (Cs) e sem NUL, que o SQLite/Python não tratam bem.
CARACTERES = st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00")


# ---------------------------------------------------------------------------
# Banco temporário compartilhado pelo módulo (nada deve ser inserido nele)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def banco_modulo():
    """Banco temporário populado pelo seed; restaura db.DB_PATH ao final."""
    original = db.DB_PATH
    tmpdir = tempfile.mkdtemp(prefix="patasegura_valpet_")
    caminho = os.path.join(tmpdir, "valpet_test.db")
    db.DB_PATH = caminho
    db.bootstrap()
    try:
        yield caminho
    finally:
        db.DB_PATH = original
        with contextlib.suppress(OSError):
            os.remove(caminho)
            os.rmdir(tmpdir)


def contagens() -> dict[str, int]:
    conn = db.get_conn()
    try:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABELAS}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Geradores
# ---------------------------------------------------------------------------


def texto_valido(max_len: int | None) -> st.SearchStrategy[str]:
    return st.text(CARACTERES, min_size=1, max_size=max_len or 50).filter(lambda s: s.strip())


def datas_validas() -> st.SearchStrategy:
    hoje = date.today()
    d = st.dates(min_value=hoje - timedelta(days=3650), max_value=hoje)
    return st.one_of(d, d.map(date.isoformat))


@st.composite
def pet_valido(draw) -> dict:
    return {
        "nome": draw(texto_valido(100)),
        "especie": draw(texto_valido(None)),
        "descricao": draw(texto_valido(500)),
        "contato": draw(texto_valido(100)),
        "lat": draw(st.floats(min_value=-90, max_value=90)),
        "lng": draw(st.floats(min_value=-180, max_value=180)),
        "data_desaparecimento": draw(datas_validas()),
    }


VAZIOS = st.sampled_from([None, "", " ", "   ", "\t\n"])
REMOVER = object()  # sentinela: remove a chave do dicionário


def fora_da_faixa(limite: float) -> st.SearchStrategy:
    return st.one_of(
        st.floats(min_value=limite, exclude_min=True),
        st.floats(max_value=-limite, exclude_max=True),
        st.just(math.nan),
    )


def mutacao_texto(campo: str) -> st.SearchStrategy:
    opcoes = [st.just(REMOVER), VAZIOS, st.integers(), st.lists(st.integers(), max_size=2)]
    max_len = LIMITES_TEXTO[campo]
    if max_len is not None:
        opcoes.append(
            st.text(CARACTERES, min_size=max_len + 1, max_size=max_len + 50).filter(
                lambda s: s.strip()
            )
        )
    return st.one_of(*opcoes)


def mutacao_coordenada(limite: float) -> st.SearchStrategy:
    return st.one_of(
        st.just(REMOVER),
        VAZIOS,
        fora_da_faixa(limite),
        st.sampled_from(["abc", "norte", [1.0], {"v": 1}, True, False]),
    )


def mutacao_data() -> st.SearchStrategy:
    hoje = date.today()
    futuras = st.dates(min_value=hoje + timedelta(days=1), max_value=hoje + timedelta(days=3650))
    return st.one_of(
        st.just(REMOVER),
        VAZIOS,
        futuras,
        futuras.map(date.isoformat),
        st.sampled_from(["ontem", "31/12/2023", "2024-13-01", "2023-02-30", "abc", "2024-1"]),
        st.integers(),
    )


MUTACOES = {
    "nome": mutacao_texto("nome"),
    "especie": mutacao_texto("especie"),
    "descricao": mutacao_texto("descricao"),
    "contato": mutacao_texto("contato"),
    "lat": mutacao_coordenada(90),
    "lng": mutacao_coordenada(180),
    "data_desaparecimento": mutacao_data(),
}


@st.composite
def pet_invalido(draw) -> tuple[dict, set[str]]:
    """Pet válido com 1+ campos invalidados; retorna (dados, campos_mutados)."""
    dados = draw(pet_valido())
    campos = draw(st.sets(st.sampled_from(CAMPOS), min_size=1))
    for campo in campos:
        valor = draw(MUTACOES[campo])
        if valor is REMOVER:
            dados.pop(campo, None)
        else:
            dados[campo] = valor
    return dados, campos


def campos_com_erro(erros: list[str]) -> set[str]:
    return {e.split(": ", 1)[0] for e in erros}


# ---------------------------------------------------------------------------
# Propriedades
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(caso=pet_invalido())
def test_pet_invalido_rejeitado_sem_persistir(caso):
    """Feature: patasegura, Property 6: Validação de pet rejeita entradas inválidas sem persistir

    **Validates: Requirements 3.3, 3.4**
    """
    dados, campos_mutados = caso
    antes = contagens()

    erros = db.validar_pet(dados)
    assert erros, f"esperava erros para {campos_mutados}"
    # Mensagens indicam exatamente os campos ausentes/fora de faixa ou formato.
    assert campos_com_erro(erros) == campos_mutados

    with pytest.raises(ValueError) as exc:
        db.inserir_pet(dados)
    assert exc.value.args[0] == erros

    assert contagens() == antes


@settings(max_examples=100, deadline=None)
@given(dados=pet_valido())
def test_pet_valido_sem_erros(dados):
    """Sanidade do gerador: pets válidos não produzem erros de validação.

    **Validates: Requirements 3.1**
    """
    assert db.validar_pet(dados) == []
