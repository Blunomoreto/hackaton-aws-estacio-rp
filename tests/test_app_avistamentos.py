"""Testes de exemplo da aba "Reportar/Avistamento" (tarefa 5.2).

Valida a mensagem exibida quando o pet selecionado não tem avistamentos (Req. 4.4).
"""

from streamlit.testing.v1 import AppTest

import db

MSG_SEM_AVISTAMENTOS = "Nenhum avistamento registrado para este pet."

PET_VALIDO = {
    "nome": "Rex",
    "especie": "Cachorro",
    "descricao": "Vira-lata caramelo com coleira azul.",
    "contato": "(11) 90000-0000",
    "lat": -23.55,
    "lng": -46.63,
    "data_desaparecimento": "2024-01-10",
}


def _run(app_path):
    at = AppTest.from_file(app_path, default_timeout=30)
    at.run()
    return at


def _infos(at):
    return [i.value for i in at.info]


def _pets_por_qtd_avistamentos():
    """(ids de pets desaparecidos sem avistamentos, ids com avistamentos)."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT p.id, COUNT(a.id) AS n FROM pets p "
            "LEFT JOIN avistamentos a ON a.pet_id = p.id "
            "WHERE p.status = 'desaparecido' GROUP BY p.id"
        ).fetchall()
    finally:
        conn.close()
    sem = [r["id"] for r in rows if r["n"] == 0]
    com = [r["id"] for r in rows if r["n"] > 0]
    return sem, com


def test_mensagem_quando_unico_pet_nao_tem_avistamentos(tmp_db, app_path):
    # Banco pré-populado com um pet: o seed não roda (pets não vazia).
    db.init_db()
    pet_id = db.inserir_pet(dict(PET_VALIDO))

    at = _run(app_path)

    assert not at.exception
    assert at.selectbox(key="avist_pet").value == pet_id
    assert MSG_SEM_AVISTAMENTOS in _infos(at)


def test_mensagem_some_apos_pet_ter_avistamento(tmp_db, app_path):
    db.init_db()
    pet_id = db.inserir_pet(dict(PET_VALIDO))
    db.inserir_avistamento({"pet_id": pet_id, "lat": -23.56, "lng": -46.64, "observacao": "Na praça"})

    at = _run(app_path)

    assert not at.exception
    assert MSG_SEM_AVISTAMENTOS not in _infos(at)


def test_mensagem_conforme_pet_selecionado_no_banco_com_seed(tmp_db, app_path):
    at = _run(app_path)
    assert not at.exception

    sem, com = _pets_por_qtd_avistamentos()
    assert sem and com, "o seed deveria ter pets com e sem avistamentos"

    at.selectbox(key="avist_pet").set_value(sem[0]).run()
    assert not at.exception
    assert MSG_SEM_AVISTAMENTOS in _infos(at)

    at.selectbox(key="avist_pet").set_value(com[0]).run()
    assert not at.exception
    assert MSG_SEM_AVISTAMENTOS not in _infos(at)
