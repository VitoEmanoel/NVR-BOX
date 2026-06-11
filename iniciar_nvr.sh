#!/bin/bash

set -e

DIRETORIO_ATUAL="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$DIRETORIO_ATUAL/.run"

mkdir -p "$RUN_DIR"
cd "$DIRETORIO_ATUAL"

parar_processo() {
    local nome="$1"
    local pid_file="$RUN_DIR/$nome.pid"

    if [ ! -f "$pid_file" ]; then
        return
    fi

    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
        echo "Parando $nome anterior (PID $pid)..."
        kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
}

encerrar_todos() {
    parar_processo servidor
    parar_processo captura
    parar_processo limpeza
}

trap encerrar_todos EXIT INT TERM

echo "Limpando instancias anteriores do NVRBox..."
encerrar_todos

echo "Iniciando NVRBox no diretorio: $DIRETORIO_ATUAL"

echo "-> [1/3] Ativando script de Limpeza Automatica..."
python3 limpeza.py &
echo "$!" > "$RUN_DIR/limpeza.pid"

echo "-> [2/3] Ativando motor de Captura FFmpeg..."
python3 captura.py &
echo "$!" > "$RUN_DIR/captura.pid"

echo "-> [3/3] Abrindo Painel Web... Sistema ONLINE!"
python3 servidor.py &
echo "$!" > "$RUN_DIR/servidor.pid"

wait "$(cat "$RUN_DIR/servidor.pid")"
