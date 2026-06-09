#!/bin/bash

echo "Limpando instÃ¢ncias anteriores para evitar conflitos..."
pkill -f servidor.py
pkill -f captura.py
pkill -f limpeza.py
pkill -f ffmpeg

DIRETORIO_ATUAL="$(cd "$(dirname "$0")" && pwd)"
cd "$DIRETORIO_ATUAL"

echo "Iniciando NVRBox no diretÃ³rio: $DIRETORIO_ATUAL"

echo "-> [1/3] Ativando script de Limpeza AutomÃ¡tica..."
python3 ../limpeza.py & 

echo "-> [2/3] Ativando motor de Captura FFmpeg..."
python3 captura.py &

echo "-> [3/3] Abrindo Painel Web... Sistema ONLINE!"
python3 servidor.py