
from flask import Flask, jsonify, render_template, send_file, request, redirect, url_for, Response
import os
import re
import subprocess
import shutil
import socket
import time
from secrets import compare_digest
from urllib.parse import unquote, urlparse

from config import (
    AUTH_ATIVA,
    AUTH_SENHA,
    AUTH_USUARIO,
    RTSP_PERFIS,
    RTSP_TRANSPORTE_PADRAO,
    TESTAR_RTSP_CADASTRO,
    TEMPOS_SEGMENTO_PERMITIDOS,
    TIMEOUT_TESTE_RTSP,
    carregar_cameras,
    construir_rtsp_url,
    definir_armazenamento,
    definir_tempo_segmento,
    get_caminho_videos,
    get_tempo_segmento,
    garantir_diretorios,
    gerar_slug,
    listar_armazenamentos,
    mascarar_rtsp,
    salvar_cameras,
    slug_camera,
)

app = Flask(__name__)

garantir_diretorios()
print(f"Sistema rodando! Gravando em: {get_caminho_videos()}")

MAC_REGEX = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")
DATA_VIDEO_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.mp4$")
VIDEO_INFO_CACHE = {}
IDADE_MINIMA_EXCLUSAO_VIDEO = 60


@app.before_request
def exigir_autenticacao():
    if not AUTH_ATIVA or request.endpoint == "static":
        return None

    auth = request.authorization
    usuario_ok = auth and compare_digest(auth.username or "", AUTH_USUARIO)
    senha_ok = auth and compare_digest(auth.password or "", AUTH_SENHA)
    if usuario_ok and senha_ok:
        return None

    return Response(
        "Autenticacao necessaria.",
        401,
        {"WWW-Authenticate": 'Basic realm="NVRBox"'},
    )


def buscar_camera_por_slug(cameras, slug):
    slug_normalizado = gerar_slug(slug)
    return next((camera for camera in cameras if slug_camera(camera) == slug_normalizado), None)


def obter_caminho_manual_camera(camera):
    parsed = urlparse(camera.get("rtsp_url", ""))
    caminho = parsed.path or ""
    if parsed.query:
        caminho = f"{caminho}?{parsed.query}"
    return camera.get("caminho_manual") or caminho


def dados_edicao_camera(camera):
    parsed = urlparse(camera.get("rtsp_url", ""))
    return {
        "nome": camera.get("nome", ""),
        "ip": camera.get("ip") or parsed.hostname or "",
        "usuario": camera.get("usuario") or unquote(parsed.username or "admin"),
        "porta": str(camera.get("porta") or parsed.port or 554),
        "mac": camera.get("mac", ""),
        "perfil": camera.get("perfil", "onvif1"),
        "protocolo": camera.get("protocolo", RTSP_TRANSPORTE_PADRAO),
        "caminho_manual": obter_caminho_manual_camera(camera) if camera.get("perfil") == "manual" else "",
    }

def get_disk_info(caminho_videos):
    """Calcula o uso do HD externo de forma leve """
    try:
        total, usado, livre = shutil.disk_usage(caminho_videos)
        return {
            "total": f"{total / (1024**3):.1f} GB",
            "usado": f"{usado / (1024**3):.1f} GB",
            "porcentagem": int((usado / total) * 100)
        }
    except OSError:
        return {"total": "0", "usado": "0", "porcentagem": 0}

