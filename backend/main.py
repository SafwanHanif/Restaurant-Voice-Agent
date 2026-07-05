from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import HOST, PORT, RESTAURANT_NAME
from db import init_db
import twilio_routes
import web_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Resolve paths relative to this file so the app works regardless of cwd
HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(HERE, "..", "frontend")

app = FastAPI(title=f"{RESTAURANT_NAME} Voice Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your restaurant's domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(twilio_routes.router)
app.include_router(web_routes.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "restaurant": RESTAURANT_NAME}


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT)
