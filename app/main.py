import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.limiter import limiter
from app.routers import auth, demo, health, lecturer, p1, sessions, student

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# Log klien HTTP memuat URL Supabase; cukup tampilkan peringatan.
for noisy in ("httpx", "httpx2", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

app = FastAPI(
    title="ADAPTIA API",
    version="1.0.0",
    description="AI mengusulkan, aturan memverifikasi, dosen memutuskan. Login di sini adalah mode demo, "
                "bukan autentikasi.",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)
install_error_handlers(app)


@app.exception_handler(RateLimitExceeded)
async def _rate_limited(_: Request, exc: RateLimitExceeded):
    return JSONResponse({"error": {"code": "rate_limited", "message": f"Terlalu banyak permintaan ({exc.detail})."}},
                        status_code=429)


for router in (health.router, auth.router, demo.router, sessions.router, student.router, lecturer.router, p1.router):
    app.include_router(router, prefix="/api")
