import os
import signal
import subprocess
import sys
import time

from config import (
    FFMPEG_LOG_MAX_BYTES,
    RTSP_TRANSPORTE_PADRAO,
    TEMPO_SEGMENTO,
    carregar_cameras,
    get_caminho_videos,
    garantir_diretorios,
    mascarar_rtsp,
    slug_camera,
)


def rotacionar_log(caminho_log):
    try:
        if os.path.getsize(caminho_log) < FFMPEG_LOG_MAX_BYTES:
            return
    except OSError:
        return

    caminho_antigo = f"{caminho_log}.1"
    try:
        if os.path.exists(caminho_antigo):
            os.remove(caminho_antigo)
        os.replace(caminho_log, caminho_antigo)
    except OSError as erro:
        print(f"[!] Nao foi possivel rotacionar log {caminho_log}: {erro}", flush=True)


def iniciar_ffmpeg(cam, caminho_videos):
    url = cam['rtsp_url']
    slug = slug_camera(cam)
    transporte = cam.get('protocolo', RTSP_TRANSPORTE_PADRAO)
    saida = os.path.join(caminho_videos, f"{slug}_%Y-%m-%d_%H-%M-%S.mp4")
    log_file = os.path.join(caminho_videos, f"erro_{slug}.txt")
    rotacionar_log(log_file)
    comando = [
        'ffmpeg',
        '-rtsp_transport', transporte,
        '-analyzeduration', '15000000',
        '-fflags', '+genpts+igndts',
        '-i', url,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-f', 'segment',
        '-segment_time', str(TEMPO_SEGMENTO),
        '-segment_format', 'mp4',
        '-segment_format_options', 'movflags=frag_keyframe+empty_moov+default_base_moof',
        '-strftime', '1',
        '-reset_timestamps', '1',
        saida
    ]
    f_log = open(log_file, "w", encoding="utf-8")
    processo = subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=f_log)
    return {"processo": processo, "log": f_log}

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

if __name__ == '__main__':
    processos = {}

    def encerrar_todos(_signum=None, _frame=None):
        for slug, registro in list(processos.items()):
            print(f"[!] Encerrando captura: {slug}", flush=True)
            encerrar_ffmpeg(registro)
            processos.pop(slug, None)
        sys.exit(0)

    signal.signal(signal.SIGTERM, encerrar_todos)
    signal.signal(signal.SIGINT, encerrar_todos)

    caminho_atual = None
    print("--- NVRBox: Motor Blindado e Vigiado ---", flush=True)

    while True:
        try:
            novo_caminho = get_caminho_videos()
            garantir_diretorios(novo_caminho)
            if caminho_atual != novo_caminho:
                if caminho_atual is not None:
                    print(f"[!] Armazenamento alterado: {novo_caminho}", flush=True)
                    for slug, registro in list(processos.items()):
                        print(f"[!] Reiniciando captura em novo armazenamento: {slug}", flush=True)
                        encerrar_ffmpeg(registro)
                        processos.pop(slug, None)
                caminho_atual = novo_caminho

            lista_cameras = carregar_cameras()
            slugs_ativos = {slug_camera(cam) for cam in lista_cameras}

            for slug in list(processos.keys()):
                if slug not in slugs_ativos:
                    print(f"[!] Encerrando captura removida: {slug}", flush=True)
                    encerrar_ffmpeg(processos.pop(slug))

            for cam in lista_cameras:
                nome = cam['nome']
                slug = slug_camera(cam)
                registro = processos.get(slug)
                if registro and registro["processo"].poll() is not None:
                    registro["log"].close()
                    processos.pop(slug)

                if slug not in processos:
                    print(f"[!] Iniciando captura: {nome} -> {mascarar_rtsp(cam['rtsp_url'])}", flush=True)
                    processos[slug] = iniciar_ffmpeg(cam, caminho_atual)
        except Exception as e:
            print(f"Erro no Watchdog: {e}")
        time.sleep(30)
