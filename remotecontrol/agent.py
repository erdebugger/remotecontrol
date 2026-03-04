from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .policy import InternetPolicy


class AgentHandler(BaseHTTPRequestHandler):
    token: str = ""

    def do_POST(self):  # noqa: N802
        if self.path != "/execute":
            self._send(404, {"ok": False, "error": "Not found"})
            return

        size = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(size)
        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "JSON inválido"})
            return

        if payload.get("token") != self.token:
            self._send(403, {"ok": False, "error": "Token inválido"})
            return

        action = payload.get("action")
        if action == "shutdown":
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Stop-Computer -Force"], capture_output=True, text=True)
            return self._result(proc)

        if action == "restart":
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Restart-Computer -Force"], capture_output=True, text=True)
            return self._result(proc)

        if action == "policy":
            policy_data = payload.get("policy") or {}
            policy = InternetPolicy(
                mode=policy_data.get("mode", "allow_all"),
                allowed_domains=list(policy_data.get("allowed_domains", [])),
                allowed_ips=list(policy_data.get("allowed_ips", [])),
                allowed_dns_servers=list(policy_data.get("allowed_dns_servers", [])),
            )
            script = policy.to_powershell()
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
            return self._result(proc)

        self._send(400, {"ok": False, "error": f"Acción no soportada: {action}"})

    def log_message(self, format, *args):  # noqa: A003
        return

    def _result(self, proc: subprocess.CompletedProcess):
        if proc.returncode == 0:
            self._send(200, {"ok": True, "message": "ok"})
        else:
            self._send(500, {"ok": False, "error": proc.stderr or proc.stdout or "Error"})

    def _send(self, code: int, obj: dict):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_agent(host: str = "0.0.0.0", port: int = 8765, token: str = "changeme"):
    AgentHandler.token = token
    httpd = ThreadingHTTPServer((host, port), AgentHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    run_agent()
