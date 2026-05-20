import threading
import webbrowser

import uvicorn

from config import settings
from main import app


def open_browser() -> None:
    webbrowser.open(f"http://{settings.server_host}:{settings.server_port}")


if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()
    uvicorn.run(app, host=settings.server_host, port=settings.server_port, reload=False)
