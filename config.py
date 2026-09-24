import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from urllib.parse import quote, urlparse, urlunparse


DIRETORIO_PROJETO = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CONFIGURACOES = os.path.join(DIRETORIO_PROJETO, "sistema.json")
ARQUIVO_CAMERAS = os.environ.get(
    "NVRBOX_CAMERAS",
    os.path.join(DIRETORIO_PROJETO, "cameras.local.json"),
)
ARQUIVO_CAMERAS_EXEMPLO = os.path.join(DIRETORIO_PROJETO, "cameras.example.json")
ARQUIVO_ESTADO_CAPTURA = os.environ.get(
    "NVRBOX_ESTADO_CAPTURA",
    os.path.join(DIRETORIO_PROJETO, ".run", "estado_captura.json"),
)
RAIZES_ARMAZENAMENTO_EXTERNO = ("/media", "/mnt", "/storage", "/run/media")
CAMINHOS_ARMAZENAMENTO_FIXOS = ("/sdcard", "/storage/emulated/0", "/storage/self/primary")
NOMES_IGNORADOS_ARMAZENAMENTO = {"self", "runtime", "tmp", "tmpfs"}
VALORES_VERDADEIROS = {"1", "true", "yes", "sim", "on"}
TEMPOS_SEGMENTO_PERMITIDOS = (300, 600, 900)
TEMPO_SEGMENTO_PADRAO = 600
DATA_VIDEO_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.mp4$")


def env_bool(nome, padrao=False):
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in VALORES_VERDADEIROS


def normalizar_caminho(caminho):
    return os.path.abspath(os.path.expanduser(caminho))


def carregar_configuracoes():
    if not os.path.exists(ARQUIVO_CONFIGURACOES):
        return {}
    try:
        with open(ARQUIVO_CONFIGURACOES, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {}


def salvar_json_atomico(caminho, dados, sincronizar=True):
    diretorio = os.path.dirname(caminho) or "."
    os.makedirs(diretorio, exist_ok=True)
    nome_base = os.path.basename(caminho)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=diretorio,
            prefix=f".{nome_base}.",
            suffix=".tmp",
            delete=False,
        ) as arquivo:
            temporario = arquivo.name
            json.dump(dados, arquivo, indent=4, ensure_ascii=False)
            arquivo.write("\n")
            arquivo.flush()
            if sincronizar:
                os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if temporario and os.path.exists(temporario):
            os.remove(temporario)


def salvar_configuracoes(configuracoes):
    salvar_json_atomico(ARQUIVO_CONFIGURACOES, configuracoes)


def _candidatos_armazenamento_externo():
    for caminho in CAMINHOS_ARMAZENAMENTO_FIXOS:
        if os.path.isdir(caminho):
            yield caminho

    for raiz in RAIZES_ARMAZENAMENTO_EXTERNO:
        if not os.path.isdir(raiz):
            continue

        try:
            itens = os.listdir(raiz)
        except OSError:
            continue

        for item in itens:
            if item in NOMES_IGNORADOS_ARMAZENAMENTO:
                continue

            caminho = os.path.join(raiz, item)
            if os.path.isdir(caminho):
                yield caminho

            try:
                filhos = os.listdir(caminho)
            except OSError:
                continue

            for filho in filhos:
                if filho in NOMES_IGNORADOS_ARMAZENAMENTO:
                    continue
                subcaminho = os.path.join(caminho, filho)
                if os.path.isdir(subcaminho):
                    yield subcaminho


class ArmazenamentoIndisponivel(OSError):
    """Pasta de gravacao inutilizavel. A mensagem e escrita para o usuario final."""


def _ponto_de_montagem(caminho):
    atual = caminho
    while not os.path.exists(atual) and atual != os.sep:
        atual = os.path.dirname(atual)
    while not os.path.ismount(atual) and atual != os.sep:
        atual = os.path.dirname(atual)
    return atual


def _raiz_externa(caminho):
    for raiz in RAIZES_ARMAZENAMENTO_EXTERNO:
        if caminho == raiz or caminho.startswith(raiz + os.sep):
            return raiz
    return None


