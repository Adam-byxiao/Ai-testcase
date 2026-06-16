from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from blueprint_main.api.routes import router as blueprint_main_router


app = FastAPI(
    title="Blueprint Main API",
    description="Structured blueprint pipeline for snapshot, graph, and tree generation.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blueprint_main_router)


@app.get("/healthz", tags=["System"])
def healthcheck():
    return {"ok": True}

