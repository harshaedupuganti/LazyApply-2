import os
import re
import asyncio

import config

class CaptchaHandler:
    def __init__(self, mode: str = None):
        self.mode = mode or config.CAPTCHA_MODE or "manual"

    async def solve(self, page, captcha_type: str = "auto") -> bool:
        """Detect and solve CAPTCHA on the current page."""
        
        if captcha_type == "auto":
            recaptcha_v2 = await page.locator("iframe[src*='recaptcha']").count() > 0
            hcaptcha = await page.locator("iframe[src*='hcaptcha']").count() > 0
            cloudflare = await page.locator("iframe[src*='challenges.cloudflare']").count() > 0
            
            if recaptcha_v2: 
                captcha_type = "recaptcha_v2"
            elif hcaptcha: 
                captcha_type = "hcaptcha"
            elif cloudflare: 
                captcha_type = "cloudflare"
            else: 
                return True  # No CAPTCHA detected

        if self.mode == "manual":
            print(f"⚠️ {captcha_type} CAPTCHA detected!")
            print("   Please solve it in the browser window.")
            await asyncio.to_thread(input, "   Press Enter here when done...")
            return True

        if self.mode == "2captcha" and captcha_type == "recaptcha_v2":
            return await self._solve_with_2captcha_recaptcha(page)

        # Fallback to manual for anything we can't auto-solve or if mode is unknown
        print(f"⚠️ Cannot auto-solve {captcha_type} with mode '{self.mode}', falling back to manual")
        print("   Please solve CAPTCHA in the browser window.")
        await asyncio.to_thread(input, "   Press Enter here when done...")
        return True

    async def _solve_with_2captcha_recaptcha(self, page) -> bool:
        try:
            from twocaptcha import TwoCaptcha
        except ImportError:
            print("❌ twocaptcha package not installed. Run: pip install 2captcha-python")
            print("   Falling back to manual mode...")
            await asyncio.to_thread(input, "   Solve manually, press Enter...")
            return True
            
        solver = TwoCaptcha(config.TWOCAPTCHA_API_KEY)
        
        # Extract site key from iframe src
        iframe = page.locator("iframe[src*='recaptcha']").first
        iframe_src = await iframe.get_attribute("src")
        
        sitekey_match = re.search(r'k=([A-Za-z0-9_-]+)', iframe_src)
        if not sitekey_match:
            print("❌ Could not extract reCAPTCHA sitekey, falling back to manual")
            await asyncio.to_thread(input, "   Solve manually, press Enter...")
            return True
        
        sitekey = sitekey_match.group(1)
        page_url = page.url
        
        print(f"   Sending reCAPTCHA to 2captcha service...")
        try:
            # We run the synchronous solver in a background thread to prevent blocking FastAPI
            result = await asyncio.to_thread(solver.recaptcha, sitekey=sitekey, url=page_url)
            token = result['code']
            
            # Inject the token directly into the DOM
            await page.evaluate(f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                if (typeof ___grecaptcha_cfg !== 'undefined') {{
                    try {{ ___grecaptcha_cfg.clients[0].aa.l.callback('{token}'); }} catch(e) {{}}
                }}
            """)
            await asyncio.sleep(2)
            print("✅ CAPTCHA solved automatically!")
            return True
        except Exception as e:
            print(f"❌ 2captcha solver failed: {e}")
            await asyncio.to_thread(input, "   Solve manually, press Enter...")
            return True