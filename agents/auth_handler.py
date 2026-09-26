import asyncio
import urllib.parse
import config

class AuthHandler:
    """This class handles keeping platform sessions alive."""
    
    async def verify_and_refresh(self, platform: str, page) -> bool:
        """Check if logged in; attempt re-login if not."""
        p_lower = platform.lower()
        
        if p_lower == "linkedin":
            try:
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                
                # Resilient check applied from Block 7
                parsed_url = urllib.parse.urlparse(page.url)
                if parsed_url.path.strip("/") == "feed":
                    return True
            except Exception as e:
                print(f"AuthHandler checking LinkedIn feed failed: {e}")

            # Not logged in - need to re-login
            print("AuthHandler: LinkedIn session expired or missing. Initiating login...")
            from scrapers.linkedin import LinkedInScraper
            scraper = LinkedInScraper()
            try:
                # Ensure the scraper builds its internal browser/page objects before calling login
                await scraper._ensure_browser()
                success = await scraper.login()
                return success
            finally:
                await scraper.close()
        
        if p_lower == "naukri":
            # Naukri uses stateless HTTP — just check if we have credentials
            return bool(config.NAUKRI_EMAIL and config.NAUKRI_PASSWORD)
        
        # Unknown platform, assume ok
        return True