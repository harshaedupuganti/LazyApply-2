import os
import asyncio
import urllib.parse
from playwright.async_api import async_playwright
from sqlalchemy.future import select

import config
from core.database import async_session, Job

async def save_jobs(jobs_data: list[dict]) -> list[dict]:
    """Helper function to save jobs to DB, checking for URL duplicates."""
    saved_jobs = []
    async with async_session() as db:
        for job_dict in jobs_data:
            url = job_dict.get("url")
            if not url:
                continue
                
            result = await db.execute(select(Job).where(Job.url == url))
            existing = result.scalars().first()
            
            if not existing:
                db_job = Job(
                    title=job_dict.get("title", "Unknown")[:255],
                    company=job_dict.get("company", "Unknown")[:255],
                    location=job_dict.get("location", "")[:255],
                    url=url,
                    platform=job_dict.get("platform", "linkedin"),
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

class LinkedInScraper:
    def __init__(self):
        self.browser = None
        self.context = None  
        self.page = None
        self.profile_dir = os.path.join(config.BROWSER_PROFILES_DIR, "linkedin")
        os.makedirs(self.profile_dir, exist_ok=True)

    async def _ensure_browser(self):
        if self.browser:
            return
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=config.HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-web-security",
            ]
        )
        
        session_path = os.path.join(self.profile_dir, "session.json")
        storage_state = session_path if os.path.exists(session_path) else None
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            storage_state=storage_state
        )
        self.page = await self.context.new_page()

    async def _check_logged_in(self) -> bool:
        try:
            # INCREASED TIMEOUT TO 60 SECONDS
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            parsed_url = urllib.parse.urlparse(self.page.url)
            if parsed_url.path.strip("/") == "feed":
                return True
                
            return False
        except Exception as e:
            print(f"Warning while checking login state (Timeout?): {e}")
            # If it timed out but the URL is correct, we are still logged in!
            parsed_url = urllib.parse.urlparse(self.page.url)
            if parsed_url.path.strip("/") == "feed":
                return True
            return False

    async def login(self) -> bool:
        print("Checking LinkedIn login status...")
        if await self._check_logged_in():
            print("✅ LinkedIn already logged in")
            return True
            
        print("Not logged in. Attempting to log in...")
        
        try:
            await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            try:
                username_field = self.page.locator('input#username, input[name="session_key"]').first
                password_field = self.page.locator('input#password, input[name="session_password"]').first
                submit_btn = self.page.locator('button[type="submit"], button[aria-label="Sign in"]').first
                
                await username_field.fill(config.LINKEDIN_EMAIL, timeout=5000)
                await password_field.fill(config.LINKEDIN_PASSWORD, timeout=5000)
                await submit_btn.click(timeout=5000)
                await asyncio.sleep(3)
            except Exception as auto_fill_error:
                print(f"⚠️ Auto-fill failed: {auto_fill_error}")
                
            current_url = self.page.url
            
            if "checkpoint" in current_url or "challenge" in current_url:
                print("⚠️ LinkedIn 2FA required — please complete it in the browser window")
                await asyncio.to_thread(input, "   Press Enter here when done...") 
            
            if await self.page.locator("iframe[src*='recaptcha']").count() > 0:
                print("⚠️ CAPTCHA detected — please solve it in the browser")
                await asyncio.to_thread(input, "   Press Enter here when done...")
            
            if await self._check_logged_in():
                await self.context.storage_state(path=os.path.join(self.profile_dir, "session.json"))
                print("✅ LinkedIn login successful, session saved")
                return True
            else:
                print("❌ LinkedIn login failed (Wrong password or unexpected screen).")
                print("   The browser is open. Please log in manually.")
                await asyncio.to_thread(input, "   Press Enter here when you have successfully logged in...")
                
                if await self._check_logged_in():
                    await self.context.storage_state(path=os.path.join(self.profile_dir, "session.json"))
                    print("✅ LinkedIn manual login successful, session saved")
                    return True
                    
                print("Final login check failed. Aborting.")
                return False
                
        except Exception as e:
            print(f"Fatal Exception during LinkedIn login: {e}")
            return False

    async def search(self, keywords: str, location: str = "", max_results: int = 25) -> list[dict]:
        await self._ensure_browser()
        
        if not await self._check_logged_in():
            success = await self.login()
            if not success:
                print("Search aborted due to login failure.")
                return []
        
        print(f"Starting LinkedIn search for: {keywords} in {location}")
        
        kw = urllib.parse.quote(keywords)
        loc = urllib.parse.quote(location)
        url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&f_TPR=r86400&sortBy=DD"
        
        try:
            # INCREASED TIMEOUT TO 60 SECONDS
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            try:
                await self.page.wait_for_selector(".job-card-container, li[data-occludable-job-id], div[data-job-id]", timeout=15000)
            except Exception:
                print("⚠️ Job cards didn't load in 15 seconds. Trying extraction anyway.")
                
            await asyncio.sleep(2)
        except Exception as e:
            # RESILIENCE FIX: Don't return [] here! Try to extract whatever loaded.
            print(f"Warning: search page took too long to load completely: {e}")
            print("Attempting to scrape whatever loaded on the screen...")
        
        jobs = []
        seen_urls = set()
        scroll_attempts = 0
        
        print("Extracting job cards...")
        while len(jobs) < max_results and scroll_attempts < 5:
            try:
                cards = await self.page.locator(".job-card-container, li[data-occludable-job-id], div[data-job-id]").all()
                
                for card in cards:
                    try:
                        title_el = card.locator("a[href*='/jobs/view/'], a.job-card-list__title, a.job-card-container__link").first
                        
                        if await title_el.count() == 0:
                            continue
                            
                        title = await title_el.inner_text()
                        href = await title_el.get_attribute("href")
                        
                        if not href:
                            continue
                            
                        clean_href = href.split("?")[0] if "?" in href else href
                        
                        if clean_href in seen_urls:
                            continue
                            
                        seen_urls.add(clean_href)
                        
                        company_loc = card.locator(".job-card-container__company-name, .job-card-container__primary-description, span.artdeco-entity-lockup__subtitle").first
                        company = await company_loc.inner_text() if await company_loc.count() > 0 else "Unknown Company"
                        
                        loc_el = card.locator(".job-card-container__metadata-item, ul.job-card-container__metadata li").first
                        location_text = await loc_el.inner_text() if await loc_el.count() > 0 else "Unknown Location"
                        
                        is_easy = await card.locator("span:has-text('Easy Apply'), span:has-text('Apply')").count() > 0
                        
                        jobs.append({
                            "title": title.strip(),
                            "company": company.strip(),
                            "location": location_text.strip(),
                            "url": f"https://www.linkedin.com{clean_href}" if clean_href.startswith("/") else clean_href,
                            "platform": "linkedin",
                            "is_easy_apply": is_easy,
                            "description": title.strip(), 
                            "status": "NEW"
                        })
                    except Exception as loop_err:
                        continue
                    
                    if len(jobs) >= max_results:
                        break
            except Exception as e:
                print(f"Error extracting cards: {e}")
                
            try:
                await self.page.evaluate("""
                    let list = document.querySelector('.jobs-search-results-list');
                    if(list) { list.scrollBy(0, 800); } else { window.scrollBy(0, 800); }
                """)
            except:
                pass
                
            await asyncio.sleep(2)
            scroll_attempts += 1
            
        print(f"Extraction complete. Found {len(jobs)} jobs.")
        final_jobs = jobs[:max_results]
        return await save_jobs(final_jobs)

    async def close(self):
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()