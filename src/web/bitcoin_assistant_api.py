try:
    from fastapi import FastAPI
except Exception:
    # Minimal stub if FastAPI not installed
    class FastAPI:  # type: ignore
        def __init__(self):
            self.routes = []

app = FastAPI()
