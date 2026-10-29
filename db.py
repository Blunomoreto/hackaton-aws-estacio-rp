"""Camada de dados do PataSegura: conexão SQLite, schema e bootstrap."""

import os
import random
import sqlite3
from datetime import date, datetime, timedelta

# Caminho do arquivo SQLite. Testes podem sobrescrever: `db.DB_PATH = tmp_path`.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patasegura.db")

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS pets (
        id                   INTEGER PRIMARY KEY,
        nome                 TEXT    NOT NULL,
        especie              TEXT    NOT NULL,
        descricao            TEXT    NOT NULL,
        lat                  REAL    NOT NULL,
        lng                  REAL    NOT NULL,
        data_desaparecimento TEXT    NOT NULL,
        status               TEXT    NOT NULL DEFAULT 'desaparecido',
        contato              TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS avistamentos (
        id          INTEGER PRIMARY KEY,
        pet_id      INTEGER NOT NULL,
        lat         REAL    NOT NULL,
        lng         REAL    NOT NULL,
        data        TEXT    NOT NULL,
        observacao  TEXT,
        FOREIGN KEY (pet_id) REFERENCES pets(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS denuncias (
        id          INTEGER PRIMARY KEY,
        tipo        TEXT    NOT NULL,
        descricao   TEXT    NOT NULL,
        lat         REAL    NOT NULL,
        lng         REAL    NOT NULL,
        data        TEXT    NOT NULL,
        distrito    TEXT    NOT NULL
    )
    """,
)


def get_conn() -> sqlite3.Connection:
    """Abre conexão com o banco (DB_PATH lido em tempo de chamada)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Cria as tabelas pets, avistamentos e denuncias se não existirem.

    Exceções do sqlite3 são propagadas para o chamador (bootstrap em app.py).
    """
    conn = get_conn()
    try:
        with conn:
            for ddl in SCHEMA:
                conn.execute(ddl)
    finally:
        conn.close()


# Distritos reais de São Paulo com coordenadas aproximadas (lat, lng).
# Os nomes são a chave compartilhada com maps.CENTROIDES_DISTRITOS.
DISTRITOS_SP: dict[str, tuple[float, float]] = {
    "Sé": (-23.5505, -46.6340),
    "República": (-23.5440, -46.6420),
    "Bela Vista": (-23.5610, -46.6450),
    "Pinheiros": (-23.5670, -46.6930),
    "Mooca": (-23.5600, -46.5990),
    "Tatuapé": (-23.5400, -46.5760),
    "Itaquera": (-23.5360, -46.4560),
    "Capão Redondo": (-23.6720, -46.7790),
    "Grajaú": (-23.7580, -46.6970),
    "Santana": (-23.5020, -46.6250),
    "Butantã": (-23.5710, -46.7080),
    "Jabaquara": (-23.6460, -46.6410),
    "Brasilândia": (-23.4700, -46.6880),
    "Campo Limpo": (-23.6400, -46.7590),
    "Cidade Ademar": (-23.6700, -46.6570),
}

# Distribuição desigual das ~40 denúncias de seed (total = 40), para que o
# mapa de risco mostre diferenças claras entre distritos.
_SEED_DENUNCIAS_POR_DISTRITO: dict[str, int] = {
    "Capão Redondo": 7,
    "Grajaú": 6,
    "Brasilândia": 5,
    "Itaquera": 5,
    "Sé": 4,
    "Campo Limpo": 3,
    "Cidade Ademar": 3,
    "Jabaquara": 2,
    "Mooca": 2,
    "República": 1,
    "Santana": 1,
    "Tatuapé": 1,
}

_TIPOS_DENUNCIA = (
    "Abandono",
    "Agressão física",
    "Falta de alimentação",
    "Confinamento inadequado",
    "Envenenamento",
    "Animal acorrentado",
)

_DESCRICOES_DENUNCIA = (
    "Animal deixado sozinho no quintal há vários dias, sem água.",
    "Vizinho agride o cachorro com frequência; ouvem-se ganidos à noite.",
    "Gato muito magro preso em varanda sem comida.",
    "Cachorro mantido em espaço minúsculo, sem sombra, exposto ao sol.",
    "Suspeita de envenenamento de animais de rua na praça.",
    "Cão acorrentado o dia inteiro com corrente curta e ferimentos.",
)

# (nome, especie, descricao, distrito, dias_atras, contato)
_SEED_PETS = (
    ("Thor", "Cachorro", "Vira-lata caramelo, porte médio, coleira azul.", "Pinheiros", 3, "(11) 91234-0001"),
    ("Mel", "Cachorro", "Golden retriever fêmea, muito dócil.", "Mooca", 5, "(11) 91234-0002"),
    ("Frajola", "Gato", "Gato preto e branco, olhos verdes.", "Santana", 2, "(11) 91234-0003"),
    ("Luna", "Gato", "Gata siamesa, castrada, tímida.", "Bela Vista", 8, "(11) 91234-0004"),
    ("Bob", "Cachorro", "Beagle macho com mancha no olho esquerdo.", "Tatuapé", 1, "(11) 91234-0005"),
    ("Nina", "Cachorro", "Poodle branca pequena, pelo curto.", "Butantã", 12, "(11) 91234-0006"),
    ("Simba", "Gato", "Gato laranja rajado, porte grande.", "Jabaquara", 4, "(11) 91234-0007"),
    ("Pipoca", "Cachorro", "Shih-tzu fêmea com laço rosa.", "Sé", 6, "(11) 91234-0008"),
    ("Rex", "Cachorro", "Pastor alemão, coleira de couro.", "Itaquera", 10, "(11) 91234-0009"),
    ("Mia", "Gato", "Gata cinza, pequena, com coleira de guizo.", "República", 3, "(11) 91234-0010"),
    ("Paçoca", "Cachorro", "Vira-lata marrom com rabo enrolado.", "Capão Redondo", 7, "(11) 91234-0011"),
    ("Tom", "Gato", "Gato tigrado cinza, muito miador.", "Grajaú", 9, "(11) 91234-0012"),
    ("Belinha", "Cachorro", "Dachshund fêmea, pelo preto e caramelo.", "Campo Limpo", 2, "(11) 91234-0013"),
    ("Kiwi", "Pássaro", "Calopsita amarela com bochechas laranja.", "Brasilândia", 1, "(11) 91234-0014"),
    ("Zeca", "Cachorro", "Labrador preto, idoso, anda devagar.", "Cidade Ademar", 15, "(11) 91234-0015"),
)

# (indice do pet em _SEED_PETS, distrito, horas_atras, observacao)
_SEED_AVISTAMENTOS = (
    (0, "Pinheiros", 30, "Visto perto do Largo da Batata."),
    (0, "Butantã", 10, "Parecia estar indo em direção à USP."),
    (1, "Mooca", 20, "Cachorra parecida perto da Rua da Mooca."),
    (4, "Tatuapé", 5, "Beagle correndo perto do metrô Tatuapé."),
    (7, "Sé", 40, "Vista na Praça da Sé com um morador de rua."),
    (8, "Itaquera", 60, "Pastor alemão perto do estádio."),
    (10, "Capão Redondo", 12, "Vira-lata caramelo-escuro perto da estação."),
    (12, "Campo Limpo", 3, "Dachshund atravessando a avenida."),
)


def _perto(rng: random.Random, distrito: str, raio: float = 0.008) -> tuple[float, float]:
    """Coordenada aleatória próxima ao centro aproximado do distrito."""
    lat, lng = DISTRITOS_SP[distrito]
    return (
        round(lat + rng.uniform(-raio, raio), 6),
        round(lng + rng.uniform(-raio, raio), 6),
    )


def seed() -> None:
    """Popula dados sintéticos de SP somente se a tabela pets estiver vazia.

    Idempotente: com 1+ pets existentes, nenhum registro é inserido.
    Toda a inserção ocorre em uma única transação.
    """
    rng = random.Random(42)  # determinístico para demos reproduzíveis
    agora = datetime.now().replace(microsecond=0)
    hoje = date.today()

    conn = get_conn()
    try:
        with conn:
            (total_pets,) = conn.execute("SELECT COUNT(*) FROM pets").fetchone()
            if total_pets > 0:
                return

            pet_ids: list[int] = []
            for nome, especie, descricao, distrito, dias, contato in _SEED_PETS:
                lat, lng = _perto(rng, distrito)
                cur = conn.execute(
                    "INSERT INTO pets (nome, especie, descricao, lat, lng, "
                    "data_desaparecimento, status, contato) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        nome,
                        especie,
                        descricao,
                        lat,
                        lng,
                        (hoje - timedelta(days=dias)).isoformat(),
                        "desaparecido",
                        contato,
                    ),
                )
                pet_ids.append(cur.lastrowid)

            for idx_pet, distrito, horas, observacao in _SEED_AVISTAMENTOS:
                lat, lng = _perto(rng, distrito)
                conn.execute(
                    "INSERT INTO avistamentos (pet_id, lat, lng, data, observacao) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        pet_ids[idx_pet],
                        lat,
                        lng,
                        (agora - timedelta(hours=horas)).isoformat(),
                        observacao,
                    ),
                )

            for distrito, quantidade in _SEED_DENUNCIAS_POR_DISTRITO.items():
                for _ in range(quantidade):
                    lat, lng = _perto(rng, distrito, raio=0.012)
                    k = rng.randrange(len(_TIPOS_DENUNCIA))
                    conn.execute(
                        "INSERT INTO denuncias (tipo, descricao, lat, lng, data, distrito) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            _TIPOS_DENUNCIA[k],
                            _DESCRICOES_DENUNCIA[k],
                            lat,
                            lng,
                            (agora - timedelta(hours=rng.randint(1, 24 * 30))).isoformat(),
                            distrito,
                        ),
                    )
    finally:
        conn.close()


def bootstrap() -> None:
    """Prepara o banco no startup: schema e depois seed."""
    init_db()
    seed()


# ---------------------------------------------------------------------------
# Registro de Pets: validação e inserção
# ---------------------------------------------------------------------------

import math as _math  # noqa: E402  (mantido junto do bloco que o usa)

STATUS_DESAPARECIDO = "desaparecido"


def _validar_texto(dados: dict, campo: str, max_len: int | None, erros: list[str]) -> None:
    """Campo de texto obrigatório: não vazio (após strip) e até max_len caracteres."""
    valor = dados.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        erros.append(f"{campo}: campo obrigatório ausente")
    elif not isinstance(valor, str):
        erros.append(f"{campo}: deve ser um texto")
    elif max_len is not None and len(valor) > max_len:
        erros.append(f"{campo}: deve ter entre 1 e {max_len} caracteres")


def _validar_coordenada(dados: dict, campo: str, limite: float, erros: list[str]) -> None:
    """Coordenada obrigatória: número finito (não bool) dentro de [-limite, limite]."""
    valor = dados.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        erros.append(f"{campo}: campo obrigatório ausente")
    elif isinstance(valor, bool) or not isinstance(valor, (int, float)):
        erros.append(f"{campo}: deve ser um número")
    elif not _math.isfinite(valor) or not (-limite <= valor <= limite):
        erros.append(f"{campo}: deve estar entre {-limite:g} e {limite:g}")


def _parse_data(valor) -> date | None:
    """Converte date/datetime ou string ISO (YYYY-MM-DD) em date; None se inválido."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor.strip())
        except ValueError:
            return None
    return None


def validar_pet(dados: dict) -> list[str]:
    """Valida os dados de um pet; retorna lista de erros (vazia se válido).

    Nunca levanta exceção para entradas malformadas.
    """
    if not isinstance(dados, dict):
        return ["dados: formato inválido"]

    erros: list[str] = []
    _validar_texto(dados, "nome", 100, erros)
    _validar_texto(dados, "especie", None, erros)
    _validar_texto(dados, "descricao", 500, erros)
    _validar_texto(dados, "contato", 100, erros)
    _validar_coordenada(dados, "lat", 90, erros)
    _validar_coordenada(dados, "lng", 180, erros)

    bruto = dados.get("data_desaparecimento")
    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        erros.append("data_desaparecimento: campo obrigatório ausente")
    else:
        d = _parse_data(bruto)
        if d is None:
            erros.append("data_desaparecimento: data inválida (use AAAA-MM-DD)")
        elif d > date.today():
            erros.append("data_desaparecimento: não pode ser uma data futura")

    return erros


def inserir_pet(dados: dict) -> int:
    """Valida e persiste um pet com status "desaparecido"; retorna o id.

    Levanta ValueError(lista_de_erros) se inválido, sem persistir nada.
    """
    erros = validar_pet(dados)
    if erros:
        raise ValueError(erros)

    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO pets (nome, especie, descricao, lat, lng, "
                "data_desaparecimento, status, contato) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    dados["nome"],
                    dados["especie"],
                    dados["descricao"],
                    float(dados["lat"]),
                    float(dados["lng"]),
                    _parse_data(dados["data_desaparecimento"]).isoformat(),
                    STATUS_DESAPARECIDO,
                    dados["contato"],
                ),
            )
            return cur.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Registro de Pets: listagem
# ---------------------------------------------------------------------------


def listar_pets(especie: str | None = None) -> list[sqlite3.Row]:
    """Lista pets com status "desaparecido", do desaparecimento mais recente ao mais antigo.

    `especie` opcional filtra por correspondência exata; None ou string vazia
    (após strip) significa "sem filtro".
    """
    sql = "SELECT * FROM pets WHERE status = ?"
    params: list = [STATUS_DESAPARECIDO]
    if isinstance(especie, str) and especie.strip():
        sql += " AND especie = ?"
        params.append(especie)
    sql += " ORDER BY data_desaparecimento DESC, id DESC"

    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def listar_especies() -> list[str]:
    """Espécies distintas entre os pets desaparecidos, em ordem alfabética (para o filtro da UI)."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT especie FROM pets WHERE status = ? ORDER BY especie",
            (STATUS_DESAPARECIDO,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Métricas de topo e índice de risco
# ---------------------------------------------------------------------------


def _contar(sql: str, params: tuple = ()) -> int:
    """Executa um SELECT COUNT(*) estático e retorna o inteiro (0 se vazio)."""
    conn = get_conn()
    try:
        (total,) = conn.execute(sql, params).fetchone()
        return int(total or 0)
    finally:
        conn.close()


def contar_pets() -> int:
    """Total de pets com status "desaparecido" (rótulo da métrica: "Pets desaparecidos")."""
    return _contar("SELECT COUNT(*) FROM pets WHERE status = ?", (STATUS_DESAPARECIDO,))


def contar_avistamentos() -> int:
    """Total de avistamentos registrados."""
    return _contar("SELECT COUNT(*) FROM avistamentos")


def contar_denuncias() -> int:
    """Total de denúncias registradas."""
    return _contar("SELECT COUNT(*) FROM denuncias")


def contar_metricas() -> dict[str, int]:
    """Métricas de topo: {"pets", "avistamentos", "denuncias"} (0 quando a tabela está vazia).

    "pets" conta apenas pets com status "desaparecido", coerente com o rótulo
    "Pets desaparecidos" da UI. Cada contador abre a própria conexão; a UI chama
    os contadores individuais em try/except separados para que a falha de uma
    métrica não afete as demais (Req 2.6).
    """
    return {
        "pets": contar_pets(),
        "avistamentos": contar_avistamentos(),
        "denuncias": contar_denuncias(),
    }


def indice_de_risco() -> dict[str, int]:
    """Índice de risco por distrito: {distrito: contagem} via GROUP BY distrito COUNT(*).

    Só aparecem distritos com 1 ou mais denúncias; sem denúncias retorna {}.
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT distrito, COUNT(*) AS total FROM denuncias GROUP BY distrito"
        ).fetchall()
        return {r["distrito"]: int(r["total"]) for r in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Registro de Avistamentos: validação, inserção e listagem
# ---------------------------------------------------------------------------

MAX_OBSERVACAO = 500

# Faixa de INTEGER do SQLite (64 bits com sinal); ints fora dela não podem ser
# usados como parâmetro de consulta e, portanto, não referenciam nenhum pet.
_SQLITE_INT_MIN = -(2**63)
_SQLITE_INT_MAX = 2**63 - 1


def _pet_existe(pet_id: int) -> bool:
    """True se existe um registro em pets com o id informado."""
    conn = get_conn()
    try:
        return conn.execute("SELECT 1 FROM pets WHERE id = ?", (pet_id,)).fetchone() is not None
    finally:
        conn.close()


def validar_avistamento(dados: dict) -> list[str]:
    """Valida os dados de um avistamento; retorna lista de erros (vazia se válido).

    Regras: pet_id inteiro (não bool) que referencia um pet existente;
    lat ∈ [-90, 90]; lng ∈ [-180, 180]; observacao opcional (None ou "" são
    aceitos), mas se informada deve ser texto com até 500 caracteres.
    Nunca levanta exceção para entradas malformadas.
    """
    if not isinstance(dados, dict):
        return ["dados: formato inválido"]

    erros: list[str] = []

    pet_id = dados.get("pet_id")
    if pet_id is None:
        erros.append("pet_id: campo obrigatório ausente")
    elif isinstance(pet_id, bool) or not isinstance(pet_id, int):
        erros.append("pet_id: deve ser um número inteiro")
    elif not (_SQLITE_INT_MIN <= pet_id <= _SQLITE_INT_MAX) or not _pet_existe(pet_id):
        erros.append("pet_id: pet não encontrado")

    _validar_coordenada(dados, "lat", 90, erros)
    _validar_coordenada(dados, "lng", 180, erros)

    observacao = dados.get("observacao")
    if observacao is not None:
        if not isinstance(observacao, str):
            erros.append("observacao: deve ser um texto")
        elif len(observacao) > MAX_OBSERVACAO:
            erros.append(f"observacao: deve ter no máximo {MAX_OBSERVACAO} caracteres")

    return erros


def inserir_avistamento(dados: dict) -> int:
    """Valida e persiste um avistamento associado a pet_id; retorna o id.

    `data` é preenchida com datetime.now() em ISO-8601 com microssegundos, para
    que a ordenação por data seja determinística mesmo em inserções no mesmo
    segundo. `observacao` é gravada como recebida (None permanece NULL).
    O status do pet não é alterado (Req 4.5).
    Levanta ValueError(lista_de_erros) se inválido, sem persistir nada.
    """
    erros = validar_avistamento(dados)
    if erros:
        raise ValueError(erros)

    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO avistamentos (pet_id, lat, lng, data, observacao) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    dados["pet_id"],
                    float(dados["lat"]),
                    float(dados["lng"]),
                    datetime.now().isoformat(),
                    dados.get("observacao"),
                ),
            )
            return cur.lastrowid
    finally:
        conn.close()


