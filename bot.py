import asyncio
import re
import sqlite3
import requests
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import geocoder, carrier
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

TOKEN = "8408315552:AAG5CczuITP2tJnNdMlCnRPXnvXoM6-xSUA"

# 11 основных платформ для автоматического поиска
ALL_SERVICES = {
    "tg": "✈️ Telegram",
    "yt": "🔴 YouTube",
    "tt": "🎵 TikTok",
    "vk": "🔵 VK",
    "pin": "📌 Pinterest",
    "red": "🟧 Reddit",
    "stm": "🎮 Steam",
    "gh": "🐙 GitHub",
    "tw": "🟣 Twitch",
    "rbl": "🟥 Roblox",
    "hb": "🟩 Habr"
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
        f"1. Отправь в чат номер телефона, ФИО или @username.\n"
        f"2. Выберите нужную действие кнопкой под сообщением:\n"
        f"   • `📁 Досье из Базы` — быстрый поиск твоих людей.\n"
        f"   • `📞 Оператор и Страна` — определить телефонную сеть.\n"
        f"   • `🌐 Соцсети` — прямой авто-поиск по 11 площадкам.\n\n"
        f"3. Для добавления контакта используй команду:\n"
        f"`/add КЛЮЧ | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ЗАМЕТКИ`\n\n"
        f"🆔 **Твой TG ID:** `{user.id}`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_bottom_keyboard())

# --- ОБРАБОТЧИК ВВОДА СООБЩЕНИЙ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_input = update.message.text.strip()

    if "Инструкция" in raw_input or raw_input == "/help":
        await start(update, context)
        return
    elif "Мой Баланс" in raw_input:
        await update.message.reply_text("📊 **Ваш баланс:** Безлимитный доступ.", parse_mode="Markdown")
        return

    # Ровно 3 чистые кнопки выбора
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Показать Досье из Базы (ФИО, Заметки)", callback_data=f"mode_db_{raw_input}")],
        [InlineKeyboardButton("📞 Определить Оператора и Страну по номеру", callback_data=f"mode_phone_{raw_input}")],
        [InlineKeyboardButton("🌐 Сканировать Все Соцсети (11 площадок)", callback_data=f"mode_social_{raw_input}")]
    ])

    await update.message.reply_text(
        f"🔍 **Запрос:** `{raw_input}`\n\n"
        f"👇 **Выбери действие:**",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# --- БЫСТРЫЙ ПОИСК ПО ВСЕМ 11 СОЦСЕТЯМ ---
async def parse_page_details(url: str, response_text: str) -> str:
    try:
        soup = BeautifulSoup(response_text, 'html.parser')
        info_parts = []
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            desc = og_desc["content"].strip().replace("\n", " ")
            if len(desc) > 100:
                desc = desc[:97] + "..."
            info_parts.append(f"📝 {desc}")
        if info_parts:
            return "\n   └ " + "\n   └ ".join(info_parts)
    except Exception:
        pass
    return ""

async def run_instant_social_search(username: str, query_msg, context: ContextTypes.DEFAULT_TYPE):
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []

    service_urls = {
        "tg": f"https://t.me/{username}",
        "yt": f"https://www.youtube.com/@{username}",
        "tt": f"https://www.tiktok.com/@{username}",
        "vk": f"https://vk.com/{username}",
        "pin": f"https://www.pinterest.com/{username}/",
        "red": f"https://www.reddit.com/user/{username}",
        "stm": f"https://steamcommunity.com/id/{username}",
        "gh": f"https://github.com/{username}",
        "tw": f"https://www.twitch.tv/{username}",
        "rbl": f"https://www.roblox.com/user.aspx?username={username}",
        "hb": f"https://habr.com/ru/users/{username}"
    }

    for key, name in ALL_SERVICES.items():
        url = service_urls[key]
        if key == "tg":
            try:
                chat_info = await context.bot.get_chat(f"@{username}")
                title = chat_info.first_name or chat_info.title or "Профиль"
                results.append(f"{name}: ✅ [Профиль Telegram]({url})\n   └ 👤 Имя: {title}")
            except Exception:
                results.append(f"{name}: ❌ Не найден")
            continue

        try:
            res = requests.get(url, headers=headers, timeout=2.0)
            if res.status_code in [200, 301, 302] and "page_not_found" not in res.url:
                details = await parse_page_details(url, res.text)
                results.append(f"{name}: ✅ [Открыть страницу]({url}){details}")
            else:
                results.append(f"{name}: ❌ Не найден")
        except Exception:
            results.append(f"{name}: ⚠️ Таймаут")

    report_text = f"🌐 **Результат сканирования по 11 сетям для** `@{username}`:\n\n" + "\n".join(results)
    await query_msg.message.edit_text(report_text, parse_mode="Markdown", disable_web_page_preview=True)

# --- ОБРАБОТКА НАЖАТИЯ ИНЛАЙН-КНОПОК ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("mode_db_"):
        search_target = data.replace("mode_db_", "")
        await query.answer()
        
        db_matches = search_in_db(search_target)
        if db_matches:
            response_text = "👤 **Результаты из локальной Базы:**\n\n"
            for record in db_matches:
                full_name, phone, username, notes = record
                response_text += (
                    f"▫️ **ФИО:** {full_name}\n"
                    f"  ├ **Телефон:** `{phone}`\n"
                    f"  ├ **Username:** `{username}`\n"
                    f"  └ **Заметки:** {notes}\n\n"
                )
            await query.message.edit_text(response_text, parse_mode="Markdown")
        else:
            await query.message.edit_text(f"❌ Ничего не найдено в Базе по запросу `{search_target}`.", parse_mode="Markdown")
        return

    if data.startswith("mode_phone_"):
        phone_raw = data.replace("mode_phone_", "")
        await query.answer()
        
        clean_phone = re.sub(r"\D", "", phone_raw)
        if len(clean_phone) == 11 and clean_phone.startswith("8"):
            clean_phone = "7" + clean_phone[1:]
        
        formatted_phone = f"+{clean_phone}"
        country_name, operator_name = "Неизвестно", "Неизвестно"
        try:
            parsed_num = phonenumbers.parse(formatted_phone, None)
            if phonenumbers.is_valid_number(parsed_num):
                country_name = geocoder.description_for_number(parsed_num, "ru") or "Неизвестно"
                operator_name = carrier.name_for_number(parsed_num, "ru") or "Частный/Неизвестен"
        except Exception:
            pass

        wa_url = f"https://wa.me/{clean_phone}"
        tg_url = f"https://t.me/+{clean_phone}"

        phone_text = (
            f"📞 **Анализ номера:** `{formatted_phone}`\n\n"
            f"📌 **Оператор:** `{operator_name}`\n"
            f"📌 **Страна:** `{country_name}`\n\n"
            f"💬 **Мессенджеры:** [WhatsApp]({wa_url}) | [Telegram]({tg_url})"
        )
        await query.message.edit_text(phone_text, parse_mode="Markdown", disable_web_page_preview=True)
        return

    if data.startswith("mode_social_"):
        target = data.replace("mode_social_", "").replace("@", "")
        await query.answer()
        await query.message.edit_text(f"🌐 Сканирую 11 соцсетей для `{target}`...", parse_mode="Markdown")
        await run_instant_social_search(target, query, context)
        return

# --- ДОБАВЛЕНИЕ ЗАПИСЕЙ ---
async def add_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.partition(' ')[2].strip()
    
    if not raw_text or "|" not in raw_text:
        await update.message.reply_text(
            "⚠️ **Формат добавления:**\n"
            "`/add КЛЮЧ | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ЗАМЕТКИ`",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in raw_text.split("|")]
    
    if len(parts) < 5:
        await update.message.reply_text("⚠️ Ошибка! Заполните все 5 полей через разделитель `|`", parse_mode="Markdown")
        return

    search_key, full_name, phone, username, notes = parts[0], parts[1], parts[2], parts[3], parts[4]
    
    add_to_db(search_key, full_name, phone, username, notes)
    await update.message.reply_text(
        f"✅ **Успешно добавлено в Базу!**\n\n"
        f"🔑 **Ключ:** `{search_key}`\n"
        f"👤 **ФИО:** {full_name}\n"
        f"📞 **Телефон:** `{phone}`\n"
        f"💬 **Юзернейм:** `{username}`", 
        parse_mode="Markdown"
    )

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("add", add_dossier_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    print("🤖 Бот запущен!")
    app.run_polling()
