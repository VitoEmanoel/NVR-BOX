import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

from config import (
    ArmazenamentoIndisponivel,
    FFMPEG_LOG_MAX_BYTES,
    RTSP_TRANSPORTE_PADRAO,
    argumentos_timeout_rtsp,
    atualizar_camera,
    carregar_cameras,
    get_caminho_videos,
    get_tempo_segmento,
    garantir_diretorios,
    host_rtsp,
    mascarar_rtsp,
    nome_video_pertence_camera,
    salvar_estado_captura,
    slug_camera,
    trocar_host_rtsp,
)
from rede import PORTA_RTSP_PADRAO, ler_tabela_arp, localizar_camera, normalizar_mac, varrer_rede

INTERVALO_WATCHDOG = 10
# Tempo para o FFmpeg conectar e gravar o primeiro trecho (inclui -analyzeduration de 15 s).
TOLERANCIA_INICIO = 90
# Sem o arquivo crescer por esse tempo, a gravacao e considerada travada.
LIMITE_SEM_GRAVACAO = int(os.environ.get("NVRBOX_LIMITE_SEM_GRAVACAO", "60"))
# Evita reiniciar em loop uma camera desligada.
INTERVALO_MINIMO_REINICIO = 30
# Teste de escrita no armazenamento (cria e apaga um arquivo); a checagem de montagem e a cada ciclo.
INTERVALO_TESTE_ESCRITA = 60
# O estado e regravado quando muda e, no maximo, a cada INTERVALO_ESTADO como sinal de vida.
INTERVALO_ESTADO = 60
# Conferencia pelo MAC de cameras que nao estao gravando (inclusive sem HD).
INTERVALO_CONFERENCIA = 30
# Varredura da rede atras de uma camera sumida: no maximo uma a cada 5 minutos por camera.
INTERVALO_VARREDURA = 300
# Aviso "mudou de endereco" fica visivel no painel por 24 horas.
DURACAO_AVISO = 24 * 3600

RTSP_CREDENCIAIS_REGEX = re.compile(r"(rtsp://)[^@\s/]*@")


def rotacionar_log(caminho_log):
    """Copia o log para .1 e zera o original quando passa do limite.

    Copiar e truncar funciona com o FFmpeg rodando, porque o log e aberto em
    modo de acrescimo: as proximas escritas vao para o inicio do arquivo zerado.
    """
    try:
        if os.path.getsize(caminho_log) < FFMPEG_LOG_MAX_BYTES:
            return
    except OSError:
        return

    try:
        shutil.copyfile(caminho_log, f"{caminho_log}.1")
        os.truncate(caminho_log, 0)
    except OSError as erro:
        print(f"[!] Nao foi possivel rotacionar log {caminho_log}: {erro}", flush=True)


def ultima_linha_log(caminho_log, max_bytes=4096):
    try:
        with open(caminho_log, "rb") as arquivo:
            arquivo.seek(0, os.SEEK_END)
            tamanho = arquivo.tell()
            arquivo.seek(max(0, tamanho - max_bytes))
            conteudo = arquivo.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""

    for linha in reversed(re.split(r"[\r\n]+", conteudo)):
        linha = linha.strip()
        if linha and not linha.startswith("==="):
            return RTSP_CREDENCIAIS_REGEX.sub(r"\1****@", linha)[:200]
    return ""


def ultimo_segmento_camera(caminho_videos, slug):
    maior = ""
    try:
        with os.scandir(caminho_videos) as itens:
            for item in itens:
                if item.name > maior and nome_video_pertence_camera(item.name, slug):
                    maior = item.name
    except OSError:
        return None
    return os.path.join(caminho_videos, maior) if maior else None


def arquivo_aberto_pelo_processo(pid):
    """Segmento .mp4 que o FFmpeg esta escrevendo, lido de /proc (Linux/Android)."""
    pasta_fd = f"/proc/{pid}/fd"
    try:
        descritores = os.listdir(pasta_fd)
    except OSError:
        return None

    for descritor in descritores:
        try:
            destino = os.readlink(os.path.join(pasta_fd, descritor))
        except OSError:
            continue
        if destino.endswith(".mp4"):
            return destino
    return None


