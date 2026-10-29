"""Mapas do PataSegura: centroides de distritos, carregador de GeoJSON, cores
e `build_risk_map` (HeatMap + marcadores + círculos + polígonos opcionais).
"""

from __future__ import annotations

import json
import logging
import os
import unicodedata

import folium
import requests
import streamlit as st
from folium.plugins import HeatMap

logger = logging.getLogger(__name__)

SP_CENTER = (-23.55, -46.63)

# GeoJSON público (sem autenticação) dos 96 distritos administrativos de SP.
# Fonte: Geosampa/SMDU, convertido por codigourbano/distritos-sp (CRS84, lng/lat).
# O nome do distrito fica em properties["ds_nome"], em MAIÚSCULAS e sem acentos
# (ex.: "CAPAO REDONDO"). Use `nome_distrito(feature)` para obter a chave canônica.
URL_GEOJSON = (
    "https://raw.githubusercontent.com/codigourbano/distritos-sp/master/"
    "distritos-sp.geojson"
)
PROPRIEDADE_NOME = "ds_nome"
TIMEOUT_DOWNLOAD = 10  # segundos

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CACHE_PATH = os.path.join(DATA_DIR, "distritos_sp.geojson")

# Centroides (lat, lng) dos 96 distritos de SP, calculados a partir dos polígonos
# do GeoJSON acima. Chaves com grafia acentuada, iguais às de db.DISTRITOS_SP.
CENTROIDES_DISTRITOS: dict[str, tuple[float, float]] = {
    "Água Rasa": (-23.5668, -46.5719),
    "Alto de Pinheiros": (-23.5476, -46.7120),
    "Anhanguera": (-23.4309, -46.7929),
    "Aricanduva": (-23.5738, -46.5156),
    "Artur Alvim": (-23.5401, -46.4858),
    "Barra Funda": (-23.5212, -46.6741),
    "Bela Vista": (-23.5609, -46.6476),
    "Belém": (-23.5376, -46.5948),
    "Bom Retiro": (-23.5261, -46.6368),
    "Brás": (-23.5437, -46.6175),
    "Brasilândia": (-23.4486, -46.6884),
    "Butantã": (-23.5702, -46.7263),
    "Cachoeirinha": (-23.4544, -46.6621),
    "Cambuci": (-23.5644, -46.6170),
    "Campo Belo": (-23.6281, -46.6679),
    "Campo Grande": (-23.6746, -46.6875),
    "Campo Limpo": (-23.6359, -46.7635),
    "Cangaíba": (-23.4970, -46.5204),
    "Capão Redondo": (-23.6688, -46.7805),
    "Carrão": (-23.5511, -46.5383),
    "Casa Verde": (-23.5010, -46.6574),
    "Cidade Ademar": (-23.6738, -46.6568),
    "Cidade Dutra": (-23.7258, -46.7024),
    "Cidade Líder": (-23.5620, -46.4913),
    "Cidade Tiradentes": (-23.5848, -46.4008),
    "Consolação": (-23.5487, -46.6602),
    "Cursino": (-23.6314, -46.6207),
    "Ermelino Matarazzo": (-23.4912, -46.4845),
    "Freguesia do Ó": (-23.4863, -46.6975),
    "Grajaú": (-23.7897, -46.6687),
    "Guaianases": (-23.5564, -46.4066),
    "Iguatemi": (-23.6128, -46.4267),
    "Ipiranga": (-23.5918, -46.6028),
    "Itaim Bibi": (-23.6021, -46.6854),
    "Itaim Paulista": (-23.5034, -46.3863),
    "Itaquera": (-23.5340, -46.4559),
    "Jabaquara": (-23.6506, -46.6459),
    "Jaçanã": (-23.4601, -46.5749),
    "Jaguara": (-23.5110, -46.7471),
    "Jaguaré": (-23.5438, -46.7487),
    "Jaraguá": (-23.4459, -46.7400),
    "Jardim Ângela": (-23.7164, -46.7687),
    "Jardim Helena": (-23.4837, -46.4131),
    "Jardim Paulista": (-23.5665, -46.6668),
    "Jardim São Luís": (-23.6807, -46.7394),
    "José Bonifácio": (-23.5674, -46.4327),
    "Lajeado": (-23.5336, -46.4087),
    "Lapa": (-23.5226, -46.7060),
    "Liberdade": (-23.5670, -46.6320),
    "Limão": (-23.4975, -46.6760),
    "Mandaqui": (-23.4595, -46.6409),
    "Marsilac": (-23.9353, -46.7079),
    "Moema": (-23.5961, -46.6614),
    "Mooca": (-23.5613, -46.5964),
    "Morumbi": (-23.5963, -46.7080),
    "Parelheiros": (-23.8300, -46.7166),
    "Pari": (-23.5272, -46.6175),
    "Parque do Carmo": (-23.5760, -46.4630),
    "Pedreira": (-23.7067, -46.6498),
    "Penha": (-23.5231, -46.5291),
    "Perdizes": (-23.5387, -46.6809),
    "Perus": (-23.4079, -46.7461),
    "Pinheiros": (-23.5665, -46.6887),
    "Pirituba": (-23.4809, -46.7263),
    "Ponte Rasa": (-23.5157, -46.4937),
    "Raposo Tavares": (-23.5924, -46.7856),
    "República": (-23.5448, -46.6411),
    "Rio Pequeno": (-23.5714, -46.7589),
    "Sacomã": (-23.6308, -46.5982),
    "Santa Cecília": (-23.5318, -46.6529),
    "Santana": (-23.5000, -46.6304),
    "Santo Amaro": (-23.6424, -46.7012),
    "São Domingos": (-23.4934, -46.7476),
    "São Lucas": (-23.5947, -46.5436),
    "São Mateus": (-23.6000, -46.4812),
    "São Miguel": (-23.5011, -46.4408),
    "São Rafael": (-23.6282, -46.4540),
    "Sapopemba": (-23.6056, -46.5095),
    "Saúde": (-23.6146, -46.6411),
    "Sé": (-23.5477, -46.6314),
    "Socorro": (-23.6853, -46.7137),
    "Tatuapé": (-23.5387, -46.5675),
    "Tremembé": (-23.4172, -46.5895),
    "Tucuruvi": (-23.4757, -46.6060),
    "Vila Andrade": (-23.6262, -46.7283),
    "Vila Curuçá": (-23.5100, -46.4157),
    "Vila Formosa": (-23.5679, -46.5460),
    "Vila Guilherme": (-23.5092, -46.6058),
    "Vila Jacuí": (-23.5026, -46.4616),
    "Vila Leopoldina": (-23.5293, -46.7344),
    "Vila Maria": (-23.5130, -46.5778),
    "Vila Mariana": (-23.5865, -46.6358),
    "Vila Matilde": (-23.5394, -46.5179),
    "Vila Medeiros": (-23.4887, -46.5776),
    "Vila Prudente": (-23.5926, -46.5728),
    "Vila Sônia": (-23.5994, -46.7392),
}


