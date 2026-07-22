import os
import tempfile
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


if __name__ == "__main__":
    unittest.main()
