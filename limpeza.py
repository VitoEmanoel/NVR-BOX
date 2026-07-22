import os
import shutil
import time

from config import LIMITE_USO_PORCENTAGEM, get_caminho_videos, garantir_diretorios

IDADE_MINIMA_PARA_LIMPEZA = 15 * 60
INTERVALO_VERIFICACAO = 300


def obter_uso_detalhado(pasta_videos):
    try:
        uso = shutil.disk_usage(pasta_videos)
        porcentagem = (uso.used / uso.total) * 100
        usado_gb = uso.used / (1024 ** 3)
        total_gb = uso.total / (1024 ** 3)
        return porcentagem, usado_gb, total_gb
    except OSError:
        return 0, 0, 0


def listar_videos_elegiveis(pasta_videos, agora=None):
    agora = time.time() if agora is None else agora
    arquivos = []

    try:
        for item in os.scandir(pasta_videos):
            if not item.name.endswith('.mp4'):
                continue
            if not item.is_file(follow_symlinks=False):
                continue
            try:
                modificado = item.stat(follow_symlinks=False).st_mtime
            except OSError:
                continue
            if agora - modificado < IDADE_MINIMA_PARA_LIMPEZA:
                continue
            arquivos.append(item.path)
    except OSError as erro:
        print(f"[Erro na Limpeza] Nao foi possivel listar {pasta_videos}: {erro}", flush=True)
        return []

    arquivos.sort(key=os.path.getmtime)
    return arquivos


def apagar_video_mais_antigo(pasta_videos, agora=None):
    try:
        arquivos = listar_videos_elegiveis(pasta_videos, agora=agora)
        if not arquivos:
            print("[Faxina] Nenhum video antigo elegivel para apagar.", flush=True)
            return False
        arquivo_mais_velho = arquivos[0]
        tamanho_mb = os.path.getsize(arquivo_mais_velho) / (1024 ** 2)
        nome_arquivo = os.path.basename(arquivo_mais_velho)
        os.remove(arquivo_mais_velho)
        print(f"[Faxina] Apagado: {nome_arquivo} (Liberou {tamanho_mb:.1f} MB)", flush=True)
        return True
    except Exception as e:
        print(f"[Erro na Limpeza] {e}", flush=True)
        return False


def executar_limpeza(pasta_videos, limite_porcentagem=LIMITE_USO_PORCENTAGEM, obter_uso=obter_uso_detalhado):
    apagados = 0
    ignorado_sem_elegiveis = False

    while True:
        porcentagem, _, _ = obter_uso(pasta_videos)
        if porcentagem <= limite_porcentagem:
            if apagados:
                print(f" Faxina concluida! O uso caiu para {porcentagem:.1f}%", flush=True)
            break

        if not apagar_video_mais_antigo(pasta_videos):
            ignorado_sem_elegiveis = True
            print(
                f" Faxina interrompida. Uso em {porcentagem:.1f}% e nenhum video antigo elegivel.",
                flush=True,
            )
            break
        apagados += 1

    return {
        "apagados": apagados,
        "sem_elegiveis": ignorado_sem_elegiveis,
    }


def ciclo_limpeza():
    pasta_videos = get_caminho_videos()
    garantir_diretorios(pasta_videos)
    porcentagem, usado_gb, total_gb = obter_uso_detalhado(pasta_videos)
    print(f" Status do HD: {usado_gb:.2f} GB usados de {total_gb:.2f} GB ({porcentagem:.1f}%)", flush=True)
    if porcentagem > LIMITE_USO_PORCENTAGEM:
        print(f" ALERTA: Limite de {LIMITE_USO_PORCENTAGEM}% atingido! Iniciando faxina...", flush=True)
        executar_limpeza(pasta_videos)


def main():
    print(" Motor de Limpeza Iniciado! Vigiando o HD...", flush=True)
    while True:
        ciclo_limpeza()
        time.sleep(INTERVALO_VERIFICACAO)


if __name__ == "__main__":
    main()