def verificar_armazenamento(caminho_gravacoes, testar_escrita=True):
    """Confere se da para gravar no caminho, sem criar pastas em disco desconectado.

    Em memorias externas (/media, /mnt, /storage, /run/media) o disco precisa
    estar montado dentro da raiz. Sem isso, a pasta seria criada no disco do
    sistema e a gravacao seguiria no lugar errado sem aviso. Por isso nao basta
    achar qualquer ponto de montagem: /run, por exemplo, ja e um tmpfs.
    """
    caminho = os.path.realpath(normalizar_caminho(caminho_gravacoes))
    raiz = _raiz_externa(caminho)
    if raiz and not _ponto_de_montagem(caminho).startswith(raiz + os.sep):
        return False, f"O HD externo nao esta conectado ({caminho}). Conecte o HD para voltar a gravar."

    try:
        os.makedirs(caminho, exist_ok=True)
        if testar_escrita:
            arquivo_teste = os.path.join(caminho, ".nvrbox_write_test")
            with open(arquivo_teste, "w", encoding="utf-8") as arquivo:
                arquivo.write("ok")
            os.remove(arquivo_teste)
    except PermissionError:
        return False, f"Sem permissao para gravar em {caminho}."
    except OSError as erro:
        return False, f"Nao foi possivel gravar em {caminho}: {erro.strerror or erro}."
    return True, None


def _pode_gravar_em(caminho_gravacoes):
    return verificar_armazenamento(caminho_gravacoes)[0]


def _info_disco(caminho):
    try:
        uso = shutil.disk_usage(caminho)
        total_gb = uso.total / (1024 ** 3)
        livre_gb = uso.free / (1024 ** 3)
        usado_gb = uso.used / (1024 ** 3)
        return {
            "total": f"{total_gb:.1f} GB",
            "livre": f"{livre_gb:.1f} GB",
            "usado": f"{usado_gb:.1f} GB",
            "porcentagem": int((uso.used / uso.total) * 100),
        }
    except OSError:
        return {"total": "0 GB", "livre": "0 GB", "usado": "0 GB", "porcentagem": 0}


def _nome_armazenamento(caminho_base):
    if caminho_base == DIRETORIO_PROJETO:
        return "Memoria interna do sistema"
    if caminho_base in {"/sdcard", "/storage/emulated/0", "/storage/self/primary"}:
        return "Memoria interna Android"
    nome = os.path.basename(caminho_base.rstrip(os.sep))
    return nome or caminho_base


def _caminho_gravacoes_para_base(caminho_base):
    return os.path.join(caminho_base, "gravacoes")


def encontrar_armazenamento():
    caminho_configurado = os.environ.get("NVRBOX_GRAVACOES")
    if caminho_configurado:
        return normalizar_caminho(caminho_configurado)

    configuracoes = carregar_configuracoes()
    caminho_escolhido = configuracoes.get("caminho_videos")
    if caminho_escolhido:
        return normalizar_caminho(caminho_escolhido)

    for candidato in _candidatos_armazenamento_externo():
        caminho_gravacoes = _caminho_gravacoes_para_base(candidato)
        if _pode_gravar_em(caminho_gravacoes):
            return caminho_gravacoes

    return os.path.join(DIRETORIO_PROJETO, "gravacoes")


def get_caminho_videos():
    return encontrar_armazenamento()


def garantir_diretorios(caminho=None, testar_escrita=True):
    ok, erro = verificar_armazenamento(caminho or get_caminho_videos(), testar_escrita)
    if not ok:
        raise ArmazenamentoIndisponivel(erro)


