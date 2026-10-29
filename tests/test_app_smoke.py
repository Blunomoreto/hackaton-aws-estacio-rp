"""Smoke tests do shell do app (tarefa 1.3).

Valida os rótulos/ordem das abas (Req. 2.1) e a interrupção da renderização
quando o bootstrap do banco falha (Req. 1.2).
"""

import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

import db

ABAS_ESPERADAS = [
    "Mapa de Risco",
    "Pets Desaparecidos",
    "Reportar/Avistamento",
    "Denúncia Anônima",
]
MSG_FALHA_BOOTSTRAP = "Falha na preparação do Banco de Dados."


def _run(app_path):
    at = AppTest.from_file(app_path, default_timeout=30)
    at.run()
    return at


def test_quatro_abas_com_rotulos_e_ordem_corretos(tmp_db, app_path):
    at = _run(app_path)

    assert not at.exception
    assert [tab.label for tab in at.tabs] == ABAS_ESPERADAS
    # O app rodou contra o banco temporário, não contra o patasegura.db real.
    assert tmp_db.exists()


def test_metricas_de_topo_renderizadas_acima_das_abas(tmp_db, app_path):
    at = _run(app_path)

    assert len(at.metric) == 3


@pytest.mark.parametrize("modo", ["excecao_no_bootstrap", "db_path_invalido"])
def test_falha_no_bootstrap_interrompe_renderizacao(tmp_db, tmp_path, monkeypatch, app_path, modo):
    if modo == "excecao_no_bootstrap":
        def _falha():
            raise sqlite3.OperationalError("falha simulada")

        monkeypatch.setattr(db, "bootstrap", _falha)
    else:
        # Um diretório não pode ser aberto como arquivo SQLite.
        monkeypatch.setattr(db, "DB_PATH", str(tmp_path))

    at = _run(app_path)

    assert not at.exception
    assert [e.value for e in at.error] == [MSG_FALHA_BOOTSTRAP]
    assert len(at.tabs) == 0
    assert len(at.metric) == 0
