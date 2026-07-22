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


if __name__ == "__main__":
    unittest.main()
