"""Start the app and open it in the browser: `python run.py`."""

import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8000

if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"MediaGala is running at {url} (press Ctrl+C to stop)")
    # Give the server a moment to start before opening the browser.
    threading.Timer(1.5, webbrowser.open, args=[url]).start()
    uvicorn.run("app.main:app", host=HOST, port=PORT)
