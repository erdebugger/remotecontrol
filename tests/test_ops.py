import unittest

from remotecontrol.ops import ClassroomController


class OpsFormattingTests(unittest.TestCase):
    def test_extracts_clixml_and_suggests_trustedhosts(self):
        stderr = (
            "#< CLIXML "
            "<Objs Version='1.1.0.1' xmlns='http://schemas.microsoft.com/powershell/2004/04'>"
            "<S S='Error'>[192.168.50.3] Error de conexión _x000D__x000A_ TrustedHosts</S>"
            "<S S='Error'> + FullyQualifiedErrorId : ServerNotTrusted</S>"
            "</Objs>"
        )
        msg = ClassroomController.format_error(stderr)
        self.assertIn("WinRM no confía", msg)

    def test_formats_plain_text_error(self):
        stderr = "fallo de autenticación"
        msg = ClassroomController.format_error(stderr)
        self.assertEqual("fallo de autenticación", msg)


if __name__ == "__main__":
    unittest.main()