def listar_avistamentos(pet_id: int) -> list[sqlite3.Row]:
    """Avistamentos do pet, do mais recente ao mais antigo (id desc como desempate)."""
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM avistamentos WHERE pet_id = ? ORDER BY data DESC, id DESC",
            (pet_id,),
        ).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Registro de Denúncias: validação e inserção anônima
# ---------------------------------------------------------------------------

# Únicos campos aceitos do chamador; id e data são gerados internamente.
CAMPOS_DENUNCIA = ("tipo", "descricao", "lat", "lng", "distrito")
MAX_DESCRICAO_DENUNCIA = 1000


def validar_denuncia(dados: dict) -> list[str]:
    """Valida os dados de uma denúncia; retorna lista de erros (vazia se válido).

    Regras: tipo e distrito não vazios; descricao com 1 a 1000 caracteres;
    lat ∈ [-90, 90]; lng ∈ [-180, 180]. Cada mensagem começa com o nome do
    campo inválido (Req 5.5–5.9). Chaves fora de CAMPOS_DENUNCIA são ignoradas
    (não geram erro). Nunca levanta exceção para entradas malformadas.
    """
    if not isinstance(dados, dict):
        return ["dados: formato inválido"]

    erros: list[str] = []
    _validar_texto(dados, "tipo", None, erros)
    _validar_texto(dados, "descricao", MAX_DESCRICAO_DENUNCIA, erros)
    _validar_coordenada(dados, "lat", 90, erros)
    _validar_coordenada(dados, "lng", 180, erros)
    _validar_texto(dados, "distrito", None, erros)
    return erros


