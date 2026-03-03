from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass

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

        encoded = self._pwsh_encoded(invoke)
        cmd = ["powershell", "-NoProfile", "-EncodedCommand", encoded]
        return subprocess.run(cmd, capture_output=True, text=True)

    def shutdown(self, target_ip: str) -> subprocess.CompletedProcess:
        return self._invoke_remote_script(target_ip, "Stop-Computer -Force")

    def restart(self, target_ip: str) -> subprocess.CompletedProcess:
        return self._invoke_remote_script(target_ip, "Restart-Computer -Force")

    def apply_internet_policy(self, target_ip: str, policy: InternetPolicy) -> subprocess.CompletedProcess:
        return self._invoke_remote_script(target_ip, policy.to_powershell())
