"""
Main FastAPI application for YouTube Contextual Product Pipeline.
Entry point for the API server.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.config import settings
from api.database import init_db
from api.routers import (
    campaigns_router,
    keywords_router,
    youtube_router,
    scoring_router,
    transcript_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.
    Initializes database on startup.
    """
    # Startup
    print("🚀 Starting YouTube Contextual Product Pipeline API...")
    init_db()
    print("✅ API is ready!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down API...")


# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(campaigns_router, prefix="/api/campaign")
app.include_router(keywords_router, prefix="/api")
app.include_router(youtube_router, prefix="/api")  # Added YouTube router
app.include_router(scoring_router, prefix="/api")
app.include_router(transcript_router, prefix="/api")



@app.get("/")
def root():
    """Root endpoint - API health check."""
    return {
        "message": "YouTube Contextual Product Pipeline API",
        "version": settings.api_version,
        "status": "healthy",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "YouTube Contextual Product Pipeline API",
        "version": settings.api_version
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload
    )
