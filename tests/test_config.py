import os
import tempfile
import unittest
from unittest import mock

import config


class ConfiguracaoTest(unittest.TestCase):
    def test_get_tempo_segmento_usa_configuracao_salva(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo_config = os.path.join(pasta, "sistema.json")
            with mock.patch.object(config, "ARQUIVO_CONFIGURACOES", arquivo_config):
                ok, erro = config.definir_tempo_segmento(300)

                self.assertTrue(ok)
                self.assertIsNone(erro)
                self.assertEqual(config.get_tempo_segmento(), 300)

    def test_get_tempo_segmento_rejeita_valor_fora_das_opcoes(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo_config = os.path.join(pasta, "sistema.json")
            with mock.patch.object(config, "ARQUIVO_CONFIGURACOES", arquivo_config):
                ok, erro = config.definir_tempo_segmento(120)

                self.assertFalse(ok)
                self.assertEqual(erro, "Escolha 5, 10 ou 15 minutos.")
                self.assertEqual(config.get_tempo_segmento(), config.TEMPO_SEGMENTO_PADRAO)

    def test_variavel_de_ambiente_tem_prioridade_no_tempo_segmento(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo_config = os.path.join(pasta, "sistema.json")
            with (
                mock.patch.object(config, "ARQUIVO_CONFIGURACOES", arquivo_config),
                mock.patch.dict(os.environ, {"NVRBOX_TEMPO_SEGMENTO": "120"}, clear=False),
            ):
                ok, _erro = config.definir_tempo_segmento(300)

                self.assertTrue(ok)
                self.assertEqual(config.get_tempo_segmento(), 120)


class TimeoutRtspTest(unittest.TestCase):
    def setUp(self):
        config._OPCAO_TIMEOUT_RTSP = None

    def tearDown(self):
        config._OPCAO_TIMEOUT_RTSP = None

    def ajuda_ffmpeg(self, texto):
        return mock.patch.object(
            config.subprocess, "run", return_value=mock.Mock(stdout=texto)
        )

    def test_ffmpeg_novo_usa_timeout(self):
        with self.ajuda_ffmpeg("  -timeout  <int64>  set timeout (in microseconds) of socket I/O operations"):
            self.assertEqual(config.argumentos_timeout_rtsp(15), ["-timeout", "15000000"])

    def test_ffmpeg_antigo_usa_stimeout(self):
        # No FFmpeg antigo, -timeout colocaria o RTSP em modo de escuta.
        with self.ajuda_ffmpeg("  -timeout  <int>  set maximum timeout (in seconds) to wait for incoming connections\n"
                               "  -stimeout <int>  set timeout (in microseconds) of socket TCP I/O operations"):
            self.assertEqual(config.argumentos_timeout_rtsp(15), ["-stimeout", "15000000"])

    def test_timeout_limitado_ao_maximo_aceito_pelo_ffmpeg(self):
        with self.ajuda_ffmpeg("-timeout"):
            self.assertEqual(config.argumentos_timeout_rtsp(3600), ["-timeout", "2000000000"])
            self.assertEqual(config.argumentos_timeout_rtsp(0), ["-timeout", "1000000"])

    def test_sem_ffmpeg_nao_quebra(self):
        with mock.patch.object(config.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(config.opcao_timeout_rtsp(), "-timeout")


class EstadoCapturaTest(unittest.TestCase):
    def test_salva_e_carrega_estado(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = os.path.join(pasta, ".run", "estado_captura.json")
            with mock.patch.object(config, "ARQUIVO_ESTADO_CAPTURA", arquivo):
                self.assertIsNone(config.carregar_estado_captura())
                config.salvar_estado_captura({"ativo": True, "cameras": {}})
                self.assertEqual(config.carregar_estado_captura(), {"ativo": True, "cameras": {}})


if __name__ == "__main__":
    unittest.main()