# ---------------------------------------------------------------------------
# Normalização de nomes (casar polígonos do GeoJSON com chaves do índice)
# ---------------------------------------------------------------------------

def normalizar_nome(nome: str | None) -> str:
    """Chave de comparação: sem acentos, maiúsculas, espaços colapsados.

    "Capão Redondo", "CAPAO REDONDO" e " capão  redondo " -> "CAPAO REDONDO".
    """
    if not nome:
        return ""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", str(nome)) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.upper().split())


# Mapa nome normalizado -> nome canônico acentuado.
_CANONICO_POR_NORMALIZADO: dict[str, str] = {
    normalizar_nome(n): n for n in CENTROIDES_DISTRITOS
}


def nome_canonico(nome: str | None) -> str | None:
    """Nome acentuado de CENTROIDES_DISTRITOS correspondente a `nome`, ou None."""
    return _CANONICO_POR_NORMALIZADO.get(normalizar_nome(nome))


def nome_distrito(feature: dict) -> str | None:
    """Nome canônico do distrito de uma feature do GeoJSON.

    Lê properties["ds_nome"]; se o nome não estiver em CENTROIDES_DISTRITOS,
    devolve o valor original em formato título. None se não houver nome.
    """
    try:
        bruto = (feature.get("properties") or {}).get(PROPRIEDADE_NOME)
    except AttributeError:
        return None
    if not bruto:
        return None
    return nome_canonico(bruto) or str(bruto).strip().title()


