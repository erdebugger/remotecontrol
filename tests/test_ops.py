import unittest

from remotecontrol.ops import AgentConfig, ClassroomController, Credentials


class SpyController(ClassroomController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scripts: list[str] = []

    def _run_local_powershell(self, script: str):
        self.scripts.append(script)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()


class AgentSpyController(ClassroomController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_calls: list[str] = []
        self.winrm_calls: list[str] = []

    def _invoke_agent(self, target_ip: str, action: str, policy=None):
        self.agent_calls.append(action)

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    def _invoke_remote_script(self, target_ip: str, script: str):
        self.winrm_calls.append(script)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()


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

    def test_access_denied_has_agent_recommendation(self):
        stderr = "AccessDenied"
        msg = ClassroomController.format_error(stderr)
        self.assertIn("Acceso denegado", msg)
        self.assertIn("modo Agente", msg)


class OpsInvocationTests(unittest.TestCase):
    def test_shutdown_autotrust_adds_trustedhost_and_uses_authentication(self):
        controller = SpyController(
            credentials=Credentials(username="DOM\\admin", password="secret"),
            auto_trust_hosts=True,
            use_ssl=False,
            authentication="Negotiate",
        )

        controller.shutdown("192.168.50.3")

        self.assertEqual(2, len(controller.scripts))
        self.assertIn("WSMan:\\localhost\\Client\\TrustedHosts", controller.scripts[0])
        self.assertIn("Invoke-Command -ComputerName 192.168.50.3", controller.scripts[1])
        self.assertIn("-Authentication Negotiate", controller.scripts[1])
        self.assertIn("-Credential $cred", controller.scripts[1])

    def test_restart_uses_ssl_when_configured(self):
        controller = SpyController(use_ssl=True, authentication="Default")
        controller.restart("192.168.50.4")
        self.assertIn("-UseSSL", controller.scripts[-1])

    def test_agent_mode_prioritizes_agent_over_winrm(self):
        controller = AgentSpyController(agent=AgentConfig(enabled=True, token="t"))
        controller.shutdown("192.168.50.9")
        self.assertEqual(["shutdown"], controller.agent_calls)
        self.assertEqual([], controller.winrm_calls)


if __name__ == "__main__":
    unittest.main()
