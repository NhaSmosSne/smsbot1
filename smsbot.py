import telebot
import requests
import time
from telebot import types
import datetime
import os
from collections import defaultdict

# ================== CHANGE THESE TWO LINES ONLY ==================
BOT_TOKEN = '8546740798:AAFRlHzSRFYsnZUeZ0Bsz6YL2LqfQVYLmEc'          # from @BotFather
SMS_API_KEY = 'YODCmDukcmvKJda3J21QxiIy39KG6MB2'          # from smsbower.app profile
# =================================================================

# === PERMISSION CONTROL ===
ALLOWED_USER_IDS = [
    1134429449,          # ← REPLACE THIS WITH YOUR REAL TELEGRAM ID (required!)
    7400961650,        # ← add friends/teammates here if you want to share access
    # 555555555,
]

# Only the first ID in the list is considered the owner (can use /stats)
OWNER_ID = ALLOWED_USER_IDS[0]

LOG_FILE = 'purchases.log'

# Service settings (GRAB - Australia)
SERVICE = 'jg'
COUNTRY = 175
MAX_PRICE = 0.004

bot = telebot.TeleBot(BOT_TOKEN)
current_id = None  # active number ID (shared for simplicity)

def is_allowed(chat_id):
    return chat_id in ALLOWED_USER_IDS

def log_purchase(user_id, username, phone):
    today = datetime.date.today().isoformat()
    line = f"{today} | user:{user_id} | @{username if username else 'unknown'} | phone:{phone}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line)

def get_daily_stats():
    if not os.path.exists(LOG_FILE):
        return "No purchases logged yet."

    daily_counts = defaultdict(lambda: defaultdict(int))
    user_names = {}

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.strip().split(' | ')
            if len(parts) < 3:
                continue
            date = parts[0]
            user_part = parts[1]
            # username part may be in the line after @
            if '@' in line:
                uname_part = line.split('@')[1].split(' | ')[0].strip()
                user_id_str = user_part.split(':')[1]
                user_names[user_id_str] = uname_part

            user_id = user_part.split(':')[1]
            daily_counts[date][user_id] += 1

    if not daily_counts:
        return "No purchases logged yet."

    lines = ["📊 Daily purchase stats (user ID → count)\n"]
    for date in sorted(daily_counts.keys(), reverse=True):
        lines.append(f"\n{date}:")
        for uid, count in sorted(daily_counts[date].items(), key=lambda x: x[1], reverse=True):
            uname = user_names.get(uid, 'unknown')
            lines.append(f"  • {uid} (@{uname}) → {count} numbers")

    return "\n".join(lines)

@bot.message_handler(commands=['start'])
def start(msg):
    if not is_allowed(msg.chat.id):
        bot.reply_to(msg, "🚫 Sorry, this bot is private. You don't have access.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('💰 Balance', '📲 Get Number')
    bot.send_message(msg.chat.id, 
        "✅ Welcome! Bot ready for GRAB (Australia).\n\n"
        "Use buttons or commands:\n"
        "/number   /status   /cancel   /done   /stats (owner only)",
        reply_markup=markup
    )

@bot.message_handler(commands=['balance'])
def get_balance(msg):
    if not is_allowed(msg.chat.id):
        bot.reply_to(msg, "🚫 Access denied.")
        return
    r = requests.get(f"https://smsbower.page/stubs/handler_api.php?api_key={SMS_API_KEY}&action=getBalance")
    bot.reply_to(msg, f"💰 Balance: {r.text}")

@bot.message_handler(commands=['number'])
def get_number(msg):
    if not is_allowed(msg.chat.id):
        bot.reply_to(msg, "🚫 Access denied.")

        return

    global current_id
    url = f"https://smsbower.page/stubs/handler_api.php?api_key={SMS_API_KEY}&action=getNumber&service={SERVICE}&country={COUNTRY}&maxPrice={MAX_PRICE}"
    r = requests.get(url)
    
    if 'ACCESS_NUMBER' in r.text:
        parts = r.text.split(':')
        current_id = parts[1]
        phone = parts[2]
        
        # Log successful purchase
        username = msg.from_user.username if msg.from_user.username else None
        log_purchase(msg.chat.id, username, phone)
        
        bot.reply_to(msg, f"✅ **Number ready!**\n📱 +{phone}\n🆔 ID: {current_id}\n\nSend /status to check code")
    else:
        bot.reply_to(msg, f"❌ {r.text} (maybe no stock or price too high?)")

@bot.message_handler(commands=['status'])
def check_status(msg):
    if not is_allowed(msg.chat.id):
        bot.reply_to(msg, "🚫 Access denied.")
        return
    if not current_id:
        bot.reply_to(msg, "No active number. Send /number first.")
        return
    
    r = requests.get(f"https://smsbower.page/stubs/handler_api.php?api_key={SMS_API_KEY}&action=getStatus&id={current_id}")
    text = r.text
    if 'STATUS_OK:' in text:
        code = text.split(':')[1]
        bot.reply_to(msg, f"🔑 **CODE RECEIVED:** `{code}`")
    else:
        bot.reply_to(msg, f"⏳ {text}")

@bot.message_handler(commands=['cancel', 'done'])
def finish(msg):
    if not is_allowed(msg.chat.id):
        bot.reply_to(msg, "🚫 Access denied.")
        return
    global current_id
    if not current_id:
        bot.reply_to(msg, "No active number to finish.")
        return
    
    status = '8' if msg.text == '/cancel' else '6'
    r = requests.get(f"https://smsbower.page/stubs/handler_api.php?api_key={SMS_API_KEY}&action=setStatus&status={status}&id={current_id}")
    bot.reply_to(msg, f"✅ {r.text}")
    current_id = None

@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.chat.id != OWNER_ID:
        bot.reply_to(msg, "🚫 Only the bot owner can use /stats")
        return
    
    summary = get_daily_stats()
    bot.reply_to(msg, summary)

@bot.message_handler(func=lambda m: True)
def keyboard(msg):
    if not is_allowed(msg.chat.id):
        bot.reply_to(msg, "🚫 Access denied.")
        return
    
    if msg.text == '💰 Balance':
        get_balance(msg)
    elif msg.text == '📲 Get Number':
        get_number(msg)

print("🚀 Bot is running with access control & stats...")
bot.polling()