# ---------------------------------------------------------------------------
# Carregador resiliente de GeoJSON
# ---------------------------------------------------------------------------

def _geojson_valido(data) -> bool:
    return (
        isinstance(data, dict)
        and data.get("type") == "FeatureCollection"
        and isinstance(data.get("features"), list)
        and len(data["features"]) > 0
    )


def _ler_cache_local(caminho: str) -> dict | None:
    if not os.path.isfile(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # cache corrompido: ignora e tenta baixar
        logger.warning("Cache local de GeoJSON inválido (%s): %s", caminho, exc)
        return None
    return data if _geojson_valido(data) else None


def _gravar_cache_local(caminho: str, data: dict) -> None:
    """Grava o GeoJSON em disco; falhas são só registradas."""
    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        tmp = caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, caminho)
    except Exception as exc:
        logger.warning("Não foi possível gravar cache do GeoJSON em %s: %s", caminho, exc)


def carregar_geojson_sem_cache(
    url: str | None = None, cache_path: str | None = None
) -> dict | None:
    """Implementação de `load_geojson` sem o cache do Streamlit (útil em testes).

    1. Cache local em `data/` válido -> retorna sem download.
    2. Senão baixa (timeout 10s), valida FeatureCollection, grava em `data/`.
    Qualquer falha -> registra aviso e retorna None. Nunca levanta exceção.
    """
    url = url or URL_GEOJSON
    cache_path = cache_path or CACHE_PATH
    try:
        local = _ler_cache_local(cache_path)
        if local is not None:
            return local

        resp = requests.get(url, timeout=TIMEOUT_DOWNLOAD)
        resp.raise_for_status()
        data = resp.json()
        if not _geojson_valido(data):
            raise ValueError("resposta não é um FeatureCollection com features")

        _gravar_cache_local(cache_path, data)
        return data
    except Exception as exc:
        logger.warning("Falha ao carregar GeoJSON de distritos (%s): %s", url, exc)
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_geojson() -> dict | None:
    """GeoJSON dos distritos de SP, cacheado pelo Streamlit; None em falha."""
    return carregar_geojson_sem_cache()


# ---------------------------------------------------------------------------
# Faixas de cor por índice de risco
# ---------------------------------------------------------------------------

# (limite mínimo inclusivo, cor), em ordem crescente de limite e de intensidade.
FAIXAS_COR: tuple[tuple[int, str], ...] = (
    (0, "#f0f0f0"),  # sem denúncias
    (1, "#fed976"),  # 1–2: amarelo
    (3, "#fd8d3c"),  # 3–4: laranja
    (5, "#e31a1c"),  # 5–6: vermelho
    (7, "#800026"),  # 7+: vermelho escuro
)


def faixa_index(indice) -> int:
    """Posição da faixa em FAIXAS_COR (0 = menos intensa). Entrada inválida -> 0."""
    try:
        valor = int(indice)
    except (TypeError, ValueError):
        valor = 0
    valor = max(valor, 0)
    pos = 0
    for i, (minimo, _cor) in enumerate(FAIXAS_COR):
        if valor >= minimo:
            pos = i
    return pos


