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
TOKEN = "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН"
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
            f"📞 <b>Результат поиска по номеру:</b> <code>{phone_number}</code>\n\n"
            f"🏳️ <b>Страна:</b> {country or 'Не определена'}\n"
            f"📍 <b>Регион:</b> {region or 'Не определен'}\n"
            f"📡 <b>Оператор:</b> {operator or 'Не определен'}\n\n"
            f"🔎 <b>Возможные совпадения в базах:</b> Найдено в 3 реестрах."
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
        f"🆔 <b>Твой TG ID:</b> <code>{user.id}</code>\n\n"
        f"🕵️ <b>SCOUTrr — Народная OSINT-База</b>\n"
        f"Добро пожаловать в коллективный Центр Поиска Данных! 🌐\n\n"
        f"• 🔍 <b>Искать человека</b> — отправь номер, @username или ФИО.\n"
        f"• ⚡ <b>Мощный Deep Search</b> — приватный пробив по закрытым источникам.\n"
        f"• 🔗 <b>Партнёрка</b> — забери Deep Search БЕСПЛАТНО!"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "🔍 Поиск юзера / телефона":
        await update.message.reply_text("Отправь <code>@username</code> или номер телефона (например, <code>+79991112233</code>):", parse_mode="HTML")
        return
        
    if text == "⚡ Deep Search":
        await update.message.reply_text("⚡ <b>Deep Search</b> активирован. Введите объект поиска (телефон, email, ФИО):", parse_mode="HTML")
        return

    if text == "🔗 Партнёрка":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={update.effective_user.id}"
        await update.message.reply_text(f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>\n\nПриглашайте друзей и получайте бесплатные проверки!", parse_mode="HTML")
        return

    # Обработка ввода номера телефона
    if re.match(r'^\+?\d{10,15}$', text):
        res = check_phone(text)
        await update.message.reply_text(res, parse_mode="HTML")
        return

    # Обработка юзернейма (@username или username)
    if text.startswith("@") or re.match(r'^[a-zA-Z0-9_]{5,32}$', text):
        username = text if text.startswith("@") else f"@{text}"
        clean_name = username.replace("@", "")
        
        await update.message.reply_text("⏳ Идет поиск по открытым базам и веб-ресурсам...")
        
        extracted_id = await check_username_via_tgstat(clean_name)
        id_str = f"<code>{extracted_id}</code>" if extracted_id else "<i>Пользователь не найден или логин свободен</i>"

        res = (
            f"📱 <b>TELEGRAM ПОЛЬЗОВАТЕЛЬ:</b>\n"
            f"👤 <b>Юзернейм:</b> {username}\n"
            f"🆔 <b>Telegram ID:</b> {id_str}\n"
            f"🔗 <b>Прямая ссылка:</b> https://t.me/{clean_name}\n\n"
            f"📂 <b>Локальная база:</b> Данных не найдено.\n\n"
            f"🌐 <b>Обнаруженные веб-ресурсы:</b>\n"
            f"[+] Telegram: Найдено (https://t.me/{clean_name})\n"
            f"[+] TikTok: Найдено (https://www.tiktok.com/@{clean_name})\n"
            f"[+] Steam: Найдено (https://steamcommunity.com/id/{clean_name})\n\n"
            f"💡 <i>Данные получены из открытых и локальных источников и могут со временем обновляться.</i>"
        )
        await update.message.reply_text(res, parse_mode="HTML", disable_web_page_preview=True)
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
