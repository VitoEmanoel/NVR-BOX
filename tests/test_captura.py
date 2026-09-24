import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import captura


class CapturaTest(unittest.TestCase):
    def test_assinatura_camera_inclui_tempo_segmento(self):
        camera = {
            "rtsp_url": "rtsp://admin:senha@192.168.0.10:554/onvif1",
            "protocolo": "tcp",
        }

        assinatura_5_min = captura.assinatura_camera(camera, 300)
        assinatura_10_min = captura.assinatura_camera(camera, 600)

        self.assertNotEqual(assinatura_5_min, assinatura_10_min)
        self.assertEqual(
            assinatura_5_min,
            ("rtsp://admin:senha@192.168.0.10:554/onvif1", "tcp", 300),
        )


class DeteccaoTravamentoTest(unittest.TestCase):
    def test_sem_progresso_respeita_tolerancia_de_inicio(self):
        registro = {"inicio_mono": 1000}

        self.assertFalse(captura.gravacao_travada(registro, 1080, limite=60, tolerancia=90))
        self.assertTrue(captura.gravacao_travada(registro, 1091, limite=60, tolerancia=90))

    def test_arquivo_parado_alem_do_limite_e_travamento(self):
        registro = {"inicio_mono": 1000, "ultimo_progresso_mono": 2000}

        self.assertFalse(captura.gravacao_travada(registro, 2060, limite=60, tolerancia=90))
        self.assertTrue(captura.gravacao_travada(registro, 2061, limite=60, tolerancia=90))

    def test_progresso_so_conta_quando_arquivo_muda(self):
        registro = {"inicio_mono": 0, "medida": ("/v/a.mp4", 100)}

        self.assertFalse(captura.atualizar_progresso(registro, ("/v/a.mp4", 100), 50, 5000))
        self.assertIsNone(registro.get("ultimo_progresso_mono"))
        self.assertFalse(captura.atualizar_progresso(registro, None, 50, 5000))

        self.assertTrue(captura.atualizar_progresso(registro, ("/v/a.mp4", 200), 60, 5010))
        self.assertEqual(registro["ultimo_progresso_mono"], 60)
        self.assertEqual(registro["ultimo_progresso"], 5010)

        self.assertTrue(captura.atualizar_progresso(registro, ("/v/b.mp4", 10), 70, 5020))

    def test_estado_camera(self):
        self.assertEqual(captura.estado_camera(None, 100), "reconectando")
        self.assertEqual(captura.estado_camera({"inicio_mono": 0}, 100), "iniciando")
        self.assertEqual(captura.estado_camera({"ultimo_progresso_mono": 90}, 100), "gravando")
        self.assertEqual(
            captura.estado_camera({"ultimo_progresso_mono": 0}, captura.LIMITE_SEM_GRAVACAO + 1),
            "parada",
        )


