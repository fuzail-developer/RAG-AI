import os
import uvicorn
from main import app

if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    print(f"Starting CogniVault on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=False)
