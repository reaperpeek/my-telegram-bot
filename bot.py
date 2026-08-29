import asyncio
import re
import sqlite3
import time
import requests
import phonenumbers
from phonenumbers import geocoder, carrier
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, PreCheckoutQueryHandler, filters, ContextTypes
)

TOKEN = "8408315552:AAG5CczuITP2tJnNdMlCnRPXnvXoM6-xSUA"
ADMIN_ID = 7786483533
REFS_NEEDED = 5       # Нужно пригласить 5 человек
TIME_LIMIT_SEC = 3600  # Время на приглашение — 1 час (3600 секунд)

ALL_SERVICES = {
    "tg": "Telegram", "yt": "YouTube", "tt": "TikTok", "vk": "VK",
    "pin": "Pinterest", "red": "Reddit", "stm": "Steam", "gh": "GitHub",
    "tw": "Twitch", "rbl": "Roblox", "hb": "Habr"
}

# --- БАЗА ДАННЫХ ---
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            ref_count INTEGER DEFAULT 0,
            ref_start_time INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_or_create_user(user_id: int, referrer_id: int = None):
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, referrer_id FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    is_new = False
    actual_referrer = None

    if not row:
        is_new = True
        if referrer_id and referrer_id != user_id:
            actual_referrer = referrer_id
        cursor.execute('INSERT INTO users (user_id, referrer_id, ref_count, ref_start_time) VALUES (?, ?, 0, 0)', (user_id, actual_referrer))
        conn.commit()
        
        if actual_referrer:
            cursor.execute('SELECT ref_count, ref_start_time FROM users WHERE user_id = ?', (actual_referrer,))
            ref_row = cursor.fetchone()
            if ref_row:
                ref_count, ref_start_time = ref_row
                current_time = int(time.time())
                
                if ref_start_time > 0 and (current_time - ref_start_time) <= TIME_LIMIT_SEC:
                    new_count = ref_count + 1
                    cursor.execute('UPDATE users SET ref_count = ? WHERE user_id = ?', (new_count, actual_referrer))
                    conn.commit()
                else:
                    actual_referrer = None
            
    conn.close()
    return is_new, actual_referrer

