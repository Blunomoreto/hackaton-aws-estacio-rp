"""PataSegura — entrypoint Streamlit.

Shell da aplicação: bootstrap do banco no startup, métricas de topo
reais e as quatro abas de navegação.
"""

from datetime import date, datetime

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import db
import maps

st.set_page_config(page_title="PataSegura", page_icon="🐾", layout="wide")

# --- Formulário de pet: opções, valores iniciais e rótulos de erro ---
ESPECIES_PET = ["Cachorro", "Gato", "Pássaro", "Outro"]
_PET_DEFAULTS = {
    "pet_nome": "",
    "pet_especie": ESPECIES_PET[0],
    "pet_descricao": "",
    "pet_contato": "",
    "pet_lat": -23.55,
    "pet_lng": -46.63,
    "pet_data": date.today,  # callable: avaliado a cada inicialização
}
_ROTULOS_PET = {
    "nome": "Nome",
    "especie": "Espécie",
    "descricao": "Descrição",
    "contato": "Contato",
    "lat": "Latitude",
    "lng": "Longitude",
    "data_desaparecimento": "Data do desaparecimento",
}


# --- Formulário de avistamento: valores iniciais e rótulos de erro ---
_AVIST_DEFAULTS = {
    "avist_lat": -23.55,
    "avist_lng": -46.63,
    "avist_obs": "",
}
_ROTULOS_AVIST = {
    "pet_id": "Pet",
    "lat": "Latitude",
    "lng": "Longitude",
    "observacao": "Observação",
}


# --- Formulário de denúncia anônima: opções, valores iniciais e rótulos de erro ---
# Só os campos de db.CAMPOS_DENUNCIA existem no formulário: nenhum dado identificável (Req 5.3).
TIPOS_DENUNCIA = [
    "Abandono",
    "Agressão física",
    "Falta de alimentação",
    "Confinamento inadequado",
    "Envenenamento",
    "Animal acorrentado",
    "Outro",
]
DISTRITOS_DENUNCIA = sorted(maps.CENTROIDES_DISTRITOS)
_DEN_DEFAULTS = {
    "den_tipo": TIPOS_DENUNCIA[0],
    "den_descricao": "",
    "den_distrito": DISTRITOS_DENUNCIA[0],
    "den_lat": maps.SP_CENTER[0],
    "den_lng": maps.SP_CENTER[1],
}
_ROTULOS_DENUNCIA = {
    "tipo": "Tipo",
    "descricao": "Descrição",
    "lat": "Latitude",
    "lng": "Longitude",
    "distrito": "Distrito",
}


def _rotulo_erro(erro: str, rotulos: dict[str, str] = _ROTULOS_PET) -> str:
    """Troca a chave técnica ("nome: ...") pelo rótulo amigável ("Nome: ...")."""
    campo, sep, msg = erro.partition(":")
    return f"{rotulos.get(campo, campo)}{sep}{msg}"


def _formatar_data_hora(valor) -> str:
    """ISO-8601 → "DD/MM/YYYY HH:MM"; devolve o valor original se não for parseável."""
    try:
        return datetime.fromisoformat(str(valor)).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(valor)

# --- Startup: prepara banco e seed antes de renderizar qualquer página ---
try:
    db.bootstrap()
except Exception:
    st.error("Falha na preparação do Banco de Dados.")
    st.stop()

st.title("🐾 PataSegura")
st.caption("Proteção animal em São Paulo: pets desaparecidos, denúncias anônimas e mapa de risco.")

# --- Métricas de topo (acima das abas) ---
# Cada métrica é lida de forma independente: a falha de uma só afeta a sua coluna (Req 2.6).
_METRICAS = (
    ("Pets desaparecidos", db.contar_pets),
    ("Avistamentos", db.contar_avistamentos),
    ("Denúncias", db.contar_denuncias),
)
for _col, (_rotulo, _contador) in zip(st.columns(3), _METRICAS):
    try:
        _col.metric(_rotulo, _contador())
    except Exception:
        _col.metric(_rotulo, "—")
        _col.error("Erro ao carregar")

# --- Abas (ordem fixa) ---
tab_mapa, tab_pets, tab_avist, tab_denuncia = st.tabs(
    ["Mapa de Risco", "Pets Desaparecidos", "Reportar/Avistamento", "Denúncia Anônima"]
)

with tab_mapa:
    st.subheader("Mapa de Risco")
    try:
        indice = db.indice_de_risco()
    except Exception:
        indice = {}
        st.error("Erro ao carregar as denúncias.")
    geojson = maps.load_geojson_simplificado()
    if geojson is None:
        st.warning("Polígonos dos distritos indisponíveis; exibindo mapa de calor e marcadores.")
    if not maps.tem_denuncias(indice):
        st.info("Nenhuma denúncia registrada ainda.")
    try:
        st_folium(maps.build_risk_map(indice, geojson), height=550, use_container_width=True, returned_objects=[])
    except Exception:
        st.error("Erro ao renderizar o mapa.")
    if maps.tem_denuncias(indice):
        _ranking = sorted(indice.items(), key=lambda kv: kv[1], reverse=True)[:10]
        st.dataframe(
            pd.DataFrame(_ranking, columns=["Distrito", "Denúncias"]),
            hide_index=True,
            use_container_width=True,
        )