def medir_progresso(registro, caminho_videos):
    """Retorna (arquivo, tamanho) do segmento atual; muda quando a gravacao avanca."""
    caminho = arquivo_aberto_pelo_processo(registro["processo"].pid)
    if caminho is None:
        caminho = ultimo_segmento_camera(caminho_videos, registro["slug"])
    if not caminho:
        return None
    try:
        return (caminho, os.path.getsize(caminho))
    except OSError:
        return None


def atualizar_progresso(registro, medida, agora_mono, agora):
    if medida is None or medida == registro.get("medida"):
        return False
    registro["medida"] = medida
    registro["ultimo_progresso_mono"] = agora_mono
    registro["ultimo_progresso"] = agora
    return True


def gravacao_travada(registro, agora_mono, limite=LIMITE_SEM_GRAVACAO, tolerancia=TOLERANCIA_INICIO):
    referencia = registro.get("ultimo_progresso_mono")
    if referencia is None:
        return agora_mono - registro["inicio_mono"] > tolerancia
    return agora_mono - referencia > limite


def porta_camera(cam):
    try:
        return int(cam.get("porta") or 0) or PORTA_RTSP_PADRAO
    except (TypeError, ValueError):
        return PORTA_RTSP_PADRAO


def endereco_trocado(cam, tabela_arp):
    """True se o IP da camera passou a responder por outro aparelho (outro MAC)."""
    mac = normalizar_mac(cam.get("mac"))
    if not mac or not tabela_arp:
        return False
    mac_atual = tabela_arp.get(host_rtsp(cam.get("rtsp_url", "")))
    return mac_atual is not None and mac_atual != mac


def aprender_mac(cam, slug, tabela_arp, macs_em_uso, salvar=atualizar_camera):
    """Salva o MAC de uma camera que esta gravando e ainda nao tem MAC.

    Retorna o MAC salvo, ou None. Nao salva MAC ja usado por outra camera
    (repetidores Wi-Fi com "MAC NAT" mostram o mesmo MAC para varios aparelhos).
    """
    if normalizar_mac(cam.get("mac")) or not tabela_arp:
        return None
    mac = tabela_arp.get(host_rtsp(cam.get("rtsp_url", "")))
    if not mac or mac in macs_em_uso:
        return None
    salvar(slug, mac=mac)
    cam["mac"] = mac
    return mac


def preparar_inicio(cam, slug, info, agora_mono, agora,
                    localizar=localizar_camera, varrer=varrer_rede, salvar=atualizar_camera):
    """Confere pelo MAC se a camera ainda esta no IP salvo antes de iniciar o FFmpeg.

    Retorna a camera (com IP atualizado se ela mudou de endereco) ou None se ela
    nao foi encontrada na rede. Sem MAC salvo, segue com o IP atual.
    """
    ip_atual = host_rtsp(cam.get("rtsp_url", ""))
    porta = porta_camera(cam)

    def varrer_limitado(ip_referencia, porta_rtsp):
        if agora_mono - info.get("ultima_varredura_mono", float("-inf")) < INTERVALO_VARREDURA:
            return ler_tabela_arp()
        info["ultima_varredura_mono"] = agora_mono
        return varrer(ip_referencia, porta_rtsp)

    novo_ip, situacao = localizar(cam.get("mac"), ip_atual, porta, varrer=varrer_limitado)
    if situacao == "nao_encontrada":
        if not info.get("nao_encontrada"):
            print(f"[!] Camera nao encontrada na rede: {cam.get('nome', slug)}", flush=True)
        info["nao_encontrada"] = True
        return None

    info["nao_encontrada"] = False
    if situacao == "mudou":
        nova_url = trocar_host_rtsp(cam["rtsp_url"], novo_ip)
        salvar(slug, ip=novo_ip, rtsp_url=nova_url)
        cam = {**cam, "ip": novo_ip, "rtsp_url": nova_url}
        aviso = f"Camera mudou de endereco ({ip_atual} -> {novo_ip}) e o sistema atualizou sozinho"
        print(f"[!] {aviso}: {cam.get('nome', slug)}", flush=True)
        info["aviso"] = aviso
        info["aviso_em"] = agora
    return cam


