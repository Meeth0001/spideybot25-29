import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from portal_client import PortalClient
from result_parser import parse_semesters, parse_results, format_result_message
from config import TELEGRAM_BOT_TOKEN, PORTAL_BASE_URL

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Conversation states
MOBILE, PASSWORD = range(2)


# ── Minimal health-check HTTP server ─────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # suppress access logs


def start_health_server(port: int = 8000):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info("Health-check server listening on :%d", port)


# ── Telegram Bot handlers ─────────────────────────────────────────────────────

async def safe_reply(message, text, **kwargs):
    try:
        return await message.reply_text(text, **kwargs)
    except TimedOut:
        logger.warning("Telegram timed out while sending message: %s", text[:80])
    except TelegramError as e:
        logger.warning("Telegram send failed: %s", e)
    return None


async def safe_edit(query, text, **kwargs):
    try:
        return await query.edit_message_text(text, **kwargs)
    except TimedOut:
        logger.warning("Telegram timed out while editing message: %s", text[:80])
    except TelegramError as e:
        logger.warning("Telegram edit failed: %s", e)
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    keyboard = [
        [InlineKeyboardButton("📚 2nd Semester Notes", callback_data="menu_notes")],
        [InlineKeyboardButton("📊 Results Portal", callback_data="menu_results")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_reply(
        update.message,
        "Welcome to the JSS STU Student Portal Bot!\n\n"
        "Please select an option below:",
        reply_markup=reply_markup
    )

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the main menu selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_notes":
        keyboard = [
            [InlineKeyboardButton("📅 Academic Calendar", url="https://drive.google.com/file/d/1Y17VzPOWrjFOBzSS89tOdUddVojwZd_j/view?usp=drive_link")],
            [InlineKeyboardButton("🔵 P Cycle", callback_data="notes_pcycle")],
            [InlineKeyboardButton("🟢 C Cycle", callback_data="notes_ccycle")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(
            query,
            "📚 <b>2nd Semester Notes</b>\n\nSelect a cycle to explore:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    elif query.data == "notes_pcycle":
        keyboard = [
            [InlineKeyboardButton("📅 P Cycle 2025-26", url="https://drive.google.com/file/d/1ZbHxEqPqAQ6gQHaTpsTwB2HE4KH-yGMu/view")],
            [InlineKeyboardButton("⚡ Elements of Electrical Engg", callback_data="pcycle_eee")],
            [InlineKeyboardButton("⚙️ Elements of Mechanical Engg", callback_data="pcycle_eme")],
            [InlineKeyboardButton("🔭 Physics", callback_data="pcycle_phy")],
            [InlineKeyboardButton("⬅️ Back to Notes", callback_data="menu_notes")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(
            query,
            "🔵 <b>P Cycle — 2nd Semester</b>\n\nSelect a subject:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    # ── P Cycle: Elements of Electrical Engineering (Unit 2-5) ──────────────
    elif query.data == "pcycle_eee":
        keyboard = [
            [InlineKeyboardButton("📘 Unit 2", url="https://drive.google.com/file/d/1mLNdHwNwwc0aqt4LKIZ0o7MOUcJ5kp6l/view?usp=drive_link")],
            [InlineKeyboardButton("📘 Unit 3", url="https://drive.google.com/file/d/1zm9QkcxQfKF3i8Pbg4Ji81Nul3BzOHMa/view?usp=drive_link")],
            [InlineKeyboardButton("📘 Unit 4", url="https://drive.google.com/file/d/1uv4H7jIdEGr3kpw0WTeODQAR3u3ohL_S/view?usp=drive_link")],
            [InlineKeyboardButton("📘 Unit 5", url="https://drive.google.com/file/d/1AdoILO4GI2kn1o2XmUajib41gxIJOa1D/view?usp=drive_link")],
            [InlineKeyboardButton("⬅️ Back to P Cycle", callback_data="notes_pcycle")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(
            query,
            "⚡ <b>Elements of Electrical Engineering</b>\n<i>Units 2 – 5</i>\n\nSelect a unit:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    # ── P Cycle: Elements of Mechanical Engineering (Unit 1-5) ──────────────
    elif query.data == "pcycle_eme":
        keyboard = [
            [InlineKeyboardButton("📙 Unit 1", url="https://drive.google.com/file/d/1daAtjPUUsUe9cdrUo4DP3TIdx1WK7XwO/view?usp=drive_link")],
            [InlineKeyboardButton("📙 Unit 2", url="https://drive.google.com/file/d/1bZRYBzWF_T7wQTdbI7GtDqPDeH7zsAJN/view?usp=drive_link")],
            [InlineKeyboardButton("📙 Unit 3", url="https://drive.google.com/file/d/13eslK3sKHFqYXf-Me4tl49foITqPYtuO/view?usp=drive_link")],
            [InlineKeyboardButton("📙 Unit 4", url="https://drive.google.com/file/d/1aW9jkg1bLS3Y_BKwL32MS4JjV5L3MQxs/view?usp=drive_link")],
            [InlineKeyboardButton("📙 Unit 5", url="https://drive.google.com/file/d/1Loog61Ht5lGNBfLGPd7li3QbcVzBL-G6/view?usp=drive_link")],
            [InlineKeyboardButton("⬅️ Back to P Cycle", callback_data="notes_pcycle")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(
            query,
            "⚙️ <b>Elements of Mechanical Engineering</b>\n<i>Units 1 – 5</i>\n\nSelect a unit:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    # ── P Cycle: Physics (Unit 1-4) ──────────────────────────────────────────
    elif query.data == "pcycle_phy":
        keyboard = [
            [InlineKeyboardButton("🔬 Unit 1", url="https://drive.google.com/file/d/1kzK95W7hc4v2rySrJDiDTjXS7eJ5MtDY/view?usp=drive_link")],
            [InlineKeyboardButton("🔬 Unit 2", url="https://drive.google.com/file/d/1NYMYIz1qmrc5LbZqv4yNAay0PVL1ylKL/view?usp=drive_link")],
            [InlineKeyboardButton("🔬 Unit 3", url="https://drive.google.com/file/d/1ThPIL7Y5gyuah0Jr2Qu26GpF6pQXMucS/view?usp=drive_link")],
            [InlineKeyboardButton("🔬 Unit 4", url="https://drive.google.com/file/d/1Lp0Nz05IZU1cXpXvnwhuNJbiB5XaNSbL/view?usp=drive_link")],
            [InlineKeyboardButton("⬅️ Back to P Cycle", callback_data="notes_pcycle")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(
            query,
            "🔭 <b>Physics</b>\n<i>Units 1 – 4</i>\n\nSelect a unit:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    elif query.data == "notes_ccycle":
        keyboard = [
            [InlineKeyboardButton("📝 C Cycle Notes", url="https://eng-batman.github.io/batman/")],
            [InlineKeyboardButton("⬅️ Back to Notes", callback_data="menu_notes")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(
            query,
            "🟢 <b>C Cycle — 2nd Semester</b>\n\nSelect a resource:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif query.data == "menu_results":
        if "portal_client" in context.user_data and context.user_data["portal_client"].is_authenticated:
            await safe_edit(query, "✅ You are already logged in!\n\nUse /result to view your grades.")
        else:
            await safe_edit(query, "🔐 <b>Authentication Required</b>\n\nYou need to login to view results.\nPlease type /login to authenticate.", parse_mode="HTML")
    elif query.data == "menu_back":
        keyboard = [
            [InlineKeyboardButton("📚 2nd Semester Notes", callback_data="menu_notes")],
            [InlineKeyboardButton("📊 Results Portal", callback_data="menu_results")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit(
            query,
            "Welcome to the JSS STU Student Portal Bot!\n\n"
            "Please select an option below:",
            reply_markup=reply_markup
        )


async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the login conversation and asks for mobile number."""
    # We allow the user to log in again even if they are already logged in to switch accounts
    if "portal_client" in context.user_data and context.user_data["portal_client"].is_authenticated:
        await safe_reply(update.message, "You are already logged in, but you can enter new credentials to switch accounts.")
        
    await safe_reply(
        update.message,
        "Please enter your registered mobile number:\n"
        "(Type /cancel to abort)"
    )
    return MOBILE

async def login_mobile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores mobile number and asks for password."""
    context.user_data['mobile'] = update.message.text
    await safe_reply(update.message, "Please enter your password:")
    return PASSWORD

async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Authenticates the user using the provided password."""
    mobile = context.user_data.get('mobile')
    password = update.message.text
    
    # Immediately delete the message containing the password if possible for privacy
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete password message: {e}")
        
    await safe_reply(update.message, "Authenticating...")
    
    client = PortalClient()
    success = await asyncio.to_thread(client.login, mobile, password)
    
    # We never store the password in user_data, only the authenticated session object
    if success:
        context.user_data['portal_client'] = client
        await safe_reply(update.message, "Login successful.\n\nUse /result to fetch your results.")
    else:
        await safe_reply(update.message, "Login failed. Please check your credentials and try /login again.")
        
    # Clear the mobile from user_data just in case
    context.user_data.pop('mobile', None)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels and ends the conversation."""
    await safe_reply(update.message, "Login cancelled.")
    context.user_data.pop('mobile', None)
    return ConversationHandler.END

async def result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches available exams and shows them as inline buttons. Can also accept an explicit examno like /result A-2025-2."""
    if "portal_client" not in context.user_data or not context.user_data["portal_client"].is_authenticated:
        await safe_reply(update.message, "You need to /login first.")
        return

    client = context.user_data["portal_client"]
    
    # Check if user provided an explicit examno, e.g. /result A-2025-2
    args = context.args
    if args:
        examno = args[0]
        await safe_reply(update.message, f"Fetching results for custom exam ID: {examno}...")
        
        raw_result = await asyncio.to_thread(client.get_result, examno)
        result_data = parse_results(raw_result)
        
        message = format_result_message(result_data)
        keyboard = [[InlineKeyboardButton("View on Portal", url=PORTAL_BASE_URL)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_reply(update.message, message, reply_markup=reply_markup, parse_mode="HTML")
        return

    # If no arguments provided, show impressive informational text
    info_text = (
        "🎓 <b>JSS STU Results Quick Access</b>\n"
        "<i>(Batch 2025-2029)</i>\n\n"
        "To instantly fetch your results, click or type the specific command for your semester:\n\n"
        "<b>1️⃣ First Year</b>\n"
        " ├ 1st Sem: <code>/result A-2025-2</code>\n"
        " └ 2nd Sem: <code>/result A-2026-1</code>\n\n"
        "<b>2️⃣ Second Year</b>\n"
        " ├ 3rd Sem: <code>/result A-2026-2</code>\n"
        " └ 4th Sem: <code>/result A-2027-1</code>\n\n"
        "<b>3️⃣ Third Year</b>\n"
        " ├ 5th Sem: <code>/result A-2027-2</code>\n"
        " └ 6th Sem: <code>/result A-2028-1</code>\n\n"
        "<b>4️⃣ Fourth Year</b>\n"
        " ├ 7th Sem: <code>/result A-2028-2</code>\n"
        " └ 8th Sem: <code>/result A-2029-1</code>\n\n"
        "💡 <i>Tip: You can simply tap on any of the blue commands above to instantly run it!</i>"
    )
    await safe_reply(update.message, info_text, parse_mode="HTML")

async def semester_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles exam selection and fetches results."""
    query = update.callback_query
    await query.answer()
    
    if "portal_client" not in context.user_data or not context.user_data["portal_client"].is_authenticated:
        await safe_edit(query, "Session expired. Please /login again.")
        return
        
    examno = query.data.removeprefix("sem_")
    client = context.user_data["portal_client"]
    
    await safe_edit(query, "Fetching results...")
    
    raw_result = await asyncio.to_thread(client.get_result, examno)
    result_data = parse_results(raw_result)
    
    message = format_result_message(result_data)
    
    # Add a link to the portal
    keyboard = [[InlineKeyboardButton("View on Portal", url=PORTAL_BASE_URL)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit(query, message, reply_markup=reply_markup, parse_mode="HTML")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs the user out by clearing the session data."""
    context.user_data.pop("portal_client", None)
    await safe_reply(update.message, "You have been logged out successfully.")

def main():
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("Please set the TELEGRAM_BOT_TOKEN in config.py or .env file.")
        return

    # Start minimal health-check HTTP server in a background daemon thread
    start_health_server(port=8000)

    # Create the application
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Login Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={
            MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_mobile)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("result", result))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(conv_handler)
    
    # Callback Query Handlers for Inline Buttons
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^notes_"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^pcycle_"))
    application.add_handler(CallbackQueryHandler(semester_callback, pattern="^sem_"))

    # Start the Bot
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