with tab_pets:
    st.subheader("Pets Desaparecidos")

    # --- Listagem com filtro por espécie (Req 3.5, 3.6, 3.7) ---
    try:
        especie_sel = st.selectbox(
            "Filtrar por espécie",
            ["Todas", *db.listar_especies()],
            key="filtro_especie",
        )
        pets = db.listar_pets(None if especie_sel == "Todas" else especie_sel)

        if not pets:
            st.info("Nenhum pet desaparecido registrado.")
        else:
            df_pets = pd.DataFrame([dict(p) for p in pets])
            st.dataframe(
                df_pets[["nome", "especie", "descricao", "data_desaparecimento", "contato"]].rename(
                    columns={
                        "nome": "Nome",
                        "especie": "Espécie",
                        "descricao": "Descrição",
                        "data_desaparecimento": "Desaparecido em",
                        "contato": "Contato",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
            st.map(df_pets.rename(columns={"lng": "lon"})[["lat", "lon"]])
    except Exception:
        st.error("Erro ao carregar a lista de pets desaparecidos.")

    st.divider()
    # --- Registro de pet desaparecido (Req 3.1–3.4) ---
    st.subheader("Registrar pet desaparecido")

    # Após um registro bem-sucedido o app faz rerun: limpa o formulário antes
    # de os widgets serem criados e mostra a confirmação (Req 3.2).
    if st.session_state.pop("_pet_reset", False):
        for _k in _PET_DEFAULTS:
            st.session_state.pop(_k, None)
    for _k, _v in _PET_DEFAULTS.items():
        st.session_state.setdefault(_k, _v() if callable(_v) else _v)
    _flash = st.session_state.pop("_pet_flash", None)
    if _flash:
        st.success(_flash)

    # Os valores ficam em st.session_state pelas keys, preservados em caso de erro.
    with st.form("form_pet", clear_on_submit=False):
        st.text_input("Nome", max_chars=100, key="pet_nome")
        st.selectbox("Espécie", ESPECIES_PET, key="pet_especie")
        st.text_area("Descrição", max_chars=500, key="pet_descricao")
        st.text_input("Contato", max_chars=100, key="pet_contato")
        _c_lat, _c_lng = st.columns(2)
        _c_lat.number_input(
            "Latitude", min_value=-90.0, max_value=90.0, format="%.6f", key="pet_lat"
        )
        _c_lng.number_input(
            "Longitude", min_value=-180.0, max_value=180.0, format="%.6f", key="pet_lng"
        )
        st.date_input(
            "Data do desaparecimento", max_value=date.today(), format="DD/MM/YYYY", key="pet_data"
        )
        enviado = st.form_submit_button("Registrar pet")

    if enviado:
        dados = {
            "nome": st.session_state["pet_nome"].strip(),
            "especie": st.session_state["pet_especie"],
            "descricao": st.session_state["pet_descricao"].strip(),
            "contato": st.session_state["pet_contato"].strip(),
            "lat": st.session_state["pet_lat"],
            "lng": st.session_state["pet_lng"],
            "data_desaparecimento": st.session_state["pet_data"],
        }
        erros = db.validar_pet(dados)
        if erros:
            st.error(
                "Corrija os campos abaixo:\n\n"
                + "\n".join(f"- {_rotulo_erro(e)}" for e in erros)
            )
        else:
            try:
                db.inserir_pet(dados)
            except Exception:
                st.error("Erro ao salvar o pet.")
            else:
                st.session_state["_pet_flash"] = "Pet registrado com sucesso!"
                st.session_state["_pet_reset"] = True
                st.rerun()

with tab_avist:
    st.subheader("Reportar/Avistamento")

    try:
        pets_avist = db.listar_pets()
    except Exception:
        pets_avist = None
        st.error("Erro ao carregar a lista de pets desaparecidos.")

    if pets_avist is not None and not pets_avist:
        st.info("Nenhum pet desaparecido registrado para reportar avistamento.")
    elif pets_avist:
        _pets_por_id = {p["id"]: p for p in pets_avist}
        pet_id_sel = st.selectbox(
            "Pet avistado",
            list(_pets_por_id),
            format_func=lambda i: (
                f"{_pets_por_id[i]['nome']} ({_pets_por_id[i]['especie']}) — #{i}"
            ),
            key="avist_pet",
        )

        # --- Registro de avistamento (Req 4.1, 4.2) ---
        # Após sucesso o app faz rerun: limpa a observação antes de criar os
        # widgets e mostra a confirmação (mesmo padrão do formulário de pet).
        if st.session_state.pop("_avist_reset", False):
            st.session_state.pop("avist_obs", None)
        for _k, _v in _AVIST_DEFAULTS.items():
            st.session_state.setdefault(_k, _v)
        _flash_avist = st.session_state.pop("_avist_flash", None)
        if _flash_avist:
            st.success(_flash_avist)

        with st.form("form_avistamento", clear_on_submit=False):
            _a_lat, _a_lng = st.columns(2)
            _a_lat.number_input(
                "Latitude", min_value=-90.0, max_value=90.0, format="%.6f", key="avist_lat"
            )
            _a_lng.number_input(
                "Longitude", min_value=-180.0, max_value=180.0, format="%.6f", key="avist_lng"
            )
            st.text_area("Observação", max_chars=db.MAX_OBSERVACAO, key="avist_obs")
            enviado_avist = st.form_submit_button("Registrar avistamento")

        if enviado_avist:
            _obs = (st.session_state["avist_obs"] or "").strip()
            dados_avist = {
                "pet_id": pet_id_sel,
                "lat": st.session_state["avist_lat"],
                "lng": st.session_state["avist_lng"],
                "observacao": _obs or None,
            }
            erros_avist = db.validar_avistamento(dados_avist)
            if erros_avist:
                st.error(
                    "Corrija os campos abaixo:\n\n"
                    + "\n".join(f"- {_rotulo_erro(e, _ROTULOS_AVIST)}" for e in erros_avist)
                )
            else:
                try:
                    db.inserir_avistamento(dados_avist)
                except Exception:
                    st.error("Erro ao salvar o avistamento.")
                else:
                    st.session_state["_avist_flash"] = "Avistamento registrado com sucesso!"
                    st.session_state["_avist_reset"] = True
                    st.rerun()

        # --- Listagem de avistamentos do pet selecionado (Req 4.3, 4.4) ---
        st.divider()
        st.subheader(f"Avistamentos de {_pets_por_id[pet_id_sel]['nome']}")
        try:
            avistamentos = db.listar_avistamentos(pet_id_sel)  # mais recente primeiro
            if not avistamentos:
                st.info("Nenhum avistamento registrado para este pet.")
            else:
                df_avist = pd.DataFrame(
                    {
                        "Data": [_formatar_data_hora(a["data"]) for a in avistamentos],
                        "Latitude": [a["lat"] for a in avistamentos],
                        "Longitude": [a["lng"] for a in avistamentos],
                        "Observação": [a["observacao"] or "" for a in avistamentos],
                    }
                )
                st.dataframe(df_avist, hide_index=True, width="stretch")
        except Exception:
            st.error("Erro ao carregar os avistamentos.")

with tab_denuncia:
    st.subheader("Denúncia Anônima")
    st.caption(
        "Sua denúncia é anônima: não coletamos nome, e-mail, telefone "
        "ou qualquer dado que identifique você."
    )

    # Após sucesso o app faz rerun: limpa a descrição antes de criar os
    # widgets e mostra a confirmação (mesmo padrão dos outros formulários).
    if st.session_state.pop("_den_reset", False):
        st.session_state.pop("den_descricao", None)
    for _k, _v in _DEN_DEFAULTS.items():
        st.session_state.setdefault(_k, _v)
    _flash_den = st.session_state.pop("_den_flash", None)
    if _flash_den:
        st.success(_flash_den)

    with st.form("form_denuncia", clear_on_submit=False):
        st.selectbox("Tipo de maus-tratos", TIPOS_DENUNCIA, key="den_tipo")
        st.text_area(
            "Descrição", max_chars=db.MAX_DESCRICAO_DENUNCIA, key="den_descricao"
        )
        st.selectbox("Distrito", DISTRITOS_DENUNCIA, key="den_distrito")
        _d_lat, _d_lng = st.columns(2)
        _d_lat.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            format="%.6f",
            key="den_lat",
            help="Local aproximado da ocorrência (padrão: centro de São Paulo).",
        )
        _d_lng.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            format="%.6f",
            key="den_lng",
            help="Local aproximado da ocorrência (padrão: centro de São Paulo).",
        )
        enviado_den = st.form_submit_button("Enviar denúncia anônima")

    if enviado_den:
        # Payload montado apenas com os cinco campos permitidos (Req 5.1, 5.4).
        dados_den = {
            "tipo": st.session_state["den_tipo"],
            "descricao": (st.session_state["den_descricao"] or "").strip(),
            "lat": st.session_state["den_lat"],
            "lng": st.session_state["den_lng"],
            "distrito": st.session_state["den_distrito"],
        }
        erros_den = db.validar_denuncia(dados_den)
        if erros_den:
            st.error(
                "Corrija os campos abaixo:\n\n"
                + "\n".join(f"- {_rotulo_erro(e, _ROTULOS_DENUNCIA)}" for e in erros_den)
            )
        else:
            try:
                db.inserir_denuncia(dados_den)
            except Exception:
                st.error("Erro ao salvar a denúncia.")
            else:
                st.session_state["_den_flash"] = "Denúncia registrada anonimamente. Obrigado!"
                st.session_state["_den_reset"] = True
                st.rerun()