def conferir_camera(cam, slug, info, agora_mono, agora, preparar=preparar_inicio):
    """Confere o endereco pelo MAC e anota quando foi. Retorna a camera ou None."""
    info["ultima_conferencia_mono"] = agora_mono
    try:
        return preparar(cam, slug, info, agora_mono, agora)
    except OSError as erro:
        # Falha ao salvar o cadastro nao pode derrubar a captura; tenta de novo depois.
        print(f"[!] Nao foi possivel atualizar o endereco de {cam.get('nome', slug)}: {erro}", flush=True)
        return cam


def conferir_cameras_paradas(lista_cameras, processos, historico, agora_mono, agora, conferir=conferir_camera):
    """Mantem o IP das cameras que nao estao gravando atualizado pelo MAC.

    Roda antes da checagem do HD: mesmo sem gravar, o cadastro precisa apontar
    para a camera certa, senao o ao vivo do painel mostra outra camera.
    """
    atualizadas = []
    for cam in lista_cameras:
        slug = slug_camera(cam)
        info = historico.setdefault(slug, {})
        vencida = agora_mono - info.get("ultima_conferencia_mono", float("-inf")) >= INTERVALO_CONFERENCIA
        if slug not in processos and vencida:
            cam = conferir(cam, slug, info, agora_mono, agora) or cam
        atualizadas.append(cam)
    return atualizadas


def iniciar_ffmpeg(cam, caminho_videos, tempo_segmento):
    url = cam['rtsp_url']
    slug = slug_camera(cam)
    transporte = cam.get('protocolo', RTSP_TRANSPORTE_PADRAO)
    saida = os.path.join(caminho_videos, f"{slug}_%Y-%m-%d_%H-%M-%S.mp4")
    log_file = os.path.join(caminho_videos, f"erro_{slug}.txt")
    rotacionar_log(log_file)
    comando = [
        'ffmpeg',
        '-nostats',
        '-loglevel', 'warning',
        '-rtsp_transport', transporte,
        *argumentos_timeout_rtsp(),
        '-analyzeduration', '15000000',
        '-fflags', '+genpts+igndts',
        '-i', url,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-f', 'segment',
        '-segment_time', str(tempo_segmento),
        '-segment_format', 'mp4',
        '-segment_format_options', 'movflags=frag_keyframe+empty_moov+default_base_moof',
        '-strftime', '1',
        '-reset_timestamps', '1',
        saida
    ]
    f_log = open(log_file, "a", encoding="utf-8")
    f_log.write(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} Iniciando captura ===\n")
    f_log.flush()
    # Segmento que ja existia antes de iniciar nao conta como progresso desta execucao.
    medida_inicial = None
    ultimo = ultimo_segmento_camera(caminho_videos, slug)
    if ultimo:
        try:
            medida_inicial = (ultimo, os.path.getsize(ultimo))
        except OSError:
            pass
    processo = subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=f_log)
    return {
        "processo": processo,
        "log": f_log,
        "log_path": log_file,
        "slug": slug,
        "assinatura": assinatura_camera(cam, tempo_segmento),
        "inicio_mono": time.monotonic(),
        "medida": medida_inicial,
    }


def assinatura_camera(cam, tempo_segmento):
    return (
        cam.get('rtsp_url', ''),
        cam.get('protocolo', RTSP_TRANSPORTE_PADRAO),
        tempo_segmento,
    )

def encerrar_ffmpeg(registro):
    processo = registro["processo"]
    if processo.poll() is None:
        processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait()
    registro["log"].close()


def estado_camera(registro, agora_mono, info=None):
    if registro is None:
        return "nao_encontrada" if (info or {}).get("nao_encontrada") else "reconectando"
    if registro.get("ultimo_progresso_mono") is None:
        return "iniciando"
    if agora_mono - registro["ultimo_progresso_mono"] <= LIMITE_SEM_GRAVACAO:
        return "gravando"
    return "parada"


