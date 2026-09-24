import os
import tempfile
import time
import unittest
from unittest import mock

import servidor


class ServidorCalendarioTest(unittest.TestCase):
    def criar_arquivo(self, pasta, nome):
        caminho = os.path.join(pasta, nome)
        with open(caminho, "wb") as arquivo:
            arquivo.write(b"teste")
        return caminho

    def test_lista_dias_gravacoes_por_camera(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.criar_arquivo(pasta, "garagem_2026-07-21_10-00-00.mp4")
            self.criar_arquivo(pasta, "garagem_2026-07-21_10-10-00.mp4")
            self.criar_arquivo(pasta, "garagem_2026-07-22_08-00-00.mp4")
            self.criar_arquivo(pasta, "garagem_fundos_2026-07-22_08-00-00.mp4")
            self.criar_arquivo(pasta, "garagem_2026-07-22_08-00-00.txt")
            self.criar_arquivo(pasta, "garagem_sem_data.mp4")

            dias = servidor.listar_dias_gravacoes_camera(pasta, "garagem")

        self.assertEqual(
            dias,
            [
                {"data": "2026-07-22", "total": 1},
                {"data": "2026-07-21", "total": 2},
            ],
        )

    def test_api_calendario_retorna_dias_da_camera(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.criar_arquivo(pasta, "entrada_2026-07-22_08-00-00.mp4")
            self.criar_arquivo(pasta, "entrada_2026-07-22_08-10-00.mp4")
            self.criar_arquivo(pasta, "sala_2026-07-22_08-00-00.mp4")

            cameras = [
                {
                    "nome": "Entrada",
                    "slug": "entrada",
                    "rtsp_url": "rtsp://admin:senha@192.168.0.10:554/onvif1",
                }
            ]

            with (
                mock.patch.object(servidor, "carregar_cameras", return_value=cameras),
                mock.patch.object(servidor, "get_caminho_videos", return_value=pasta),
            ):
                resposta = servidor.app.test_client().get("/api/camera/entrada/calendario")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.get_json(),
            {"dias": [{"data": "2026-07-22", "total": 2}]},
        )

    def test_tela_detalhe_inclui_calendario(self):
        cameras = [
            {
                "nome": "Entrada",
                "slug": "entrada",
                "rtsp_url": "rtsp://admin:senha@192.168.0.10:554/onvif1",
            }
        ]

        with mock.patch.object(servidor, "carregar_cameras", return_value=cameras):
            resposta = servidor.app.test_client().get("/camera/entrada")

        html = resposta.get_data(as_text=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('id="recording-calendar-grid"', html)
        self.assertIn('/api/camera/entrada/calendario', html)


class StatusGravacaoTest(unittest.TestCase):
    AGORA = 1_000_000

    def estado(self, **camera):
        return {
            "ativo": True,
            "atualizado_em": self.AGORA - 30,
            "cameras": {"garagem": {"estado": "gravando", "reinicios": 0, **camera}},
        }

    def test_sem_estado_indica_captura_parada(self):
        resumo = servidor.resumo_gravacao("garagem", None, agora=self.AGORA)
        self.assertEqual(resumo["codigo"], "captura_parada")

    def test_estado_desatualizado_indica_captura_parada(self):
        estado = self.estado()
        estado["atualizado_em"] = self.AGORA - servidor.ESTADO_CAPTURA_VALIDADE - 1
        self.assertEqual(servidor.resumo_gravacao("garagem", estado, agora=self.AGORA)["codigo"], "captura_parada")

    def test_captura_encerrada_indica_captura_parada(self):
        estado = {"ativo": False, "atualizado_em": self.AGORA, "cameras": {}}
        self.assertEqual(servidor.resumo_gravacao("garagem", estado, agora=self.AGORA)["codigo"], "captura_parada")

    def test_gravando(self):
        resumo = servidor.resumo_gravacao("garagem", self.estado(), agora=self.AGORA)
        self.assertEqual(resumo, {"codigo": "gravando", "texto": "Gravando", "detalhe": ""})

    def test_parada_mostra_tempo_e_ultimo_erro(self):
        estado = self.estado(
            estado="iniciando",
            ultima_gravacao=self.AGORA - 3 * 24 * 3600 - 2 * 3600,
            reinicios=4,
            ultimo_erro="Connection timed out",
        )
        resumo = servidor.resumo_gravacao("garagem", estado, agora=self.AGORA)
        self.assertEqual(resumo["codigo"], "parada")
        self.assertEqual(resumo["texto"], "Sem gravar ha 3 dias 2 h")
        self.assertEqual(resumo["detalhe"], "Connection timed out")

    def test_reconexao_recente_aparece_como_conectando(self):
        estado = self.estado(estado="iniciando", ultima_gravacao=self.AGORA - 20)
        self.assertEqual(servidor.resumo_gravacao("garagem", estado, agora=self.AGORA)["codigo"], "iniciando")

    def test_formatar_tempo_decorrido(self):
        self.assertEqual(servidor.formatar_tempo_decorrido(30), "menos de 1 min")
        self.assertEqual(servidor.formatar_tempo_decorrido(5 * 60), "5 min")
        self.assertEqual(servidor.formatar_tempo_decorrido(2 * 3600), "2 h")
        self.assertEqual(servidor.formatar_tempo_decorrido(3600 + 60 * 7), "1 h 7 min")
        self.assertEqual(servidor.formatar_tempo_decorrido(26 * 3600), "1 dia 2 h")

    def cameras(self):
        return [{"nome": "Garagem", "slug": "garagem", "rtsp_url": "rtsp://admin:senha@127.0.0.1:9/onvif1"}]

    def get(self, url, estado):
        with tempfile.TemporaryDirectory() as pasta:
            with (
                mock.patch.object(servidor, "carregar_cameras", return_value=self.cameras()),
                mock.patch.object(servidor, "carregar_estado_captura", return_value=estado),
                mock.patch.object(servidor, "get_caminho_videos", return_value=pasta),
                mock.patch.object(servidor, "listar_armazenamentos", return_value=[]),
                mock.patch.object(servidor, "verificar_online", return_value=True),
            ):
                return servidor.app.test_client().get(url)

    def test_painel_avisa_quando_captura_parada(self):
        html = self.get("/", None).get_data(as_text=True)
        self.assertIn("Nenhuma câmera está gravando.", html)
        self.assertIn("rec-captura_parada", html)

    def test_painel_mostra_camera_gravando(self):
        estado = self.estado()
        estado["atualizado_em"] = time.time()
        html = self.get("/", estado).get_data(as_text=True)
        self.assertNotIn("Nenhuma câmera está gravando.", html)
        self.assertIn("rec-gravando", html)

    def test_painel_avisa_hd_desconectado_sem_quebrar(self):
        erro = servidor.ArmazenamentoIndisponivel("O HD externo nao esta conectado (/mnt/hd/gravacoes).")
        with mock.patch.object(servidor, "garantir_diretorios", side_effect=erro):
            resposta = self.get("/", None)
        html = resposta.get_data(as_text=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Não é possível gravar.", html)
        self.assertIn("O HD externo nao esta conectado", html)

    def test_erro_geral_da_captura_aparece_na_camera(self):
        estado = self.estado(estado="reconectando", ultima_gravacao=self.AGORA - 600)
        estado["erro"] = "O HD externo nao esta conectado (/mnt/hd/gravacoes). Conecte o HD para voltar a gravar."
        resumo = servidor.resumo_gravacao("garagem", estado, agora=self.AGORA)
        self.assertEqual(resumo["codigo"], "parada")
        self.assertEqual(resumo["texto"], "Sem gravar ha 10 min")
        self.assertIn("Conecte o HD", resumo["detalhe"])

    def test_camera_nao_encontrada_na_rede(self):
        estado = self.estado(estado="nao_encontrada")
        resumo = servidor.resumo_gravacao("garagem", estado, agora=self.AGORA)
        self.assertEqual(resumo["texto"], "Camera nao encontrada na rede")
        self.assertIn("Verifique se ela esta ligada", resumo["detalhe"])

    def test_gravando_mostra_aviso_de_troca_de_endereco(self):
        estado = self.estado(aviso="Camera mudou de endereco (192.168.0.2 -> 192.168.0.3) e foi reconectada automaticamente")
        resumo = servidor.resumo_gravacao("garagem", estado, agora=self.AGORA)
        self.assertEqual(resumo["codigo"], "gravando")
        self.assertIn("reconectada automaticamente", resumo["detalhe"])

    def test_api_status_inclui_gravacao(self):
        dados = self.get("/api/camera/garagem/status", None).get_json()
        self.assertTrue(dados["online"])
        self.assertEqual(dados["gravacao"]["codigo"], "captura_parada")


class MacNoCadastroTest(unittest.TestCase):
    def camera_atual(self):
        return {
            "nome": "Lateral casa",
            "slug": "lateral_casa",
            "ip": "192.168.0.2",
            "mac": "28:f5:2b:a9:6f:27",
            "usuario": "admin",
            "porta": 554,
            "perfil": "onvif1",
            "protocolo": "udp",
            "rtsp_url": "rtsp://admin:senha@192.168.0.2:554/onvif1",
        }

    def form(self, **campos):
        dados = {"nome": "Lateral casa", "ip": "192.168.0.2", "usuario": "admin", "porta": "554",
                 "perfil": "onvif1", "protocolo": "udp", "mac": "28:f5:2b:a9:6f:27"}
        dados.update(campos)
        return dados

    def validar(self, dados, mac_na_rede):
        atual = self.camera_atual()
        with (
            mock.patch.object(servidor, "TESTAR_RTSP_CADASTRO", False),
            mock.patch.object(servidor.rede, "mac_do_ip", return_value=mac_na_rede) as mac_do_ip,
        ):
            camera, erro = servidor.validar_edicao_camera(dados, [atual], "lateral_casa", atual)
        self.assertIsNone(erro)
        return camera, mac_do_ip

    def test_mudar_ip_troca_o_mac_pelo_do_novo_aparelho(self):
        camera, _ = self.validar(self.form(ip="192.168.0.3"), "f0:a8:82:02:91:1a")
        self.assertEqual(camera["ip"], "192.168.0.3")
        self.assertEqual(camera["mac"], "f0:a8:82:02:91:1a")

    def test_mudar_ip_sem_achar_mac_deixa_vazio_para_aprender_depois(self):
        camera, _ = self.validar(self.form(ip="192.168.0.3"), None)
        self.assertEqual(camera["mac"], "")

    def test_sem_mudar_ip_mantem_mac(self):
        camera, mac_do_ip = self.validar(self.form(), "f0:a8:82:02:91:1a")
        self.assertEqual(camera["mac"], "28:f5:2b:a9:6f:27")
        mac_do_ip.assert_not_called()

    def test_cadastro_novo_preenche_mac_sozinho(self):
        dados = {"nome": "Garagem", "ip": "192.168.0.4", "senha": "x", "perfil": "onvif1"}
        with (
            mock.patch.object(servidor, "TESTAR_RTSP_CADASTRO", False),
            mock.patch.object(servidor.rede, "mac_do_ip", return_value="4c:a3:8f:35:ec:30"),
        ):
            camera, erro = servidor.validar_nova_camera(dados, [])
        self.assertIsNone(erro)
        self.assertEqual(camera["mac"], "4c:a3:8f:35:ec:30")


if __name__ == "__main__":
    unittest.main()
