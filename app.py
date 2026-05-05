import os
import socket
import uvicorn
from main import app


def _is_port_in_use(host: str, port: int) -> bool:
    # Use bind-based check so 0.0.0.0 listeners are detected reliably on Windows.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return False
        except OSError:
            return True


def _find_available_port(host: str, start_port: int, max_tries: int = 20) -> int:
    for port in range(start_port, start_port + max_tries):
        if not _is_port_in_use(host, port):
            return port
    raise RuntimeError(
        f"No free port found in range {start_port}-{start_port + max_tries - 1}"
    )

def _get_lan_ip() -> str:
    # Best-effort LAN IP discovery for showing a mobile-friendly URL.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    pythonhost = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    if _is_port_in_use(pythonhost, port):
        next_port = _find_available_port(pythonhost, port + 1)
        print(f"Port {port} busy hai, switching to {next_port}")
        port = next_port
    lan_ip = _get_lan_ip()
    print(f"Laptop URL: http://127.0.0.1:{port}/app")
    print(f"Mobile URL: http://{lan_ip}:{port}/app")
    uvicorn.run(
        app,
        host=pythonhost,
        port=port,
        reload=False,
        log_level="warning",
        access_log=False,
    )
