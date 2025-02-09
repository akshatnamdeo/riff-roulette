from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health, upload, song_fetching  # Import the new songs router
from app.api import websocket
from app.core.local_config import local_config
from app.core.service_container import ServiceContainer
from contextlib import asynccontextmanager
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO if local_config.DEBUG else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

services = ServiceContainer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app"""
    # Startup
    logging.info("Starting Riff Roulette API")
    await services.initialize()
    
    yield
    
    # Shutdown
    logging.info("Shutting down Riff Roulette API")
    await services.cleanup()

# Initialize FastAPI app
app = FastAPI(
    title="Riff Roulette",
    description="Real-time music improvisation game",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(upload.router, tags=["upload"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(song_fetching.router, tags=["song_fetching"])  # Register the new songs router

# Make services available to routes
app.state.services = services

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=local_config.HOST,
        port=local_config.PORT,
        reload=local_config.DEBUG
    )
