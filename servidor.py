
from flask import Flask, render_template, send_from_directory, request, redirect, url_for, Response
import os
import json
import subprocess
import shutil
import socket

app = Flask(__name__)

def encontrar_armazenamento():
    DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__))
    caminho_final = os.path.join(DIRETORIO_BASE, 'gravacoes')
    return caminho_final

CAMINHO_VIDEOS = encontrar_armazenamento()
DIRETORIO_PROJETO = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CAMERAS = os.path.join(DIRETORIO_PROJETO, 'cameras.json')

os.makedirs(CAMINHO_VIDEOS, exist_ok=True)
print(f"Sistema rodando! Gravando em: {CAMINHO_VIDEOS}")

def get_disk_info():
    """Calcula o uso do HD externo de forma leve """
    try:
        total, usado, livre = shutil.disk_usage(CAMINHO_VIDEOS)
        return {
            "total": f"{total / (1024**3):.1f} GB",
            "usado": f"{usado / (1024**3):.1f} GB",
            "porcentagem": int((usado / total) * 100)
        }
    except:
        return {"total": "0", "usado": "0", "porcentagem": 0}

def verificar_online(url):
    """Tenta conexÃ£o rÃ¡pida com a porta RTSP (554) para checar se a cÃ¢mera estÃ¡ viva"""
    try:
        ip = url.split('@')[1].split(':')[0]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((ip, 554))
        s.close()
        return True
    except:
        return False

def contar_arquivos(slug_camera):
    try:
        arquivos = [f for f in os.listdir(CAMINHO_VIDEOS) if f.startswith(slug_camera) and f.endswith('.mp4')]
        return len(arquivos)
    except:
        return 0

def carregar_cameras():
    if not os.path.exists(ARQUIVO_CAMERAS): return []
    with open(ARQUIVO_CAMERAS, 'r') as f: return json.load(f)

def salvar_cameras(cameras):
    with open(ARQUIVO_CAMERAS, 'w') as f: json.dump(cameras, f, indent=4)

def gerar_frames(rtsp_url):
    os.system("pkill -9 -f image2pipe")
    comando = [
        'ffmpeg', '-rtsp_transport', 'udp', '-i', rtsp_url,
        '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q', '5',
        '-vf', 'scale=640:-1', '-'
    ]
    processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    buffer = b""
    try:
        while True:
            chunk = processo.stdout.read(8192)
            if not chunk: break
            buffer += chunk
            if len(buffer) > 1024 * 1024: buffer = b""
            a = buffer.find(b'\xff\xd8')
            if a != -1:
                b = buffer.find(b'\xff\xd9', a)
                if b != -1:
                    jpg = buffer[a:b+2]
                    buffer = buffer[b+2:]
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(jpg)).encode() + b'\r\n\r\n' + jpg + b'\r\n')
    except: pass
    finally:
        processo.kill()
        processo.wait()


@app.route('/')
def index():
    cameras = carregar_cameras()
    total_cams = len(cameras)
    online_count = 0
    for camera in cameras:
        camera['online'] = verificar_online(camera['rtsp_url'])
        if camera['online']:
            online_count += 1
        slug_fixo = camera.get('slug', camera['nome'].replace(" ", "_"))
        try:
            videos = [f for f in os.listdir(CAMINHO_VIDEOS) if f.startswith(slug_fixo) and f.endswith('.mp4')]
            camera['qtd_videos'] = len(videos)
        except Exception:
            camera['qtd_videos'] = 0

    try:
        uso = shutil.disk_usage(CAMINHO_VIDEOS)
        disco = {
            'usado': f"{(uso.used / (1024**3)):.1f} GB",
            'total': f"{(uso.total / (1024**3)):.1f} GB",
            'livre': f"{(uso.free / (1024**3)):.1f} GB",
            'porcentagem': int((uso.used / uso.total) * 100)
        }
    except Exception:
        disco = {'usado': '0 GB', 'total': '0 GB', 'livre': '0 GB', 'porcentagem': 0}

    return render_template('index.html', cameras=cameras, total_cams=total_cams, online_count=online_count, disco=disco)

@app.route('/camera/<nome>')
def detalhe_camera(nome):
    cameras = carregar_cameras()
    camera = next((c for c in cameras if c['nome'].lower() == nome.lower()), None)
    if not camera:
        return redirect(url_for('index'))

    data_filtro = request.args.get('data', '')

    esta_viva = verificar_online(camera['rtsp_url'])
    camera['online'] = esta_viva 
    slug_fixo = camera.get('slug', camera['nome'].replace(" ", "_"))
    try:
        ficheiros = [f for f in os.listdir(CAMINHO_VIDEOS) if f.startswith(slug_fixo) and f.endswith('.mp4')]
        if data_filtro:
            ficheiros = [f for f in ficheiros if data_filtro in f]
        ficheiros.sort(reverse=True)
    except:
        ficheiros = []

    return render_template('detalhe.html', camera=camera, videos=ficheiros, data_filtro=data_filtro)

@app.route('/live/<nome>')
def live_stream(nome):
    cameras = carregar_cameras()
    camera = next((c for c in cameras if c['nome'].lower() == nome.lower()), None)
    if camera:
        return Response(gerar_frames(camera['rtsp_url']), mimetype='multipart/x-mixed-replace; boundary=frame')
    return "CÃ¢mara nÃ£o encontrada", 404

@app.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(CAMINHO_VIDEOS, filename)

@app.route('/adicionar_camera', methods=['POST'])
def adicionar_camera():
    nome = request.form.get('nome')
    rtsp_url = request.form.get('rtsp_url')
    mac = request.form.get('mac')

    cameras = carregar_cameras()
    nova_camera = {
        "nome": nome,
        "rtsp_url": rtsp_url,
        "mac": mac,
        "slug": nome.lower().replace(" ", "_")
    }
    cameras.append(nova_camera)
    salvar_cameras(cameras)
    return redirect('/')

@app.route('/apagar_camera/<nome>')
def apagar_camera(nome):
    cams = carregar_cameras()
    cams = [c for c in cams if c['nome'].lower() != nome.lower()]
    salvar_cameras(cams)
    os.system("systemctl restart captura-camera.service > /dev/null 2>&1")
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_video(filename):
    return send_from_directory(CAMINHO_VIDEOS, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
