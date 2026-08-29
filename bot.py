import asyncio
import re
import sqlite3
import requests
import phonenumbers
from phonenumbers import geocoder, carrier
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

TOKEN = "8408315552:AAG5CczuITP2tJnNdMlCnRPXnvXoM6-xSUA"

# ⚠️ ТВОЙ TELEGRAM ID ДЛЯ ПОЛУЧЕНИЯ ЗАЯВОК И ЖАЛОБ
ADMIN_ID = 7786483533

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

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    # Таблица досье
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
    # Таблица очереди модерации
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_add (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            search_key TEXT,
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
        SELECT id, full_name, phone, username, notes FROM dossiers 
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

def delete_from_db_by_id(rec_id: int):
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM dossiers WHERE id = ?', (rec_id,))
    rows = cursor.rowcount
    conn.commit()
    conn.close()
    return rows

def delete_from_db_by_key(search_key: str):
    clean_key = search_key.lower().replace("+", "").replace("@", "").strip()
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM dossiers WHERE LOWER(search_key) = ? OR LOWER(phone) = ?', (clean_key, clean_key))
    rows = cursor.rowcount
    conn.commit()
    conn.close()
    return rows

def save_pending(user_id: int, search_key: str, full_name: str, phone: str, username: str, notes: str):
    clean_key = search_key.lower().replace("+", "").replace("@", "").strip()
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pending_add (user_id, search_key, full_name, phone, username, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, clean_key, full_name, phone, username, notes))
    pending_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return pending_id

def get_pending_by_id(pending_id: int):
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, search_key, full_name, phone, username, notes FROM pending_add WHERE id = ?', (pending_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def delete_pending(pending_id: int):
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM pending_add WHERE id = ?', (pending_id,))
    conn.commit()
    conn.close()

# --- ИНТЕРФЕЙС ---
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
        BotCommand("help", "Инструкция"),
        BotCommand("add", "Добавить запись на модерацию"),
        BotCommand("del", "Удалить запись (Админ)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"🕵️‍♂️ **SCOUTrr — Народная OSINT-База**\n\n"
        f"Добро пожаловать в коллективный Центр Поиска Данных! 🌐\n\n"
        f"• **🔍 Искать человека** — отправь номер, @username или ФИО.\n"
        f"• **➕ Добавить человека** — отправить данные на проверку.\n\n"
        f"🆔 **Твой TG ID:** `{user.id}`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_bottom_keyboard())

# --- ДОБАВЛЕНИЕ (ОТПРАВКА НА ПРЕМОДЕРАЦИЮ) ---
async def add_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_text = update.message.text
    if full_text.startswith('/add'):
        full_text = full_text[4:].strip()

    if not full_text or "|" not in full_text:
        await update.message.reply_text(
            "⚠️ **Ошибка формата!**\n\n"
            "Отправь данные в одну строчку через разделитель `|`:\n"
            "`/add НОМЕР | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ИНФОРМАЦИЯ`\n\n"
            "💡 **Пример:**\n"
            "`/add +380991234567 | Иванов Иван | +380991234567 | @vanya | ДР: 15.05.2005. Город: Киев.`",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in full_text.split("|")]

    search_key = parts[0]
    full_name = parts[1] if len(parts) > 1 else "Не указано"
    phone = parts[2] if len(parts) > 2 else "Не указано"
    username = parts[3] if len(parts) > 3 else "Не указано"
    notes = " | ".join(parts[4:]) if len(parts) > 4 else "Нет заметок"

    # Сохраняем в заявки
    pending_id = save_pending(user.id, search_key, full_name, phone, username, notes)

    await update.message.reply_text(
        "⏳ **Заявка отправлена модератору!**\n"
        "После проверки администратором данные будут добавлены в общую базу.",
        parse_mode="Markdown"
    )

    # Отправляем сообщение АДМИНУ с кнопками
    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{pending_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{pending_id}")
        ]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📥 **Новая заявка на добавление!**\n"
            f"От: [{user.first_name}](tg://user?id={user.id}) (`{user.id}`)\n\n"
            f"[+] **Номер/Ключ:** `{search_key}`\n"
            f"[+] **ФИО:** {full_name}\n"
            f"[+] **Телефон:** {phone}\n"
            f"[+] **Юзернейм:** {username}\n"
            f"[+] **Заметки:** {notes}"
        ),
        parse_mode="Markdown",
        reply_markup=admin_markup
    )

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

    deleted = delete_from_db_by_key(key)
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
    elif "➕ Добавить человека" in raw_input:
        instruction = (
            "➕ **Как предложить запись в базу:**\n\n"
            "Скопируй шаблон, заполни данные и отправь боту одной строкой:\n\n"
            "`/add НОМЕР | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ИНФОРМАЦИЯ`\n\n"
            "💡 Заявка уйдёт администратору на модерацию и после проверки появится в базе!"
        )
        await update.message.reply_text(instruction, parse_mode="Markdown")
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
    first_record_id = None
    
    if db_matches:
        for record in db_matches:
            rec_id, full_name, phone, username, notes = record
            if not first_record_id:
                first_record_id = rec_id
            
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
    
    # Кнопка жалобы под результатами
    reply_markup = None
    if first_record_id:
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ Пожаловаться на запись", callback_data=f"report_{first_record_id}")]
        ])

    await status_msg.edit_text(final_text, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=reply_markup)

