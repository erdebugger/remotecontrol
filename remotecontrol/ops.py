from __future__ import annotations

import base64
import json
import re
import subprocess
from dataclasses import dataclass
from urllib import error, request
from xml.etree import ElementTree

from .policy import InternetPolicy


@dataclass(slots=True)
class Credentials:
    username: str
    password: str


@dataclass(slots=True)
class AgentConfig:
    enabled: bool = False
    port: int = 8765
    token: str = ""
    timeout_s: int = 5


class ClassroomController:
    def __init__(
        self,
        credentials: Credentials | None = None,
        auto_trust_hosts: bool = False,
        use_ssl: bool = False,
        authentication: str = "Default",
        agent: AgentConfig | None = None,
    ):
        self.credentials = credentials
        self.auto_trust_hosts = auto_trust_hosts
        self.use_ssl = use_ssl
        self.authentication = authentication
        self.agent = agent or AgentConfig()

    def _pwsh_encoded(self, script: str) -> str:
        data = script.encode("utf-16le")
        return base64.b64encode(data).decode("ascii")

    def _run_local_powershell(self, script: str) -> subprocess.CompletedProcess:
        encoded = self._pwsh_encoded(script)
        cmd = ["powershell", "-NoProfile", "-EncodedCommand", encoded]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _invoke_remote_script(self, target_ip: str, script: str) -> subprocess.CompletedProcess:
        if self.auto_trust_hosts and not self.use_ssl:
            self.add_trusted_host(target_ip)

        auth_block = ""
        cred_part = ""
        if self.credentials:
            auth_block = (
                "$sec = ConvertTo-SecureString '{pwd}' -AsPlainText -Force;"
                "$cred = New-Object System.Management.Automation.PSCredential('{usr}',$sec);"
            ).format(usr=self.credentials.username, pwd=self.credentials.password)
            cred_part = " -Credential $cred"

        ssl_part = " -UseSSL" if self.use_ssl else ""
        auth_part = f" -Authentication {self.authentication}" if self.authentication else ""
        invoke = (
            f"{auth_block} Invoke-Command -ComputerName {target_ip}{cred_part}{ssl_part}{auth_part} "
            f"-ScriptBlock {{{script}}}"
        )

        return self._run_local_powershell(invoke)

    def _invoke_agent(self, target_ip: str, action: str, policy: InternetPolicy | None = None) -> subprocess.CompletedProcess:
        if not self.agent.enabled:
            return subprocess.CompletedProcess(args=["agent"], returncode=1, stdout="", stderr="Agent deshabilitado")

        url = f"http://{target_ip}:{self.agent.port}/execute"
        body: dict[str, object] = {"token": self.agent.token, "action": action}
        if policy is not None:
            body["policy"] = {
                "mode": policy.mode,
                "allowed_domains": policy.allowed_domains,
                "allowed_ips": policy.allowed_ips,
                "allowed_dns_servers": policy.allowed_dns_servers,
            }

        data = json.dumps(body).encode("utf-8")
        req = request.Request(url=url, data=data, method="POST", headers={"Content-Type": "application/json"})

        try:
            with request.urlopen(req, timeout=self.agent.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8") or "{}")
            if payload.get("ok"):
                return subprocess.CompletedProcess(args=["agent"], returncode=0, stdout=str(payload.get("message", "ok")), stderr="")
            return subprocess.CompletedProcess(args=["agent"], returncode=1, stdout="", stderr=str(payload.get("error", "Fallo agente")))
        except error.HTTPError as exc:
            msg = exc.read().decode("utf-8", errors="replace")
            return subprocess.CompletedProcess(args=["agent"], returncode=1, stdout="", stderr=f"HTTP {exc.code}: {msg}")
        except Exception as exc:  # noqa: BLE001
            return subprocess.CompletedProcess(args=["agent"], returncode=1, stdout="", stderr=f"No se pudo conectar al agente: {exc}")

    def add_trusted_host(self, host_or_ip: str) -> subprocess.CompletedProcess:
        script = (
            "$existing=(Get-Item WSMan:\\localhost\\Client\\TrustedHosts).Value;"
            f"$new='{host_or_ip}';"
            "if ([string]::IsNullOrWhiteSpace($existing)) {"
            "Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value $new -Force;"
            "} elseif ($existing -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -eq $new }) {"
            "Write-Output 'already-present';"
            "} else {"
            "Set-Item WSMan:\\localhost\\Client\\TrustedHosts -Value ($existing + ',' + $new) -Force;"
            "}"
        )
        return self._run_local_powershell(script)

    def shutdown(self, target_ip: str) -> subprocess.CompletedProcess:
        if self.agent.enabled:
            via_agent = self._invoke_agent(target_ip, "shutdown")
            if via_agent.returncode == 0:
                return via_agent
        return self._invoke_remote_script(target_ip, "Stop-Computer -Force")

    def restart(self, target_ip: str) -> subprocess.CompletedProcess:
        if self.agent.enabled:
            via_agent = self._invoke_agent(target_ip, "restart")
            if via_agent.returncode == 0:
                return via_agent
        return self._invoke_remote_script(target_ip, "Restart-Computer -Force")

    def apply_internet_policy(self, target_ip: str, policy: InternetPolicy) -> subprocess.CompletedProcess:
        if self.agent.enabled:
            via_agent = self._invoke_agent(target_ip, "policy", policy=policy)
            if via_agent.returncode == 0:
                return via_agent
        return self._invoke_remote_script(target_ip, policy.to_powershell())

    @staticmethod
    def format_error(stderr: str, stdout: str = "") -> str:
        raw = (stderr or "").strip() or (stdout or "").strip()
        if not raw:
            return "Error remoto desconocido"

        cleaned = ClassroomController._extract_clixml(raw)
        if "AccessDenied" in raw or "Acceso denegado" in cleaned:
            return (
                "Acceso denegado en remoto. Usa credenciales con permisos de administrador local, "
                "o despliega el modo Agente en los equipos de alumnos para control sin WinRM."
            )
        if "ServerNotTrusted" in raw or "TrustedHosts" in cleaned or "ServerNotTrusted" in cleaned:
            return (
                "WinRM no confía en el equipo remoto. "
                "Activa 'Auto-agregar IPs a TrustedHosts' en la barra lateral, "
                "o agrega manualmente la IP/host en el PC del profesor, "
                "o usa WinRM por HTTPS (5986)."
            )
        return cleaned

    @staticmethod
    def _extract_clixml(text: str) -> str:
        start = text.find("<Objs")
        if start == -1:
            return re.sub(r"\s+", " ", text).strip()

        xml_text = text[start:]
        try:
            root = ElementTree.fromstring(xml_text)
            messages: list[str] = []
            for node in root.iter():
                if node.tag.endswith("S") and (node.text or "").strip():
                    value = node.text.replace("_x000D_", " ").replace("_x000A_", " ")
                    messages.append(value.strip())
            if messages:
                joined = " ".join(messages)
                return re.sub(r"\s+", " ", joined).strip()
        except ElementTree.ParseError:
            pass

        return re.sub(r"\s+", " ", text).strip()
