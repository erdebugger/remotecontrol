from __future__ import annotations

import base64
import re
import subprocess
from dataclasses import dataclass
from xml.etree import ElementTree

from .policy import InternetPolicy


@dataclass(slots=True)
class Credentials:
    username: str
    password: str


class ClassroomController:
    def __init__(self, credentials: Credentials | None = None):
        self.credentials = credentials

    def _pwsh_encoded(self, script: str) -> str:
        data = script.encode("utf-16le")
        return base64.b64encode(data).decode("ascii")

    def _run_local_powershell(self, script: str) -> subprocess.CompletedProcess:
        encoded = self._pwsh_encoded(script)
        cmd = ["powershell", "-NoProfile", "-EncodedCommand", encoded]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _invoke_remote_script(self, target_ip: str, script: str) -> subprocess.CompletedProcess:
        auth_block = ""
        if self.credentials:
            auth_block = (
                "$sec = ConvertTo-SecureString '{pwd}' -AsPlainText -Force;"
                "$cred = New-Object System.Management.Automation.PSCredential('{usr}',$sec);"
            ).format(usr=self.credentials.username, pwd=self.credentials.password)
            invoke = f"{auth_block} Invoke-Command -ComputerName {target_ip} -Credential $cred -ScriptBlock {{{script}}}"
        else:
            invoke = f"Invoke-Command -ComputerName {target_ip} -ScriptBlock {{{script}}}"

        return self._run_local_powershell(invoke)

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
        return self._invoke_remote_script(target_ip, "Stop-Computer -Force")

    def restart(self, target_ip: str) -> subprocess.CompletedProcess:
        return self._invoke_remote_script(target_ip, "Restart-Computer -Force")

    def apply_internet_policy(self, target_ip: str, policy: InternetPolicy) -> subprocess.CompletedProcess:
        return self._invoke_remote_script(target_ip, policy.to_powershell())

    @staticmethod
    def format_error(stderr: str, stdout: str = "") -> str:
        raw = (stderr or "").strip() or (stdout or "").strip()
        if not raw:
            return "Error remoto desconocido"

        cleaned = ClassroomController._extract_clixml(raw)
        if "ServerNotTrusted" in raw or "TrustedHosts" in cleaned or "ServerNotTrusted" in cleaned:
            return (
                "WinRM no confía en el equipo remoto. "
                "Agrega la IP/host a TrustedHosts en el PC del profesor "
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
