import os
import json
from fastapi import APIRouter
from pydantic import BaseModel

import config

router = APIRouter()
SETTINGS_FILE = os.path.join(config.BASE_DIR, "settings.json")

@router.post("/api/settings")
async def save_settings(settings: dict):
    # Read existing settings to merge them
    existing = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            pass
            
    # Merge and save
    existing.update(settings)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(existing, f, indent=4)
        
    # Reload relevant config values dynamically into the running instance
    if "set-max-apps" in settings:
        config.MAX_APPLICATIONS_PER_DAY = int(settings["set-max-apps"])
    if "set-auto-submit" in settings:
        # Convert string/bool combinations
        config.AUTO_SUBMIT = str(settings["set-auto-submit"]).lower() == 'true'
    if "captcha" in settings:
        config.CAPTCHA_MODE = settings["captcha"]
        
    return {"success": True}

@router.get("/api/settings")
async def get_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
        
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            
        # Mask passwords before sending to the frontend
        masked_settings = {}
        for k, v in settings.items():
            k_lower = k.lower()
            if "pass" in k_lower or "key" in k_lower or "gemini" in k_lower:
                masked_settings[k] = "****" if v else ""
            else:
                masked_settings[k] = v
                
        return masked_settings
    except json.JSONDecodeError:
        return {}