from fastapi import APIRouter
from datetime import datetime

router = APIRouter(
    prefix="/health",
    tags=["health"]
)

@router.get("/")
async def health_check():
    """Health check endpoint for load balancer"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "riff-roulette-api"
    }