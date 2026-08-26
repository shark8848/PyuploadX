"""Alias package so `python -m upload_service` dispatches to app.cli."""

from app.cli import main

__all__ = ["main"]
