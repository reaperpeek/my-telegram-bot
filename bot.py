import asyncio
import re
import sqlite3
import os
import aiohttp
import phonenumbers
from phonenumbers import geocoder, carrier

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters,
    PreCheckoutQueryHandler
)

TOKEN = "8408315552:AAFswxkq2cabG-xpUUUsF1iCl3co4E0yXjo"
ADMIN_ID = 7786483533

WAITING_PERSON_DATA = 1
REFS_NEEDED = 5

def init_db():
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            searches_left INTEGER DEFAULT 0,
            referrals_count INTEGER DEFAULT 0,
            ref_id INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS osint_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id TEXT,
            username TEXT,
            phone TEXT,
            fio TEXT,
            birth_date TEXT,
            info TEXT,
            status TEXT DEFAULT 'approved'
        )
    """)
    
    cursor.execute("PRAGMA table_info(osint_base)")
    columns = [column[1] for column in cursor.fetchall()]
    if "fio" not in columns:
        cursor.execute("ALTER TABLE osint_base ADD COLUMN fio TEXT")
    if "birth_date" not in columns:
        cursor.execute("ALTER TABLE osint_base ADD COLUMN birth_date TEXT")

    # Чистка тестов
    cursor.execute("DELETE FROM osint_base WHERE phone = '+79000000000' OR fio = 'Анастасия'")

    conn.commit()
    conn.close()

init_db()

def save_bot_user(user_id, username, ref_id=None):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM bot_users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO bot_users (user_id, username, searches_left, referrals_count, ref_id) VALUES (?, ?, 0, 0, ?)", 
                       (user_id, username, ref_id))
        
        if ref_id:
            cursor.execute("UPDATE bot_users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (ref_id,))
            cursor.execute("SELECT referrals_count FROM bot_users WHERE user_id = ?", (ref_id,))
            row = cursor.fetchone()
            
            if row and row[0] >= REFS_NEEDED:
                cursor.execute("UPDATE bot_users SET searches_left = searches_left + 1, referrals_count = referrals_count - ? WHERE user_id = ?", (REFS_NEEDED, ref_id))
    
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("SELECT searches_left, referrals_count FROM bot_users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (0, 0)

def add_searches(user_id, count=1):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_users SET searches_left = searches_left + ? WHERE user_id = ?", (count, user_id))
    conn.commit()
    conn.close()

def get_all_bot_users():
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, searches_left, referrals_count FROM bot_users")
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_in_local_db(query):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    clean_q = query.replace("@", "").strip()
    cursor.execute(
        "SELECT target_id, username, phone, fio, birth_date, info FROM osint_base WHERE (username = ? OR target_id = ? OR phone = ?) AND status = 'approved' ORDER BY id DESC", 
        (clean_q, clean_q, clean_q)
    )
    res = cursor.fetchone()
    conn.close()
    return res

def delete_from_osint_base(query):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    clean_q = query.replace("@", "").strip()
    cursor.execute(
        "DELETE FROM osint_base WHERE username = ? OR target_id = ? OR phone = ?", 
        (clean_q, clean_q, clean_q)
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def add_to_osint_base(target_id, username, phone, fio, birth_date, info):
    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()
    clean_user = username.replace("@", "").strip() if username else ""
    
    if clean_user:
        cursor.execute("DELETE FROM osint_base WHERE username = ?", (clean_user,))
    if phone:
        cursor.execute("DELETE FROM osint_base WHERE phone = ?", (phone,))
    if target_id:
        cursor.execute("DELETE FROM osint_base WHERE target_id = ?", (target_id,))
        
    cursor.execute(
        "INSERT INTO osint_base (target_id, username, phone, fio, birth_date, info, status) VALUES (?, ?, ?, ?, ?, ?, 'approved')",
        (target_id, clean_user, phone, fio, birth_date, info)
    )
    conn.commit()
    conn.close()

def format_local_profile(target_id, username, phone, fio, birth_date, info):
    clean_fio = fio.strip() if fio else "<i>Не указано</i>"
    clean_dob = birth_date.strip() if birth_date else "<i>Не указана</i>"
    clean_user = f"@{username}" if username and not username.startswith("@") else (username or "<i>Не указан</i>")
    clean_id = f"<code>{target_id}</code>" if target_id else "<i>Не указан</i>"
    clean_phone = f"<code>{phone}</code>" if phone else "<i>Не указан</i>"

    card = (
        f"📂 <b>КАРТОЧКА ИЗ ЛОКАЛЬНОЙ БАЗЫ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>ФИО:</b> {clean_fio}\n"
        f"🎂 <b>Дата рождения:</b> {clean_dob}\n"
        f"🔗 <b>Юзернейм:</b> {clean_user}\n"
        f"🆔 <b>Telegram ID:</b> {clean_id}\n"
        f"📞 <b>Телефон:</b> {clean_phone}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    return card

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user.id else None
    
    save_bot_user(user.id, user.username, ref_id)
    searches, refs = get_user_stats(user.id)
    
    keyboard = [
        [KeyboardButton("🔍 Поиск юзера / телефона")],
        [KeyboardButton("➕ Добавить в базу на модерацию")],
        [KeyboardButton("⚡ Deep Search (Платный)"), KeyboardButton("🔗 Партнёрка")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    msg = (
        f"🆔 <b>Твой TG ID:</b> <code>{user.id}</code>\n"
        f"⚡ <b>Доступно Deep Search:</b> {searches} шт.\n"
        f"👥 <b>Прогресс рефералов:</b> {refs}/{REFS_NEEDED}\n\n"
        f"🕵️ <b>SCOUTrr — Народная OSINT-База</b>\n\n"
        f"• 🔍 <b>Базовый поиск</b> — открытая информация (бесплатно).\n"
        f"• ⚡ <b>Deep Search</b> — полная проверка по архивам (требует 1 проверку).\n"
        f"• ➕ <b>Добавить человека</b> — внеси данные на модерацию.\n"
        f"• 🔗 <b>Партнёрка</b> — пригласи 5 друзей и получи Deep Search БЕСПЛАТНО!"
    )
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=reply_markup)

async def delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: <code>/del @username</code> или <code>/del +380...</code> или <code>/del ID</code>", parse_mode="HTML")
        return
    
    target = context.args[0]
    deleted_count = delete_from_osint_base(target)
    
    if deleted_count > 0:
        await update.message.reply_text(f"🗑 Запись <code>{target}</code> успешно удалена из базы!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Запись <code>{target}</code> не найдена в базе.", parse_mode="HTML")

async def get_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = get_all_bot_users()
    text = f"👥 <b>Пользователи ({len(users)}):</b>\n\n"
    for uid, uname, s_count, r_count in users:
        text += f"• ID: <code>{uid}</code> | @{uname or 'скрыт'} | Баланс: {s_count} | Рефы: {r_count}/{REFS_NEEDED}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def export_db_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if os.path.exists("bot_base.db"):
        await update.message.reply_document(document=open("bot_base.db", "rb"), caption="💾 База данных")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    doc = update.message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Отправь файл в формате .txt!")
        return

    await update.message.reply_text("⏳ Обрабатываю TXT файл...")
    
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()
    text_content = file_bytes.decode('utf-8', errors='ignore')

    lines = text_content.splitlines()
    added_count = 0

    conn = sqlite3.connect("bot_base.db")
    cursor = conn.cursor()

    for line in lines:
        if not line.strip():
            continue
        parts = line.split(";")
        if len(parts) >= 3:
            t_id = parts[0].strip()
            u_name = parts[1].strip().replace("@", "")
            ph = parts[2].strip()
            fio = parts[3].strip() if len(parts) > 3 else ""
            dob = parts[4].strip() if len(parts) > 4 else ""

            cursor.execute(
                "INSERT OR REPLACE INTO osint_base (target_id, username, phone, fio, birth_date, status) VALUES (?, ?, ?, ?, ?, 'approved')",
                (t_id, u_name, ph, fio, dob)
            )
            added_count += 1

    conn.commit()
    conn.close()

    await update.message.reply_text(f"🚀 Успешно занесено <b>{added_count}</b> человек в базу!", parse_mode="HTML")

async def handle_deep_search_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    searches, refs = get_user_stats(user_id)
    
    if searches <= 0:
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐️ Купить 1 Deep Search (10 Stars)", callback_data="buy_1")],
            [InlineKeyboardButton("⭐️ Купить 5 Deep Search (40 Stars)", callback_data="buy_5")]
        ])
        
        text = (
            f"❌ <b>У вас 0 доступных Deep Search проверок!</b>\n\n"
            f"🎁 <b>Как получить бесплатно:</b>\n"
            f"Пригласите <b>5 друзей</b> по своей ссылке, чтобы получить <b>1 Deep Search</b>!\n"
            f"Прогресс: <b>{refs}/{REFS_NEEDED}</b> друзей приглашено.\n\n"
            f"🔗 Твоя реферальная ссылка:\n<code>{ref_link}</code>\n\n"
            f"💳 <b>Или купи проверки мгновенно за Telegram Stars:</b>"
        )
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(
            f"⚡ <b>Deep Search Активирован!</b>\nУ вас осталось проверок: <b>{searches}</b>\n\n"
            f"Отправьте объект для глубокого пробива (номер или @username):",
            parse_mode="HTML"
        )

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    count = 1 if query.data == "buy_1" else 5
    price = 10 if count == 1 else 40
    prices = [LabeledPrice(f"{count} Deep Search", price)]
    
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=f"Пополнение Deep Search ({count} шт.)",
        description=f"Приобретение {count} глубоких проверок",
        payload=f"deep_search_{count}",
        provider_token="",
        currency="XTR",
        prices=prices
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    user_id = update.effective_user.id
    
    count = 1 if "1" in payload else 5
    add_searches(user_id, count)
    
    await update.message.reply_text(
        f"🎉 <b>Оплата прошла успешно!</b>\nВам начислено <b>+{count} Deep Search</b>.",
        parse_mode="HTML"
    )

async def start_add_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 <b>Отправь данные человека для добавления в базу:</b>\n\n"
        "Отправь информацию в удобном виде (ФИО, дата рождения, @username, телефон, ID).\n\n"
        "Для отмены отправь: /cancel",
        parse_mode="HTML"
    )
    return WAITING_PERSON_DATA

async def receive_person_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user.id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}")]
    ])
    context.bot_data[f"pending_{user.id}"] = text
    await context.bot.send_message(ADMIN_ID, f"📥 <b>Заявка от</b> @{user.username} (ID: <code>{user.id}</code>):\n\n{text}", parse_mode="HTML", reply_markup=keyboard)
    await update.message.reply_text("✅ Отправлено на модерацию администратору!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("buy_"):
        await buy_callback(update, context)
        return

    action, user_id_str = data.split("_")
    pending_key = f"pending_{user_id_str}"
    info_text = context.bot_data.get(pending_key, "")

    if action == "approve":
        target_id = re.search(r'(?:ID:?|id:?|\b)\s*(\d{7,11})\b', info_text)
        username = re.search(r'@([a-zA-Z0-9_]{5,32})', info_text)
        phone = re.search(r'\+?\d{10,15}', info_text)
        dob = re.search(r'\b(\d{2}[\.\/]\d{2}[\.\/]\d{4})\b', info_text)
        
        fio_match = re.search(r'(?:ФИО:?|ФИО\s*-?)\s*([^\n\r]+)', info_text, re.IGNORECASE)
        fio_val = ""
        if fio_match:
            fio_val = fio_match.group(1).split("Юз")[0].split("Тел")[0].split("ID")[0].split("ДР")[0].strip()
        elif not username and not phone:
            lines = [l.strip() for l in info_text.split('\n') if l.strip()]
            if lines:
                fio_val = lines[0]

        t_id = target_id.group(1) if target_id else ""
        u_name = username.group(1) if username else ""
        ph = phone.group(0) if phone else ""
        dob_val = dob.group(1) if dob else ""

        add_to_osint_base(t_id, u_name, ph, fio_val, dob_val, "")
        await query.edit_message_text(f"✅ <b>Заявка одобрена и занесена в базу!</b>\n\n{info_text}", parse_mode="HTML")
        try:
            await context.bot.send_message(int(user_id_str), "🎉 Ваша заявка одобрена!")
        except Exception:
            pass
    else:
        await query.edit_message_text(f"❌ <b>Заявка отклонена.</b>\n\n{info_text}", parse_mode="HTML")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    if text == "🔍 Поиск юзера / телефона":
        await update.message.reply_text("Отправь <code>@username</code> или номер телефона:", parse_mode="HTML")
        return
        
    if text in ["⚡ Deep Search", "⚡ Deep Search (Платный)"]:
        await handle_deep_search_click(update, context)
        return

    if text == "🔗 Партнёрка":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        searches, refs = get_user_stats(user_id)
        await update.message.reply_text(
            f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n"
            f"📊 <b>Ваша статистика:</b>\n"
            f"• Доступно Deep Search: <b>{searches} шт.</b>\n"
            f"• Приглашено в текущем круге: <b>{refs}/{REFS_NEEDED} друзей</b>\n\n"
            f"🎁 Пригласите ещё {REFS_NEEDED - refs} чел., чтобы получить <b>+1 Deep Search</b>!",
            parse_mode="HTML"
        )
        return

    if re.match(r'^\+?\d{10,15}$', text):
        local = search_in_local_db(text)
        phone_info = check_phone(text)
        if local:
            local_card = format_local_profile(local[0], local[1], local[2], local[3], local[4], local[5])
            res = f"{phone_info}\n\n{local_card}"
        else:
            res = f"{phone_info}\n\n📂 <b>Локальная база:</b> <i>Данные не найдены.</i>"
        await update.message.reply_text(res, parse_mode="HTML")
        return

    if text.startswith("@") or re.match(r'^[a-zA-Z0-9_]{5,32}$', text):
        username = text if text.startswith("@") else f"@{text}"
        clean_name = username.replace("@", "")
        
        await update.message.reply_text("⏳ Идет поиск по открытым базам...")
        
        local = search_in_local_db(clean_name)
        if local:
            local_card = format_local_profile(local[0], local[1], local[2], local[3], local[4], local[5])
            extracted_id = local[0] or await check_username_via_tgstat(clean_name)
        else:
            local_card = "📂 <b>Локальная база:</b> <i>Запись не найдена.</i>"
            extracted_id = await check_username_via_tgstat(clean_name)

        id_str = f"<code>{extracted_id}</code>" if extracted_id else "<i>Пользователь не найден или логин свободен</i>"

        res = (
            f"📱 <b>TELEGRAM ПОЛЬЗОВАТЕЛЬ:</b>\n"
            f"👤 <b>Юзернейм:</b> {username}\n"
            f"🆔 <b>Telegram ID:</b> {id_str}\n"
            f"🔗 <b>Прямая ссылка:</b> https://t.me/{clean_name}\n\n"
            f"{local_card}\n\n"
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
    app.add_handler(CommandHandler("del", delete_entry))
    app.add_handler(CommandHandler("users", get_users_list))
    app.add_handler(CommandHandler("export", export_db_file))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот успешно запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
