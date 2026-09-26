import json
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional, List

from core.database import get_db, Job, Resume
from agents.skill_extractor import SkillExtractor
import core.gemini_client as gemini_module
from scrapers.naukri import NaukriScraper
from scrapers.linkedin import LinkedInScraper

router = APIRouter()

class AddJobRequest(BaseModel):
    url: str
    resume_id: str

class SearchJobsRequest(BaseModel):
    keywords: str
    location: str = ""
    platforms: List[str]
    max_results: int = 25
    resume_id: str

@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(Job)
    
    if status:
        query = query.where(Job.status == status)
    if min_score is not None:
        query = query.where(Job.match_score >= min_score)
        
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return [
        {
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "platform": j.platform,
            "status": j.status,
            "match_score": j.match_score,
            "url": j.url,
            "created_at": j.created_at
        }
        for j in jobs
    ]

@router.post("/jobs/add-url")
async def add_job_url(req: AddJobRequest, db: AsyncSession = Depends(get_db)):
    # 1. Fetch Resume to get skills
    result = await db.execute(select(Resume).where(Resume.id == req.resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    resume_skills = []
    if resume.extracted_skills:
        try:
            resume_skills = json.loads(resume.extracted_skills)
        except json.JSONDecodeError:
            pass
            
    # 2. Fetch Job Page
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(req.url, timeout=10.0)
            resp.raise_for_status()
            html_text = resp.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")

    # 3. Extract Job Details using BeautifulSoup
    soup = BeautifulSoup(html_text, "html.parser")
    
    job_title = None
    company_name = "Unknown Company"
    job_description = None
    
    # Try og tags
    og_title = soup.find("meta", property="og:title")
    if og_title:
        job_title = og_title.get("content")
        
    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        job_description = og_desc.get("content")
        
    # Fallback to h1 for title
    if not job_title:
        h1 = soup.find("h1")
        if h1:
            job_title = h1.get_text(strip=True)
            
    # Fallback description to generic page text if missing
    if not job_description:
        job_description = soup.get_text(separator=" ", strip=True)[:1000]

    # 4. If extraction fails or is sparse, use Gemini
    if gemini_module.gemini and (not job_title or len(job_description) < 100):
        prompt = f"""Extract job_title, company_name, job_description from this page text. JSON only.
Page text (truncated): {soup.get_text(separator=" ", strip=True)[:3000]}"""
        
        try:
            llm_res = await gemini_module.gemini.generate(prompt, json_mode=True, max_tokens=500)
            if llm_res:
                data = json.loads(llm_res)
                job_title = data.get("job_title", job_title or "Unknown Job")
                company_name = data.get("company_name", company_name)
                job_description = data.get("job_description", job_description)
        except Exception as e:
            print(f"Job parsing Gemini fallback failed: {e}")

    # Fallback default values if all extraction methods failed completely
    if not job_title:
        job_title = "Unknown Job"
    if not job_description:
        job_description = "No description found."

    # 5. Analyze Fit
    extractor = SkillExtractor()
    fit_analysis = await extractor.analyze_job_fit(resume_skills, job_description)
    
    # 6. Save to Job table
    # Simple heuristic to determine platform
    platform = "custom"
    url_lower = req.url.lower()
    if "linkedin.com" in url_lower:
        platform = "linkedin"
    elif "naukri.com" in url_lower:
        platform = "naukri"
    elif "indeed.com" in url_lower:
        platform = "indeed"

    db_job = Job(
        title=job_title[:255],
        company=company_name[:255],
        url=req.url,
        platform=platform,
        description=job_description,
        match_score=fit_analysis.get("match_score", 0),
        status="NEW"
    )
    
    db.add(db_job)
    try:
        await db.commit()
        await db.refresh(db_job)
    except Exception as e:
        await db.rollback()
        # Handle unique constraint violation on URL
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="Job with this URL already exists")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    return {
        "job": {
            "id": db_job.id,
            "title": db_job.title,
            "company": db_job.company,
            "platform": db_job.platform,
            "url": db_job.url,
            "match_score": db_job.match_score
        },
        "analysis": fit_analysis
    }

@router.post("/jobs/search")
async def search_jobs(req: SearchJobsRequest, db: AsyncSession = Depends(get_db)):
    # 1. Fetch Resume and skills
    result = await db.execute(select(Resume).where(Resume.id == req.resume_id))
    resume = result.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    resume_skills = []
    if resume.extracted_skills:
        try:
            resume_skills = json.loads(resume.extracted_skills)
        except json.JSONDecodeError:
            pass
            
    all_jobs = []
    
    # 2. Run Scraping based on requested platforms
    for platform in req.platforms:
        p_lower = platform.lower()
        if p_lower == "naukri":
            scraper = NaukriScraper()
            scraped_jobs = await scraper.search(req.keywords, req.location, req.max_results)
            all_jobs.extend(scraped_jobs)
        elif p_lower == "linkedin":
            scraper = LinkedInScraper()
            try:
                scraped_jobs = await scraper.search(req.keywords, req.location, req.max_results)
                all_jobs.extend(scraped_jobs)
            finally:
                await scraper.close()
        elif p_lower == "indeed":
            print(f"Platform {p_lower} scraper not yet implemented. Skipping.")
        else:
            print(f"Unknown platform requested: {p_lower}")

    # 3. Analyze Job fit and Update Match Scores in DB
    extractor = SkillExtractor()
    processed_jobs = []
    
    for job_dict in all_jobs:
        # Use description for analysis if available, otherwise title
        desc_to_analyze = job_dict.get("description")
        if not desc_to_analyze:
            desc_to_analyze = job_dict.get("title", "")
            
        fit_analysis = await extractor.analyze_job_fit(resume_skills, desc_to_analyze)
        score = fit_analysis.get("match_score", 0)
        
        job_dict["match_score"] = score
        job_dict["recommendation"] = fit_analysis.get("recommendation", "SKIP")
        
        # Update DB job with calculated score
        if "id" in job_dict:
            db_result = await db.execute(select(Job).where(Job.id == job_dict["id"]))
            db_job = db_result.scalars().first()
            if db_job:
                db_job.match_score = score
                await db.commit()
                
        processed_jobs.append(job_dict)
        
    return {
        "total_found": len(processed_jobs),
        "jobs": processed_jobs
    }