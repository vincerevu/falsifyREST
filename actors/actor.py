from dataclasses import dataclass, field


@dataclass
class Actor:
    id: str
    role: str
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    token: str | None = None

    def request_headers(self) -> dict[str, str]:
        headers = dict(self.headers)
        if self.token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.cookies:
            headers.setdefault("Cookie", "; ".join(f"{key}={value}" for key, value in self.cookies.items()))
        return headers