def listar_armazenamentos():
    vistos = set()
    caminho_atual = normalizar_caminho(get_caminho_videos())
    opcoes = []

    def adicionar(caminho_gravacoes, nome):
        caminho_gravacoes = normalizar_caminho(caminho_gravacoes)
        if caminho_gravacoes in vistos or not _pode_gravar_em(caminho_gravacoes):
            return
        vistos.add(caminho_gravacoes)
        info = _info_disco(caminho_gravacoes)
        opcoes.append({
            "nome": nome,
            "caminho": caminho_gravacoes,
            "total": info["total"],
            "livre": info["livre"],
            "usado": info["usado"],
            "porcentagem": info["porcentagem"],
            "selecionado": caminho_gravacoes == caminho_atual,
        })

    caminho_env = os.environ.get("NVRBOX_GRAVACOES")
    if caminho_env:
        adicionar(caminho_env, "Configurado por ambiente")

    caminho_salvo = carregar_configuracoes().get("caminho_videos")
    if caminho_salvo:
        adicionar(caminho_salvo, "Armazenamento escolhido")

    adicionar(os.path.join(DIRETORIO_PROJETO, "gravacoes"), "Memoria interna do sistema")

    for candidato in _candidatos_armazenamento_externo():
        adicionar(_caminho_gravacoes_para_base(candidato), _nome_armazenamento(candidato))

    return opcoes


def definir_armazenamento(caminho_gravacoes):
    caminho_gravacoes = normalizar_caminho(caminho_gravacoes)
    ok, erro = verificar_armazenamento(caminho_gravacoes)
    if not ok:
        return False, erro

    configuracoes = carregar_configuracoes()
    configuracoes["caminho_videos"] = caminho_gravacoes
    salvar_configuracoes(configuracoes)
    return True, None


def get_tempo_segmento():
    tempo_env = os.environ.get("NVRBOX_TEMPO_SEGMENTO")
    if tempo_env:
        try:
            return int(tempo_env)
        except ValueError:
            return TEMPO_SEGMENTO_PADRAO

    configuracoes = carregar_configuracoes()
    try:
        tempo = int(configuracoes.get("tempo_segmento", TEMPO_SEGMENTO_PADRAO))
    except (TypeError, ValueError):
        tempo = TEMPO_SEGMENTO_PADRAO

    if tempo not in TEMPOS_SEGMENTO_PERMITIDOS:
        return TEMPO_SEGMENTO_PADRAO
    return tempo


def definir_tempo_segmento(tempo_segmento):
    try:
        tempo_segmento = int(tempo_segmento)
    except (TypeError, ValueError):
        return False, "Tempo de segmento invalido."

    if tempo_segmento not in TEMPOS_SEGMENTO_PERMITIDOS:
        return False, "Escolha 5, 10 ou 15 minutos."

    configuracoes = carregar_configuracoes()
    configuracoes["tempo_segmento"] = tempo_segmento
    salvar_configuracoes(configuracoes)
    return True, None


CAMINHO_VIDEOS = get_caminho_videos()
LIMITE_USO_PORCENTAGEM = int(os.environ.get("NVRBOX_LIMITE_DISCO", "90"))
TEMPO_SEGMENTO = get_tempo_segmento()
RTSP_TRANSPORTE_PADRAO = os.environ.get("NVRBOX_RTSP_TRANSPORTE", "udp")
TESTAR_RTSP_CADASTRO = env_bool("NVRBOX_TESTAR_RTSP_CADASTRO", True)
TIMEOUT_TESTE_RTSP = int(os.environ.get("NVRBOX_TIMEOUT_TESTE_RTSP", "8"))
TIMEOUT_RTSP_SEGUNDOS = int(os.environ.get("NVRBOX_TIMEOUT_RTSP", "15"))
FFMPEG_LOG_MAX_BYTES = int(os.environ.get("NVRBOX_FFMPEG_LOG_MAX_BYTES", str(2 * 1024 * 1024)))
AUTH_USUARIO = os.environ.get("NVRBOX_AUTH_USUARIO", "").strip()
AUTH_SENHA = os.environ.get("NVRBOX_AUTH_SENHA", "").strip()
AUTH_ATIVA = bool(AUTH_USUARIO and AUTH_SENHA)
RTSP_PERFIS = {
    "onvif1": {
        "nome": "ONVIF / Intelbras",
        "path": "/onvif1",
    },
    "hikvision": {
        "nome": "Hikvision",
        "path": "/Streaming/Channels/101",
    },
    "dahua": {
        "nome": "Dahua",
        "path": "/cam/realmonitor?channel=1&subtype=0",
    },
    "xm": {
        "nome": "XM / Yoosee",
        "path": "/user={usuario}&password={senha}&channel=1&stream=0.sdp",
    },
    "live_ch00": {
        "nome": "Generica CH00",
        "path": "/live/ch00_0",
    },
}


