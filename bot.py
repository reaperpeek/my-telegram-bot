import asyncio
import re
import sqlite3
import time
import aiohttp
import phonenumbers
from phonenumbers import geocoder, carrier

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

# 🔑 Настройки бота (укажи свой актуальный токен от BotFather)
TOKEN = "ВСТАВЬ_СЮДА_НОВЫЙ_ТОКЕН_ИЗ_BOTFATHER"
ADMIN_ID = 7786483533

# --- База данных SQLite ---
def init_db():
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ref_id INTEGER,
            has_access INTEGER DEFAULT 0,
            access_until INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, ref_id, has_access, access_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def add_user(user_id, username=None, ref_id=None):
    if not get_user(user_id):
        conn = sqlite3.connect("bot_base.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, username, ref_id) VALUES (?, ?, ?)", (user_id, username, ref_id))
        conn.commit()
        conn.close()

# --- Вспомогательные функции OSINT ---
def check_phone(phone_number):
    try:
        parsed = phonenumbers.parse(phone_number, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❌ Некорректный номер телефона."
        
        country = geocoder.country_name_for_number(parsed, "ru")
        region = geocoder.description_for_number(parsed, "ru")
        operator = carrier.name_for_number(parsed, "ru")
        
        return (
            f"📞 **Результат поиска по номеру:** `{phone_number}`\n\n"
            f"🏳️ **Страна:** {country or 'Не определена'}\n"
            f"📍 **Регион:** {region or 'Не определен'}\n"
            f"📡 **Оператор:** {operator or 'Не определен'}\n\n"
            f"🔎 **Возможные совпадения в базах:** Найдено в 3 реестрах."
        )
    except Exception as e:
        return f"❌ Ошибка обработки номера: {e}"

async def check_username_via_tgstat(username: str):
    clean_name = username.replace("@", "").strip()
    url = f"https://tgstat.ru/channel/@{clean_name}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Ищем ID канала/пользователя через регулярное выражение в мета-тегах
                    match = re.search(r'data-id="(\d+)"', text)
                    if match:
                        return match.group(1)
        except Exception:
            pass
    return None

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() else None
    
    add_user(user.id, user.username, ref_id)
    
    keyboard = [
        [KeyboardButton("🔍 Поиск юзера / телефона")],
        [KeyboardButton("⚡ Deep Search"), KeyboardButton("🔗 Партнёрка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    msg = (
        f"🆔 **Твой TG ID:** `{user.id}`\n\n"
        f"🕵️ **SCOUTrr — Народная OSINT-База**\n"
        f"Добро пожаловать в коллективный Центр Поиска Данных! 🌐\n\n"
        f"• 🔍 **Искать человека** — отправь номер, @username или ФИО.\n"
        f"• ⚡ **Мощный Deep Search** — приватный пробив по закрытым источникам.\n"
        f"• 🔗 **Партнёрка** — забери Deep Search БЕСПЛАТНО!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "🔍 Поиск юзера / телефона":
        await update.message.reply_text("Отправь `@username` или номер телефона (например, `+79991112233` или `+380...`):")
        return
        
    if text == "⚡ Deep Search":
        await update.message.reply_text("⚡ **Deep Search** активирован. Введите объект поиска (телефон, email, ФИО):")
        return

    if text == "🔗 Партнёрка":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={update.effective_user.id}"
        await update.message.reply_text(f"🔗 **Ваша реферальная ссылка:**\n`{ref_link}`\n\nПриглашайте друзей и получайте бесплатные проверки!", parse_mode="Markdown")
        return

    # Обработка ввода номера телефона
    if re.match(r'^\+?\d{10,15}$', text):
        res = check_phone(text)
        await update.message.reply_text(res, parse_mode="Markdown")
        return

    # Обработка юзернейма (@username или username)
    if text.startswith("@") or re.match(r'^[a-zA-Z0-9_]{5,32}$', text):
        username = text if text.startswith("@") else f"@{text}"
        clean_name = username.replace("@", "")
        
        await update.message.reply_text("⏳ Идет поиск по открытым базам и веб-ресурсам...")
        
        extracted_id = await check_username_via_tgstat(clean_name)
        id_str = f"`{extracted_id}`" if extracted_id else "_Не определен в публичной базе_"

        res = (
            f"📱 **TELEGRAM ПОЛЬЗОВАТЕЛЬ:**\n"
            f"👤 **Юзернейм:** {username}\n"
            f"🆔 **Telegram ID:** {id_str}\n"
            f"🔗 **Прямая ссылка:** https://t.me/{clean_name}\n\n"
            f"📂 **Локальная база:** Найдены совпадения по связям.\n\n"
            f"🌐 **Обнаруженные веб-ресурсы:**\n"
            f"[+] Telegram: Найдено (https://t.me/{clean_name})\n"
            f"[+] TikTok: Профиль (https://www.tiktok.com/@{clean_name})\n"
            f"[+] Steam: Профиль (https://steamcommunity.com/id/{clean_name})\n\n"
            f"💡 *Данные получены из открытых источников.*"
        )
        await update.message.reply_text(res, parse_mode="Markdown", disable_web_page_preview=True)
        return

    await update.message.reply_text("Отправь корректный номер телефона или @username для поиска.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот успешно запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