def inserir_denuncia(dados: dict) -> int:
    """Valida e persiste uma denúncia anônima; retorna o id.

    Anonimato (Req 5.3, 5.4): antes de qualquer outra etapa, o payload é
    reduzido às chaves de CAMPOS_DENUNCIA; qualquer outra chave (nome, email,
    telefone, ip, user_id, id, data...) é descartada. A tabela denuncias não
    possui colunas para dados identificáveis, então nada identificável é
    persistido. O chamador não controla `id` (gerado pelo SQLite) nem `data`
    (preenchida com datetime.now() no momento da persistência, Req 5.2).
    Levanta ValueError(lista_de_erros) se inválido, sem persistir nada.
    """
    if not isinstance(dados, dict):
        raise ValueError(["dados: formato inválido"])

    limpo = {k: dados[k] for k in CAMPOS_DENUNCIA if k in dados}

    erros = validar_denuncia(limpo)
    if erros:
        raise ValueError(erros)

    conn = get_conn()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO denuncias (tipo, descricao, lat, lng, distrito, data) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    limpo["tipo"],
                    limpo["descricao"],
                    float(limpo["lat"]),
                    float(limpo["lng"]),
                    limpo["distrito"],
                    datetime.now().isoformat(),
                ),
            )
            return cur.lastrowid
    finally:
        conn.close()
