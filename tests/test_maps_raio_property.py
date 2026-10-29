"""Teste de propriedade do raio dos círculos do mapa de risco (maps.py).

Feature: patasegura, Property 16: Raio do círculo monotônico em relação ao índice
**Validates: Requirements 6.3**
"""

import json
import math

import folium
from hypothesis import given, settings
from hypothesis import strategies as st

import maps

DISTRITOS = sorted(maps.CENTROIDES_DISTRITOS)


def _walk(element):
    """Percorre recursivamente os filhos de um elemento folium/branca."""
    for child in element._children.values():
        yield child
        yield from _walk(child)


def _raio(circle) -> float:
    """Raio do CircleMarker, compatível com versões de folium (dict ou JSON)."""
    options = circle.options
    if isinstance(options, str):
        options = json.loads(options)
    return float(options["radius"])


def _local(marker) -> tuple[float, float]:
    lat, lng = marker.location
    return (float(lat), float(lng))


indices_st = st.dictionaries(
    keys=st.sampled_from(DISTRITOS),
    values=st.integers(min_value=0, max_value=100),
    max_size=len(DISTRITOS),
)


# Feature: patasegura, Property 16: Raio do círculo monotônico em relação ao índice
# **Validates: Requirements 6.3**
@settings(max_examples=100, deadline=None)
@given(
    st.integers(min_value=1, max_value=999_999),
    st.integers(min_value=1, max_value=999_999),
)
def test_raio_circulo_monotonico(a, b):
    i1, i2 = min(a, b), max(a, b)
    assert maps.raio_circulo(i1) > 0
    assert maps.raio_circulo(i2) >= maps.raio_circulo(i1)


# Feature: patasegura, Property 16: Raio do círculo monotônico em relação ao índice
# **Validates: Requirements 6.3**
@settings(max_examples=100, deadline=None)
@given(indices_st)
def test_todo_distrito_com_indice_recebe_marcador_e_circulo(indice):
    entrada = dict(indice)
    mapa = maps.build_risk_map(indice, None)
    assert indice == entrada  # build_risk_map não altera a entrada

    elementos = list(_walk(mapa))
    circulos = [e for e in elementos if isinstance(e, folium.CircleMarker)]
    marcadores = [
        e for e in elementos
        if isinstance(e, folium.Marker) and not isinstance(e, folium.CircleMarker)
    ]

    esperados = {nome: c for nome, c in indice.items() if c >= 1}
    centroide_para_nome = {
        tuple(map(float, maps.CENTROIDES_DISTRITOS[n])): n for n in esperados
    }

    assert len(circulos) == len(esperados)
    assert len(marcadores) == len(esperados)

    raio_por_nome: dict[str, float] = {}
    for circ in circulos:
        nome = centroide_para_nome.get(_local(circ))
        assert nome is not None, f"círculo fora de centroide esperado: {circ.location}"
        assert nome not in raio_por_nome, f"círculo duplicado para {nome}"
        raio = _raio(circ)
        assert math.isclose(raio, maps.raio_circulo(esperados[nome]))
        raio_por_nome[nome] = raio

    nomes_marcados = set()
    for marc in marcadores:
        nome = centroide_para_nome.get(_local(marc))
        assert nome is not None, f"marcador fora de centroide esperado: {marc.location}"
        assert nome not in nomes_marcados, f"marcador duplicado para {nome}"
        nomes_marcados.add(nome)

    assert set(raio_por_nome) == set(esperados)
    assert nomes_marcados == set(esperados)

    # Monotonicidade entre distritos: contagem maior nunca tem raio menor.
    ordenados = sorted(esperados, key=lambda n: esperados[n])
    for menor, maior in zip(ordenados, ordenados[1:]):
        assert raio_por_nome[maior] >= raio_por_nome[menor]
