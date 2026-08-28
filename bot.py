import asyncio
import re
import requests
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import geocoder, carrier
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    PreCheckoutQueryHandler, CallbackQueryHandler, filters, ContextTypes
)

TOKEN = "8408315552:AAG5CczuITP2tJnNdMlCnRPXnvXoM6-xSUA"

USER_LIMITS = {}
REFERRALS = {}
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

def get_user_limit(user_id: int) -> int:
    if user_id not in USER_LIMITS:
        USER_LIMITS[user_id] = DEFAULT_FREE_LIMIT
    return USER_LIMITS[user_id]

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Реферальная ссылка", callback_data="btn_ref")],
        [InlineKeyboardButton("💳 Купить поиски (+2 ⭐️)", callback_data="btn_buy")],
        [InlineKeyboardButton("ℹ️ Баланс и OSINT Инфо", callback_data="btn_info")]
    ])

def get_platforms_keyboard(user_id: int, username: str):
    if user_id not in USER_SELECTIONS:
        USER_SELECTIONS[user_id] = set(ALL_SERVICES.keys())

    selected = USER_SELECTIONS[user_id]
    buttons = []
    
    keys = list(ALL_SERVICES.keys())
    for i in range(0, len(keys), 2):
        row = []
        k1 = keys[i]
        icon1 = "✅" if k1 in selected else "❌"
        row.append(InlineKeyboardButton(f"{icon1} {ALL_SERVICES[k1]}", callback_data=f"toggle_{k1}_{username}"))
        
        if i + 1 < len(keys):
            k2 = keys[i+1]
            icon2 = "✅" if k2 in selected else "❌"
            row.append(InlineKeyboardButton(f"{icon2} {ALL_SERVICES[k2]}", callback_data=f"toggle_{k2}_{username}"))
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("✅ Выбрать все", callback_data=f"select_all_{username}"),
        InlineKeyboardButton("❌ Снять все", callback_data=f"deselect_all_{username}")
    ])
    buttons.append([InlineKeyboardButton("🚀 НАЧАТЬ ПОИСК И СБОР ИНФО", callback_data=f"start_search_{username}")])
    
    return InlineKeyboardMarkup(buttons)

def parse_page_details(url: str, response_text: str, service_key: str) -> str:
    """Извлекает метатеги страницы (заголовок, описание и bio)"""
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

        if service_key == "gh":
            bio = soup.find("div", class_="p-note user-profile-bio")
            if bio:
                info_parts.append(f"📌 *Bio:* {bio.text.strip()}")
        elif service_key == "hb":
            user_name = soup.find("a", class_="tm-user-card__name")
            if user_name:
                info_parts.append(f"🏷️ *Имя на Хабре:* {user_name.text.strip()}")

        if info_parts:
            return "\n   " + "\n   ".join(info_parts)
    except Exception:
        pass
    return ""

