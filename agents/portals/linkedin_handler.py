import asyncio
from agents.intelligent_form_filler import IntelligentFormFiller

async def handle_linkedin_easy_apply(page, job: dict, resume: dict) -> dict:
    """Handle LinkedIn Easy Apply multi-step flow."""
    filler = IntelligentFormFiller()
    
    # Click Easy Apply button
    try:
        btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
        if await btn.count() > 0:
            await btn.click()
            await asyncio.sleep(2)
        else:
            return {"success": False, "error": "Easy Apply button not found on page"}
    except Exception as e:
        return {"success": False, "error": f"Could not click Easy Apply: {e}"}
    
    step = 1
    max_steps = 10
    
    while step <= max_steps:
        # Check if we're done
        if await page.locator("h3:has-text('Application submitted')").count() > 0:
            print("   ✅ LinkedIn Easy Apply submitted!")
            return {"success": True, "screenshot": None}
            
        print(f"   Processing Easy Apply Step {step}...")
        
        # Fill current step's form
        await filler.fill(page, resume, job, auto_submit=False)
        
        # Click Next or Submit
        clicked_next = False
        for btn_text in ["Submit application", "Review", "Next"]:
            btn = page.locator(f"button:has-text('{btn_text}')").first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(2)
                clicked_next = True
                break
                
        if not clicked_next:
            return {"success": False, "error": "No navigation button found in Easy Apply modal"}
        
        step += 1
    
    return {"success": False, "error": "Max steps exceeded in Easy Apply"}