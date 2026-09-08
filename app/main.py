from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import uploads, analyses, skymap, auth, admin
import app.models # Ensure all SQLAlchemy models are registered

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup hook
    print(f"Starting {settings.PROJECT_NAME}...")
    yield
    # Shutdown hook
    print(f"Shutting down {settings.PROJECT_NAME}...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
import os

# Ensure uploads directory exists so StaticFiles doesn't crash on startup
os.makedirs("uploads/profiles", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(uploads.router, prefix=f"{settings.API_V1_STR}/uploads", tags=["uploads"])
app.include_router(analyses.router, prefix=f"{settings.API_V1_STR}/analyses", tags=["analyses"])
app.include_router(skymap.router, prefix=f"{settings.API_V1_STR}/skymap", tags=["skymap"])
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail}
    )

@app.get("/")
def root():
    return {"message": "Welcome to Stellaris API"}

@app.get(f"{settings.API_V1_STR}/healthz")
def healthz():
    return {"status": "ok"}

@app.get(f"{settings.API_V1_STR}/metrics")
def metrics():
    # Placeholder for prometheus metrics
    return {"status": "metrics_will_go_here"}