def verificar_online(url):
    """Tenta conexao rapida com a porta RTSP para checar se a camera esta viva."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        porta = parsed.port or 554
        if not host:
            return False
        with socket.create_connection((host, porta), timeout=1.0):
            pass
        return True
    except OSError:
        return False

def contar_arquivos(slug_camera):
    try:
        caminho_videos = get_caminho_videos()
        arquivos = [
            f for f in os.listdir(caminho_videos)
            if nome_video_pertence_camera(f, slug_camera)
        ]
        return len(arquivos)
    except OSError:
        return 0


def formatar_tamanho(bytes_arquivo):
    if bytes_arquivo >= 1024 ** 3:
        return f"{bytes_arquivo / (1024 ** 3):.1f} GB"
    return f"{bytes_arquivo / (1024 ** 2):.1f} MB"


def formatar_duracao(segundos):
    segundos = int(float(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    return f"{minutos:02d}:{segundos:02d}"


def obter_info_video(caminho_videos, nome_arquivo):
    caminho = os.path.join(caminho_videos, nome_arquivo)
    try:
        tamanho = os.path.getsize(caminho)
        modificado = os.path.getmtime(caminho)
    except OSError:
        tamanho = 0
        modificado = 0

    cache_key = (caminho, tamanho, modificado)
    info_cache = VIDEO_INFO_CACHE.get(cache_key)
    if info_cache:
        return dict(info_cache)

    info = {
        "nome": nome_arquivo,
        "tamanho": formatar_tamanho(tamanho),
        "duracao": "",
        "reproduzivel": False,
    }

    try:
        resultado = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1",
                caminho,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=4,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return info

    duracao = resultado.stdout.strip()
    if resultado.returncode == 0 and duracao and duracao != "N/A":
        try:
            info["duracao"] = formatar_duracao(duracao)
            info["reproduzivel"] = True
        except ValueError:
            pass

    if len(VIDEO_INFO_CACHE) > 1000:
        VIDEO_INFO_CACHE.clear()
    VIDEO_INFO_CACHE[cache_key] = dict(info)
    return info


def nome_video_pertence_camera(nome_arquivo, slug_fixo):
    return extrair_data_video(nome_arquivo, slug_fixo) is not None


def extrair_data_video(nome_arquivo, slug_fixo):
    prefixo = f"{slug_fixo}_"
    if not nome_arquivo.startswith(prefixo):
        return None

    match = DATA_VIDEO_REGEX.match(nome_arquivo[len(prefixo):])
    if not match:
        return None
    return match.group(1)


def listar_videos_camera(caminho_videos, slug_fixo, data_filtro=""):
    try:
        nomes = [
            f for f in os.listdir(caminho_videos)
            if nome_video_pertence_camera(f, slug_fixo)
        ]
    except OSError:
        return []

    if data_filtro:
        nomes = [f for f in nomes if extrair_data_video(f, slug_fixo) == data_filtro]

    nomes.sort(reverse=True)
    return [obter_info_video(caminho_videos, nome) for nome in nomes]


def listar_dias_gravacoes_camera(caminho_videos, slug_fixo):
    dias = {}
    try:
        nomes = os.listdir(caminho_videos)
    except OSError:
        return []

    for nome in nomes:
        if not nome_video_pertence_camera(nome, slug_fixo):
            continue
        data_video = extrair_data_video(nome, slug_fixo)
        if not data_video:
            continue
        dias[data_video] = dias.get(data_video, 0) + 1

    return [
        {"data": data, "total": total}
        for data, total in sorted(dias.items(), reverse=True)
    ]


def obter_caminho_video_seguro(filename):
    if not filename.endswith(".mp4"):
        return None
    if os.path.basename(filename) != filename:
        return None

    caminho_videos = os.path.abspath(get_caminho_videos())
    caminho_video = os.path.abspath(os.path.join(caminho_videos, filename))
    try:
        dentro_da_pasta = os.path.commonpath([caminho_videos, caminho_video]) == caminho_videos
    except ValueError:
        dentro_da_pasta = False

    if not dentro_da_pasta or not os.path.isfile(caminho_video):
        return None

    return caminho_video


def video_pode_ser_excluido(caminho_video):
    try:
        return time.time() - os.path.getmtime(caminho_video) >= IDADE_MINIMA_EXCLUSAO_VIDEO
    except OSError:
        return False


def limpar_cache_video(caminho_video):
    for chave in list(VIDEO_INFO_CACHE):
        if chave[0] == caminho_video:
            VIDEO_INFO_CACHE.pop(chave, None)


def apagar_video_camera(slug_fixo, nome_arquivo):
    if not nome_video_pertence_camera(nome_arquivo, slug_fixo):
        return False, "Video nao pertence a esta camera."

    caminho_video = obter_caminho_video_seguro(nome_arquivo)
    if not caminho_video:
        return False, "Video nao encontrado."
    if not video_pode_ser_excluido(caminho_video):
        return False, "Video muito recente ou ainda em gravacao."

    try:
        os.remove(caminho_video)
        limpar_cache_video(caminho_video)
        return True, None
    except OSError:
        return False, "Nao foi possivel apagar o video."


def apagar_todos_videos_camera(slug_fixo):
    caminho_videos = get_caminho_videos()
    apagados = 0
    ignorados = 0
    try:
        nomes = os.listdir(caminho_videos)
    except OSError:
        return 0, 0

    for nome in nomes:
        if not nome_video_pertence_camera(nome, slug_fixo):
            continue
        caminho_video = obter_caminho_video_seguro(nome)
        if not caminho_video:
            continue
        if not video_pode_ser_excluido(caminho_video):
            ignorados += 1
            continue
        try:
            os.remove(caminho_video)
            limpar_cache_video(caminho_video)
            apagados += 1
        except OSError:
            ignorados += 1

    return apagados, ignorados


def gerar_video_compativel(caminho_video):
    comando = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-fflags", "+genpts",
        "-i", caminho_video,
        "-map", "0:v:0",
        "-an",
        "-vf", "scale=1280:-2",
        "-c:v", "libvpx",
        "-deadline", "realtime",
        "-cpu-used", "6",
        "-b:v", "1400k",
        "-f", "webm",
        "pipe:1",
    ]

    processo = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        while True:
            chunk = processo.stdout.read(64 * 1024)
            if not chunk:
                break
            yield chunk
    except (BrokenPipeError, GeneratorExit, OSError):
        pass
    finally:
        if processo.stdout:
            processo.stdout.close()
        if processo.poll() is None:
            processo.terminate()
            try:
                processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait()


def testar_rtsp_stream(url, transporte):
    comando = [
        "ffprobe",
        "-v", "error",
        "-rtsp_transport", transporte,
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        url,
    ]
    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=TIMEOUT_TESTE_RTSP,
            check=False,
        )
    except FileNotFoundError:
        return False, "ffprobe nao encontrado. Instale o FFmpeg para testar a camera."
    except subprocess.TimeoutExpired:
        return False, "Nao foi possivel confirmar o RTSP dentro do tempo limite."

    if resultado.returncode != 0 or "video" not in resultado.stdout:
        return False, "Nao foi possivel abrir video nesse RTSP. Confira IP, senha, perfil e protocolo."

    return True, None

def validar_nova_camera(dados, cameras):
    ip = (dados.get("ip") or "").strip()
    senha = (dados.get("senha") or "").strip()
    usuario = (dados.get("usuario") or "admin").strip()
    porta = (dados.get("porta") or "554").strip()
    perfil = (dados.get("perfil") or "onvif1").strip()
    caminho_manual = (dados.get("caminho_manual") or "").strip()
    nome = (dados.get("nome") or f"Camera {ip}").strip()
    mac = (dados.get("mac") or "").strip()
    protocolo = (dados.get("protocolo") or RTSP_TRANSPORTE_PADRAO).strip().lower()

    if not nome:
        return None, "Nome da camera e obrigatorio."
    if not ip:
        return None, "IP da camera e obrigatorio."
    if not senha:
        return None, "Senha da camera e obrigatoria."
    if not usuario:
        return None, "Usuario da camera e obrigatorio."
    if not porta.isdigit() or not 1 <= int(porta) <= 65535:
        return None, "Porta RTSP invalida."
    if perfil != "manual" and perfil not in RTSP_PERFIS:
        return None, "Perfil RTSP invalido."
    if perfil == "manual" and not caminho_manual:
        return None, "Caminho RTSP manual e obrigatorio."
    if protocolo not in {"udp", "tcp"}:
        return None, "Protocolo invalido."
    if mac and not MAC_REGEX.match(mac):
        return None, "MAC invalido. Use o formato aa:bb:cc:dd:ee:ff."

    rtsp_url = construir_rtsp_url(ip, senha, usuario, perfil, porta, caminho_manual)

    parsed = urlparse(rtsp_url)
    if parsed.scheme != "rtsp" or not parsed.hostname:
        return None, "URL RTSP invalida."

    slug = gerar_slug(nome)
    for camera in cameras:
        if camera.get("nome", "").strip().lower() == nome.lower():
            return None, "Ja existe uma camera com esse nome."
        if slug_camera(camera) == slug:
            return None, "Ja existe uma camera com esse slug."

    if TESTAR_RTSP_CADASTRO:
        ok, erro = testar_rtsp_stream(rtsp_url, protocolo)
        if not ok:
            return None, erro

    return {
        "nome": nome,
        "rtsp_url": rtsp_url,
        "mac": mac.lower(),
        "slug": slug,
        "protocolo": protocolo,
        "usuario": usuario,
        "ip": ip,
        "porta": int(porta),
        "perfil": perfil,
    }, None


def validar_edicao_camera(dados, cameras, slug_atual, camera_atual):
    parsed_atual = urlparse(camera_atual.get("rtsp_url", ""))
    senha_atual = unquote(parsed_atual.password or "")

    ip = (dados.get("ip") or "").strip()
    senha = (dados.get("senha") or "").strip() or senha_atual
    usuario = (dados.get("usuario") or camera_atual.get("usuario") or "admin").strip()
    porta = (dados.get("porta") or str(camera_atual.get("porta") or "554")).strip()
    perfil = (dados.get("perfil") or camera_atual.get("perfil") or "onvif1").strip()
    caminho_manual = (dados.get("caminho_manual") or "").strip()
    nome = (dados.get("nome") or camera_atual.get("nome") or f"Camera {ip}").strip()
    mac = (dados.get("mac") or "").strip()
    protocolo = (dados.get("protocolo") or camera_atual.get("protocolo") or RTSP_TRANSPORTE_PADRAO).strip().lower()

    if perfil == "manual" and not caminho_manual:
        caminho_manual = obter_caminho_manual_camera(camera_atual)

    if not nome:
        return None, "Nome da camera e obrigatorio."
    if not ip:
        return None, "IP da camera e obrigatorio."
    if not senha:
        return None, "Senha da camera e obrigatoria."
    if not usuario:
        return None, "Usuario da camera e obrigatorio."
    if not porta.isdigit() or not 1 <= int(porta) <= 65535:
        return None, "Porta RTSP invalida."
    if perfil != "manual" and perfil not in RTSP_PERFIS:
        return None, "Perfil RTSP invalido."
    if perfil == "manual" and not caminho_manual:
        return None, "Caminho RTSP manual e obrigatorio."
    if protocolo not in {"udp", "tcp"}:
        return None, "Protocolo invalido."
    if mac and not MAC_REGEX.match(mac):
        return None, "MAC invalido. Use o formato aa:bb:cc:dd:ee:ff."

    for camera in cameras:
        if slug_camera(camera) == slug_atual:
            continue
        if camera.get("nome", "").strip().lower() == nome.lower():
            return None, "Ja existe uma camera com esse nome."

    rtsp_url = construir_rtsp_url(ip, senha, usuario, perfil, porta, caminho_manual)
    parsed = urlparse(rtsp_url)
    if parsed.scheme != "rtsp" or not parsed.hostname:
        return None, "URL RTSP invalida."

    rtsp_alterado = rtsp_url != camera_atual.get("rtsp_url") or protocolo != camera_atual.get("protocolo")
    if TESTAR_RTSP_CADASTRO and rtsp_alterado:
        ok, erro = testar_rtsp_stream(rtsp_url, protocolo)
        if not ok:
            return None, erro

    camera_atualizada = dict(camera_atual)
    camera_atualizada.update({
        "nome": nome,
        "rtsp_url": rtsp_url,
        "mac": mac.lower(),
        "slug": slug_atual,
        "protocolo": protocolo,
        "usuario": usuario,
        "ip": ip,
        "porta": int(porta),
        "perfil": perfil,
    })
    if perfil == "manual":
        camera_atualizada["caminho_manual"] = caminho_manual
    else:
        camera_atualizada.pop("caminho_manual", None)

    return camera_atualizada, None

def gerar_frames(camera):
    rtsp_url = camera['rtsp_url']
    transporte = camera.get('protocolo', RTSP_TRANSPORTE_PADRAO)
    comando = [
        'ffmpeg', '-rtsp_transport', transporte, '-i', rtsp_url,
        '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q', '5',
        '-vf', 'scale=640:-1', '-'
    ]
    try:
        processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return

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
    except (BrokenPipeError, OSError):
        pass
    finally:
        if processo.poll() is None:
            processo.kill()
        processo.wait()


def montar_contexto_index():
    caminho_videos = get_caminho_videos()
    garantir_diretorios(caminho_videos)
    cameras = carregar_cameras()
    total_cams = len(cameras)
    online_count = 0
    for camera in cameras:
        camera['online'] = verificar_online(camera['rtsp_url'])
        camera['rtsp_mascarado'] = mascarar_rtsp(camera['rtsp_url'])
        if camera['online']:
            online_count += 1
        slug_fixo = slug_camera(camera)
        camera['slug'] = slug_fixo
        try:
            videos = [f for f in os.listdir(caminho_videos) if f.startswith(slug_fixo) and f.endswith('.mp4')]
            camera['qtd_videos'] = len(videos)
        except Exception:
            camera['qtd_videos'] = 0

    try:
        uso = shutil.disk_usage(caminho_videos)
        disco = {
            'usado': f"{(uso.used / (1024**3)):.1f} GB",
            'total': f"{(uso.total / (1024**3)):.1f} GB",
            'livre': f"{(uso.free / (1024**3)):.1f} GB",
            'porcentagem': int((uso.used / uso.total) * 100)
        }
    except Exception:
        disco = {'usado': '0 GB', 'total': '0 GB', 'livre': '0 GB', 'porcentagem': 0}

    return {
        "cameras": cameras,
        "total_cams": total_cams,
        "online_count": online_count,
        "disco": disco,
        "perfis_rtsp": RTSP_PERFIS,
        "caminho_videos": caminho_videos,
        "armazenamentos": listar_armazenamentos(),
        "tempo_segmento": get_tempo_segmento(),
        "tempos_segmento_permitidos": TEMPOS_SEGMENTO_PERMITIDOS,
    }


def renderizar_index(mensagem_erro=None, mensagem_sucesso=None, form_data=None, status=200):
    contexto = montar_contexto_index()
    contexto.update({
        "mensagem_erro": mensagem_erro,
        "mensagem_sucesso": mensagem_sucesso,
        "form_data": form_data or {},
    })
    return render_template('index.html', **contexto), status


@app.route('/')
def index():
    return renderizar_index(
        mensagem_erro=request.args.get("erro"),
        mensagem_sucesso=request.args.get("sucesso"),
    )


@app.route('/camera/<slug>')
def detalhe_camera(slug):
    return renderizar_detalhe_camera(
        slug,
        mensagem_erro=request.args.get("erro"),
        mensagem_sucesso=request.args.get("sucesso"),
    )


@app.route('/monitor')
def monitor_cameras():
    cameras = carregar_cameras()
    for camera in cameras:
        camera['slug'] = slug_camera(camera)
    return render_template('monitor.html', cameras=cameras)


def renderizar_detalhe_camera(
    slug,
    mensagem_erro=None,
    mensagem_sucesso=None,
    form_data=None,
    status=200,
    edicao_aberta=False,
):
    cameras = carregar_cameras()
    camera = buscar_camera_por_slug(cameras, slug)
    if not camera:
        return redirect(url_for('index'))

    data_filtro = request.args.get('data', '')
    camera['online'] = None
    camera['rtsp_mascarado'] = mascarar_rtsp(camera['rtsp_url'])
    camera['slug'] = slug_camera(camera)

    return render_template(
        'detalhe.html',
        camera=camera,
        videos=[],
        videos_validos=None,
        data_filtro=data_filtro,
        perfis_rtsp=RTSP_PERFIS,
        mensagem_erro=mensagem_erro,
        mensagem_sucesso=mensagem_sucesso,
        form_data=form_data or dados_edicao_camera(camera),
        edicao_aberta=edicao_aberta,
    ), status


@app.route('/live/<slug>')
def live_stream(slug):
    cameras = carregar_cameras()
    camera = buscar_camera_por_slug(cameras, slug)
    if camera:
        return Response(gerar_frames(camera), mimetype='multipart/x-mixed-replace; boundary=frame')
    return "Camera nao encontrada", 404


@app.route('/api/camera/<slug>/status')
def api_camera_status(slug):
    cameras = carregar_cameras()
    camera = buscar_camera_por_slug(cameras, slug)
    if not camera:
        return jsonify({"erro": "Camera nao encontrada"}), 404

    online = verificar_online(camera['rtsp_url'])
    return jsonify({
        "online": online,
        "live_url": url_for('live_stream', slug=slug_camera(camera)),
    })


@app.route('/api/camera/<slug>/videos')
def api_camera_videos(slug):
    cameras = carregar_cameras()
    camera = buscar_camera_por_slug(cameras, slug)
    if not camera:
        return jsonify({"erro": "Camera nao encontrada"}), 404

    data_filtro = request.args.get('data', '')
    caminho_videos = get_caminho_videos()
    videos = listar_videos_camera(caminho_videos, slug_camera(camera), data_filtro)
    videos_validos = sum(1 for video in videos if video["reproduzivel"])
    return jsonify({
        "videos": videos,
        "videos_validos": videos_validos,
        "total_videos": len(videos),
    })


@app.route('/api/camera/<slug>/calendario')
def api_camera_calendario(slug):
    cameras = carregar_cameras()
    camera = buscar_camera_por_slug(cameras, slug)
    if not camera:
        return jsonify({"erro": "Camera nao encontrada"}), 404

    caminho_videos = get_caminho_videos()
    dias = listar_dias_gravacoes_camera(caminho_videos, slug_camera(camera))
    return jsonify({"dias": dias})


@app.route('/video/<filename>')
def serve_video(filename):
    caminho_video = obter_caminho_video_seguro(filename)
    if not caminho_video:
        return "Video nao encontrado", 404
    return send_file(caminho_video, mimetype="video/mp4", conditional=True)


@app.route('/video_compativel/<filename>')
def serve_video_compativel(filename):
    caminho_video = obter_caminho_video_seguro(filename)
    if not caminho_video:
        return "Video nao encontrado", 404
    if not shutil.which("ffmpeg"):
        return "FFmpeg nao encontrado no sistema.", 500

    headers = {
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
    }
    return Response(
        gerar_video_compativel(caminho_video),
        mimetype="video/webm",
        headers=headers,
        direct_passthrough=True,
    )


@app.route('/adicionar_camera', methods=['POST'])
def adicionar_camera():
    cameras = carregar_cameras()
    nova_camera, erro = validar_nova_camera(request.form, cameras)
    if erro:
        return renderizar_index(
            mensagem_erro=erro,
            form_data=request.form,
            status=400,
        )

    cameras.append(nova_camera)
    salvar_cameras(cameras)
    return redirect(url_for('index', sucesso="Camera adicionada."))


@app.route('/editar_camera/<slug>', methods=['POST'])
def editar_camera(slug):
    cameras = carregar_cameras()
    slug_normalizado = gerar_slug(slug)
    for indice, camera in enumerate(cameras):
        if slug_camera(camera) != slug_normalizado:
            continue

        camera_atualizada, erro = validar_edicao_camera(
            request.form,
            cameras,
            slug_normalizado,
            camera,
        )
        if erro:
            return renderizar_detalhe_camera(
                slug_normalizado,
                mensagem_erro=erro,
                form_data=request.form,
                status=400,
                edicao_aberta=True,
            )

        cameras[indice] = camera_atualizada
        salvar_cameras(cameras)
        return redirect(url_for('detalhe_camera', slug=slug_normalizado, sucesso="Camera atualizada."))

    return redirect(url_for('index', erro="Camera nao encontrada."))


@app.route('/apagar_camera/<slug>', methods=['POST'])
def apagar_camera(slug):
    cams = carregar_cameras()
    slug_normalizado = gerar_slug(slug)
    cams = [c for c in cams if slug_camera(c) != slug_normalizado]
    salvar_cameras(cams)
    return redirect(url_for('index', sucesso="Camera removida."))


@app.route('/camera/<slug>/video/<filename>/apagar', methods=['POST'])
def apagar_video(slug, filename):
    cameras = carregar_cameras()
    slug_normalizado = gerar_slug(slug)
    camera = buscar_camera_por_slug(cameras, slug_normalizado)
    if not camera:
        return redirect(url_for('index', erro="Camera nao encontrada."))

    ok, erro = apagar_video_camera(slug_normalizado, filename)
    if not ok:
        return redirect(url_for('detalhe_camera', slug=slug_normalizado, erro=erro))
    return redirect(url_for('detalhe_camera', slug=slug_normalizado, sucesso="Video apagado."))


@app.route('/camera/<slug>/videos/apagar_todos', methods=['POST'])
def apagar_todos_videos(slug):
    cameras = carregar_cameras()
    slug_normalizado = gerar_slug(slug)
    camera = buscar_camera_por_slug(cameras, slug_normalizado)
    if not camera:
        return redirect(url_for('index', erro="Camera nao encontrada."))

    apagados, ignorados = apagar_todos_videos_camera(slug_normalizado)
    if apagados == 0 and ignorados:
        mensagem = "Nenhum video foi apagado. Ha arquivos recentes ou em gravacao."
        return redirect(url_for('detalhe_camera', slug=slug_normalizado, erro=mensagem))
    if ignorados:
        mensagem = f"{apagados} videos apagados. {ignorados} recentes foram preservados."
    else:
        mensagem = f"{apagados} videos apagados."
    return redirect(url_for('detalhe_camera', slug=slug_normalizado, sucesso=mensagem))

@app.route('/configurar_armazenamento', methods=['POST'])
def configurar_armazenamento():
    caminho = request.form.get('caminho_videos', '')
    ok, erro = definir_armazenamento(caminho)
    if not ok:
        return renderizar_index(mensagem_erro=erro, status=400)
    garantir_diretorios(get_caminho_videos())
    return redirect(url_for('index', sucesso="Armazenamento atualizado."))


@app.route('/configurar_segmento', methods=['POST'])
def configurar_segmento():
    tempo_segmento = request.form.get('tempo_segmento', '')
    ok, erro = definir_tempo_segmento(tempo_segmento)
    if not ok:
        return renderizar_index(mensagem_erro=erro, status=400)
    minutos = int(tempo_segmento) // 60
    return redirect(url_for('index', sucesso=f"Segmentos configurados para {minutos} minutos."))

@app.route('/download/<filename>')
def download_video(filename):
    caminho_video = obter_caminho_video_seguro(filename)
    if not caminho_video:
        return "Video nao encontrado", 404
    return send_file(
        caminho_video,
        mimetype="video/mp4",
        as_attachment=True,
        download_name=os.path.basename(caminho_video),
        conditional=True,
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
