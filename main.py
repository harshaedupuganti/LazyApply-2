from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

from core.database import init_db
from core.gemini_client import GeminiClient
import core.gemini_client as gemini_module
import config

app = FastAPI(title="AutoApply AI", version="1.0.0")

@app.on_event("startup")
async def startup():
    await init_db()
    keys = [k for k in [config.GEMINI_API_KEY_1, config.GEMINI_API_KEY_2] if k]
    if not keys:
        print("WARNING: No Gemini API keys configured in .env")
    else:
        gemini_module.gemini = GeminiClient(keys)
        print(f"✅ Gemini client initialized with {len(keys)} key(s)")

@app.get("/health")
async def health():
    return {"status": "ok", "message": "AutoApply AI is running"}

@app.get("/")
async def root():
    with open("frontend/index.html") as f:
        return HTMLResponse(f.read())

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)