def faixa_cor(indice) -> str:
    """Cor hex da faixa do índice; monotônica, com 5 faixas distintas."""
    return FAIXAS_COR[faixa_index(indice)][1]


# ---------------------------------------------------------------------------
# Mapa de risco (HeatMap + marcadores + círculos + polígonos opcionais)
# ---------------------------------------------------------------------------

ZOOM_INICIAL = 11

NOME_CAMADA_POLIGONOS = "Polígonos de distritos"
NOME_CAMADA_CALOR = "Mapa de calor"
NOME_CAMADA_DENUNCIAS = "Denúncias por distrito"

# Raio do CircleMarker em pixels: RAIO_BASE + RAIO_FATOR * sqrt(indice), limitado.
RAIO_BASE = 6.0
RAIO_FATOR = 4.0
RAIO_MAX = 40.0

# Simplificação dos polígonos (o GeoJSON bruto tem ~7 MB / ~157 mil pontos).
CASAS_DECIMAIS_GEOJSON = 4       # ~11 m de precisão
TOLERANCIA_SIMPLIFICACAO = 0.0005  # graus (~50 m) entre pontos mantidos
_CHAVE_SIMPLIFICADO = "_patasegura_simplificado"


def _contagem(valor) -> int:
    """Converte uma contagem em int >= 0; valores inválidos viram 0."""
    try:
        return max(int(valor), 0)
    except (TypeError, ValueError):
        return 0


def tem_denuncias(indice: dict | None) -> bool:
    """True se algum distrito do índice tem ao menos 1 denúncia."""
    if not indice:
        return False
    return any(_contagem(v) >= 1 for v in indice.values())


def raio_circulo(indice) -> float:
    """Raio (px) do círculo de um distrito; monotônico não decrescente.

    0 para índice < 1; para índice >= 1: min(RAIO_MAX, RAIO_BASE + RAIO_FATOR*sqrt(indice)).
    """
    valor = _contagem(indice)
    if valor < 1:
        return 0.0
    return min(RAIO_MAX, RAIO_BASE + RAIO_FATOR * (valor ** 0.5))


def _indice_canonico(indice: dict | None) -> dict[str, int]:
    """Agrega o índice por nome canônico (com centroide conhecido), só contagens >= 1.

    Distritos sem centroide conhecido são registrados em log e ignorados.
    """
    resultado: dict[str, int] = {}
    for nome, valor in (indice or {}).items():
        contagem = _contagem(valor)
        if contagem < 1:
            continue
        canonico = nome_canonico(nome)
        if canonico is None:
            logger.warning("Distrito sem centroide conhecido ignorado no mapa: %r", nome)
            continue
        resultado[canonico] = resultado.get(canonico, 0) + contagem
    return resultado


# --- Simplificação de geometria -------------------------------------------

def _simplificar_anel(anel, casas: int, tol: float) -> list | None:
    """Arredonda e decima um anel (lista de [lng, lat]); None se degenerar."""
    pontos: list[list[float]] = []
    tol2 = tol * tol
    for ponto in anel:
        try:
            lng, lat = round(float(ponto[0]), casas), round(float(ponto[1]), casas)
        except (TypeError, ValueError, IndexError):
            continue
        if pontos:
            dx, dy = lng - pontos[-1][0], lat - pontos[-1][1]
            if dx * dx + dy * dy < tol2:
                continue
        pontos.append([lng, lat])
    if not pontos:
        return None
    if pontos[0] != pontos[-1]:
        pontos.append(list(pontos[0]))
    return pontos if len(pontos) >= 4 else None


def _simplificar_poligono(poligono, casas: int, tol: float) -> list | None:
    aneis = []
    for i, anel in enumerate(poligono or []):
        simplificado = _simplificar_anel(anel, casas, tol)
        if simplificado is None:
            if i == 0:  # anel externo degenerou: tenta só arredondar
                simplificado = _simplificar_anel(anel, casas, 0.0)
                if simplificado is None:
                    return None
            else:  # buraco pequeno demais: descarta
                continue
        aneis.append(simplificado)
    return aneis or None


