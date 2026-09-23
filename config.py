import os
from dotenv import load_dotenv

load_dotenv()

# Gemini
GEMINI_API_KEY_1 = os.getenv("GEMINI_API_KEY_1", "")
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "")
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"
MAX_TOKENS_PER_CALL = 1000
RPM_LIMIT = 15

# Platform credentials
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL", "")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD", "")

# CAPTCHA
CAPTCHA_MODE = os.getenv("CAPTCHA_MODE", "manual")
TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY", "")
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY", "")

# App behaviour
AUTO_SUBMIT = os.getenv("AUTO_SUBMIT", "false").lower() == "true"
MAX_APPLICATIONS_PER_DAY = int(os.getenv("MAX_APPLICATIONS_PER_DAY", "50"))
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")
BROWSER_PROFILES_DIR = os.path.join(BASE_DIR, "browser_profiles")
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'autoapply.db')}"

# Create directories on import
for d in [UPLOAD_DIR, SCREENSHOT_DIR, BROWSER_PROFILES_DIR]:
    os.makedirs(d, exist_ok=True)