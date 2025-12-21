from datetime import datetime

def log(msg: str):
    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] {msg}")
