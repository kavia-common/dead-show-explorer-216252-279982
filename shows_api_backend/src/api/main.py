from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import get_settings
from src.api import models  # noqa: F401  - ensure models are imported and metadata is available

settings = get_settings()

app = FastAPI(
    title="Grateful Dead Show Explorer API",
    description="REST API for browsing Grateful Dead live shows, authentication, and favorites.",
    version="0.1.0",
    contact={"name": "Show Explorer", "url": "https://example.com"},
    openapi_tags=[
        {"name": "System", "description": "System status and metadata"},
        {"name": "Users", "description": "User accounts and authentication"},
        {"name": "Shows", "description": "Shows, tracks, and search"},
        {"name": "Favorites", "description": "User favorites management"},
    ],
)

# Configure CORS based on environment settings
origins = settings.cors_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="Health Check", tags=["System"])
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON payload with basic service status message.
    """
    return {"message": "Healthy"}

# Note: For development convenience you may enable automatic table creation at startup:
# In production, use migrations (alembic) instead.
# @app.on_event("startup")
# async def _startup() -> None:
#     await init_models()
