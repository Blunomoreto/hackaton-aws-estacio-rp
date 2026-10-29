"""Testes de propriedade de maps.py: faixas de cor e resiliência do GeoJSON.

Nenhum teste acessa a rede: `maps.requests.get` é sempre substituído por um
dublê que falha, e `cache_path` aponta para um arquivo inexistente ou corrompido
em diretório temporário (o `data/distritos_sp.geojson` real é ignorado).
"""

import os
import tempfile
from unittest import mock

import folium
import requests
from folium.plugins import HeatMap
from hypothesis import given, settings
from hypothesis import strategies as st

import maps

URL_FALSA = "https://exemplo.invalido/distritos.geojson"


# ---------------------------------------------------------------------------
# Property 17
# ---------------------------------------------------------------------------

indices = st.integers(min_value=0, max_value=999_999)


# Feature: patasegura, Property 17: Faixas de cor monotônicas com no mínimo três faixas
@settings(max_examples=100, deadline=None)
@given(a=indices, b=indices)
def test_faixa_cor_monotonica_com_tres_ou_mais_faixas(a, b):
    """**Validates: Requirements 6.5**"""
    i1, i2 = min(a, b), max(a, b)

    # Monotonicidade: índice maior nunca cai em faixa menos intensa.
    assert maps.faixa_index(i1) <= maps.faixa_index(i2)

    # A cor de cada índice é uma das cores das faixas, na posição da faixa.
    cores_validas = [cor for _minimo, cor in maps.FAIXAS_COR]
    for i in (i1, i2):
        cor = maps.faixa_cor(i)
        assert cor in cores_validas
        assert cor == maps.FAIXAS_COR[maps.faixa_index(i)][1]

    # No mínimo três faixas de cor distintas.
    assert len(set(cores_validas)) >= 3
    # Os limites de faixa são estritamente crescentes.
    limites = [m for m, _c in maps.FAIXAS_COR]
    assert limites == sorted(set(limites))


# ---------------------------------------------------------------------------
# Property 18
# ---------------------------------------------------------------------------

class _RespostaFalsa:
    def __init__(self, status_exc=None, json_exc=None, payload=None):
        self._status_exc = status_exc
        self._json_exc = json_exc
        self._payload = payload

    def raise_for_status(self):
        if self._status_exc is not None:
            raise self._status_exc

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._payload


payloads_invalidos = st.sampled_from([
    None,
    [],
    [{"type": "Feature"}],
    {},
    {"type": "FeatureCollection"},
    {"type": "FeatureCollection", "features": []},
    {"type": "FeatureCollection", "features": "nao-e-lista"},
    {"type": "Feature", "features": [{"type": "Feature"}]},
    "texto",
    42,
])

# Cada estratégia produz uma função que substitui `requests.get`.
falhas_download = st.one_of(
    st.sampled_from([
        requests.ConnectionError("sem rede"),
        requests.Timeout("timeout de 10s"),
        Exception("falha genérica"),
        OSError("erro de socket"),
    ]).map(lambda exc: ("raise", exc)),
    st.integers(min_value=400, max_value=599).map(
        lambda code: ("http", requests.HTTPError(f"HTTP {code}"))
    ),
    st.sampled_from([ValueError("JSON inválido"), requests.JSONDecodeError("x", "doc", 0)])
    .map(lambda exc: ("json", exc)),
    payloads_invalidos.map(lambda p: ("payload", p)),
)


def _get_falso(falha):
    tipo, valor = falha

    def get(url, *args, **kwargs):
        if tipo == "raise":
            raise valor
        if tipo == "http":
            return _RespostaFalsa(status_exc=valor)
        if tipo == "json":
            return _RespostaFalsa(json_exc=valor)
        return _RespostaFalsa(payload=valor)

    return get


indices_risco = st.dictionaries(
    keys=st.sampled_from(sorted(maps.CENTROIDES_DISTRITOS)),
    values=st.integers(min_value=1, max_value=50),
    min_size=1,
    max_size=15,
)


def _descendentes(elemento):
    for filho in getattr(elemento, "_children", {}).values():
        yield filho
        yield from _descendentes(filho)


# Feature: patasegura, Property 18: Resiliência do carregador de GeoJSON
@settings(max_examples=100, deadline=None)
@given(falha=falhas_download, cache_corrompido=st.booleans(), indice=indices_risco)
def test_carregador_resiliente_e_mapa_fallback(falha, cache_corrompido, indice):
    """**Validates: Requirements 7.2, 7.3, 7.4**"""
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, "distritos_sp.geojson")
        if cache_corrompido:
            with open(cache_path, "w", encoding="utf-8") as fh:
                fh.write("{isto não é json")

        get_falso = mock.Mock(side_effect=_get_falso(falha))
        with mock.patch.object(maps.requests, "get", get_falso):
            resultado = maps.carregar_geojson_sem_cache(url=URL_FALSA, cache_path=cache_path)

        # Falha de download -> None, sem exceção, e o caminho de download foi usado
        # com timeout configurado.
        assert resultado is None
        get_falso.assert_called_once()
        assert get_falso.call_args.kwargs.get("timeout") == maps.TIMEOUT_DOWNLOAD

    # Fallback: sem polígonos, o mapa ainda tem HeatMap + marcador + círculo por distrito.
    mapa = maps.build_risk_map(indice, resultado)
    assert isinstance(mapa, folium.Map)
    assert list(mapa.location) == list(maps.SP_CENTER)

    elementos = list(_descendentes(mapa))
    assert any(isinstance(e, HeatMap) for e in elementos)
    assert not any(isinstance(e, folium.GeoJson) for e in elementos)

    circulos = [e for e in elementos if isinstance(e, folium.CircleMarker)]
    marcadores = [
        e for e in elementos
        if isinstance(e, folium.Marker) and not isinstance(e, folium.CircleMarker)
    ]
    for nome in indice:
        lat, lng = maps.CENTROIDES_DISTRITOS[nome]
        assert any(list(c.location) == [lat, lng] for c in circulos), nome
        assert any(list(m.location) == [lat, lng] for m in marcadores), nome
    assert len(circulos) == len(indice)
    assert len(marcadores) == len(indice)
