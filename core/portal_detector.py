def detect_portal(url: str) -> str:
    """Detect ATS type from URL. Returns portal name string."""
    if not url:
        return "UNKNOWN"
        
    url_lower = url.lower()
    
    if "myworkdayjobs.com" in url_lower or "wd1.myworkdayjobs" in url_lower: return "WORKDAY"
    if "taleo.net" in url_lower: return "TALEO"
    if "greenhouse.io" in url_lower or "boards.greenhouse.io" in url_lower: return "GREENHOUSE"
    if "lever.co" in url_lower: return "LEVER"
    if "smartrecruiters.com" in url_lower: return "SMARTRECRUITERS"
    if "icims.com" in url_lower: return "ICIMS"
    if "successfactors.com" in url_lower: return "SUCCESSFACTORS"
    if "bamboohr.com" in url_lower: return "BAMBOOHR"
    if "ashby.io" in url_lower: return "ASHBY"
    if "rippling.com" in url_lower: return "RIPPLING"
    if "linkedin.com/jobs/apply" in url_lower: return "LINKEDIN_EASY_APPLY"
    if "naukri.com" in url_lower: return "NAUKRI_NATIVE"
    if "indeed.com" in url_lower: return "INDEED_NATIVE"
    return "UNKNOWN"

async def detect_from_page(page) -> str:
    """Detect ATS type from page content when URL-based detection fails."""
    try:
        # Check page title
        title = await page.title()
        
        # Check meta tags carefully
        meta_content = ""
        try:
            meta_locator = page.locator("meta[name='application-name']")
            if await meta_locator.count() > 0:
                meta_content = await meta_locator.first.get_attribute("content")
        except Exception:
            pass
            
        checks = (title + " " + (meta_content or "")).lower()
        if "workday" in checks: return "WORKDAY"
        if "greenhouse" in checks: return "GREENHOUSE"
        if "lever" in checks: return "LEVER"
        if "taleo" in checks: return "TALEO"
        
        # Check for vendor-specific DOM patterns
        if await page.locator("[data-automation-id]").count() > 3: return "WORKDAY"
        if await page.locator("form#application-form").count() > 0: return "GREENHOUSE"
        
    except Exception as e:
        print(f"Error during page-based ATS detection: {e}")
        
    return "UNKNOWN"