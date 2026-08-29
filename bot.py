import asyncio
import re
import sqlite3
import requests
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import geocoder, carrier
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes
)

TOKEN = "8408315552:AAG5CczuITP2tJnNdMlCnRPXnvXoM6-xSUA"

ALL_SERVICES = {
    "tg": "Telegram",
    "yt": "YouTube",
    "tt": "TikTok",
    "vk": "VK",
    "pin": "Pinterest",
    "red": "Reddit",
    "stm": "Steam",
    "gh": "GitHub",
    "tw": "Twitch",
    "rbl": "Roblox",
    "hb": "Habr"
}

def init_db():
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dossiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_key TEXT UNIQUE,
            full_name TEXT,
            phone TEXT,
            username TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def search_in_db(query_text: str):
    clean_query = query_text.lower().replace("+", "").replace("@", "").strip()
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT full_name, phone, username, notes FROM dossiers 
        WHERE LOWER(search_key) LIKE ? 
           OR LOWER(phone) LIKE ? 
           OR LOWER(username) LIKE ? 
           OR LOWER(full_name) LIKE ?
    ''', (f"%{clean_query}%", f"%{clean_query}%", f"%{clean_query}%", f"%{clean_query}%"))
    results = cursor.fetchall()
    conn.close()
    return results

def add_to_db(search_key: str, full_name: str, phone: str, username: str, notes: str):
    clean_key = search_key.lower().replace("+", "").replace("@", "").strip()
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO dossiers (search_key, full_name, phone, username, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (clean_key, full_name, phone, username, notes))
    conn.commit()
    conn.close()

def get_bottom_keyboard():
    keyboard = [
        [KeyboardButton("🔍 Инструкция"), KeyboardButton("ℹ️ Мой Баланс")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def post_init(application) -> None:
    init_db()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("help", "Инструкция по поиску"),
        BotCommand("add", "Добавить запись в БД")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"🕵️‍♂️ **SCOUTrr OSINT Bot** 🕵️‍♂️\n\n"
        f"💡 **Инструкция по использованию:**\n"
        f"Отправь номер телефона, ФИО или @username.\n\n"
        f"📌 **Формат добавления в Базу:**\n"
        f"`/add КЛЮЧ | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ЗАМЕТКИ`\n\n"
        f"🆔 **Твой TG ID:** `{user.id}`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_bottom_keyboard())

# --- АВТОМАТИЧЕСКАЯ СБОРКА ЕДИНОГО ДОСЬЕ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_input = update.message.text.strip()

    if "Инструкция" in raw_input or raw_input == "/help":
        await start(update, context)
        return
    elif "Мой Баланс" in raw_input:
        await update.message.reply_text("📊 **Ваш баланс:** Безлимитный доступ.", parse_mode="Markdown")
        return

    status_msg = await update.message.reply_text(f"🔎 **Сбор информации по запросу:** `{raw_input}`...", parse_mode="Markdown")

    db_matches = search_in_db(raw_input)
    
    clean_phone = re.sub(r"\D", "", raw_input)
    phone_info = ""
    if clean_phone:
        if len(clean_phone) == 11 and clean_phone.startswith("8"):
            clean_phone = "7" + clean_phone[1:]
        formatted_phone = f"+{clean_phone}"
        try:
            parsed_num = phonenumbers.parse(formatted_phone, None)
            if phonenumbers.is_valid_number(parsed_num):
                c_name = geocoder.description_for_number(parsed_num, "ru") or "Неизвестно"
                op_name = carrier.name_for_number(parsed_num, "ru") or "Частный/Неизвестен"
                phone_info = f"[+] С т р а н а : {c_name}\n[+] О п е р а т о р : {op_name}\n"
        except Exception:
            pass

    output = []
    
    if db_matches:
        for record in db_matches:
            full_name, phone, username, notes = record
            output.append(f"🕵️‍♂️ **Результат из Базы:**")
            output.append(f"[+] Ф И О : {full_name}")
            output.append(f"[+] Н о м е р : {phone}")
            output.append(f"[+] Ю з е р н е й м : @{username}")
            if phone_info:
                output.append(phone_info.strip())
            
            notes_lines = [n.strip() for n in notes.split('.') if n.strip()]
            for line in notes_lines:
                output.append(f"[+] {line}")
            output.append("")
    else:
        output.append(f"📁 **База данных:** Запись не найдена.")
        if phone_info:
            output.append(phone_info.strip())
        output.append("")

    clean_user = raw_input.replace("@", "").strip()
    headers = {"User-Agent": "Mozilla/5.0"}
    social_results = []
    
    service_urls = {
        "tg": f"https://t.me/{clean_user}",
        "vk": f"https://vk.com/{clean_user}",
        "yt": f"https://www.youtube.com/@{clean_user}",
        "tt": f"https://www.tiktok.com/@{clean_user}",
        "stm": f"https://steamcommunity.com/id/{clean_user}",
        "gh": f"https://github.com/{clean_user}"
    }

    for key in ["tg", "vk", "yt", "tt", "stm", "gh"]:
        name = ALL_SERVICES[key]
        url = service_urls[key]
        try:
            res = requests.get(url, headers=headers, timeout=1.5)
            if res.status_code in [200, 301, 302] and "page_not_found" not in res.url:
                social_results.append(f"[+] {name} : Найден ({url})")
        except Exception:
            pass

    if social_results:
        output.append("🌐 **Найденные Соцсети:**")
        output.extend(social_results)

    final_text = "\n".join(output)
    await status_msg.edit_text(final_text, parse_mode="Markdown", disable_web_page_preview=True)

# --- НАДЕЖНОЕ ДОБАВЛЕНИЕ ЗАПИСЕЙ В БАЗУ ---
async def add_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Получаем весь текст после /add
        full_text = update.message.text
        if full_text.startswith('/add'):
            full_text = full_text[4:].strip()

        if not full_text or "|" not in full_text:
            await update.message.reply_text(
                "⚠️ **Ошибка формата!**\n\n"
                "Отправьте команду в формате:\n"
                "`/add КЛЮЧ | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ЗАМЕТКИ`",
                parse_mode="Markdown"
            )
            return

        parts = [p.strip() for p in full_text.split("|")]

        search_key = parts[0]
        full_name = parts[1] if len(parts) > 1 else "Не указано"
        phone = parts[2] if len(parts) > 2 else "Не указано"
        username = parts[3] if len(parts) > 3 else "Не указано"
        notes = " | ".join(parts[4:]) if len(parts) > 4 else "Нет заметок"

        # Запись в локальную БД
        add_to_db(search_key, full_name, phone, username, notes)

        await update.message.reply_text(
            f"✅ **Успешно занесено в Базу!**\n\n"
            f"[+] К л ю ч : {search_key}\n"
            f"[+] Ф И О : {full_name}\n"
            f"[+] Н о м е р : {phone}\n"
            f"[+] Ю з е р н е й м : {username}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ **Ошибка добавления:** `{e}`", parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("add", add_dossier_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    print("🤖 Бот запущен!")
    app.run_polling()
