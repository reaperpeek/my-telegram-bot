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
ADMIN_IDS = [7786483533]

USER_LIMITS = {}
USER_SELECTIONS = {}
DEFAULT_FREE_LIMIT = 5

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
    cursor.execute("SELECT COUNT(*) FROM dossiers")
    if cursor.fetchone()[0] == 0:
        demo_data = [
            ("380980092647", "Тестовый Контакт 1", "+380980092647", "test_user1", "Регион: Украина (Kyivstar)"),
            ("48574654698", "Тестовый Контакт 2", "+48574654698", "test_user2", "Регион: Польша (Play)"),
            ("иванов иван", "Иванов Иван Иванович", "+79991234567", "ivanov_ivan", "Зарегистрирован в реестре")
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO dossiers (search_key, full_name, phone, username, notes) VALUES (?, ?, ?, ?, ?)",
            demo_data
        )
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

def get_user_limit(user_id: int) -> int:
    if user_id not in USER_LIMITS:
        USER_LIMITS[user_id] = DEFAULT_FREE_LIMIT
    return USER_LIMITS[user_id]

async def post_init(application) -> None:
    init_db()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("help", "Инструкция по поиску"),
        BotCommand("add", "Добавить запись в БД (Админ)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    limit = get_user_limit(user.id)
    welcome_text = (
        f"🕵️‍♂️ **Добро пожаловать в OSINT Sherlock Bot!**\n\n"
        f"💡 **Как работать с ботом:**\n"
        f"1️⃣ Напишите в чат любой запрос (ФИО, номер телефона или @username).\n"
        f"2️⃣ Бот спросит, **какой именно тип поиска** вы хотите выполнить.\n"
        f"3️⃣ Выберите нужную кнопку и получите мгновенный отчёт!\n\n"
        f"📋 **Примеры запросов:**\n"
        f"• `Сидоров` или `Иванов Иван`\n"
        f"• `+79991234567`\n"
        f"• `@alex_dev`\n\n"
        f"🆔 **Ваш Telegram ID:** `{user.id}`\n"
        f"📊 **Доступно поисков:** `{limit}`"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_bottom_keyboard())

# --- ВЫБОР ТИПА ПОИСКА ПОСЛЕ ВВОДА ЗАПРОСА ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    raw_input = update.message.text.strip()

    if raw_input == "🔍 Инструкция":
        await start(update, context)
        return
    elif raw_input == "ℹ️ Мой Баланс":
        await update.message.reply_text(f"📊 **Ваш баланс:** `{get_user_limit(user_id)}` поисков.", parse_mode="Markdown")
        return

    if get_user_limit(user_id) <= 0:
        await update.message.reply_text("❌ У вас закончились бесплатные поиски!")
        return

    # Клавиатура с выбором типа поиска
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Искать в закрытой Базе Досье", callback_data=f"mode_db_{raw_input}")],
        [InlineKeyboardButton("📞 Проверить Телефон (Страна/Оператор/Мессенджеры)", callback_data=f"mode_phone_{raw_input}")],
        [InlineKeyboardButton("🌐 Сканировать Соцсети & Платформы", callback_data=f"mode_social_{raw_input}")]
    ])

    await update.message.reply_text(
        f"🔍 **Запрос принят:** `{raw_input}`\n\n"
        f"👇 **Выберите, какую именно информацию вы хотите найти:**",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# --- ОБРАБОТЧИК КНОПОК И РЕЖИМОВ ПОИСКА ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # 1. Поиск в Базе Данных
    if data.startswith("mode_db_"):
        search_target = data.replace("mode_db_", "")
        await query.answer()
        await query.message.edit_text(f"⏳ Выполняется поиск в локальной базе для `{search_target}`...", parse_mode="Markdown")
        
        db_matches = search_in_db(search_target)
        if db_matches:
            USER_LIMITS[user_id] -= 1
            for record in db_matches:
                full_name, phone, username, notes = record
                dossier_text = (
                    f"👤 **Найдено Досье в Базе:**\n"
                    f"├ **ФИО:** {full_name}\n"
                    f"├ **Телефон:** `{phone}`\n"
                    f"├ **Username:** `@{username}`\n"
                    f"└ **Заметки:** {notes}\n\n"
                    f"📉 *Осталось поисков:* `{USER_LIMITS[user_id]}`"
                )
                await query.message.reply_text(dossier_text, parse_mode="Markdown")
        else:
            await query.message.reply_text(f"❌ Запись `{search_target}` не найдена в Базе Досье.", parse_mode="Markdown")
        return

    # 2. Анализ Телефона
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
        viber_url = f"https://viber.click/{clean_phone}"
        messenger_url = f"https://www.facebook.com/messages/t/{clean_phone}"
        google_url = f"https://www.google.com/search?q=%22%2B{clean_phone}%22+OR+%22{clean_phone}%22"

        USER_LIMITS[user_id] -= 1

        phone_text = (
            f"📞 **Анализ номера:** `{formatted_phone}`\n\n"
            f"📌 **Данные оператора:**\n"
            f"• Регион/Страна: `{country_name}`\n"
            f"• Оператор связи: `{operator_name}`\n\n"
            f"💬 **Прямые мосты в мессенджеры:**\n"
            f"• 🟢 **WhatsApp:** [Открыть чат]({wa_url})\n"
            f"• ✈️ **Telegram:** [Проверить]({tg_url})\n"
            f"• 🟣 **Viber:** [Открыть чат]({viber_url})\n"
            f"• 🔵 **FB Messenger:** [Перейти]({messenger_url})\n\n"
            f"🔎 **Поисковая выдача:** [Google Search]({google_url})\n\n"
            f"📉 *Осталось поисков:* `{USER_LIMITS[user_id]}`"
        )
        await query.message.edit_text(phone_text, parse_mode="Markdown", disable_web_page_preview=True)
        return

    # 3. Сканирование Соцсетей
    if data.startswith("mode_social_"):
        target = data.replace("mode_social_", "").replace("@", "")
        await query.answer()
        await query.message.edit_text(f"🔍 Запуск сканирования соцсетей и Maigret для `{target}`...", parse_mode="Markdown")
        await run_full_search(target, query, user_id, context)
        return

async def parse_page_details(url: str, response_text: str) -> str:
    try:
        soup = BeautifulSoup(response_text, 'html.parser')
        info_parts = []
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            desc = og_desc["content"].strip().replace("\n", " ")
            if len(desc) > 120:
                desc = desc[:117] + "..."
            info_parts.append(f"📝 *Описание:* {desc}")
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
            info_parts.append(f"👤 *Имя/Заголовок:* {title}")
        if info_parts:
            return "\n   " + "\n   ".join(info_parts)
    except Exception:
        pass
    return ""

async def run_maigret_search(username: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "maigret", username, "--timeout", "3", "--top-sites", "20",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8")
        found_links = [line.strip() for line in output.split("\n") if "🔗" in line or "http" in line]
        return "\n".join(found_links[:5]) if found_links else "Профили Maigret не найдены."
    except Exception:
        return "⚠️ Сканирование завершено."

async def run_full_search(username: str, query, user_id: int, context: ContextTypes.DEFAULT_TYPE):
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
                bio = chat_info.bio or ""
                results.append(f"{name}: ✅ [Telegram Профиль]({url})\n   👤 *Имя:* {title} | Bio: {bio}")
            except Exception:
                results.append(f"{name}: ❌ Не найден")
            continue
        try:
            res = requests.get(url, headers=headers, timeout=2.5)
            if res.status_code in [200, 301, 302] and "page_not_found" not in res.url:
                details = await parse_page_details(url, res.text)
                results.append(f"{name}: ✅ [Ссылка на профиль]({url}){details}")
            else:
                results.append(f"{name}: ❌ Не найден")
        except Exception:
            results.append(f"{name}: ⚠️ Ошибка подключения")

    maigret_res = await run_maigret_search(username)
    USER_LIMITS[user_id] -= 1

    final_text = (
        f"📊 **OSINT-Отчёт по нику:** `{username}`\n\n"
        + "\n\n".join(results) +
        f"\n\n🔍 **Результаты Maigret:**\n`{maigret_res}`\n\n"
        f"📉 *Осталось поисков:* `{USER_LIMITS[user_id]}`"
    )

    await query.message.reply_text(final_text, parse_mode="Markdown", disable_web_page_preview=True)

async def add_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(f"❌ Ваш ID ({user_id}) отсутствует в ADMIN_IDS!")
        return

    raw_text = update.message.text.partition(' ')[2].strip()
    
    if not raw_text or "|" not in raw_text:
        await update.message.reply_text(
            "⚠️ **Формат команды:**\n"
            "`/add +79991234567 | Сидоров Алексей Иванович | +79991234567 | @sidorov_test | Запись`",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in raw_text.split("|")]
    
    if len(parts) < 5:
        await update.message.reply_text("⚠️ Нужно указать 5 полей через разделитель `|`!", parse_mode="Markdown")
        return

    search_key, full_name, phone, username, notes = parts[0], parts[1], parts[2], parts[3], parts[4]
    
    add_to_db(search_key, full_name, phone, username, notes)
    await update.message.reply_text(
        f"✅ **Запись успешно добавлена в Базу Досье!**\n\n"
        f"🔑 **Ключ:** `{search_key}`\n"
        f"👤 **ФИО:** {full_name}\n"
        f"📞 **Телефон:** `{phone}`\n"
        f"💬 **Юзернейм:** `{username}`", 
        parse_mode="Markdown"
    )

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_dossier_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    print("🤖 Бот запущен!")
    app.run_polling()
