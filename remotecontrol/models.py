from dataclasses import dataclass, field


@dataclass(slots=True)
class Host:
    ip: str
    name: str | None = None
    mac: str | None = None
    online: bool = False
    tags: list[str] = field(default_factory=list)
