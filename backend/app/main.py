"""FastAPI entry point for the Intelligent Email Assistant."""

from fastapi import APIRouter, FastAPI

app = FastAPI(title="Intelligent Email Assistant")
api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api)
