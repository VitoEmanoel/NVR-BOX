import unittest

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


if __name__ == "__main__":
    unittest.main()
