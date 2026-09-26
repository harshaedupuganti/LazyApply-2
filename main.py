# ============================================================
# AutoApply AI - Fresh Build
# ============================================================
# STARTUP CHECKLIST:
# 1. Copy .env.example to .env and fill your credentials
# 2. Run: bash setup.sh  (installs deps + playwright)
# 3. Run: python main.py
# 4. Visit: http://localhost:8000
# 5. Upload your resume first
# 6. Set AUTO_SUBMIT=false in .env for first 10 applications
# 7. Review each application before enabling auto-submit
# ============================================================

import os
import sys
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List

# Windows-specific event loop policy to prevent Playwright asyncio crashes
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import config
from core.database import init_db
import core.orchestrator as orch

from api.routes_apply import router as apply_router
from api.routes_settings import router as settings_router
from api.routes_resume import router as resume_router

# Setup orchestrator loop globally
app_orchestrator = orch.ApplicationOrchestrator()

# --- Jobs Router (Integrating Indeed and LinkedIn) ---
jobs_router = APIRouter()

class JobSearchRequest(BaseModel):
    keywords: str
    location: str
    platforms: List[str]
    resume_id: str
    max_results: int = 10

@jobs_router.post("/api/jobs/search")
async def search_jobs(payload: JobSearchRequest):
    all_jobs = []
    
    if "linkedin" in payload.platforms:
        from scrapers.linkedin import LinkedInScraper
        li_scraper = LinkedInScraper()
        li_jobs = await li_scraper.search(payload.keywords, payload.location, payload.max_results)
        all_jobs.extend(li_jobs)
        await li_scraper.close()
        
    if "indeed" in payload.platforms:
        from scrapers.indeed import IndeedScraper
        in_scraper = IndeedScraper()
        in_jobs = await in_scraper.search(payload.keywords, payload.location, payload.max_results)
        all_jobs.extend(in_jobs)
        
    return {"jobs": all_jobs, "total_found": len(all_jobs)}

# --- Fast API Application Setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load settings from JSON on startup
    settings_file = os.path.join(config.BASE_DIR, "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                settings = json.load(f)
            if "set-max-apps" in settings:
                config.MAX_APPLICATIONS_PER_DAY = int(settings["set-max-apps"])
            if "set-auto-submit" in settings:
                config.AUTO_SUBMIT = str(settings["set-auto-submit"]).lower() == 'true'
            if "captcha" in settings:
                config.CAPTCHA_MODE = settings["captcha"]
            print("✅ Loaded dynamic settings from settings.json")
        except Exception as e:
            print(f"⚠️ Failed to load settings.json: {e}")
            
    await init_db()
    
    # Start background orchestrator loop
    orchestrator_task = asyncio.create_task(app_orchestrator.run_loop())
    yield
    # Graceful Shutdown
    app_orchestrator.running = False
    orchestrator_task.cancel()

app = FastAPI(lifespan=lifespan)

# Register API Routers
app.include_router(apply_router)
app.include_router(settings_router)
app.include_router(jobs_router)
app.include_router(resume_router)

# Serve Frontend
@app.get("/")
async def serve_frontend():
    index_path = os.path.join(config.BASE_DIR, "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found. Make sure frontend/index.html exists."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)