# --- ОБРАБОТКА НАЖАТИЙ КНОПОК МОДЕРАЦИИ И ЖАЛОБ ---
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # Админ одобрил заявку
    if data.startswith("approve_"):
        pending_id = int(data.split("_")[1])
        item = get_pending_by_id(pending_id)
        if item:
            user_id, search_key, full_name, phone, username, notes = item
            add_to_db(search_key, full_name, phone, username, notes)
            delete_pending(pending_id)

            await query.edit_message_text(f"{query.message.text}\n\n✅ **ОДОБРЕНО И ДОБАВЛЕНО В БАЗУ**", parse_mode="Markdown")
            
            # Уведомляем автора
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 **Ваша запись по номеру `{search_key}` прошла модерацию и добавлена в общую базу!**",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("⚠️ Заявка уже обработана.")

    # Админ отклонил заявку
    elif data.startswith("reject_"):
        pending_id = int(data.split("_")[1])
        item = get_pending_by_id(pending_id)
        if item:
            user_id = item[0]
            delete_pending(pending_id)
            await query.edit_message_text(f"{query.message.text}\n\n❌ **ОТКЛОНЕНО**", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Ваша заявка на добавление записи была отклонена модератором."
                )
            except Exception:
                pass

    # Пользователь нажал "Пожаловаться"
    elif data.startswith("report_"):
        rec_id = int(data.split("_")[1])
        user = query.from_user
        
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🚨 **Спасибо! Жалоба отправлена модераторам.**"
        )

        # Пересылаем админу
        admin_del_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Удалить эту запись из БД", callback_data=f"adm_del_{rec_id}")]
        ])
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"⚠️ **ПОСТУПИЛА ЖАЛОБА НА ЗАПИСЬ (ID: {rec_id})!**\n"
                f"От пользователя: [{user.first_name}](tg://user?id={user.id}) (`{user.id}`)\n\n"
                f"Текст поиска:\n{query.message.text}"
            ),
            parse_mode="Markdown",
            reply_markup=admin_del_markup
        )

    # Админ жмёт "Удалить" по жалобе
    elif data.startswith("adm_del_"):
        rec_id = int(data.split("_")[1])
        rows = delete_from_db_by_id(rec_id)
        if rows > 0:
            await query.edit_message_text(f"{query.message.text}\n\n🗑 **ЗАПИСЬ УСПЕШНО УДАЛЕНА ИЗ БАЗЫ!**", parse_mode="Markdown")
        else:
            await query.edit_message_text("❓ Запись уже была удалена ранее.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("add", add_dossier_cmd))
    app.add_handler(CommandHandler("del", del_dossier_cmd))
    
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    
    print("🤖 Бот запущен с премодерацией и системой жалоб!")
    app.run_polling()
