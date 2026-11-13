"""The web layer: one page, and one endpoint that streams results as they arrive."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Callable

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.config import Settings
from app.errors import LookupFailure
from app.fetch.base import PageFetcher
from app.models import Fingerprint
from app.service import LookupService

PAGE = Path(__file__).parent / "static" / "index.html"
log = logging.getLogger("product-matcher")

Builder = Callable[[Settings], tuple[LookupService, PageFetcher]]


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def _product(fingerprint: Fingerprint) -> dict:
    source = fingerprint.source
    return {"title": source.title, "url": source.url, "brand": source.brand,
            "model": source.model, "category": fingerprint.category_label,
            "matched_on": fingerprint.matched_on, "platforms": fingerprint.platforms,
            "matching": fingerprint.matching, "notes": fingerprint.notes}


def create_app(builder: Builder | None = None) -> FastAPI:
    """`builder` lets tests supply a service fed from saved pages."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if builder is None:
            from app.container import build
            make = build
        else:
            make = builder
        app.state.service, app.state.fetcher = make(Settings.from_env())
        yield
        await app.state.fetcher.close()

    app = FastAPI(title="Product matcher", lifespan=lifespan)

    @app.get("/")
    async def page() -> FileResponse:
        return FileResponse(PAGE)

    @app.get("/config")
    async def config() -> dict:
        """What the page needs to know before the first lookup."""
        service = app.state.service
        return {"ai_available": service.ai_available, "ai_label": service.ai_label}

    @app.get("/check")
    async def check(url: str = Query(..., max_length=2000),
                    ai: bool = Query(False)) -> StreamingResponse:
        service: LookupService = app.state.service

        async def stream() -> AsyncIterator[str]:
            try:
                async for event in service.check(url.strip(), use_ai=ai):
                    if isinstance(event, Fingerprint):
                        yield _event("product", _product(event))
                    else:
                        yield _event("result", event.model_dump(mode="json"))
            except LookupFailure as failure:
                yield _event("failed", {"message": failure.message})
            except Exception:
                log.exception("lookup crashed")
                yield _event("failed", {"message": "Something went wrong while checking"})
            yield _event("done", {})

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
