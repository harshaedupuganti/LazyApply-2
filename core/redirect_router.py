import asyncio
from core.portal_detector import detect_portal, detect_from_page
from agents.portals.linkedin_handler import handle_linkedin_easy_apply
from agents.portals.generic_handler import handle_generic

class RedirectRouter:
    async def handle(self, page, job: dict, resume: dict) -> dict:
        """Navigate to job and apply. Handles redirects to ATS portals."""
        
        try:
            await page.goto(job["url"], wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)
        except Exception as e:
            return {"success": False, "error": f"Failed to load job URL: {e}"}
        
        # Check if this is LinkedIn Easy Apply
        if job.get("is_easy_apply") and "linkedin.com" in job["url"]:
            return await handle_linkedin_easy_apply(page, job, resume)
        
        # Look for apply button and click it
        apply_selectors = [
            "a:has-text('Apply Now')", "button:has-text('Apply Now')",
            "a:has-text('Apply')", "button:has-text('Apply')",
            ".apply-button", "#apply-button", "[class*='apply'][class*='btn']"
        ]
        
        clicked = False
        for sel in apply_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    # Listen for new tab
                    try:
                        async with page.context.expect_page(timeout=5000) as new_page_info:
                            await btn.click()
                        new_page = await new_page_info.value
                        await new_page.wait_for_load_state("domcontentloaded")
                        page = new_page  # Switch to the new tab
                        clicked = True
                        break
                    except Exception:
                        # Fallback if no new tab opened
                        await btn.click()
                        await asyncio.sleep(2)
                        clicked = True
                        break
            except Exception:
                continue
        
        if not clicked:
            return {"success": False, "error": "Could not find Apply button on job page"}
        
        # Detect what ATS we landed on
        current_url = page.url
        portal = detect_portal(current_url)
        if portal == "UNKNOWN":
            portal = await detect_from_page(page)
        
        print(f"   Detected portal: {portal}")
        
        # Route to appropriate handler
        return await handle_generic(page, job, resume, portal)