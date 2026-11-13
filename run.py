"""Start the website:  python run.py   then open http://127.0.0.1:8000

Started this way (not with `uvicorn --reload`) so that Windows uses the event
loop Playwright needs to launch a browser.
"""

import asyncio
import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    config = uvicorn.Config(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
    asyncio.run(uvicorn.Server(config).serve())