async def run_full_search(username: str, update: Update, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    results = []
    selected_keys = USER_SELECTIONS.get(user_id, set(ALL_SERVICES.keys()))

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
        if key in selected_keys:
            url = service_urls[key]
            
            # Проверка Telegram через родной Bot API
            if key == "tg":
                try:
                    chat_info = await context.bot.get_chat(f"@{username}")
                    title = chat_info.first_name or chat_info.title or "Профиль"
                    bio = chat_info.bio or ""
                    bio_str = f"\n   📝 *Bio:* {bio}" if bio else ""
                    results.append(f"{name}: ✅ [Профиль Telegram]({url})\n   👤 *Имя:* {title}{bio_str}")
                except Exception:
                    results.append(f"{name}: ❌ Не найден")
                continue

            # Проверка веб-сервисов
            try:
                res = requests.get(url, headers=headers, timeout=3.0, allow_redirects=True)
                if res.status_code in [200, 301, 302] and "page_not_found" not in res.url:
                    details = parse_page_details(url, res.text, key)
                    results.append(f"{name}: ✅ [Ссылка на профиль]({url}){details}")
                else:
                    results.append(f"{name}: ❌ Не найден")
            except Exception:
                results.append(f"{name}: ⚠️ Ошибка подключения")

    results.append(f"\n🌐 Google Search: 🔎 [Поиск упоминаний](https://www.google.com/search?q={username})")

    USER_LIMITS[user_id] -= 1
    new_limit = USER_LIMITS[user_id]

    final_text = (
        f"📊 **Расширенный отчёт по никнейму:** `{username}`\n"
        f"⚙️ **Проверено платформ:** `{len(selected_keys)} из 11`\n\n"
        + "\n\n".join(results) +
        f"\n\n📉 *Осталось поисков:* `{new_limit}`"
    )

    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(
        final_text, 
        parse_mode="Markdown", 
        disable_web_page_preview=True,
        reply_markup=get_main_keyboard()
    )

async def run_phone_search(phone_raw: str, update: Update, user_id: int):
    """Модуль OSINT-анализа по номеру телефона"""
    clean_phone = re.sub(r"\D", "", phone_raw)
    if len(clean_phone) == 11 and clean_phone.startswith("8"):
        clean_phone = "7" + clean_phone[1:]
    
    formatted_phone = f"+{clean_phone}"
    
    country_name = "Неизвестно"
    operator_name = "Неизвестно"
    is_valid = False

    try:
        parsed_num = phonenumbers.parse(formatted_phone, None)
        is_valid = phonenumbers.is_valid_number(parsed_num)
        if is_valid:
            country_name = geocoder.description_for_number(parsed_num, "ru") or "Неизвестно"
            operator_name = carrier.name_for_number(parsed_num, "ru") or "Частный/Неизвестен"
    except Exception:
        pass

    # Прямые ссылки в мессенджеры
    wa_url = f"https://wa.me/{clean_phone}"
    tg_url = f"https://t.me/+{clean_phone}"
    viber_url = f"viber://chat?number=%2B{clean_phone}"
    messenger_url = f"https://m.me/{clean_phone}"
    google_url = f"https://www.google.com/search?q=%22%2B{clean_phone}%22+OR+%22{clean_phone}%22"
    ya_url = f"https://yandex.ru/search/?text=%22{clean_phone}%22"

    USER_LIMITS[user_id] -= 1
    new_limit = USER_LIMITS[user_id]

    valid_str = "✅ Действителен" if is_valid else "⚠️ Нестандартный формат"

    phone_text = (
        f"📞 **Глубокий OSINT-Анализ номера:** `{formatted_phone}`\n\n"
        f"📌 **Данные оператора и региона:**\n"
        f"• Статус: `{valid_str}`\n"
        f"• Страна / Регион: `{country_name}`\n"
        f"• Оператор связи: `{operator_name}`\n\n"
        f"💬 **Прямой переход в мессенджеры:**\n"
        f"• 🟢 **WhatsApp:** [Перейти в чат]({wa_url})\n"
        f"• ✈️ **Telegram:** [Проверить аккаунт]({tg_url})\n"
        f"• 🟣 **Viber:** [Открыть чат]({viber_url})\n"
        f"• 🔵 **FB Messenger:** [Открыть чат]({messenger_url})\n\n"
        f"🔎 **Поисковые базы:**\n"
        f"• 🌐 **Google:** [Искать упоминания]({google_url})\n"
        f"• 🔴 **Яндекс:** [Проверить объявления]({ya_url})\n\n"
        f"📉 *Осталось поисков:* `{new_limit}`"
    )

    await update.message.reply_text(
        phone_text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=get_main_keyboard()
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    limit = get_user_limit(user.id)
    
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id != user.id and user.id not in REFERRALS:
            REFERRALS[user.id] = referrer_id
            USER_LIMITS[referrer_id] = get_user_limit(referrer_id) + 1
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text="🎉 По вашей ссылке зарегистрировался новый пользователь! Вам начислен **+1 поиск**.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    welcome_text = (
        f"⚡ **Добро пожаловать в OSINT Intel Bot, {user.first_name}!** ⚡\n\n"
        f"🎯 **Возможности:**\n"
        f"• Сбор открытых данных и парсинг профилей по Никнейму (11 платформ).\n"
        f"• Проверка Telegram ID.\n"
        f"• **Глубокий OSINT по номерам телефонов** (Регион, оператор, WhatsApp, Telegram, Viber, Messenger).\n\n"
        f"🆔 **Твой Telegram ID:** `{user.id}`\n"
        f"📊 **Осталось поисков:** `{limit}`\n\n"
        f"👇 *Отправь Никнейм, Telegram ID или Номер телефона!*"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    bot_username = (await context.bot.get_me()).username

    if data == "btn_buy":
        await query.answer()
        await buy_searches(update, context)
        return
    elif data == "btn_info":
        await query.answer()
        limit = get_user_limit(user_id)
        info_text = (
            f"👤 **Ваш профиль:**\n"
            f"• Telegram ID: `{user_id}`\n"
            f"• Доступно проверок: `{limit}`\n\n"
            f"ℹ️ **Как работает сбор данных:**\n"
            f"Бот анализирует метатеги страниц по никнеймам, а по номерам телефонов формирует прямые мосты к профилям WhatsApp, Telegram, Viber и Messenger."
        )
        await query.message.reply_text(info_text, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return
    elif data == "btn_ref":
        await query.answer()
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        ref_text = f"🤝 **Ваша реферальная ссылка:**\n`{ref_link}`\n\nЗа каждого друга получаем +1 поиск!"
        await query.message.reply_text(ref_text, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    if user_id not in USER_SELECTIONS:
        USER_SELECTIONS[user_id] = set(ALL_SERVICES.keys())

    if data.startswith("toggle_"):
        _, key, username = data.split("_", 2)
        if key in USER_SELECTIONS[user_id]:
            USER_SELECTIONS[user_id].remove(key)
        else:
            USER_SELECTIONS[user_id].add(key)
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=get_platforms_keyboard(user_id, username))

    elif data.startswith("select_all_"):
        username = data.replace("select_all_", "")
        USER_SELECTIONS[user_id] = set(ALL_SERVICES.keys())
        await query.answer("Выбраны все платформы")
        await query.edit_message_reply_markup(reply_markup=get_platforms_keyboard(user_id, username))

    elif data.startswith("deselect_all_"):
        username = data.replace("deselect_all_", "")
        USER_SELECTIONS[user_id] = set()
        await query.answer("Снять выбор со всех платформ")
        await query.edit_message_reply_markup(reply_markup=get_platforms_keyboard(user_id, username))

    elif data.startswith("start_search_"):
        username = data.replace("start_search_", "")
        if not USER_SELECTIONS[user_id]:
            await query.answer("⚠️ Выберите хотя бы одну платформу!", show_alert=True)
            return
        await query.answer()
        await query.message.edit_text(f"🔍 Парсинг данных и поиск профилей для `{username}`...", parse_mode="Markdown")
        await run_full_search(username, update, user_id, context)

async def buy_searches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title="2 поиска в OSINT Bot",
        description="Пополнение баланса: +2 проверки",
        payload="osint_searches_pack",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("2 Поиска", 1)]
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    USER_LIMITS[user_id] = get_user_limit(user_id) + 2
    await update.message.reply_text(
        f"🎉 **Оплата прошла успешно!** Вам добавлено +2 поиска. Баланс: `{USER_LIMITS[user_id]}`",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text_input = update.message.text.strip().replace("@", "")

    limit = get_user_limit(user_id)
    if limit <= 0:
        await update.message.reply_text(
            "❌ **У вас закончились бесплатные поиски!**\n\nКупите **+2 поиска** за 1 ⭐️ Star или пригласите друга по своей реферальной ссылке!",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    # 1. Распознавание номера телефона
    clean_digits = re.sub(r"\D", "", text_input)
    if (len(clean_digits) >= 10 and len(clean_digits) <= 12 and text_input.startswith("+")) or (len(clean_digits) == 11 and (text_input.startswith("8") or text_input.startswith("7"))):
        await update.message.reply_text(f"🔍 Определение оператора и поиск чатов в мессенджерах для `{text_input}`...", parse_mode="Markdown")
        await run_phone_search(text_input, update, user_id)
        return

    # 2. Проверка по Telegram ID
    if text_input.isdigit() and len(text_input) <= 10:
        target_id = int(text_input)
        username = None
        first_name = "Неизвестный профиль"

        try:
            chat_info = await asyncio.wait_for(context.bot.get_chat(target_id), timeout=1.5)
            username = chat_info.username
            first_name = chat_info.first_name or first_name
        except Exception:
            pass

        if username:
            info_text = (
                f"👤 **Данные Telegram аккаунта:**\n"
                f"• Имя: `{first_name}`\n"
                f"• Telegram ID: `{target_id}`\n"
                f"• Username: `@{username}`\n\n"
                f"⚙️ **Выберите платформы для сканирования:**"
            )
            await update.message.reply_text(info_text, parse_mode="Markdown", reply_markup=get_platforms_keyboard(user_id, username))
        else:
            info_text = (
                f"📊 **Информация по ID:** `{target_id}`\n\n"
                f"⚠️ Профиль с таким ID скрыт настройками приватности Telegram или не общался с ботом.\n"
                f"💡 Попробуйте ввести его никнейм вручную!"
            )
            await update.message.reply_text(info_text, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    # 3. Выбор платформ по никнейму
    menu_text = (
        f"🎯 **Настройка поиска для никнейма:** `{text_input}`\n\n"
        f"Выберите платформы, на которых хотите выполнить поиск:"
    )
    await update.message.reply_text(
        menu_text, 
        parse_mode="Markdown", 
        reply_markup=get_platforms_keyboard(user_id, text_input)
    )

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy_searches))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_user))
    
    print("🤖 Бот запущен! Поддержка номеров телефонов и точность поиска настроены.")
    app.run_polling()
