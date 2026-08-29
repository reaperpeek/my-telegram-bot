import asyncio
import re
import sqlite3
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

# --- ИНТЕРФЕЙС ---
def get_bottom_keyboard():
    keyboard = [
        [KeyboardButton("🔍 Искать человека"), KeyboardButton("➕ Добавить человека")],
        [KeyboardButton("⚡ Мощный Deep Search (10 ⭐)"), KeyboardButton("📖 Инструкция")],
        [KeyboardButton("ℹ️ Мой Баланс")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def post_init(application) -> None:
    init_db()
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("help", "Инструкция"),
        BotCommand("deepsearch", "Заказать глубокий пробив (10 ⭐)"),
        BotCommand("add", "Добавить запись на модерацию"),
        BotCommand("del", "Удалить запись (Админ)")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"🕵️‍♂️ <b>SCOUTrr — Народная OSINT-База</b>\n\n"
        f"Добро пожаловать в коллективный Центр Поиска Данных! 🌐\n\n"
        f"• <b>🔍 Искать человека</b> — отправь номер, @username или ФИО.\n"
        f"• <b>⚡ Мощный Deep Search</b> — приватный индивидуальный пробив по утечкам.\n"
        f"• <b>➕ Добавить человека</b> — отправить данные на проверку.\n\n"
        f"🆔 <b>Твой TG ID:</b> <code>{user.id}</code>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_bottom_keyboard())

# --- ДИП СЕРЧ / ОПЛАТА ЗВЕЗДАМИ ---
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
        "💳 <b>Стоимость:</b> 10 ⭐️ Telegram Stars\n"
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
    currency = "XTR"  # Telegram Stars
    prices = [LabeledPrice("Deep Search Отчёт", 10)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",  # Пустое поле для Telegram Stars!
        currency=currency,
        prices=prices
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload != "deep_search_payment":
        await query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_tg = f"@{user.username}" if user.username else f"ID: {user.id}"

    # Сообщение пользователю
    await update.message.reply_text(
        "🎉 <b>Оплата 10 ⭐ успешно получена!</b>\n\n"
        "📩 <b>Отправьте прямо сюда в чат вводные данные для поиска:</b>\n"
        "• Номер телефона / Telegram ID / @username / ФИО / Email / Госномер.\n\n"
        "⏳ <b>Время формирования отчёта:</b> от 30 минут до 3 часов.\n"
        "<i>Специалист уже принял ваш запрос в работу и пришлёт готовый Deep Search отчёт прямо в этот чат или в личные сообщения!</i>",
        parse_mode="HTML"
    )

    # Уведомление админу
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🚨 <b>НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ DEEP SEARCH!</b>\n\n"
                f"👤 <b>Покупатель:</b> {user_tg} (ID: <code>{user.id}</code>)\n"
                f"💰 <b>Сумма:</b> 10 ⭐ (Telegram Stars)\n\n"
                f"📥 Ожидайте от него вводные данные. У вас есть до 3 часов на выдачу отчёта!"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления админу: {e}")

# --- ДОБАВЛЕНИЕ С ПРЕМОДЕРАЦИЕЙ ---
async def add_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_text = update.message.text
    if full_text.startswith('/add'):
        full_text = full_text[4:].strip()

    if not full_text or "|" not in full_text:
        await update.message.reply_text(
            "⚠️ <b>Ошибка формата!</b>\n\n"
            "Отправь данные в одну строчку через разделитель <code>|</code>:\n"
            "<code>/add НОМЕР | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ИНФОРМАЦИЯ</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/add +380991234567 | Иванов Иван | +380991234567 | @vanya | ДР: 15.05.2005. Город: Киев.</code>",
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

    await update.message.reply_text(
        "⏳ <b>Заявка отправлена модератору!</b>\n"
        "После проверки администратором данные будут добавлены в общую базу.",
        parse_mode="HTML"
    )

    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{pending_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{pending_id}")
        ]
    ])

    user_tg = f"@{user.username}" if user.username else f"ID: {user.id}"

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📥 <b>Новая заявка на добавление!</b>\n"
                f"От: {user_tg} (ID: <code>{user.id}</code>)\n\n"
                f"[+] <b>Номер/Ключ:</b> <code>{search_key}</code>\n"
                f"[+] <b>ФИО:</b> {full_name}\n"
                f"[+] <b>Телефон:</b> {phone}\n"
                f"[+] <b>Юзернейм:</b> {username}\n"
                f"[+] <b>Заметки:</b> {notes}"
            ),
            parse_mode="HTML",
            reply_markup=admin_markup
        )
    except Exception as e:
        print(f"Ошибка при отправке заявки админу: {e}")

# --- УДАЛЕНИЕ (АДМИН) ---
async def del_dossier_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ <b>У вас нет прав на удаление записей!</b>", parse_mode="HTML")
        return

    key = update.message.text.partition(' ')[2].strip()
    if not key:
        await update.message.reply_text("⚠️ Укажите номер для удаления: <code>/del +380xxxxxxxxx</code>", parse_mode="HTML")
        return

    deleted = delete_from_db_by_key(key)
    if deleted > 0:
        await update.message.reply_text(f"🗑 Запись по номеру <code>{key}</code> удалена из базы!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❓ Запись <code>{key}</code> не найдена.", parse_mode="HTML")

