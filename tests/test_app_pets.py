"""Testes de exemplo da aba "Pets Desaparecidos" (tarefa 4.3).

Valida a mensagem de ausência de pets desaparecidos na listagem (Req. 3.7).
"""

from streamlit.testing.v1 import AppTest

import db

MSG_SEM_PETS = "Nenhum pet desaparecido registrado."


def _run(app_path):
    at = AppTest.from_file(app_path, default_timeout=30)
    at.run()
    return at


def _criar_banco_sem_pets_desaparecidos():
    """Cria o schema e insere um único pet já encontrado.

    Com `pets` não vazia o seed do bootstrap é ignorado, então a listagem
    (que só retorna status "desaparecido") fica vazia.
    """
    db.init_db()
    conn = db.get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO pets (nome, especie, descricao, lat, lng, "
                "data_desaparecimento, status, contato) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("Rex", "Cachorro", "Já voltou para casa", -23.55, -46.63,
                 "2024-01-10", "encontrado", "11 99999-0000"),
            )
    finally:
        conn.close()


def test_mensagem_quando_nao_ha_pets_desaparecidos(tmp_db, app_path):
    _criar_banco_sem_pets_desaparecidos()

    at = _run(app_path)

    assert not at.exception
    assert db.listar_pets() == []
    assert MSG_SEM_PETS in [i.value for i in at.info]
    assert len(at.dataframe) == 0


def test_sem_mensagem_quando_ha_pets_desaparecidos(tmp_db, app_path):
    at = _run(app_path)  # bootstrap aplica o seed com pets desaparecidos

    assert not at.exception
    assert len(db.listar_pets()) > 0
    assert MSG_SEM_PETS not in [i.value for i in at.info]
    assert len(at.dataframe) >= 1
