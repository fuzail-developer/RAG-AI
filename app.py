import os
import socket
import uvicorn
from main import app


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _find_available_port(host: str, start_port: int, max_tries: int = 20) -> int:
    for port in range(start_port, start_port + max_tries):
        if not _is_port_in_use(host, port):
            return port
    raise RuntimeError(
        f"No free port found in range {start_port}-{start_port + max_tries - 1}"
    )


if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    requested_port = int(os.getenv("API_PORT", "8000"))
    port = _find_available_port(host, requested_port)

    if port != requested_port:
        print(
            f"Port {requested_port} is already in use. "
            f"Starting CogniVault on available port {port}."
        )
    else:
        print(f"Starting CogniVault on http://{host}:{port}")

    uvicorn.run(app, host=host, port=port, reload=False)
