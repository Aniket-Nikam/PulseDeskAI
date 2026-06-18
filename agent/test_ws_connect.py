import websocket
import threading
import time
import json

ws_url = "ws://localhost:8000/api/v1/ws/screen-stream"
device_token = "a6797787991a2d2889d0f0cfee1759a3fcf5c122f64c61f9312188429da5b36b"
print(f"Testing WebSocketApp connection to: {ws_url}")

result = {"connected": False, "error": None, "message": None, "close_code": None}
done = threading.Event()


def on_open(ws):
    result["connected"] = True
    print("on_open: Connected!")


def on_message(ws, msg):
    result["message"] = msg
    print(f"on_message: {msg[:200]}")
    ws.close()
    done.set()


def on_error(ws, err):
    result["error"] = str(err)
    print(f"on_error: {err}")
    done.set()


def on_close(ws, code, msg):
    result["close_code"] = code
    print(f"on_close: code={code}, msg={msg}")
    done.set()


ws = websocket.WebSocketApp(
    ws_url,
    header=[f"X-Device-Token: {device_token}"],
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
)

t = threading.Thread(target=ws.run_forever, daemon=True)
t.start()
done.wait(timeout=10)

print(f"\nResult: connected={result['connected']}")
print(f"Error: {result['error']}")
print(f"Close code: {result['close_code']}")
if result["message"]:
    print(f"Message: {result['message'][:200]}")
else:
    print("Message: None")