# --- ПОИСК И ВЫВОД КАРТОЧКИ ---
async def handle_user_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_input = update.message.text.strip()

    if "🔍 Искать человека" in raw_input:
        await update.message.reply_text("🔎 Отправь номер телефона, @username или ФИО для поиска:")
        return
    elif "⚡ Мощный Deep Search" in raw_input or raw_input == "/deepsearch":
        await show_deep_search_info(update, context)
        return
    elif "➕ Добавить человека" in raw_input:
        instruction = (
            "➕ <b>Как предложить запись в базу:</b>\n\n"
            "Скопируй шаблон, заполни данные и отправь боту одной строкой:\n\n"
            "<code>/add НОМЕР | ФИО | ТЕЛЕФОН | ЮЗЕРНЕЙМ | ИНФОРМАЦИЯ</code>\n\n"
            "💡 Заявка уйдёт администратору на модерацию и после проверки появится в базе!"
        )
        await update.message.reply_text(instruction, parse_mode="HTML")
        return
    elif "📖 Инструкция" in raw_input or raw_input == "/help":
        await start(update, context)
        return
    elif "ℹ️ Мой Баланс" in raw_input:
        await update.message.reply_text("📊 <b>Ваш баланс:</b> Безлимитный доступ к базам.", parse_mode="HTML")
        return

    status_msg = await update.message.reply_text(f"🔎 <b>Сбор информации по запросу:</b> <code>{raw_input}</code>...", parse_mode="HTML")

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
            
            clean_user_display = username.lstrip("@") if username else "Не указан"
            
            output.append(f"🕵️‍♂️ <b>Результат из Народной Базы:</b>")
            output.append(f"[+] Ф И О : {full_name}")
            output.append(f"[+] Н о м е р : {phone}")
            output.append(f"[+] Ю з е р н е й м : @{clean_user_display}")
            if phone_info:
                output.append(phone_info.strip())
            
            notes_lines = [n.strip() for n in re.split(r'\||\n', notes) if n.strip()]
            for line in notes_lines:
                output.append(f"[+] {line}")
            output.append("")
    else:
        output.append(f"📁 <b>Народная база:</b> Запись не найдена.")
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
        output.append("🌐 <b>Найденные Соцсети:</b>")
        output.extend(social_results)
        output.append("")

    output.append("⚠️ <b>Примечание:</b> Юзернеймы и контактные данные пользователей могут со временем меняться!")

    final_text = "\n".join(output)
    
    inline_buttons = []
    if first_record_id:
        inline_buttons.append([InlineKeyboardButton("⚠️ Пожаловаться на запись", callback_data=f"report_{first_record_id}")])
    
    inline_buttons.append([InlineKeyboardButton("⚡ Заказать глубокий Deep Search (10 ⭐)", callback_data="buy_deep_search")])

    reply_markup = InlineKeyboardMarkup(inline_buttons)

    await status_msg.edit_text(final_text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=reply_markup)

# --- ОБРАБОТКА НАЖАТИЙ КНОПОК ---
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
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

            await query.edit_message_text(f"{query.message.text}\n\n✅ <b>ОДОБРЕНО И ДОБАВЛЕНО В БАЗУ</b>", parse_mode="HTML")
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 <b>Ваша запись по номеру <code>{search_key}</code> прошла модерацию и добавлена в базу!</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("⚠️ Заявка уже обработана.")

    elif data.startswith("reject_"):
        pending_id = int(data.split("_")[1])
        item = get_pending_by_id(pending_id)
        if item:
            user_id = item[0]
            delete_pending(pending_id)
            await query.edit_message_text(f"{query.message.text}\n\n❌ <b>ОТКЛОНЕНО</b>", parse_mode="HTML")
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Ваша заявка на добавление записи была отклонена модератором."
                )
            except Exception:
                pass

    elif data.startswith("report_"):
        rec_id = int(data.split("_")[1])
        user = query.from_user
        
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🚨 <b>Спасибо! Жалоба отправлена модераторам.</b>",
            parse_mode="HTML"
        )

        admin_del_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Удалить эту запись из БД", callback_data=f"adm_del_{rec_id}")]
        ])
        user_tg = f"@{user.username}" if user.username else f"ID: {user.id}"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"⚠️ <b>ПОСТУПИЛА ЖАЛОБА НА ЗАПИСЬ (ID: {rec_id})!</b>\n"
                f"От пользователя: {user_tg}\n\n"
                f"Текст карточки:\n{query.message.text}"
            ),
            parse_mode="HTML",
            reply_markup=admin_del_markup
        )

    elif data.startswith("adm_del_"):
        rec_id = int(data.split("_")[1])
        rows = delete_from_db_by_id(rec_id)
        if rows > 0:
            await query.edit_message_text(f"{query.message.text}\n\n🗑 <b>ЗАПИСЬ УСПЕШНО УДАЛЕНА ИЗ БАЗЫ!</b>", parse_mode="HTML")
        else:
            await query.edit_message_text("❓ Запись уже была удалена ранее.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("deepsearch", show_deep_search_info))
    app.add_handler(CommandHandler("add", add_dossier_cmd))
    app.add_handler(CommandHandler("del", del_dossier_cmd))
    
    # Обработчики платежей Telegram Stars
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_query))
    
    print("🤖 Бот запущен!")
    app.run_polling()
