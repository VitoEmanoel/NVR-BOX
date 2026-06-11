import os
import time
import shutil

from config import LIMITE_USO_PORCENTAGEM, get_caminho_videos, garantir_diretorios

IDADE_MINIMA_PARA_LIMPEZA = 15 * 60


def obter_uso_detalhado(pasta_videos):
    try:
        uso = shutil.disk_usage(pasta_videos)
        porcentagem = (uso.used / uso.total) * 100
        usado_gb = uso.used / (1024 ** 3)
        total_gb = uso.total / (1024 ** 3)
        return porcentagem, usado_gb, total_gb
    except OSError:
        return 0, 0, 0

def apagar_video_mais_antigo(pasta_videos):
    try:
        agora = time.time()
        arquivos = []
        for nome in os.listdir(pasta_videos):
            caminho = os.path.join(pasta_videos, nome)
            if not nome.endswith('.mp4') or not os.path.isfile(caminho):
                continue
            if agora - os.path.getmtime(caminho) < IDADE_MINIMA_PARA_LIMPEZA:
                continue
            arquivos.append(caminho)
        if not arquivos:
            return False
        arquivo_mais_velho = min(arquivos, key=os.path.getmtime)
        tamanho_mb = os.path.getsize(arquivo_mais_velho) / (1024 ** 2)
        nome_arquivo = os.path.basename(arquivo_mais_velho)
        os.remove(arquivo_mais_velho)
        print(f"[Faxina] Apagado: {nome_arquivo} (Liberou {tamanho_mb:.1f} MB)", flush=True)
        return True
    except Exception as e:
        print(f"[Erro na Limpeza] {e}", flush=True)
        return False

print(" Motor de Limpeza Iniciado! Vigiando o HD...", flush=True)

while True:
    pasta_videos = get_caminho_videos()
    garantir_diretorios(pasta_videos)
    porcentagem, usado_gb, total_gb = obter_uso_detalhado(pasta_videos)
    print(f" Status do HD: {usado_gb:.2f} GB usados de {total_gb:.2f} GB ({porcentagem:.1f}%)", flush=True)
    if porcentagem > LIMITE_USO_PORCENTAGEM:
        print(f" ALERTA: Limite de {LIMITE_USO_PORCENTAGEM}% atingido! Iniciando faxina...", flush=True)
        enquanto_tiver_espaco = True
        while enquanto_tiver_espaco:
            pct, _, _ = obter_uso_detalhado(pasta_videos)
            if pct <= LIMITE_USO_PORCENTAGEM:
                print(f" Faxina concluida! O uso caiu para {pct:.1f}%", flush=True)
                break
            enquanto_tiver_espaco = apagar_video_mais_antigo(pasta_videos)
    time.sleep(300)