def gerar_slug(nome):
    texto = unicodedata.normalize("NFKD", nome.strip().lower())
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    return texto or "camera"


def slug_camera(camera):
    return gerar_slug(camera.get("slug") or camera.get("nome", "camera"))


def carregar_cameras():
    if not os.path.exists(ARQUIVO_CAMERAS):
        return []
    try:
        with open(ARQUIVO_CAMERAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError) as erro:
        print(f"[Config] Erro ao carregar cameras: {erro}", flush=True)
        return []
    if not isinstance(dados, list):
        print("[Config] Arquivo de cameras invalido: esperado uma lista.", flush=True)
        return []
    return dados


def salvar_cameras(cameras):
    salvar_json_atomico(ARQUIVO_CAMERAS, cameras)


def carregar_estado_captura():
    try:
        with open(ARQUIVO_ESTADO_CAPTURA, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return None
    return dados if isinstance(dados, dict) else None


def salvar_estado_captura(estado):
    # Estado efemero reescrito com frequencia: sem fsync para poupar cartao SD.
    salvar_json_atomico(ARQUIVO_ESTADO_CAPTURA, estado, sincronizar=False)


def extrair_data_video(nome_arquivo, slug_fixo):
    prefixo = f"{slug_fixo}_"
    if not nome_arquivo.startswith(prefixo):
        return None

    match = DATA_VIDEO_REGEX.match(nome_arquivo[len(prefixo):])
    if not match:
        return None
    return match.group(1)


def nome_video_pertence_camera(nome_arquivo, slug_fixo):
    return extrair_data_video(nome_arquivo, slug_fixo) is not None


_OPCAO_TIMEOUT_RTSP = None


def opcao_timeout_rtsp():
    """Nome da opcao de timeout de socket do RTSP no FFmpeg instalado.

    FFmpeg 5+ usa -timeout. Versoes antigas usam -stimeout, e nelas -timeout
    coloca o RTSP em modo de escuta, entao nao pode ser usado.
    """
    global _OPCAO_TIMEOUT_RTSP
    if _OPCAO_TIMEOUT_RTSP is None:
        try:
            ajuda = subprocess.run(
                ["ffmpeg", "-hide_banner", "-h", "demuxer=rtsp"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
                check=False,
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            ajuda = ""
        _OPCAO_TIMEOUT_RTSP = "-stimeout" if "-stimeout" in ajuda else "-timeout"
    return _OPCAO_TIMEOUT_RTSP


# O FFmpeg guarda o timeout em microssegundos num inteiro de 32 bits (~2147 s).
TIMEOUT_RTSP_MAXIMO = 2000


def argumentos_timeout_rtsp(segundos=None):
    segundos = TIMEOUT_RTSP_SEGUNDOS if segundos is None else segundos
    segundos = min(max(1, segundos), TIMEOUT_RTSP_MAXIMO)
    return [opcao_timeout_rtsp(), str(int(segundos * 1_000_000))]


def construir_rtsp_url(ip, senha, usuario="admin", perfil="onvif1", porta=554, caminho_manual=""):
    perfil_config = RTSP_PERFIS.get(perfil)
    if perfil == "manual":
        path = caminho_manual.strip()
    elif perfil_config:
        path = perfil_config["path"]
    else:
        path = RTSP_PERFIS["onvif1"]["path"]

    if not path.startswith("/"):
        path = f"/{path}"

    usuario_seguro = quote(usuario.strip(), safe="")
    senha_segura = quote(senha.strip(), safe="")
    host = ip.strip()
    porta = str(porta or 554).strip()
    path = path.format(usuario=usuario_seguro, senha=senha_segura)

    return f"rtsp://{usuario_seguro}:{senha_segura}@{host}:{porta}{path}"


def mascarar_rtsp(url):
    parsed = urlparse(url)
    if not parsed.username and not parsed.password:
        return url

    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"

    usuario = parsed.username or ""
    auth = f"{usuario}:****@" if usuario else "****@"
    return urlunparse(parsed._replace(netloc=f"{auth}{host}"))
