"""Descoberta de cameras na rede local pelo MAC.

Quando falta energia ou o roteador reinicia, as cameras podem receber IPs
diferentes (inclusive trocados entre si). O MAC nao muda, entao o sistema usa
a tabela ARP do Linux para conferir se o IP salvo ainda e da mesma camera e,
se nao for, procura o IP novo varrendo a rede local.
"""

import ipaddress
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

ARQUIVO_ARP = "/proc/net/arp"
ARP_FLAG_COMPLETA = 0x2
MAC_REGEX = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
MACS_INVALIDOS = {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}
PORTA_RTSP_PADRAO = 554


def normalizar_mac(mac):
    mac = (mac or "").strip().lower().replace("-", ":")
    if not MAC_REGEX.match(mac) or mac in MACS_INVALIDOS:
        return None
    return mac


def _ler_proc_arp():
    tabela = {}
    with open(ARQUIVO_ARP, "r", encoding="utf-8") as arquivo:
        linhas = arquivo.readlines()[1:]
    for linha in linhas:
        partes = linha.split()
        if len(partes) < 4:
            continue
        try:
            completa = int(partes[2], 16) & ARP_FLAG_COMPLETA
        except ValueError:
            continue
        mac = normalizar_mac(partes[3])
        if completa and mac:
            tabela[partes[0]] = mac
    return tabela


def _ler_ip_neigh():
    saida = subprocess.run(
        ["ip", "-4", "neigh", "show"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=5,
        check=True,
    ).stdout
    tabela = {}
    for linha in saida.splitlines():
        partes = linha.split()
        if "lladdr" not in partes or partes[-1] in {"FAILED", "INCOMPLETE"}:
            continue
        mac = normalizar_mac(partes[partes.index("lladdr") + 1])
        if mac:
            tabela[partes[0]] = mac
    return tabela


def ler_tabela_arp():
    """Retorna {ip: mac} das vizinhancas conhecidas.

    Retorna None quando a tabela nao pode ser lida (ex.: Android 10+ bloqueia
    /proc/net/arp). Nesse caso o sistema nao deve bloquear a gravacao.
    """
    try:
        return _ler_proc_arp()
    except OSError:
        pass
    try:
        return _ler_ip_neigh()
    except (OSError, subprocess.SubprocessError):
        return None


def tocar_host(ip, porta=PORTA_RTSP_PADRAO, timeout=0.5):
    """Tenta conectar na porta RTSP. Mesmo recusada, a tentativa preenche o ARP."""
    try:
        with socket.create_connection((ip, porta), timeout=timeout):
            return True
    except OSError:
        return False


def varrer_rede(ip_referencia, porta=PORTA_RTSP_PADRAO, timeout=1.5, workers=64, espera_final=1.0):
    """Toca todos os IPs da /24 do IP de referencia e retorna a tabela ARP atualizada.

    Redes domesticas quase sempre sao /24. Cameras Wi-Fi genericas em economia
    de energia demoram a responder ARP (o Linux reenvia a pergunta a cada 1 s):
    com 0,4 s de timeout uma camera real ficou de fora. Por isso o timeout e de
    1,5 s e, no fim, ha uma espera curta para respostas atrasadas, que ainda
    completam a tabela. Com 64 conexoes em paralelo leva cerca de 7 s e so roda
    quando uma camera some.
    """
    try:
        rede = ipaddress.ip_network(f"{ip_referencia}/24", strict=False)
    except ValueError:
        return ler_tabela_arp()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(lambda ip: tocar_host(str(ip), porta, timeout), rede.hosts()))
    time.sleep(espera_final)
    return ler_tabela_arp()


def mac_do_ip(ip, porta=PORTA_RTSP_PADRAO, ler_arp=ler_tabela_arp, tocar=tocar_host):
    """MAC do aparelho que responde nesse IP agora, ou None."""
    tabela = ler_arp()
    if tabela is None:
        return None
    if ip not in tabela:
        tocar(ip, porta)
        tabela = ler_arp() or {}
    return tabela.get(ip)


def localizar_camera(mac, ip_atual, porta=PORTA_RTSP_PADRAO,
                     ler_arp=ler_tabela_arp, tocar=tocar_host, varrer=varrer_rede):
    """Descobre em que IP esta a camera com esse MAC.

    Retorna (ip, situacao):
    - (ip_atual, "confirmada"): o IP salvo continua sendo da camera;
    - (ip_novo, "mudou"): a camera foi encontrada em outro IP;
    - (None, "nao_encontrada"): a camera nao respondeu na rede;
    - (ip_atual, "sem_verificacao"): sem MAC salvo ou sem acesso a tabela ARP.
    """
    mac = normalizar_mac(mac)
    tabela = ler_arp()
    if not mac or tabela is None:
        return ip_atual, "sem_verificacao"

    if ip_atual not in tabela:
        tocar(ip_atual, porta)
        tabela = ler_arp() or {}
    if tabela.get(ip_atual) == mac:
        return ip_atual, "confirmada"

    for ip, mac_encontrado in tabela.items():
        if mac_encontrado == mac:
            return ip, "mudou"

    tabela = varrer(ip_atual, porta) or {}
    for ip, mac_encontrado in tabela.items():
        if mac_encontrado == mac:
            return ip, ("confirmada" if ip == ip_atual else "mudou")
    return None, "nao_encontrada"
