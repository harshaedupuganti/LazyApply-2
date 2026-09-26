import os
import asyncio
import config
from agents.intelligent_form_filler import IntelligentFormFiller

async def handle_generic(page, job: dict, resume: dict, portal: str = "UNKNOWN") -> dict:
    """Universal handler for any ATS portal."""
    print(f"   Using generic handler for: {portal}")
    
    filler = IntelligentFormFiller()
    
    # Generate cover letter if not present
    if not resume.get("cover_letter"):
        skills_text = ", ".join(resume.get("skills", [])[:3])
        resume["cover_letter"] = f"I am excited to apply for the {job.get('title', 'open')} position at {job.get('company', 'your company')}. With {resume.get('years_experience', 0)} years of experience and expertise in {skills_text}, I believe I would be a strong fit for this role."
    
    result = await filler.fill(page, resume, job, auto_submit=config.AUTO_SUBMIT)
    
    # Take screenshot
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    screenshot_path = os.path.join(config.SCREENSHOT_DIR, f"{job['id']}_{portal}.png")
    
    try:
        await page.screenshot(path=screenshot_path, full_page=True)
        result["screenshot"] = screenshot_path
    except Exception as e:
        print(f"   Warning: Failed to take screenshot: {e}")
        result["screenshot"] = None
        
    return result