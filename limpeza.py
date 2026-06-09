import os
import time
import shutil

def encontrar_armazenamento():
    DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__))
    caminho_final = os.path.join(DIRETORIO_BASE, 'gravacoes')
    raizes_de_montagem = ['/mnt', '/media', '/storage']

    for raiz in raizes_de_montagem:
        if not os.path.exists(raiz): continue
        for item in os.listdir(raiz):
            caminho_teste = os.path.join(raiz, item)
            if os.path.isdir(caminho_teste) and os.access(caminho_teste, os.W_OK):
                if item not in ['self', 'runtime']:
                    return os.path.join(caminho_teste, 'gravacoes')
    return caminho_final

PASTA_VIDEOS = encontrar_armazenamento()
os.makedirs(PASTA_VIDEOS, exist_ok=True)

LIMITE_USO_PORCENTAGEM = 90

def obter_uso_detalhado():
    try:
        uso = shutil.disk_usage(PASTA_VIDEOS)
        porcentagem = (uso.used / uso.total) * 100
        usado_gb = uso.used / (1024 ** 3)
        total_gb = uso.total / (1024 ** 3)
        return porcentagem, usado_gb, total_gb
    except:
        return 0, 0, 0

def apagar_video_mais_antigo():
    try:
        arquivos = [os.path.join(PASTA_VIDEOS, f) for f in os.listdir(PASTA_VIDEOS) if f.endswith('.mp4')]
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
    porcentagem, usado_gb, total_gb = obter_uso_detalhado()
    print(f" Status do HD: {usado_gb:.2f} GB usados de {total_gb:.2f} GB ({porcentagem:.1f}%)", flush=True)
    if porcentagem > LIMITE_USO_PORCENTAGEM:
        print(f" ALERTA: Limite de {LIMITE_USO_PORCENTAGEM}% atingido! Iniciando faxina...", flush=True)
        enquanto_tiver_espaco = True
        while enquanto_tiver_espaco:
            pct, _, _ = obter_uso_detalhado()
            if pct <= LIMITE_USO_PORCENTAGEM:
                print(f" Faxina concluĆ­da! O uso caiu para {pct:.1f}%", flush=True)
                break
            enquanto_tiver_espaco = apagar_video_mais_antigo()
    time.sleep(300)