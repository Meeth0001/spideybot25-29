import os
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file if present
    load_dotenv()
except ImportError:
    pass

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# Portal URLs
PORTAL_BASE_URL = "https://studentportal.universitysolutions.in"

PORTAL_LOGIN_URL = f"{PORTAL_BASE_URL}/signin.php"
PORTAL_PROFILE_URL = f"{PORTAL_BASE_URL}/src/profile.php"
PORTAL_SEMESTERS_URL = f"{PORTAL_BASE_URL}/src/results_new.php?a=getExamno"
PORTAL_RESULTS_URL = f"{PORTAL_BASE_URL}/src/results_new.php?a=getResults"

# Default User-Agent to simulate a real browser
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded",
}
