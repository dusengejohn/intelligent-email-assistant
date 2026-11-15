"""FastAPI entry point for the Intelligent Email Assistant."""

from fastapi import FastAPI

app = FastAPI(title="Intelligent Email Assistant")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