def start_or_get_ref_campaign(user_id: int):
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('SELECT ref_count, ref_start_time FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    current_time = int(time.time())
    
    if not row:
        cursor.execute('INSERT INTO users (user_id, ref_count, ref_start_time) VALUES (?, 0, ?)', (user_id, current_time))
        conn.commit()
        conn.close()
        return 0, current_time
    
    ref_count, ref_start_time = row
    
    if ref_start_time == 0 or (current_time - ref_start_time) > TIME_LIMIT_SEC:
        cursor.execute('UPDATE users SET ref_count = 0, ref_start_time = ? WHERE user_id = ?', (current_time, user_id))
        conn.commit()
        conn.close()
        return 0, current_time
    
    conn.close()
    return ref_count, ref_start_time

def reset_user_refs(user_id: int):
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET ref_count = 0, ref_start_time = 0 WHERE user_id = ?', (user_id,))
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
    clean_user = username.replace("@", "").strip()
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO dossiers (search_key, full_name, phone, username, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (clean_key, full_name, phone, clean_user, notes))
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
    clean_user = username.replace("@", "").strip()
    conn = sqlite3.connect("dossier_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pending_add (user_id, search_key, full_name, phone, username, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, clean_key, full_name, phone, clean_user, notes))
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

# --- ОЦЕНКА ДАТЫ РЕГИСТРАЦИИ ПО TELEGRAM ID ---
def estimate_tg_creation_date(user_id: int) -> str:
    ranges = [
        (100000000, "Январь 2015"), (200000000, "Март 2016"),
        (300000000, "Декабрь 2016"), (400000000, "Май 2017"),
        (500000000, "Декабрь 2017"), (700000000, "Ноябрь 2018"),
        (1000000000, "Декабрь 2019"), (1500000000, "Февраль 2021"),
        (2000000000, "Октябрь 2021"), (5000000000, "Февраль 2022"),
        (6000000000, "Март 2023"), (7000000000, "Февраль 2024"),
        (8000000000, "Май 2025"), (9000000000, "Январь 2026")
    ]
    if user_id < 100000000:
        return "2013 — 2014 гг."
    prev_date = ranges[0][1]
    for r_id, r_date in ranges:
        if user_id <= r_id:
            return f"~ {r_date} г."
        prev_date = r_date
    return f"~ {prev_date} г."

# --- ИНТЕРФЕЙС ---
def get_bottom_keyboard():
    keyboard = [
        [KeyboardButton("🔍 Искать человека"), KeyboardButton("➕ Добавить человека")],
        [KeyboardButton("⚡ Мощный Deep Search (10 ⭐)"), KeyboardButton("🔗 Партнёрка")],
        [KeyboardButton("📖 Инструкция"), KeyboardButton("ℹ️ Мой Баланс")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def post_init(application) -> None:
    init_db()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("help", "Инструкция"),
        BotCommand("deepsearch", "Заказать глубокий пробив (10 ⭐)"),
        BotCommand("ref", "Акция: Deep Search за 1 час"),
        BotCommand("add", "Добавить запись на модерацию"),
        BotCommand("del", "Удалить запись (Админ)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    referrer_id = None
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].split("_")[1])
        except ValueError:
            pass

    is_new, actual_referrer = get_or_create_user(user.id, referrer_id)

    if is_new and actual_referrer:
        try:
            conn = sqlite3.connect("dossier_database.db")
            cursor = conn.cursor()
            cursor.execute('SELECT ref_count FROM users WHERE user_id = ?', (actual_referrer,))
            ref_count = cursor.fetchone()[0]
            conn.close()

            if ref_count >= REFS_NEEDED:
                reset_user_refs(actual_referrer)
                await context.bot.send_message(
                    chat_id=actual_referrer,
                    text=(
                        f"🎉 <b>ПОЗДРАВЛЯЕМ! Цель выполнена!</b>\n\n"
                        f"Вы успели пригласить {REFS_NEEDED} друзей за 1 час!\n"
                        f"🎁 Вам начислен <b>Бесплатный Deep Search</b>.\n\n"
                        f"📩 <i>Отправьте прямо сюда в чат данные для пробива (номер, @username, ФИО и т.д.).</i>"
                    ),
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=actual_referrer,
                    text=(
                        f"⏳ <b>Новый переход по вашей ссылке!</b>\n"
                        f"👥 Приглашено: <b>{ref_count} / {REFS_NEEDED}</b>\n"
                        f"Успейте пригласить остальных, пока не истек 1 час!"
                    ),
                    parse_mode="HTML"
                )
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")

    welcome_text = (
        f"🕵️‍♂️ <b>SCOUTrr — Народная OSINT-База</b>\n\n"
        f"Добро пожаловать в коллективный Центр Поиска Данных! 🌐\n\n"
        f"• <b>🔍 Искать человека</b> — отправь номер, @username, TG ID или ФИО.\n"
        f"• <b>⚡ Мощный Deep Search</b> — приватный пробив по закрытым источникам.\n"
        f"• <b>🔗 Партнёрка</b> — забери Deep Search БЕСПЛАТНО за 1 час!\n\n"
        f"🆔 <b>Твой TG ID:</b> <code>{user.id}</code>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_bottom_keyboard())

async def show_ref_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user.id}"
    
    ref_count, ref_start_time = start_or_get_ref_campaign(user.id)
    
    current_time = int(time.time())
    elapsed = current_time - ref_start_time
    time_left = max(0, TIME_LIMIT_SEC - elapsed)
    minutes_left = time_left // 60
    seconds_left = time_left % 60

    text = (
        f"🚀 <b>АКЦИЯ: Бесплатный Deep Search за 1 час!</b>\n\n"
        f"Пригласи <b>{REFS_NEEDED} друзей</b> по своей ссылке в течение 1 часа и получи глубокий отчёт бесплатно!\n\n"
        f"⏱ <b>Осталось времени:</b> <code>{minutes_left:02d}:{seconds_left:02d} мин</code>\n"
        f"👥 <b>Приглашено друзей:</b> <b>{ref_count} / {REFS_NEEDED}</b>\n\n"
        f"🔗 <b>Твоя персональная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"⚠️ <i>Если не успеешь собрать {REFS_NEEDED} человек за 1 час, таймер и прогресс сбросятся!</i>"
    )

    await update.message.reply_text(text, parse_mode="HTML")

async def show_deep_search_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚡ <b>Мощный Deep Search (Глубокий пробив)</b>\n\n"
        "Индивидуальный поиск информации по закрытым источникам и архивным утечкам (Delivery, СДЭК, соцсети, слитые базы).\n\n"
        "<b>По каким данным мы можем искать:</b>\n"
        "1️⃣ 📱 <b>Номер телефона</b> (любой страны)\n"
        "2️⃣ 🆔 <b>Telegram ID / @username</b>\n"
        "3️⃣ 👤 <b>ФИО + Дата рождения / Город</b>\n"
        "4️⃣ 📧 <b>Email / Почта</b>\n"
        "5️⃣ 🚗 <b>Госномер или VIN авто</b>\n\n"
        "💳 <b>Стоимость:</b> 10 ⭐️ Telegram Stars (или бесплатно за 5 друзей за 1 час!)\n"
        "<i>После оплаты вы отправляете вводные данные, и специалист формирует полный персональный отчёт!</i>"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Оплатить 10 Stars и Заказать", callback_data="buy_deep_search")]
    ])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)

