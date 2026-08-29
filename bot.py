import asyncio
import re
import sqlite3
import requests
import phonenumbers
from phonenumbers import geocoder, carrier
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ConversationHandler, filters, ContextTypes
)

TOKEN = "8408315552:AAG5CczuITP2tJnNdMlCnRPXnvXoM6-xSUA"
ADMIN_ID = 7786483533

# Состояния для пошагового диалога добавления
WAITING_KEY, WAITING_FNAME, WAITING_NOTES = range(3)

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

def delete_from_db(search_key: str):
    clean_key = search_key.lower().replace("+", "").replace("@", "").strip()
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM dossiers WHERE LOWER(search_key) = ? OR LOWER(phone) = ?', (clean_key, clean_key))
    rows_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_deleted

def get_bottom_keyboard():
    keyboard = [
        [KeyboardButton("🔍 Искать человека"), KeyboardButton("➕ Добавить человека")],
        [KeyboardButton("📖 Инструкция"), KeyboardButton("ℹ️ Мой Баланс")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def post_init(application) -> None:
    init_db()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("add", "Добавить запись в БД"),
        BotCommand("cancel", "Отмена действия"),
        BotCommand("del", "Удалить запись (Админ)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"🕵️‍♂️ **SCOUTrr — Народная OSINT-База**\n\n"
        f"Добро пожаловать в коллективный Центр Поиска Данных! 🌐\n\n"
        f"Выберите действие с помощью кнопок ниже:\n"
        f"• **🔍 Искать человека** — найти досье по номеру, нику или ФИО.\n"
        f"• **➕ Добавить человека** — внести новые данные в общую базу по шагам.\n\n"
        f"🆔 **Твой TG ID:** `{user.id}`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_bottom_keyboard())

# --- ПОШАГОВЫЙ МАСТЕР ДОБАВЛЕНИЯ ---
async def start_add_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 **Шаг 1 из 3:**\n\n"
        "Отправьте главный **номер телефона** или **@username**, по которому люди будут находить запись.\n\n"
        "_Для отмены отправьте /cancel_",
        parse_mode="Markdown"
    )
    return WAITING_KEY

async def get_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_key'] = update.message.text.strip()
    await update.message.reply_text(
        "👤 **Шаг 2 из 3:**\n\n"
        "Введите **ФИО или Имя** человека (например: `Иванов Иван`):\n"
        "_(Если не знаете, отправьте `-`)_",
        parse_mode="Markdown"
    )
    return WAITING_FNAME

async def get_add_fname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_fname'] = update.message.text.strip()
    await update.message.reply_text(
        "📌 **Шаг 3 из 3:**\n\n"
        "Введите **дополнительную информацию** (дата рождения, город, юзернейм, заметки):\n"
        "_(Если нет доп. информации, отправьте `-`)_",
        parse_mode="Markdown"
    )
    return WAITING_NOTES

async def get_add_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get('add_key', 'Не указано')
    fname = context.user_data.get('add_fname', 'Не указано')
    notes = update.message.text.strip()

    phone = key if re.sub(r"\D", "", key) else "Не указано"
    username = key if key.startswith("@") or not re.sub(r"\D", "", key) else "Не указано"

    add_to_db(key, fname, phone, username, notes)

    await update.message.reply_text(
        f"✅ **Данные успешно добавлены в Народную Базу!**\n\n"
        f"[+] Н о м е р / К л ю ч : `{key}`\n"
        f"[+] Ф И О : {fname}\n"
        f"[+] Заметки : {notes}",
        parse_mode="Markdown",
        reply_markup=get_bottom_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Добавление отменено.", reply_markup=get_bottom_keyboard())
    return ConversationHandler.END

# --- УДАЛЕНИЕ (АДМИН) ---
async def del_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **У вас нет прав на удаление записей!**", parse_mode="Markdown")
        return

    key = update.message.text.partition(' ')[2].strip()
    if not key:
        await update.message.reply_text("⚠️ Укажите номер для удаления: `/del +380xxxxxxxxx`", parse_mode="Markdown")
        return

    deleted = delete_from_db(key)
    if deleted > 0:
        await update.message.reply_text(f"🗑 Запись по номеру `{key}` удалена из базы!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❓ Запись `{key}` не найдена.", parse_mode="Markdown")

# --- ПОИСК И СБОР ИНФОРМАЦИИ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_input = update.message.text.strip()

    if "🔍 Искать человека" in raw_input:
        await update.message.reply_text("🔎 Отправь номер телефона, @username или ФИО для поиска:")
        return
    elif "📖 Инструкция" in raw_input or raw_input == "/help":
        await start(update, context)
        return
    elif "ℹ️ Мой Баланс" in raw_input:
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
            output.append(f"🕵️‍♂️ **Результат из Народной Базы:**")
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
        output.append(f"📁 **Народная база:** Запись не найдена.")
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

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    # Разговорный обработчик пошагового добавления
    add_wizard = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Добавить человека$"), start_add_wizard),
            CommandHandler("add", start_add_wizard)
        ],
        states={
            WAITING_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_key)],
            WAITING_FNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_fname)],
            WAITING_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel_wizard)]
    )

    app.add_handler(add_wizard)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("del", del_dossier_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    
    print("🤖 Бот запущен!")
    app.run_polling()
