from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.routers import demo, health, sessions

app = FastAPI(title="ADAPTIA API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)
install_error_handlers(app)

for router in (health.router, demo.router, sessions.router):
    app.include_router(router, prefix="/api")