async def send_deep_search_invoice(chat_id, context):
    title = "⚡ Deep Search Отчёт"
    description = "Персональный глубокий пробив по закрытым источникам и утечкам."
    payload = "deep_search_payment"
    currency = "XTR"
    prices = [LabeledPrice("Deep Search Отчёт", 10)]

    await context.bot.send_invoice(
        chat_id=chat_id, title=title, description=description,
        payload=payload, provider_token="", currency=currency, prices=prices
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "deep_search_payment":
        await query.answer(ok=False, error_message="Ошибка оплаты...")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_tg = f"@{user.username}" if user.username else f"ID: {user.id}"

    await update.message.reply_text(
        "🎉 <b>Оплата 10 ⭐ успешно получена!</b>\n\n"
        "📩 <b>Отправьте прямо сюда в чат вводные данные для поиска:</b>\n"
        "• Номер телефона / Telegram ID / @username / ФИО / Email / Госномер.\n\n"
        "⏳ <b>Время формирования отчёта:</b> от 30 минут до 3 часов.\n"
        "<i>Специалист уже принял ваш запрос в работу и пришлёт готовый Deep Search отчёт!</i>",
        parse_mode="HTML"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🚨 <b>НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ DEEP SEARCH (STARS)!</b>\n\n"
                f"👤 <b>Покупатель:</b> {user_tg} (ID: <code>{user.id}</code>)\n"
                f"💰 <b>Сумма:</b> 10 ⭐\n\n"
                f"📥 Ожидайте вводные данные!"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления админу: {e}")

async def add_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_text = update.message.text
    if full_text.startswith('/add'):
        full_text = full_text[4:].strip()

    if not full_text or "|" not in full_text:
        await update.message.reply_text(
            "⚠️ <b>Ошибка формата!</b>\n\n"
            "Отправь данные в одну строчку через разделитель <code>|</code>:\n"
            "<code>/add НОМЕР | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ИНФОРМАЦИЯ</code>",
            parse_mode="HTML"
        )
        return

    parts = [p.strip() for p in full_text.split("|")]
    search_key = parts[0]
    full_name = parts[1] if len(parts) > 1 else "Не указано"
    phone = parts[2] if len(parts) > 2 else "Не указано"
    username = parts[3] if len(parts) > 3 else "Не указано"
    notes = " | ".join(parts[4:]) if len(parts) > 4 else "Нет заметок"

    pending_id = save_pending(user.id, search_key, full_name, phone, username, notes)

    await update.message.reply_text("⏳ <b>Заявка отправлена модератору!</b>", parse_mode="HTML")

    admin_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{pending_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{pending_id}")]
    ])
    user_tg = f"@{user.username}" if user.username else f"ID: {user.id}"

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📥 <b>Заявка на добавление:</b> от {user_tg}\nКлюч: <code>{search_key}</code>",
            parse_mode="HTML", reply_markup=admin_markup
        )
    except Exception as e:
        print(f"Ошибка админа: {e}")

