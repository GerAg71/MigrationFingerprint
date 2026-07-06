"""REST API (MS-3.1): FastAPI app over the identical engine (spec Ch. 18)."""

from src.api.app import app, create_app

__all__ = ["app", "create_app"]