class SegmentosTest(unittest.TestCase):
    def criar(self, pasta, nome):
        with open(os.path.join(pasta, nome), "wb") as arquivo:
            arquivo.write(b"x")

    def test_ultimo_segmento_ignora_camera_com_prefixo_parecido(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.criar(pasta, "sala_2026-09-01_10-00-00.mp4")
            self.criar(pasta, "sala_2026-09-01_10-10-00.mp4")
            self.criar(pasta, "sala_2_2026-09-02_10-00-00.mp4")
            self.criar(pasta, "sala_2026-09-03_10-00-00.txt")

            self.assertEqual(
                captura.ultimo_segmento_camera(pasta, "sala"),
                os.path.join(pasta, "sala_2026-09-01_10-10-00.mp4"),
            )
            self.assertEqual(
                captura.ultimo_segmento_camera(pasta, "sala_2"),
                os.path.join(pasta, "sala_2_2026-09-02_10-00-00.mp4"),
            )
            self.assertIsNone(captura.ultimo_segmento_camera(pasta, "garagem"))

    @unittest.skipUnless(os.path.isdir("/proc/self/fd"), "requer /proc")
    def test_arquivo_aberto_pelo_processo_via_proc(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = os.path.join(pasta, "cam_2026-09-01_10-00-00.mp4")
            processo = subprocess.Popen([
                sys.executable, "-c",
                "import sys, time; f = open(sys.argv[1], 'wb'); print('ok', flush=True); time.sleep(30)",
                destino,
            ], stdout=subprocess.PIPE, text=True)
            try:
                processo.stdout.readline()
                self.assertEqual(
                    os.path.realpath(captura.arquivo_aberto_pelo_processo(processo.pid)),
                    os.path.realpath(destino),
                )
            finally:
                processo.kill()
                processo.wait()
                processo.stdout.close()


class LogTest(unittest.TestCase):
    def test_rotacao_com_arquivo_aberto_em_acrescimo(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "erro_cam.txt")
            with open(caminho, "a", encoding="utf-8") as log:
                log.write("a" * 50)
                log.flush()
                with mock.patch.object(captura, "FFMPEG_LOG_MAX_BYTES", 10):
                    captura.rotacionar_log(caminho)
                log.write("depois")
                log.flush()

            with open(caminho, encoding="utf-8") as arquivo:
                self.assertEqual(arquivo.read(), "depois")
            with open(f"{caminho}.1", encoding="utf-8") as arquivo:
                self.assertEqual(arquivo.read(), "a" * 50)

    def test_ultima_linha_log_mascara_senha(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "erro_cam.txt")
            with open(caminho, "w", encoding="utf-8") as arquivo:
                arquivo.write("=== 2026-09-24 10:00:00 Iniciando captura ===\n")
                arquivo.write("[in#0] rtsp://admin:segredo@192.168.0.2:554/onvif1: Connection timed out\n\n")

            linha = captura.ultima_linha_log(caminho)

        self.assertNotIn("segredo", linha)
        self.assertIn("rtsp://****@192.168.0.2:554/onvif1", linha)
        self.assertIn("Connection timed out", linha)

    def test_ffmpeg_sem_progresso_no_log_e_com_timeout(self):
        camera = {
            "nome": "Garagem",
            "slug": "garagem",
            "rtsp_url": "rtsp://admin:senha@192.168.0.4:554/onvif1",
            "protocolo": "udp",
        }
        with tempfile.TemporaryDirectory() as pasta:
            with (
                mock.patch.object(captura.subprocess, "Popen") as popen,
                mock.patch.object(captura, "argumentos_timeout_rtsp", return_value=["-timeout", "15000000"]),
            ):
                registro = captura.iniciar_ffmpeg(camera, pasta, 900)
                registro["log"].close()

            comando = popen.call_args.args[0]
            self.assertIn("-nostats", comando)
            self.assertEqual(comando[comando.index("-loglevel") + 1], "warning")
            self.assertLess(comando.index("-timeout"), comando.index("-i"))
            self.assertEqual(registro["log"].mode, "a")
            with open(os.path.join(pasta, "erro_garagem.txt"), encoding="utf-8") as arquivo:
                self.assertIn("Iniciando captura", arquivo.read())


class EstadoTest(unittest.TestCase):
    def test_resumo_nao_muda_so_por_horario(self):
        estado = {
            "caminho_videos": "/v",
            "erro": None,
            "cameras": {
                "garagem": {"estado": "gravando", "reinicios": 0, "ultimo_motivo": None, "ultima_gravacao": 1},
            },
        }
        outro = {**estado, "atualizado_em": 99}
        outro["cameras"] = {"garagem": {**estado["cameras"]["garagem"], "ultima_gravacao": 2}}
        self.assertEqual(captura.resumo_para_comparar(estado), captura.resumo_para_comparar(outro))

        outro["cameras"]["garagem"]["estado"] = "parada"
        self.assertNotEqual(captura.resumo_para_comparar(estado), captura.resumo_para_comparar(outro))


MAC_LATERAL = "28:f5:2b:a9:6f:27"
MAC_QUINTAL = "f0:a8:82:02:91:1a"


def camera(nome, slug, ip, mac=""):
    return {
        "nome": nome,
        "slug": slug,
        "ip": ip,
        "mac": mac,
        "porta": 554,
        "rtsp_url": f"rtsp://admin:senha@{ip}:554/onvif1",
    }


class CameraPorMacTest(unittest.TestCase):
    def test_troca_de_ip_entre_duas_cameras_corrige_o_cadastro(self):
        lateral = camera("Lateral casa", "lateral_casa", "192.168.0.2", MAC_LATERAL)
        quintal = camera("Quintal", "quintal", "192.168.0.3", MAC_QUINTAL)
        tabela = {"192.168.0.2": MAC_QUINTAL, "192.168.0.3": MAC_LATERAL}
        salvos = {}

        def localizar(mac, ip, porta, varrer):
            return captura.localizar_camera(
                mac, ip, porta, ler_arp=lambda: tabela, tocar=lambda *a: False, varrer=varrer
            )

        def salvar(slug, **campos):
            salvos[slug] = campos

        infos = {"lateral_casa": {}, "quintal": {}}
        nova_lateral = captura.preparar_inicio(lateral, "lateral_casa", infos["lateral_casa"], 0, 1000, localizar=localizar, salvar=salvar)
        novo_quintal = captura.preparar_inicio(quintal, "quintal", infos["quintal"], 0, 1000, localizar=localizar, salvar=salvar)

        self.assertEqual(nova_lateral["rtsp_url"], "rtsp://admin:senha@192.168.0.3:554/onvif1")
        self.assertEqual(novo_quintal["rtsp_url"], "rtsp://admin:senha@192.168.0.2:554/onvif1")
        self.assertEqual(salvos["lateral_casa"], {"ip": "192.168.0.3", "rtsp_url": "rtsp://admin:senha@192.168.0.3:554/onvif1"})
        self.assertEqual(salvos["quintal"]["ip"], "192.168.0.2")
        self.assertIn("192.168.0.2 -> 192.168.0.3", infos["lateral_casa"]["aviso"])

    def test_camera_nao_encontrada_nao_inicia_e_limita_varredura(self):
        cam = camera("Lateral casa", "lateral_casa", "192.168.0.2", MAC_LATERAL)
        varreduras = []

        def localizar(mac, ip, porta, varrer):
            varrer(ip, porta)
            return None, "nao_encontrada"

        info = {}
        with mock.patch.object(captura, "ler_tabela_arp", return_value={}):
            for agora_mono in (0, 30, 60, captura.INTERVALO_VARREDURA + 1):
                self.assertIsNone(captura.preparar_inicio(
                    cam, "lateral_casa", info, agora_mono, 0,
                    localizar=localizar, varrer=lambda ip, porta: varreduras.append(ip) or {},
                ))

        self.assertTrue(info["nao_encontrada"])
        self.assertEqual(len(varreduras), 2)
        self.assertEqual(captura.estado_camera(None, 0, info), "nao_encontrada")

    def test_endereco_trocado_detecta_outro_aparelho_no_ip(self):
        cam = camera("Lateral casa", "lateral_casa", "192.168.0.2", MAC_LATERAL)
        self.assertFalse(captura.endereco_trocado(cam, {"192.168.0.2": MAC_LATERAL}))
        self.assertFalse(captura.endereco_trocado(cam, {}))
        self.assertFalse(captura.endereco_trocado(cam, None))
        self.assertTrue(captura.endereco_trocado(cam, {"192.168.0.2": MAC_QUINTAL}))
        self.assertFalse(captura.endereco_trocado(camera("Sem mac", "sem_mac", "192.168.0.2"), {"192.168.0.2": MAC_QUINTAL}))

    def test_aprende_mac_sem_repetir(self):
        salvos = {}
        cam = camera("Garagem", "garagem", "192.168.0.4")
        tabela = {"192.168.0.4": "4c:a3:8f:35:ec:30"}

        mac = captura.aprender_mac(cam, "garagem", tabela, set(), salvar=lambda slug, **c: salvos.update({slug: c}))
        self.assertEqual(mac, "4c:a3:8f:35:ec:30")
        self.assertEqual(salvos, {"garagem": {"mac": "4c:a3:8f:35:ec:30"}})

        outra = camera("Fundos", "fundos", "192.168.0.4")
        self.assertIsNone(captura.aprender_mac(outra, "fundos", tabela, {"4c:a3:8f:35:ec:30"}, salvar=lambda *a, **c: self.fail()))


class ConferenciaSemGravarTest(unittest.TestCase):
    def test_confere_so_cameras_paradas_e_respeita_intervalo(self):
        garagem = camera("Garagem", "garagem", "192.168.0.4", "4c:a3:8f:35:ec:30")
        quintal = camera("Quintal", "quintal", "192.168.0.2", MAC_QUINTAL)
        conferidas = []

        def conferir(cam, slug, info, agora_mono, agora):
            info["ultima_conferencia_mono"] = agora_mono
            conferidas.append(slug)
            return {**cam, "ip": "192.168.0.99"}

        historico = {}
        processos = {"garagem": object()}  # garagem gravando
        lista = captura.conferir_cameras_paradas([garagem, quintal], processos, historico, 0, 0, conferir=conferir)
        self.assertEqual(conferidas, ["quintal"])
        self.assertEqual([c["ip"] for c in lista], ["192.168.0.4", "192.168.0.99"])

        captura.conferir_cameras_paradas([garagem, quintal], processos, historico, 10, 0, conferir=conferir)
        self.assertEqual(conferidas, ["quintal"])
        captura.conferir_cameras_paradas([garagem, quintal], processos, historico, captura.INTERVALO_CONFERENCIA, 0, conferir=conferir)
        self.assertEqual(conferidas, ["quintal", "quintal"])

    def test_camera_nao_encontrada_continua_na_lista(self):
        cam = camera("Quintal", "quintal", "192.168.0.2", MAC_QUINTAL)
        lista = captura.conferir_cameras_paradas([cam], {}, {}, 0, 0, conferir=lambda *a: None)
        self.assertEqual(lista, [cam])

    def test_falha_ao_salvar_cadastro_nao_derruba(self):
        cam = camera("Quintal", "quintal", "192.168.0.2", MAC_QUINTAL)

        def preparar(*_args):
            raise PermissionError("somente leitura")

        info = {}
        self.assertIs(captura.conferir_camera(cam, "quintal", info, 5, 0, preparar=preparar), cam)
        self.assertEqual(info["ultima_conferencia_mono"], 5)


if __name__ == "__main__":
    unittest.main()