async def del_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    key = update.message.text.partition(' ')[2].strip()
    if delete_from_db_by_key(key) > 0:
        await update.message.reply_text(f"🗑 Запись <code>{key}</code> удалена!", parse_mode="HTML")
    else:
        await update.message.reply_text("❓ Запись не найдена.", parse_mode="HTML")

# --- ПОИСК И ВЫВОД КАРТОЧКИ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_input = update.message.text.strip()

    if "🔍 Искать человека" in raw_input:
        await update.message.reply_text("🔎 Отправь номер телефона, @username, TG ID или ФИО для поиска:")
        return
    elif "⚡ Мощный Deep Search" in raw_input or raw_input == "/deepsearch":
        await show_deep_search_info(update, context)
        return
    elif "🔗 Партнёрка" in raw_input or raw_input == "/ref":
        await show_ref_program(update, context)
        return
    elif "➕ Добавить человека" in raw_input:
        await update.message.reply_text(
            "➕ <b>Отправь данные в формате:</b>\n<code>/add НОМЕР | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ИНФОРМАЦИЯ</code>",
            parse_mode="HTML"
        )
        return
    elif "📖 Инструкция" in raw_input or raw_input == "/help":
        await start(update, context)
        return
    elif "ℹ️ Мой Баланс" in raw_input:
        await update.message.reply_text("📊 <b>Ваш статус:</b> Доступ активен", parse_mode="HTML")
        return

    status_msg = await update.message.reply_text(f"🔎 <b>Сбор информации:</b> <code>{raw_input}</code>...", parse_mode="HTML")

    output = []
    clean_tg_input = raw_input.replace("@", "").replace("tgid", "").strip()

    # --- 1. TELEGRAM API / ОПРЕДЕЛЕНИЕ ID И ДАТЫ ---
    if clean_tg_input.isdigit() and 5 <= len(clean_tg_input) <= 12:
        tg_id_num = int(clean_tg_input)
        created_date = estimate_tg_creation_date(tg_id_num)
        output.append("📱 <b>TELEGRAM ПОЛЬЗОВАТЕЛЬ:</b>")
        output.append(f"🆔 <b>ID:</b> <code>{tg_id_num}</code>")
        output.append(f"📅 <b>Создан:</b> {created_date}")
        output.append("")

    elif raw_input.startswith("@") or not raw_input.isdigit():
        try:
            tg_username = f"@{clean_tg_input}"
            chat_info = await context.bot.get_chat(tg_username)
            if chat_info and chat_info.id:
                tg_id_num = chat_info.id
                created_date = estimate_tg_creation_date(tg_id_num)
                
                output.append("📱 <b>TELEGRAM ПОЛЬЗОВАТЕЛЬ:</b>")
                output.append(f"🆔 <b>ID:</b> <code>{tg_id_num}</code>")
                if chat_info.first_name:
                    name_str = chat_info.first_name + (f" {chat_info.last_name}" if chat_info.last_name else "")
                    output.append(f"👤 <b>Имя:</b> {name_str}")
                output.append(f"🔗 <b>Username:</b> @{clean_tg_input}")
                output.append(f"📅 <b>Создан:</b> {created_date}")
                output.append("")
        except Exception:
            pass

    # --- 2. НАРОДНАЯ БАЗА И ОПЕРАТОР ---
    db_matches = search_in_db(raw_input)
    clean_phone = re.sub(r"\D", "", raw_input)
    phone_info = ""
    
    if clean_phone:
        if len(clean_phone) == 11 and clean_phone.startswith("8"):
            clean_phone = "7" + clean_phone[1:]
        try:
            parsed_num = phonenumbers.parse(f"+{clean_phone}", None)
            if phonenumbers.is_valid_number(parsed_num):
                c_name = geocoder.description_for_number(parsed_num, "ru") or "Неизвестно"
                op_name = carrier.name_for_number(parsed_num, "ru") or "Частный"
                phone_info = f"[+] С т р а н а : {c_name}\n[+] О п е р а т о р : {op_name}\n"
        except Exception:
            pass

    first_record_id = None
    if db_matches:
        for record in db_matches:
            rec_id, full_name, phone, username, notes = record
            if not first_record_id:
                first_record_id = rec_id
            clean_user_display = username.lstrip("@") if username else "Не указан"
            
            output.append("🕵️‍♂️ <b>Результат из Народной Базы:</b>")
            output.append(f"[+] Ф И О : {full_name}")
            output.append(f"[+] Н о м е р : {phone}")
            output.append(f"[+] Ю з е р н е й м : @{clean_user_display}")
            if phone_info:
                output.append(phone_info.strip())
            
            for line in [n.strip() for n in re.split(r'\||\n', notes) if n.strip()]:
                output.append(f"[+] {line}")
            output.append("")
    else:
        output.append("📁 <b>Народная база:</b> Запись не найдена.")
        if phone_info:
            output.append(phone_info.strip())
        output.append("")

    # --- 3. СОЦСЕТИ ---
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
        try:
            res = requests.get(service_urls[key], headers=headers, timeout=1.5)
            if res.status_code in [200, 301, 302] and "page_not_found" not in res.url:
                social_results.append(f"[+] {ALL_SERVICES[key]} : Найден ({service_urls[key]})")
        except Exception:
            pass

    if social_results:
        output.append("🌐 <b>Найденные Соцсети:</b>")
        output.extend(social_results)
        output.append("")

    output.append("⚠️ Данные могут со временем меняться.")

    inline_buttons = []
    if first_record_id:
        inline_buttons.append([InlineKeyboardButton("⚠️ Пожаловаться на запись", callback_data=f"report_{first_record_id}")])
    inline_buttons.append([InlineKeyboardButton("⚡ Заказать глубокий Deep Search (10 ⭐)", callback_data="buy_deep_search")])

    await status_msg.edit_text("\n".join(output), parse_mode="HTML", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(inline_buttons))

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    await query.answer()

    if data == "buy_deep_search":
        await send_deep_search_invoice(query.message.chat_id, context)

    elif data.startswith("approve_"):
        pending_id = int(data.split("_")[1])
        item = get_pending_by_id(pending_id)
        if item:
            user_id, search_key, full_name, phone, username, notes = item
            add_to_db(search_key, full_name, phone, username, notes)
            delete_pending(pending_id)
            await query.edit_message_text(f"{query.message.text}\n\n✅ <b>ОДОБРЕНО</b>", parse_mode="HTML")
            try:
                await context.bot.send_message(chat_id=user_id, text=f"🎉 Ваша запись <code>{search_key}</code> добавлена в базу!", parse_mode="HTML")
            except Exception:
                pass

    elif data.startswith("reject_"):
        pending_id = int(data.split("_")[1])
        item = get_pending_by_id(pending_id)
        if item:
            delete_pending(pending_id)
            await query.edit_message_text(f"{query.message.text}\n\n❌ <b>ОТКЛОНЕНО</b>", parse_mode="HTML")

    elif data.startswith("report_"):
        rec_id = int(data.split("_")[1])
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=query.message.chat_id, text="🚨 Жалоба отправлена модераторам.", parse_mode="HTML")
        user_tg = f"@{user.username}" if user.username else f"ID: {user.id}"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ <b>Жалоба на запись ID {rec_id}</b> от {user_tg}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{rec_id}")]])
        )

    elif data.startswith("adm_del_"):
        rec_id = int(data.split("_")[1])
        if delete_from_db_by_id(rec_id) > 0:
            await query.edit_message_text(f"{query.message.text}\n\n🗑 <b>ЗАПИСЬ УДАЛЕНА</b>", parse_mode="HTML")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("deepsearch", show_deep_search_info))
    app.add_handler(CommandHandler("ref", show_ref_program))
    app.add_handler(CommandHandler("add", add_dossier_cmd))
    app.add_handler(CommandHandler("del", del_dossier_cmd))
    
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    
    print("🤖 Бот запущен!")
    app.run_polling()