def montar_estado(caminho_videos, lista_cameras, processos, historico, agora_mono, agora, erro=None):
    cameras = {}
    for cam in lista_cameras:
        slug = slug_camera(cam)
        registro = processos.get(slug)
        info = historico.get(slug, {})
        aviso_recente = info.get("aviso") and agora - info.get("aviso_em", 0) <= DURACAO_AVISO
        cameras[slug] = {
            "nome": cam.get("nome", slug),
            "estado": estado_camera(registro, agora_mono, info),
            "aviso": info.get("aviso") if aviso_recente else None,
            "ultima_gravacao": info.get("ultima_gravacao"),
            "reinicios": info.get("reinicios", 0),
            "ultimo_motivo": info.get("ultimo_motivo"),
            "ultimo_motivo_em": info.get("ultimo_motivo_em"),
            "ultimo_erro": info.get("ultimo_erro"),
        }
    return {
        "ativo": True,
        "pid": os.getpid(),
        "atualizado_em": agora,
        "caminho_videos": caminho_videos,
        "erro": erro,
        "cameras": cameras,
    }


def resumo_para_comparar(estado):
    """Parte do estado que, ao mudar, deve ser salva na hora (sem horarios que mudam todo ciclo)."""
    return (
        estado.get("caminho_videos"),
        estado.get("erro"),
        tuple(
            (slug, info["estado"], info["reinicios"], info["ultimo_motivo"], info.get("aviso"))
            for slug, info in sorted(estado["cameras"].items())
        ),
    )


def registrar_motivo(historico, slug, motivo, registro, agora):
    info = historico.setdefault(slug, {})
    info["reinicios"] = info.get("reinicios", 0) + 1
    info["ultimo_motivo"] = motivo
    info["ultimo_motivo_em"] = agora
    if registro is not None:
        info["ultimo_erro"] = ultima_linha_log(registro["log_path"]) or info.get("ultimo_erro")


