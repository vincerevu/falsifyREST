"""Small HTTP forwarding proxy that records normalized black-box traffic as JSONL."""
import argparse
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class CaptureProxy:
    def __init__(self, upstream: str, trace_path: str | Path):
        self.upstream = upstream.rstrip("/")
        self.trace_path = Path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def handler(self):
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def _forward(self):
                length = int(self.headers.get("Content-Length", "0"))
                request_body = self.rfile.read(length) if length else None
                headers = {key: value for key, value in self.headers.items() if key.lower() not in {"host", "connection", "content-length"}}
                request = urllib.request.Request(proxy.upstream + self.path, data=request_body, headers=headers, method=self.command)
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        status, response_headers, raw = response.status, dict(response.headers.items()), response.read()
                except urllib.error.HTTPError as error:
                    status, response_headers, raw = error.code, dict(error.headers.items()) if error.headers else {}, error.read()
                except urllib.error.URLError as error:
                    status, response_headers, raw = 599, {}, str(error).encode()
                self.send_response(status)
                for key, value in response_headers.items():
                    if key.lower() not in {"connection", "transfer-encoding", "content-length"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                try:
                    response_body = json.loads(raw.decode()) if raw else None
                except (UnicodeDecodeError, json.JSONDecodeError):
                    response_body = raw.decode(errors="replace")
                try:
                    parsed_request = json.loads(request_body.decode()) if request_body else {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    parsed_request = {}
                explicit_resource_id = self.headers.get("X-FalsifyREST-Resource-Id")
                features = {key: value for key, value in {
                    "resource_type": self.headers.get("X-FalsifyREST-Resource-Type"),
                    "owner": self.headers.get("X-FalsifyREST-Resource-Owner"),
                }.items() if value is not None}
                record = {"status_code": status, "method": self.command, "endpoint": self.path.split("?", 1)[0],
                          "actor": self.headers.get("X-FalsifyREST-Actor", "anonymous"), "request_query": {},
                          "request_body": parsed_request, "response_body": response_body, "response_headers": response_headers,
                          "extracted_ids": {"resource_id": explicit_resource_id} if explicit_resource_id else {}, "features": features,
                          "timestamp": time.time()}
                with proxy._lock, proxy.trace_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, default=str) + "\n")

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = _forward

        return Handler

    def serve(self, host: str, port: int) -> None:
        ThreadingHTTPServer((host, port), self.handler()).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3002)
    args = parser.parse_args()
    CaptureProxy(args.upstream, args.trace).serve(args.host, args.port)


if __name__ == "__main__":
    main()
