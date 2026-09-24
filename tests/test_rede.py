import os
import tempfile
import unittest
from unittest import mock

import rede

MAC_LATERAL = "28:f5:2b:a9:6f:27"
MAC_QUINTAL = "f0:a8:82:02:91:1a"


class TabelaArpTest(unittest.TestCase):
    def test_le_so_entradas_completas(self):
        conteudo = (
            "IP address       HW type     Flags       HW address            Mask     Device\n"
            "192.168.0.3      0x1         0x2         F0:A8:82:02:91:1A     *        end0\n"
            "192.168.0.7      0x1         0x0         10:7c:61:a5:a6:93     *        end0\n"
            "192.168.0.9      0x1         0x2         00:00:00:00:00:00     *        end0\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as arquivo:
            arquivo.write(conteudo)
        try:
            with mock.patch.object(rede, "ARQUIVO_ARP", arquivo.name):
                self.assertEqual(rede.ler_tabela_arp(), {"192.168.0.3": MAC_QUINTAL})
        finally:
            os.remove(arquivo.name)

    def test_sem_acesso_a_tabela_retorna_none(self):
        # Android 10+ bloqueia /proc/net/arp e o comando ip neigh.
        with (
            mock.patch.object(rede, "ARQUIVO_ARP", "/caminho/inexistente"),
            mock.patch.object(rede.subprocess, "run", side_effect=OSError),
        ):
            self.assertIsNone(rede.ler_tabela_arp())

    def test_normalizar_mac(self):
        self.assertEqual(rede.normalizar_mac("F0-A8-82-02-91-1A"), MAC_QUINTAL)
        self.assertIsNone(rede.normalizar_mac(""))
        self.assertIsNone(rede.normalizar_mac("nao e mac"))


class LocalizarCameraTest(unittest.TestCase):
    def localizar(self, mac, ip, tabela, tabela_apos_varredura=None):
        varreduras = []

        def varrer(ip_referencia, porta):
            varreduras.append(ip_referencia)
            return tabela_apos_varredura if tabela_apos_varredura is not None else tabela

        resultado = rede.localizar_camera(
            mac, ip, 554,
            ler_arp=lambda: tabela, tocar=lambda ip, porta: False, varrer=varrer,
        )
        return resultado, varreduras

    def test_ip_confirmado_nao_varre_a_rede(self):
        resultado, varreduras = self.localizar(MAC_LATERAL, "192.168.0.2", {"192.168.0.2": MAC_LATERAL})
        self.assertEqual(resultado, ("192.168.0.2", "confirmada"))
        self.assertEqual(varreduras, [])

    def test_cameras_trocadas_sao_encontradas_sem_varrer(self):
        # Depois de reiniciar o roteador, .2 e .3 foram trocados entre as cameras.
        tabela = {"192.168.0.2": MAC_QUINTAL, "192.168.0.3": MAC_LATERAL}
        self.assertEqual(self.localizar(MAC_LATERAL, "192.168.0.2", tabela)[0], ("192.168.0.3", "mudou"))
        self.assertEqual(self.localizar(MAC_QUINTAL, "192.168.0.3", tabela)[0], ("192.168.0.2", "mudou"))

    def test_camera_fora_da_tabela_e_achada_pela_varredura(self):
        resultado, varreduras = self.localizar(
            MAC_LATERAL, "192.168.0.2", {}, tabela_apos_varredura={"192.168.0.23": MAC_LATERAL}
        )
        self.assertEqual(resultado, ("192.168.0.23", "mudou"))
        self.assertEqual(varreduras, ["192.168.0.2"])

    def test_camera_desligada_nao_e_encontrada(self):
        resultado, _ = self.localizar(MAC_LATERAL, "192.168.0.2", {"192.168.0.1": "28:ee:52:d9:9a:d8"})
        self.assertEqual(resultado, (None, "nao_encontrada"))

    def test_sem_mac_ou_sem_tabela_nao_bloqueia(self):
        self.assertEqual(self.localizar("", "192.168.0.2", {})[0], ("192.168.0.2", "sem_verificacao"))
        self.assertEqual(self.localizar(MAC_LATERAL, "192.168.0.2", None)[0], ("192.168.0.2", "sem_verificacao"))


if __name__ == "__main__":
    unittest.main()
