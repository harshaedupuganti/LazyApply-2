import asyncio
import random
import config
from core.application_queue import ApplicationQueue
from agents.intelligent_form_filler import IntelligentFormFiller
from core.redirect_router import RedirectRouter

class ApplicationOrchestrator:
    def __init__(self):
        self.queue = ApplicationQueue()
        self.form_filler = IntelligentFormFiller()
        self.redirect_router = RedirectRouter()
        self.running = False
        self.playwright = None
        self.browser = None

    async def start_browser(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=config.HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )

    async def process_next(self):
        item = await self.queue.dequeue()
        if not item:
            return
        
        job = item["job"]
        resume = item["resume"]
        
        print(f"🚀 Applying to: {job.get('title')} at {job.get('company')}")
        
        page = await self.browser.new_page()
        try:
            result = await self.redirect_router.handle(page, job, resume)
            if result["success"]:
                await self.queue.mark_done(item["id"], result.get("screenshot"))
                print(f"✅ Applied successfully!")
            else:
                await self.queue.mark_failed(item["id"], result.get("error"))
                print(f"❌ Failed: {result.get('error')}")
        except Exception as e:
            await self.queue.mark_failed(item["id"], str(e))
            print(f"❌ Fatal Error: {e}")
        finally:
            await page.close()
        
        # Human-like delay between applications
        delay = random.uniform(30, 90)
        print(f"   Waiting {int(delay)}s before next application...")
        await asyncio.sleep(delay)

    async def run_loop(self):
        self.running = True
        await self.start_browser()
        try:
            while self.running:
                stats = await self.queue.get_stats()
                if stats["applied_today"] >= config.MAX_APPLICATIONS_PER_DAY:
                    print(f"Daily limit reached ({config.MAX_APPLICATIONS_PER_DAY}). Stopping for today.")
                    break
                await self.process_next()
                await asyncio.sleep(5)
        finally:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.running = False