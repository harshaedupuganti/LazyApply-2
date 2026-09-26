import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy.future import select

from core.database import async_session, Job

async def save_jobs(jobs_data: list[dict]) -> list[dict]:
    """Helper function to save jobs to DB, checking for URL duplicates."""
    saved_jobs = []
    async with async_session() as db:
        for job_dict in jobs_data:
            url = job_dict["url"]
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
                    platform=job_dict.get("platform", "naukri"),
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

class NaukriScraper:
    async def search(self, keywords: str, location: str = "", max_results: int = 25) -> list[dict]:
        """Scrape Naukri job listings. Returns list of job dicts."""
        jobs = []
        
        # APPROACH 1 — Try Naukri's internal API (fast, no browser)
        try:
            url = "https://www.naukri.com/jobapi/v3/search"
            params = {
                "noOfResults": min(max_results, 20),
                "urlType": "search_by_keyword",
                "searchType": "adv",
                "keyword": keywords,
                "location": location,
                "pageNo": 1,
                "functionAreaIdGte": 0,
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "appid": "109",
                "systemid": "Naukri",
                "Referer": "https://www.naukri.com/",
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params, headers=headers)
                
            if response.status_code == 200:
                data = response.json()
                if "jobDetails" in data:
                    for job in data["jobDetails"]:
                        job_url = job.get("jdURL", "")
                        if job_url.startswith("/"):
                            job_url = f"https://www.naukri.com{job_url}"
                            
                        desc_html = job.get("jobDescription", "")
                        desc_text = BeautifulSoup(desc_html, "html.parser").get_text(separator=" ", strip=True) if desc_html else ""
                        
                        placeholders = job.get("placeholders", [])
                        loc = placeholders[0].get("label", "") if placeholders else ""
                        
                        # External apply redirect means it's not Easy Apply
                        is_easy = not bool(job.get("applyRedirectUrl"))
                        
                        jobs.append({
                            "title": job.get("title", ""),
                            "company": job.get("companyName", ""),
                            "location": loc,
                            "url": job_url,
                            "description": desc_text,
                            "platform": "naukri",
                            "is_easy_apply": is_easy
                        })
        except Exception as e:
            print(f"Naukri API search failed: {e}")

        # APPROACH 2 — Fall back to Playwright scraping if API fails or returns nothing
        if not jobs:
            print("Falling back to Playwright for Naukri...")
            jobs = await self._playwright_search(keywords, location, max_results)
            
        jobs = jobs[:max_results]
        return await save_jobs(jobs)

    async def _playwright_search(self, keywords: str, location: str, max_results: int) -> list[dict]:
        jobs = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                kw_fmt = keywords.replace(" ", "-").lower()
                loc_fmt = location.replace(" ", "-").lower()
                
                if loc_fmt:
                    url = f"https://www.naukri.com/{kw_fmt}-jobs-in-{loc_fmt}"
                else:
                    url = f"https://www.naukri.com/{kw_fmt}-jobs"
                    
                await page.goto(url, wait_until="domcontentloaded")
                
                try:
                    await page.wait_for_selector('article.jobTuple, div[class*="jobTuple"]', timeout=10000)
                except Exception:
                    print("Playwright: Job selector not found on Naukri.")
                    await browser.close()
                    return []
                    
                js_code = """
                () => {
                    const cards = Array.from(document.querySelectorAll('article.jobTuple, div[class*="jobTuple"]'));
                    return cards.map(card => {
                        const titleEl = card.querySelector('a.title');
                        const companyEl = card.querySelector('a.subTitle, a.comp-name');
                        const locEl = card.querySelector('span.locWdth');
                        return {
                            title: titleEl ? titleEl.innerText.trim() : "",
                            url: titleEl ? titleEl.href : "",
                            company: companyEl ? companyEl.innerText.trim() : "",
                            location: locEl ? locEl.innerText.trim() : ""
                        };
                    });
                }
                """
                extracted = await page.evaluate(js_code)
                for item in extracted:
                    if item["url"] and item["title"]:
                        item["platform"] = "naukri"
                        item["description"] = item["title"]  # Missing description in list view, fallback to title
                        item["is_easy_apply"] = False
                        jobs.append(item)
                        
                await browser.close()
        except Exception as e:
            print(f"Playwright fallback failed: {e}")
            
        return jobs