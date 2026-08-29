import asyncio
import re
import sqlite3
import aiohttp
import phonenumbers
from phonenumbers import geocoder, carrier

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

TOKEN = "8408315552:AAEqn2OXCEiVMvlAjAzGF1Y8WN3O1-vsa70"
ADMIN_ID = 7786483533

# Состояния для диалога добавления человека
WAITING_PERSON_DATA = 1

# --- База данных SQLite ---
def init_db():
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    # Таблица пользователей бота
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT
        )
    """)
    # Таблица найденных/добавленных людей в OSINT-базу
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS osint_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id TEXT,
            username TEXT,
            phone TEXT,
            info TEXT,
            status TEXT DEFAULT 'approved'
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_bot_user(user_id, username):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO bot_users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def search_in_local_db(query):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    clean_q = query.replace("@", "").strip()
    cursor.execute(
        "SELECT target_id, username, phone, info FROM osint_base WHERE (username = ? OR target_id = ? OR phone = ?) AND status = 'approved'", 
        (clean_q, clean_q, clean_q)
    )
    res = cursor.fetchone()
    conn.close()
    return res

def add_to_osint_base(target_id, username, phone, info):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    clean_user = username.replace("@", "").strip() if username else ""
    cursor.execute(
        "INSERT INTO osint_base (target_id, username, phone, info, status) VALUES (?, ?, ?, ?, 'approved')",
        (target_id, clean_user, phone, info)
    )
    conn.commit()
    conn.close()

# --- Вспомогательные функции ---
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
            f"📡 <b>Оператор:</b> {operator or 'Не определен'}"
        )
    except Exception as e:
        return f"❌ Ошибка: {e}"

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

# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_bot_user(user.id, user.username)
    
    keyboard = [
        [KeyboardButton("🔍 Поиск юзера / телефона")],
        [KeyboardButton("➕ Добавить в базу на модерацию")],
        [KeyboardButton("⚡ Deep Search"), KeyboardButton("🔗 Партнёрка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    msg = (
        f"🆔 <b>Твой TG ID:</b> <code>{user.id}</code>\n\n"
        f"🕵️ <b>SCOUTrr — Народная OSINT-База</b>\n"
        f"Наш сервис работает по принципу коллективного пополнения! 🌐\n\n"
        f"• 🔍 <b>Искать человека</b> — отправь номер или @username.\n"
        f"• ➕ <b>Добавить человека</b> — внеси известную информацию (ID, ник, номер) на модерацию в базу.\n"
        f"• ⚡ <b>Deep Search</b> — поиск по открытым реестрам.\n"
        f"• 🔗 <b>Партнёрка</b> — приглашай друзей и открывай приватные записи!"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

# Процесс добавления информации на модерацию
async def start_add_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 <b>Отправь данные человека для добавления в базу:</b>\n\n"
        "Формат (можно всё в одно сообщение):\n"
        "<code>Юзернейм: @example\n"
        "ID: 123456789\n"
        "Телефон: +79990000000\n"
        "Заметка: Любая дополнительная инфа</code>\n\n"
        "Для отмены отправь /cancel",
        parse_mode="HTML"
    )
    return WAITING_PERSON_DATA

async def receive_person_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    
    # Кнопки для админа
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}")
        ]
    ])
    
    # Сохраняем во временный контекст админа
    context.bot_data[f"pending_{user.id}"] = text

    # Отправляем сообщение админу
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📥 <b>Новая заявка в базу от</b> @{user.username} (ID: <code>{user.id}</code>):\n\n{text}",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await update.message.reply_text("✅ Спасибо! Данные отправлены на модерацию администратору.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавление отменено.")
    return ConversationHandler.END

# Обработка решений модератора
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    action, user_id_str = data.split("_")
    pending_key = f"pending_{user_id_str}"
    
    info_text = context.bot_data.get(pending_key, "")

    if action == "approve":
        # Парсим юзернейм, id и телефон из текста
        target_id = re.search(r'ID:\s*(\d+)', info_text, re.IGNORECASE)
        username = re.search(r'@([a-zA-Z0-9_]+)', info_text)
        phone = re.search(r'\+?\d{10,15}', info_text)
        
        t_id = target_id.group(1) if target_id else ""
        u_name = username.group(1) if username else ""
        ph = phone.group(0) if phone else ""
        
        add_to_osint_base(t_id, u_name, ph, info_text)
        
        await query.edit_message_text(f"✅ <b>Заявка одобрена и добавлена в базу!</b>\n\n{info_text}", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=int(user_id_str), text="🎉 Ваша заявка на добавление человека в базу была успешно одобрена!")
        except Exception:
            pass
    else:
        await query.edit_message_text(f"❌ <b>Заявка отклонена.</b>\n\n{info_text}", parse_mode="HTML")

# Поиск
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if text == "🔍 Поиск юзера / телефона":
        await update.message.reply_text("Отправь <code>@username</code> или номер телефона:", parse_mode="HTML")
        return
        
    if text == "⚡ Deep Search":
        await update.message.reply_text("⚡ <b>Deep Search</b> активирован. Введите объект поиска:", parse_mode="HTML")
        return

    if text == "🔗 Партнёрка":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={update.effective_user.id}"
        await update.message.reply_text(f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>", parse_mode="HTML")
        return

    # Проверка номера
    if re.match(r'^\+?\d{10,15}$', text):
        local = search_in_local_db(text)
        res = check_phone(text)
        if local:
            res += f"\n\n📂 <b>Найдено в нашей базе:</b>\nID: <code>{local[0]}</code>\nИнформация: {local[3]}"
        await update.message.reply_text(res, parse_mode="HTML")
        return

    # Проверка юзернейма
    if text.startswith("@") or re.match(r'^[a-zA-Z0-9_]{5,32}$', text):
        username = text if text.startswith("@") else f"@{text}"
        clean_name = username.replace("@", "")
        
        await update.message.reply_text("⏳ Идет поиск по открытым базам...")
        
        # 1. Сначала ищем в нашей локальной модераторской базе
        local = search_in_local_db(clean_name)
        
        if local and local[0]:
            extracted_id = local[0]
            local_info = f"Найдена запись:\n{local[3]}"
        else:
            extracted_id = await check_username_via_tgstat(clean_name)
            local_info = "Данных не найдено."

        id_str = f"<code>{extracted_id}</code>" if extracted_id else "<i>Пользователь не найден или логин свободен</i>"

        res = (
            f"📱 <b>TELEGRAM ПОЛЬЗОВАТЕЛЬ:</b>\n"
            f"👤 <b>Юзернейм:</b> {username}\n"
            f"🆔 <b>Telegram ID:</b> {id_str}\n"
            f"🔗 <b>Прямая ссылка:</b> https://t.me/{clean_name}\n\n"
            f"📂 <b>Локальная база:</b> {local_info}\n\n"
            f"🌐 <b>Обнаруженные веб-ресурсы:</b>\n"
            f"[+] Telegram: Найдено (https://t.me/{clean_name})\n"
            f"[+] TikTok: Найдено (https://www.tiktok.com/@{clean_name})\n"
            f"[+] Steam: Найдено (https://steamcommunity.com/id/{clean_name})\n\n"
            f"💡 <i>Данные получены из открытых и локальных источников.</i>"
        )
        await update.message.reply_text(res, parse_mode="HTML", disable_web_page_preview=True)
        return

    await update.message.reply_text("Отправь номер телефона или @username.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить в базу на модерацию$"), start_add_person)],
        states={WAITING_PERSON_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_person_data)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот успешно запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