def _simplificar_geometria(geom, casas: int, tol: float) -> dict | None:
    if not isinstance(geom, dict):
        return None
    tipo = geom.get("type")
    coords = geom.get("coordinates")
    if tipo == "Polygon":
        poligono = _simplificar_poligono(coords, casas, tol)
        return {"type": "Polygon", "coordinates": poligono} if poligono else None
    if tipo == "MultiPolygon":
        poligonos = [
            p for p in (_simplificar_poligono(c, casas, tol) for c in (coords or [])) if p
        ]
        return {"type": "MultiPolygon", "coordinates": poligonos} if poligonos else None
    return None


def simplificar_geojson(
    geojson: dict | None,
    casas: int = CASAS_DECIMAIS_GEOJSON,
    tolerancia: float = TOLERANCIA_SIMPLIFICACAO,
) -> dict | None:
    """Cópia leve do GeoJSON para renderização; não altera a entrada.

    Mantém só a propriedade "nome" (nome canônico do distrito), arredonda as
    coordenadas e remove pontos mais próximos que `tolerancia` do anterior.
    Features sem nome ou com geometria inválida são descartadas.
    """
    if not _geojson_valido(geojson):
        return None
    if geojson.get(_CHAVE_SIMPLIFICADO):
        return geojson
    features = []
    for feature in geojson["features"]:
        if not isinstance(feature, dict):
            continue
        nome = nome_distrito(feature)
        geom = _simplificar_geometria(feature.get("geometry"), casas, tolerancia)
        if not nome or geom is None:
            continue
        features.append({"type": "Feature", "properties": {"nome": nome}, "geometry": geom})
    if not features:
        return None
    return {"type": "FeatureCollection", "features": features, _CHAVE_SIMPLIFICADO: True}


@st.cache_data(ttl=3600, show_spinner=False)
def load_geojson_simplificado() -> dict | None:
    """GeoJSON de distritos já simplificado para o mapa (cacheado); None em falha."""
    try:
        return simplificar_geojson(load_geojson())
    except Exception as exc:
        logger.warning("Falha ao simplificar GeoJSON de distritos: %s", exc)
        return None


# --- Camadas ---------------------------------------------------------------

def _camada_poligonos(geojson_simpl: dict, indice: dict[str, int]) -> folium.FeatureGroup:
    """Polígonos coloridos por faixa de risco; features novas, geometria compartilhada."""
    features = []
    for feature in geojson_simpl["features"]:
        nome = feature["properties"].get("nome")
        features.append({
            "type": "Feature",
            "properties": {"nome": nome, "denuncias": indice.get(nome, 0)},
            "geometry": feature["geometry"],
        })
    dados = {"type": "FeatureCollection", "features": features}

    def estilo(feature):
        contagem = (feature.get("properties") or {}).get("denuncias", 0)
        return {
            "fillColor": faixa_cor(contagem),
            "color": "#555555",
            "weight": 1,
            "fillOpacity": 0.45 if _contagem(contagem) >= 1 else 0.15,
        }

    grupo = folium.FeatureGroup(name=NOME_CAMADA_POLIGONOS, show=True)
    folium.GeoJson(
        dados,
        name=NOME_CAMADA_POLIGONOS,
        style_function=estilo,
        highlight_function=lambda _f: {"weight": 3, "color": "#222222"},
        tooltip=folium.GeoJsonTooltip(
            fields=["nome", "denuncias"], aliases=["Distrito:", "Denúncias:"]
        ),
    ).add_to(grupo)
    return grupo


