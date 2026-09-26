import httpx
from bs4 import BeautifulSoup
from sqlalchemy.future import select

import config
from core.database import async_session, Job

async def save_jobs(jobs_data: list[dict]) -> list[dict]:
    """Helper function to save indeed jobs to DB, checking for duplicates."""
    saved_jobs = []
    async with async_session() as db:
        for job_dict in jobs_data:
            url = job_dict.get("url")
            if not url:
                continue
                
            # Check for duplicate
            result = await db.execute(select(Job).where(Job.url == url))
            existing = result.scalars().first()
            
            if not existing:
                db_job = Job(
                    title=job_dict.get("title", "Unknown")[:255],
                    company=job_dict.get("company", "Unknown")[:255],
                    location=job_dict.get("location", "")[:255],
                    url=url,
                    platform=job_dict.get("platform", "indeed"),
                    description=job_dict.get("description", ""),
                    is_easy_apply=job_dict.get("is_easy_apply", False),
                    status="NEW"
                )
                db.add(db_job)
                await db.commit()
                await db.refresh(db_job)
                job_dict["id"] = db_job.id
                saved_jobs.append(job_dict)
            else:
                job_dict["id"] = existing.id
                saved_jobs.append(job_dict)
                
    return saved_jobs

class IndeedScraper:
    async def search(self, keywords: str, location: str = "", max_results: int = 25) -> list[dict]:
        url = "https://www.indeed.com/jobs"
        params = {"q": keywords, "l": location, "fromage": "1", "sort": "date"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, params=params, headers=headers)
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Indeed frequently changes class names to deter scraping
            cards = soup.find_all("div", class_="job_seen_beacon")
            if not cards:
                cards = soup.find_all("div", attrs={"data-jk": True})
                
            jobs = []
            for card in cards:
                if len(jobs) >= max_results:
                    break
                    
                title_elem = card.find("h2", class_="jobTitle")
                title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
                
                company_elem = card.find("span", attrs={"data-testid": "company-name"})
                company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
                
                location_elem = card.find("div", attrs={"data-testid": "text-location"})
                job_location = location_elem.get_text(strip=True) if location_elem else "Unknown Location"
                
                job_id = card.get("data-jk", "")
                if not job_id:
                    a_tag = card.find("a", attrs={"data-jk": True})
                    if a_tag:
                        job_id = a_tag.get("data-jk", "")
                        
                job_url = f"https://www.indeed.com/viewjob?jk={job_id}" if job_id else None
                
                if job_url:
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": job_location,
                        "url": job_url,
                        "platform": "indeed",
                        "description": title,
                        "is_easy_apply": False,
                        "status": "NEW"
                    })
                    
            if not jobs:
                print("Indeed scraping blocked — try LinkedIn or Naukri instead")
                return []
                
            return await save_jobs(jobs)
            
        except Exception as e:
            print(f"Indeed scraping failed: {e}")
            print("Indeed scraping blocked — try LinkedIn or Naukri instead")
            return []