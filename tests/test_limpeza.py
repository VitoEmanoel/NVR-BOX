import contextlib
import io
import os
import tempfile
import time
import unittest
import unittest.mock

import limpeza


class LimpezaTest(unittest.TestCase):
    def criar_arquivo(self, pasta, nome, idade_segundos):
        caminho = os.path.join(pasta, nome)
        with open(caminho, "wb") as arquivo:
            arquivo.write(b"teste")
        modificado = time.time() - idade_segundos
        os.utime(caminho, (modificado, modificado))
        return caminho

    def test_apaga_apenas_mp4_antigo_mais_velho(self):
        with tempfile.TemporaryDirectory() as pasta:
            mais_velho = self.criar_arquivo(pasta, "camera_mais_velho.mp4", 3600)
            mais_novo = self.criar_arquivo(pasta, "camera_mais_novo.mp4", 2400)
            recente = self.criar_arquivo(pasta, "camera_recente.mp4", 10)
            texto = self.criar_arquivo(pasta, "camera_log.txt", 3600)

            with contextlib.redirect_stdout(io.StringIO()):
                apagou = limpeza.apagar_video_mais_antigo(pasta)

            self.assertTrue(apagou)
            self.assertFalse(os.path.exists(mais_velho))
            self.assertTrue(os.path.exists(mais_novo))
            self.assertTrue(os.path.exists(recente))
            self.assertTrue(os.path.exists(texto))

    def test_executar_limpeza_para_quando_volta_ao_limite(self):
        with tempfile.TemporaryDirectory() as pasta:
            antigo_1 = self.criar_arquivo(pasta, "camera_1.mp4", 3600)
            antigo_2 = self.criar_arquivo(pasta, "camera_2.mp4", 2400)
            recente = self.criar_arquivo(pasta, "camera_recente.mp4", 10)

            def uso_simulado(_pasta):
                if os.path.exists(antigo_1):
                    return 95, 95, 100
                return 89, 89, 100

            with contextlib.redirect_stdout(io.StringIO()):
                resultado = limpeza.executar_limpeza(pasta, limite_porcentagem=90, obter_uso=uso_simulado)

            self.assertEqual(resultado["apagados"], 1)
            self.assertFalse(resultado["sem_elegiveis"])
            self.assertFalse(os.path.exists(antigo_1))
            self.assertTrue(os.path.exists(antigo_2))
            self.assertTrue(os.path.exists(recente))

    def test_executar_limpeza_preserva_quando_nao_ha_elegiveis(self):
        with tempfile.TemporaryDirectory() as pasta:
            recente = self.criar_arquivo(pasta, "camera_recente.mp4", 10)
            texto = self.criar_arquivo(pasta, "camera_log.txt", 3600)

            def uso_alto(_pasta):
                return 95, 95, 100

            with contextlib.redirect_stdout(io.StringIO()):
                resultado = limpeza.executar_limpeza(pasta, limite_porcentagem=90, obter_uso=uso_alto)

            self.assertEqual(resultado["apagados"], 0)
            self.assertTrue(resultado["sem_elegiveis"])
            self.assertTrue(os.path.exists(recente))
            self.assertTrue(os.path.exists(texto))


class LimpezaSemArmazenamentoTest(unittest.TestCase):
    def test_ciclo_nao_derruba_processo_com_hd_desconectado(self):
        saida = io.StringIO()
        erro = limpeza.ArmazenamentoIndisponivel("O HD externo nao esta conectado (/mnt/hd/gravacoes).")
        with (
            unittest.mock.patch.object(limpeza, "get_caminho_videos", return_value="/mnt/hd/gravacoes"),
            unittest.mock.patch.object(limpeza, "garantir_diretorios", side_effect=erro),
            unittest.mock.patch.object(limpeza, "executar_limpeza") as executar,
            contextlib.redirect_stdout(saida),
        ):
            limpeza.ciclo_limpeza()

        executar.assert_not_called()
        self.assertIn("Limpeza suspensa", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