def _camada_calor(indice: dict[str, int]) -> folium.FeatureGroup:
    maximo = max(indice.values())
    pontos = [
        [CENTROIDES_DISTRITOS[nome][0], CENTROIDES_DISTRITOS[nome][1], contagem / maximo]
        for nome, contagem in indice.items()
    ]
    grupo = folium.FeatureGroup(name=NOME_CAMADA_CALOR, show=True)
    HeatMap(pontos, name=NOME_CAMADA_CALOR, radius=30, blur=20, min_opacity=0.3).add_to(grupo)
    return grupo


def _camada_denuncias(indice: dict[str, int]) -> folium.FeatureGroup:
    grupo = folium.FeatureGroup(name=NOME_CAMADA_DENUNCIAS, show=True)
    for nome, contagem in sorted(indice.items(), key=lambda kv: kv[1]):
        lat, lng = CENTROIDES_DISTRITOS[nome]
        texto = f"{nome}: {contagem} denúncia{'s' if contagem != 1 else ''}"
        cor = faixa_cor(contagem)
        folium.CircleMarker(
            location=[lat, lng],
            radius=raio_circulo(contagem),
            color=cor,
            weight=2,
            fill=True,
            fill_color=cor,
            fill_opacity=0.5,
            tooltip=texto,
        ).add_to(grupo)
        folium.Marker(
            location=[lat, lng],
            tooltip=texto,
            popup=folium.Popup(texto, max_width=250),
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(grupo)
    return grupo


def _legenda_html() -> str:
    itens = []
    limites = [m for m, _c in FAIXAS_COR]
    for i, (minimo, cor) in enumerate(FAIXAS_COR):
        if i + 1 < len(limites):
            maximo = limites[i + 1] - 1
            rotulo = str(minimo) if maximo == minimo else f"{minimo}–{maximo}"
        else:
            rotulo = f"{minimo}+"
        itens.append(
            f'<div><span style="display:inline-block;width:12px;height:12px;'
            f'background:{cor};border:1px solid #777;margin-right:6px"></span>{rotulo}</div>'
        )
    return (
        '<div style="position:fixed;bottom:24px;left:24px;z-index:9999;'
        'background:white;padding:8px 10px;border:1px solid #999;border-radius:4px;'
        'font-size:12px;line-height:18px">'
        "<b>Denúncias por distrito</b>" + "".join(itens) + "</div>"
    )


def build_risk_map(indice: dict[str, int] | None, geojson: dict | None) -> folium.Map:
    """Mapa de risco centrado em SP.

    - Distritos com índice >= 1 (e centroide conhecido): HeatMap ponderado,
      Marker e CircleMarker com raio `raio_circulo(indice)`.
    - `geojson` válido: camada de polígonos coloridos por `faixa_cor`.
    - `geojson` None/inválido: só HeatMap + marcadores + círculos (fallback).
    - Sem denúncias: mapa base (polígonos, se houver); a UI mostra a mensagem.
    Nunca chama Streamlit e não altera as entradas.
    """
    mapa = folium.Map(location=list(SP_CENTER), zoom_start=ZOOM_INICIAL, tiles="OpenStreetMap")
    indice_ok = _indice_canonico(indice)

    camadas = 0
    try:
        geojson_simpl = simplificar_geojson(geojson)
    except Exception as exc:  # GeoJSON inesperado: segue sem polígonos
        logger.warning("GeoJSON de distritos inutilizável; seguindo sem polígonos: %s", exc)
        geojson_simpl = None
    if geojson_simpl is not None:
        _camada_poligonos(geojson_simpl, indice_ok).add_to(mapa)
        camadas += 1

    if indice_ok:
        _camada_calor(indice_ok).add_to(mapa)
        _camada_denuncias(indice_ok).add_to(mapa)
        camadas += 2

    if camadas > 1:
        folium.LayerControl(collapsed=False).add_to(mapa)
    if camadas:
        mapa.get_root().html.add_child(folium.Element(_legenda_html()))
    return mapa
