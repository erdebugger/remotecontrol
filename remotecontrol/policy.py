from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class InternetPolicy:
    mode: str  # "allow_all", "block_all", "allow_list"
    allowed_domains: list[str] = field(default_factory=list)
    allowed_ips: list[str] = field(default_factory=list)
    allowed_dns_servers: list[str] = field(default_factory=list)

    def validate(self) -> None:
        valid_modes = {"allow_all", "block_all", "allow_list"}
        if self.mode not in valid_modes:
            raise ValueError(f"Modo inválido: {self.mode}")

        if self.mode == "allow_list" and not (self.allowed_domains or self.allowed_ips):
            raise ValueError("allow_list requiere al menos un dominio o una IP permitida")

    def to_powershell(self) -> str:
        self.validate()

        lines = [
            "$ErrorActionPreference = 'Stop'",
            "$group = 'RemoteControlAula'",
            "Get-NetFirewallRule -Group $group -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue",
        ]

        if self.mode == "allow_all":
            lines.append("# Sin restricciones de Internet")
            return "\n".join(lines)

        if self.mode == "block_all":
            lines.extend(
                [
                    "New-NetFirewallRule -DisplayName 'RCA-Block-All-Out' -Group $group -Direction Outbound -Action Block -Enabled True -Profile Any",
                ]
            )
            return "\n".join(lines)

        # allow_list
        lines.extend(
            [
                "New-NetFirewallRule -DisplayName 'RCA-Default-Block-Out' -Group $group -Direction Outbound -Action Block -Enabled True -Profile Any",
            ]
        )

        for dns in self.allowed_dns_servers:
            lines.append(
                "New-NetFirewallRule "
                f"-DisplayName 'RCA-Allow-DNS-{dns}' -Group $group -Direction Outbound "
                f"-Action Allow -Enabled True -Protocol UDP -RemotePort 53 -RemoteAddress {dns} -Profile Any"
            )
            lines.append(
                "New-NetFirewallRule "
                f"-DisplayName 'RCA-Allow-DNS-TCP-{dns}' -Group $group -Direction Outbound "
                f"-Action Allow -Enabled True -Protocol TCP -RemotePort 53 -RemoteAddress {dns} -Profile Any"
            )

        for ip in self.allowed_ips:
            lines.append(
                "New-NetFirewallRule "
                f"-DisplayName 'RCA-Allow-IP-{ip}' -Group $group -Direction Outbound "
                f"-Action Allow -Enabled True -RemoteAddress {ip} -Profile Any"
            )

        for domain in self.allowed_domains:
            safe = domain.replace("*", "wild")
            lines.append(
                "New-NetFirewallRule "
                f"-DisplayName 'RCA-Allow-FQDN-{safe}' -Group $group -Direction Outbound "
                f"-Action Allow -Enabled True -RemoteFqdn {domain} -Profile Any"
            )

        return "\n".join(lines)
