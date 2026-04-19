"""Frozen backend entrypoint for the Windows release folder."""

from app.config import settings
from app.main import app

import uvicorn


def main() -> None:
    """Start the packaged FastAPI backend without reload mode."""
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