if __name__ == '__main__':
    processos = {}
    historico = {}
    ultimo_inicio = {}

    def encerrar_todos(_signum=None, _frame=None):
        for slug, registro in list(processos.items()):
            print(f"[!] Encerrando captura: {slug}", flush=True)
            encerrar_ffmpeg(registro)
            processos.pop(slug, None)
        try:
            salvar_estado_captura({"ativo": False, "atualizado_em": time.time(), "cameras": {}})
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, encerrar_todos)
    signal.signal(signal.SIGINT, encerrar_todos)

    caminho_atual = None
    estado_anterior = None
    ultimo_estado_salvo = float("-inf")
    ultimo_teste_escrita = float("-inf")
    ultimo_erro_impresso = None
    print("--- NVRBox: Motor Blindado e Vigiado ---", flush=True)

    while True:
        agora_mono = time.monotonic()
        agora = time.time()
        lista_cameras = conferir_cameras_paradas(carregar_cameras(), processos, historico, agora_mono, agora)
        erro_ciclo = None
        try:
            novo_caminho = get_caminho_videos()
            tempo_segmento = get_tempo_segmento()
            testar_escrita = agora_mono - ultimo_teste_escrita >= INTERVALO_TESTE_ESCRITA
            try:
                garantir_diretorios(novo_caminho, testar_escrita=testar_escrita)
            except ArmazenamentoIndisponivel:
                # Sem disco, os FFmpeg gravariam no lugar errado ou falhariam: melhor parar.
                for slug, registro in list(processos.items()):
                    print(f"[!] Parando captura sem armazenamento: {slug}", flush=True)
                    encerrar_ffmpeg(processos.pop(slug))
                ultimo_teste_escrita = float("-inf")
                raise
            if testar_escrita:
                ultimo_teste_escrita = agora_mono
            if caminho_atual != novo_caminho:
                if caminho_atual is not None:
                    print(f"[!] Armazenamento alterado: {novo_caminho}", flush=True)
                    for slug, registro in list(processos.items()):
                        print(f"[!] Reiniciando captura em novo armazenamento: {slug}", flush=True)
                        encerrar_ffmpeg(registro)
                        processos.pop(slug, None)
                caminho_atual = novo_caminho

            slugs_ativos = {slug_camera(cam) for cam in lista_cameras}
            tabela_arp = ler_tabela_arp()
            macs_em_uso = {normalizar_mac(cam.get("mac")) for cam in lista_cameras} - {None}

            for slug in list(processos.keys()):
                if slug not in slugs_ativos:
                    print(f"[!] Encerrando captura removida: {slug}", flush=True)
                    encerrar_ffmpeg(processos.pop(slug))

            for cam in lista_cameras:
                nome = cam['nome']
                slug = slug_camera(cam)
                registro = processos.get(slug)
                assinatura = assinatura_camera(cam, tempo_segmento)

                if registro:
                    if atualizar_progresso(registro, medir_progresso(registro, caminho_atual), agora_mono, agora):
                        historico.setdefault(slug, {})["ultima_gravacao"] = agora

                    codigo_saida = registro["processo"].poll()
                    if codigo_saida is not None:
                        motivo = f"FFmpeg encerrou (codigo {codigo_saida})"
                        print(f"[!] {motivo}: {nome}", flush=True)
                        registrar_motivo(historico, slug, motivo, registro, agora)
                        registro["log"].close()
                        processos.pop(slug)
                    elif registro.get("assinatura") != assinatura:
                        print(f"[!] Configuracao alterada. Reiniciando captura: {nome}", flush=True)
                        encerrar_ffmpeg(processos.pop(slug))
                    elif endereco_trocado(cam, tabela_arp):
                        motivo = "O endereco da camera passou a ser de outro aparelho"
                        print(f"[!] {motivo}. Procurando a camera: {nome}", flush=True)
                        registrar_motivo(historico, slug, motivo, registro, agora)
                        encerrar_ffmpeg(processos.pop(slug))
                        # Procura ja no proximo ciclo, sem esperar o intervalo de reinicio.
                        ultimo_inicio.pop(slug, None)
                    elif gravacao_travada(registro, agora_mono):
                        if registro.get("ultimo_progresso_mono") is None:
                            motivo = f"Nenhum video gravado em {TOLERANCIA_INICIO} s apos iniciar"
                        else:
                            motivo = f"Gravacao travada: arquivo sem crescer ha {LIMITE_SEM_GRAVACAO} s"
                        print(f"[!] {motivo}. Reiniciando: {nome}", flush=True)
                        registrar_motivo(historico, slug, motivo, registro, agora)
                        encerrar_ffmpeg(processos.pop(slug))

                if slug not in processos:
                    if agora_mono - ultimo_inicio.get(slug, float("-inf")) < INTERVALO_MINIMO_REINICIO:
                        continue
                    info = historico.setdefault(slug, {})
                    if agora_mono - info.get("ultima_conferencia_mono", float("-inf")) >= INTERVALO_CONFERENCIA:
                        # Acabou de parar (enquanto gravava nao passa pela conferencia de cima).
                        cam = conferir_camera(cam, slug, info, agora_mono, agora)
                    elif info.get("nao_encontrada"):
                        cam = None
                    if cam is None:
                        continue
                    ultimo_inicio[slug] = agora_mono
                    print(f"[!] Iniciando captura: {nome} -> {mascarar_rtsp(cam['rtsp_url'])}", flush=True)
                    processos[slug] = iniciar_ffmpeg(cam, caminho_atual, tempo_segmento)
                    medida_inicial = processos[slug]["medida"]
                    if info.get("ultima_gravacao") is None and medida_inicial:
                        try:
                            info["ultima_gravacao"] = os.path.getmtime(medida_inicial[0])
                        except OSError:
                            pass
                else:
                    rotacionar_log(processos[slug]["log_path"])
                    if estado_camera(processos[slug], agora_mono) == "gravando":
                        mac = aprender_mac(cam, slug, tabela_arp, macs_em_uso)
                        if mac:
                            macs_em_uso.add(mac)
                            print(f"[!] MAC da camera registrado: {nome} -> {mac}", flush=True)
        except Exception as e:
            erro_ciclo = str(e)
            if erro_ciclo != ultimo_erro_impresso:
                print(f"Erro no Watchdog: {e}", flush=True)
        if erro_ciclo is None and ultimo_erro_impresso is not None:
            print("[!] Problema resolvido, captura normalizada.", flush=True)
        ultimo_erro_impresso = erro_ciclo

        estado = montar_estado(caminho_atual, lista_cameras, processos, historico, agora_mono, agora, erro_ciclo)
        comparavel = resumo_para_comparar(estado)
        if comparavel != estado_anterior or agora_mono - ultimo_estado_salvo >= INTERVALO_ESTADO:
            try:
                salvar_estado_captura(estado)
                estado_anterior = comparavel
                ultimo_estado_salvo = agora_mono
            except OSError as erro:
                print(f"[!] Nao foi possivel salvar estado da captura: {erro}", flush=True)
        time.sleep(INTERVALO_WATCHDOG)
