import json
import os
import subprocess
import time

def carregar_cameras():
    if not os.path.exists('cameras.json'):
        return []
    with open('cameras.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def iniciar_ffmpeg(cam):
    url = cam['rtsp_url']
    slug = cam.get('slug', cam['nome'].lower().replace(" ", "_"))
    saida = os.path.join("gravacoes", f"{slug}_%Y-%m-%d_%H-%M-%S.mp4")
    log_file = os.path.join("gravacoes", f"erro_{slug}.txt") 
    comando = [
        'ffmpeg',
        '-rtsp_transport', 'udp',
        '-analyzeduration', '15000000',
        '-fflags', '+genpts+igndts',
        '-i', url,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-f', 'segment',
        '-segment_time', '600',
        '-strftime', '1',
        '-reset_timestamps', '1',
        saida
    ]
    f_log = open(log_file, "w")
    return subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=f_log)

if __name__ == '__main__':
    processos = {}
    print("--- NVRBox: Motor Blindado e Vigiado ---", flush=True)

    while True:
        try:
            lista_cameras = carregar_cameras()
            for cam in lista_cameras:
                nome = cam['nome']
                if nome not in processos or processos[nome].poll() is not None:
                    print(f"[!] Iniciando captura: {nome} -> {cam['rtsp_url']}", flush=True)
                    processos[nome] = iniciar_ffmpeg(cam)
        except Exception as e:
            print(f"Erro no Watchdog: {e}")
        time.sleep(30)