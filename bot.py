import asyncio
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardMarkup
)

BOT_TOKEN = "8684030373:AAF653ZjZlX1wBkklfve0h_QLoXawa3-k4s"
ADMIN_ID = 7706483533

CARD_PUMB = "4314140214993815"
CARD_PLN = "4213523416991947"

PRICE_PER_GOLD_UAH = 0.42
PRICE_PER_GRAM_UAH = 65.75
UAH_TO_PLN_RATE = 0.0873

CHANNELS = [
    {"name": "Основной канал", "url": "https://t.me/monolit_main", "chat_id": "@monolit_main"},
    {"name": "Отзывы", "url": "https://t.me/monolit_reviews", "chat_id": "@monolit_reviews"},
    {"name": "Инфо", "url": "https://t.me/monolit_inf", "chat_id": "@monolit_inf"}
]

SUPPORT_USERNAME = "@monolit_hq"

user_db = {}
user_languages = {}

class OrderState(StatesGroup):
    waiting_for_custom_amount = State()
    waiting_for_payment_proof = State()
    waiting_for_withdraw_amount = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_user(user_id: int):
    if user_id not in user_db:
        user_db[user_id] = {
            "balance_stars": 100,
            "balance_gold": 200,
            "nft_inventory": [],
            "refs": 0
        }
    return user_db[user_id]

def calculate_stars_price(amount: int, currency: str) -> str:
    if amount <= 100:
        base_uah = amount * 0.88
    elif amount <= 500:
        base_uah = amount * 0.754
    else:
        base_uah = amount * 0.753
    total_uah = round(base_uah + 20.0, 2)
    if "UAH" in currency:
        return f"{total_uah} UAH"
    elif "PLN" in currency:
        return f"{round(total_uah * UAH_TO_PLN_RATE, 2)} PLN"
    elif "Crypto" in currency or "GRAM" in currency:
        return f"{round(total_uah / PRICE_PER_GRAM_UAH, 2)} GRAM"
    return f"{total_uah} UAH"

def calculate_gold_price(amount: int, currency: str) -> str:
    total_uah = round(amount * PRICE_PER_GOLD_UAH, 2)
    if "UAH" in currency:
        return f"{total_uah} UAH"
    elif "PLN" in currency:
        return f"{round(total_uah * UAH_TO_PLN_RATE, 2)} PLN"
    elif "Crypto" in currency or "GRAM" in currency:
        return f"{round(total_uah / PRICE_PER_GRAM_UAH, 2)} GRAM"
    return f"{total_uah} UAH"

def calculate_nft_price(uah_price: int, currency: str) -> str:
    if "UAH" in currency:
        return f"{uah_price} UAH"
    elif "PLN" in currency:
        return f"{round(uah_price * UAH_TO_PLN_RATE, 2)} PLN"
    elif "Crypto" in currency or "GRAM" in currency:
        return f"{round(uah_price / PRICE_PER_GRAM_UAH, 2)} GRAM"
    return f"{uah_price} UAH"

NFT_PAGES = {
    1: [
        ("🍭 419 грн", "🍭 Леденец (419 грн)"), ("🧦 449 грн", "🧦 Носок (449 грн)"),
        ("🍦 449 грн", "🍦 Мороженое (449 грн)"), ("🍜 469 грн", "🍜 Лапша (469 грн)"),
        ("🦩 449 грн", "🦩 Фламинго (449 грн)"), ("🐶 519 грн", "🐶 Пес (519 грн)"),
        ("❄️ 369 грн", "❄️ 2025 (369 грн)"),     ("🎁 449 грн", "🎁 Подарок (449 грн)")
    ],
    2: [
        ("🗽 469 грн", "🗽 Статуя (469 грн)"),   ("🍿 469 грн", "🍿 Попкорн (469 грн)"),
        ("🐍 409 грн", "🐍 Змея (409 грн)"),    ("🧙‍♂️ 519 грн", "🧙‍♂️ Лепрекон (519 грн)"),
        ("🧦 419 грн", "🧦 Носок 2 (419 грн)"),  ("🚀 469 грн", "🚀 Ракета (469 грн)"),
        ("🍪 409 грн", "🍪 Пряник (409 грн)"),   ("📖 439 грн", "📖 Книга (439 грн)")
    ],
    3: [
        ("📦 409 грн", "📦 Коробка (409 грн)"),  ("🎒 419 грн", "🎒 Рюкзак (419 грн)"),
        ("💩 469 грн", "💩 Какашка (469 грн)"),  ("🍭 409 грн", "🍭 Леденец 2 (409 грн)"),
        ("🔘 519 грн", "🔘 Кнопка (519 грн)"),   ("🍄 509 грн", "🍄 Гриб (509 грн)"),
        ("🌻 549 грн", "🌻 Семечки (549 грн)"),  ("🎩 819 грн", "🎩 Шляпа (819 грн)")
    ],
    4: [
        ("🎂 449 грн", "🎂 Торт (449 грн)"),     ("🏅 469 грн", "🏅 Медаль (469 грн)"),
        ("🌙 559 грн", "🌙 Кулон (559 грн)"),     ("🐰 499 грн", "🐰 Кролик (499 грн)"),
        ("🍀 499 грн", "🍀 Клевер (499 грн)"),   ("👁 649 грн", "👁 Глаз (649 грн)"),
        ("🐒 659 грн", "🐒 Обезьяна (659 грн)"), ("⚔️ 619 грн", "⚔️ Меч (619 грн)")
    ],
    5: [
        ("🚬 1219 грн", "🚬 Косяк (1219 грн)"),  ("🦯 369 грн", "🦯 Трость (369 грн)"),
        ("💐 519 грн", "💐 Букет (519 грн)")
    ]
}

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])
    await message.answer("<b>Выберите язык / Оберіть мову / Choose language:</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang
    await callback.message.delete()
    
    buttons = []
    for ch in CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["url"])])
    buttons.append([InlineKeyboardButton(text="Я подписался ✅", callback_data="check_sub")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await bot.send_message(
        callback.from_user.id,
        "<b>MONOLIT</b>\n\nДля доступа к сервису, пожалуйста, подпишитесь на наши каналы:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = True
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                is_subscribed = False
                break
        except Exception:
            pass
            
    if is_subscribed:
        await callback.message.delete()
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🌟 Купить Stars"), KeyboardButton(text="🥇 Купить Gold (Standoff 2)")],
                [KeyboardButton(text="🖼 Купить NFT"), KeyboardButton(text="👤 Профиль")],
                [KeyboardButton(text="🎁 Рефералка"), KeyboardButton(text="🎮 Другие игры")]
            ],
            resize_keyboard=True
        )
        await bot.send_message(user_id, "⚡️ <b>Добро пожаловать в MONOLIT!</b>\nВыберите раздел:", reply_markup=kb, parse_mode="HTML")
    else:
        await callback.answer("❌ Вы подписались не на все каналы!", show_alert=True)

@dp.message(F.text == "👤 Профиль")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    u = get_user(user_id)
    text = (
        f"👤 <b>Ваш профиль MONOLIT</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🌟 Баланс Stars: <b>{u['balance_stars']} ⭐</b>\n"
        f"🥇 Баланс Gold: <b>{u['balance_gold']} 🥇</b>\n"
        f"🖼 NFT в инвентаре: <b>{len(u['nft_inventory'])} шт.</b>\n"
        f"🎁 Приглашено друзей: <b>{u['refs']}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Вывести средства", callback_data="menu_withdraw")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.text == "🎁 Рефералка")
async def show_ref(message: types.Message):
    user_id = message.from_user.id
    u = get_user(user_id)
    ref_text = (
        "🎁 <b>Реферальная программа MONOLIT</b>\n\n"
        "1️⃣ Пригласи 7 активных друзей в бота.\n"
        "2️⃣ Напиши в чат канала @monolit_main сообщение вида:\n"
        "<code>пригласил @юз_кого_пригласил</code>\n"
        "3️⃣ За <b>7 приглашений</b> получаешь подарок <b>«Мишка» (15⭐)</b>!\n\n"
        f"👥 Ваши приглашенные рефералы: <b>{u['refs']}</b>"
    )
    await message.answer(ref_text, parse_mode="HTML")

@dp.message(F.text == "🎮 Другие игры")
async def show_other(message: types.Message):
    await message.answer(f"🎮 По всем вопросам и заказу для других игр обращайтесь в ЛС: {SUPPORT_USERNAME}")

@dp.message(F.text == "🌟 Купить Stars")
async def buy_stars(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 ⭐", callback_data="item_Stars_50"), InlineKeyboardButton(text="100 ⭐", callback_data="item_Stars_100")],
        [InlineKeyboardButton(text="250 ⭐", callback_data="item_Stars_250"), InlineKeyboardButton(text="500 ⭐", callback_data="item_Stars_500")],
        [InlineKeyboardButton(text="✏️ Свое количество", callback_data="item_Stars_custom")]
    ])
    await message.answer("🌟 <b>Выберите пакет Telegram Stars или укажите свое количество:</b>", reply_markup=kb, parse_mode="HTML")

@dp.message(F.text == "🥇 Купить Gold (Standoff 2)")
async def buy_gold(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100 🥇", callback_data="item_Gold_100"), InlineKeyboardButton(text="500 🥇", callback_data="item_Gold_500")],
        [InlineKeyboardButton(text="1000 🥇", callback_data="item_Gold_1000"), InlineKeyboardButton(text="3000 🥇", callback_data="item_Gold_3000")],
        [InlineKeyboardButton(text="✏️ Свое количество", callback_data="item_Gold_custom")]
    ])
    await message.answer("🥇 <b>Выберите количество Gold или укажите свое:</b>", reply_markup=kb, parse_mode="HTML")

@dp.message(F.text == "🖼 Купить NFT")
async def buy_nft(message: types.Message):
    await send_nft_page(message, page=1, edit=False)

async def send_nft_page(message: types.Message, page: int, edit: bool = False):
    items = NFT_PAGES.get(page, [])
    buttons = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(text=items[i][0], callback_data=f"nftitem_{items[i][1]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(text=items[i+1][0], callback_data=f"nftitem_{items[i+1][1]}"))
        buttons.append(row)
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"nftpage_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page}/5", callback_data="ignore"))
    if page < 5:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"nftpage_{page+1}"))
    buttons.append(nav_row)
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "🐸 <b>NFT Подарки</b>\n\nВыберите NFT:"
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("nftpage_"))
async def process_nft_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[1])
    await send_nft_page(callback.message, page=page, edit=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("nftitem_"))
async def process_nft_item(callback: types.CallbackQuery, state: FSMContext):
    nft_data = callback.data.replace("nftitem_", "")
    try:
        price_uah = int(nft_data.split("(")[1].replace(" грн)", "").strip())
    except Exception:
        price_uah = 400
    await state.update_data(chosen_item=f"NFT {nft_data}", item_type="NFT", nft_price=price_uah)
    await show_currency_selection(callback.message, f"NFT {nft_data}", item_type="NFT", edit=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("item_"))
async def process_item_choice(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    item_type = parts[1]
    value = parts[2]
    if value == "custom":
        await state.update_data(item_type=item_type)
        await state.set_state(OrderState.waiting_for_custom_amount)
        await callback.message.answer("⌨️ Введите нужное количество (числом) в ответном сообщении:")
        await callback.answer()
        return
    amount = int(value)
    item_name = f"{amount} {item_type}"
    await state.update_data(chosen_item=item_name, item_type=item_type, item_amount=amount)
    await show_currency_selection(callback.message, item_name, item_type=item_type, edit=True)
    await callback.answer()

@dp.message(OrderState.waiting_for_custom_amount)
async def process_custom_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item_type = data.get("item_type", "Stars")
    amount_text = message.text.strip()
    if not amount_text.isdigit():
        await message.answer("❌ Пожалуйста, введите корректное число!")
        return
    amount = int(amount_text)
    item_name = f"{amount} {item_type}"
    await state.update_data(chosen_item=item_name, item_type=item_type, item_amount=amount)
    await show_currency_selection(message, item_name, item_type=item_type, edit=False)

async def show_currency_selection(message: types.Message, item_name: str, item_type: str, edit: bool = False):
    currency_buttons = [
        [InlineKeyboardButton(text="🇵🇱 PLN (Blik / Card)", callback_data="pay_PLN")],
        [InlineKeyboardButton(text="🇺🇦 UAH (Гривны ПУМБ)", callback_data="pay_UAH")],
        [InlineKeyboardButton(text="💎 Crypto (GRAM)", callback_data="pay_Crypto")],
        [InlineKeyboardButton(text="💵 USD / 💶 EUR", callback_data="pay_USD_EUR")]
    ]
    if item_type == "Gold":
        currency_buttons.insert(2, [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="pay_Stars")])
    kb = InlineKeyboardMarkup(inline_keyboard=currency_buttons)
    text = f"💳 <b>Вы выбрали:</b> {item_name}\n\nВыберите удобную валюту для оплаты:"
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("pay_"))
async def process_currency_choice(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.replace("pay_", "").replace("_", "/")
    data = await state.get_data()
    item_name = data.get("chosen_item", "Товар")
    item_type = data.get("item_type", "Stars")
    amount = data.get("item_amount", 100)
    
    if item_type == "Stars":
        price_str = f"К оплате: <b>{calculate_stars_price(amount, currency)}</b>"
    elif item_type == "Gold":
        price_str = f"К оплате: <b>{calculate_gold_price(amount, currency)}</b>"
    elif item_type == "NFT":
        nft_price_uah = data.get("nft_price", 400)
        price_str = f"К оплате: <b>{calculate_nft_price(nft_price_uah, currency)}</b>"
    else:
        price_str = ""

    await state.update_data(chosen_currency=currency, price_info=price_str)
    
    card_info = ""
    if "UAH" in currency:
        card_info = f"<code>{CARD_PUMB}</code>\n\n💬 Bank: <b>ПУМБ (Украина)</b>"
    elif "PLN" in currency:
        card_info = f"<code>{CARD_PLN}</code>\n\n💬 Card / Blik (Польша)"
    elif "Crypto" in currency or "GRAM" in currency:
        card_info = f"💎 <b>Оплата криптовалютой GRAM</b>\nПеревод на юзернейм: <code>{SUPPORT_USERNAME}</code>"
    else:
        card_info = f"Для реквизитов напишите оператору: {SUPPORT_USERNAME}"
        
    text = (
        f"<b>Заказ:</b> {item_name}\n"
        f"💰 {price_str}\n\n"
        f"<b>Реквизиты для оплаты:</b>\n{card_info}\n\n"
        f"🏦 <b>После оплаты отправьте сюда скриншот или PDF-чек 👇</b>"
    )
    await state.set_state(OrderState.waiting_for_payment_proof)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# --- ОБРАБОТЧИК ЧЕКОВ (ПРИЕМ ЛЮБОГО СООБЩЕНИЯ/ФОТО ПОСЛЕ ВЫБОРА РЕКВИЗИТОВ) ---
@dp.message(OrderState.waiting_for_payment_proof)
async def receive_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item = data.get("chosen_item", "Товар")
    currency = data.get("chosen_currency", "Валюта")
    price_info = data.get("price_info", "")
    user = message.from_user
    username_text = f"@{user.username}" if user.username else f"ID: {user.id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Начислить на баланс", callback_data=f"adm_accept_{user.id}_{item}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject_{user.id}")
    ]])
    
    admin_caption = (
        f"📥 <b>Новая оплата на модерацию!</b>\n\n"
        f"👤 Пользователь {username_text} приобрел <b>{item}</b> ({price_info})\n"
        f"💳 Валюта: <b>{currency}</b>"
    )

    # Пересылаем админу фото или документ
    if message.photo:
        await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
    elif message.document:
        await bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
    else:
        # Если отправили просто текст вместо квитанции
        await bot.send_message(chat_id=ADMIN_ID, text=f"{admin_caption}\n\n💬 Текст пользователя: {message.text}", reply_markup=kb, parse_mode="HTML")

    await message.answer("✅ <b>Чек отправлен на модерацию!</b> Ожидайте проверки администратором.", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "menu_withdraw")
async def start_withdraw_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_for_withdraw_amount)
    await callback.message.answer(
        "📤 <b>Запрос на вывод средств</b>\n\n"
        "Напишите в чат, что хотите вывести (например: <code>100 Gold</code> или <code>50 Stars</code>).\n\n"
        "⚠️ <i>Минимум:</i> Gold — <b>100</b>, Stars — <b>50</b>.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(OrderState.waiting_for_payment_proof, F.photo | F.document | F.text)
async def receive_payment_proof(message: types.Message, state: FSMContext):
    print("--- ПОЛУЧЕН ЧЕК ОТ ПОЛЬЗОВАТЕЛЯ ---")
    data = await state.get_data()
    print(f"Данные стейта: {data}")
    
    item = data.get("chosen_item", "Товар")
    currency = data.get("chosen_currency", "Валюта")
    price_info = data.get("price_info", "")
    user = message.from_user
    username_text = f"@{user.username}" if user.username else f"ID: {user.id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Начислить на баланс", callback_data=f"adm_accept_{user.id}_{item}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject_{user.id}")
    ]])
    
    admin_caption = (
        f"📥 <b>Новая оплата на модерацию!</b>\n\n"
        f"👤 Пользователь {username_text} приобрел <b>{item}</b> ({price_info})\n"
        f"💳 Валюта: <b>{currency}</b>"
    )

    try:
        if message.photo:
            print("Отправка фото админу...")
            await bot.send_photo(chat_id=7786483533, photo=message.photo[-1].file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
        elif message.document:
            print("Отправка документа админу...")
            await bot.send_document(chat_id=7786483533, document=message.document.file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
        else:
            print("Отправка текста админу...")
            await bot.send_message(chat_id=7786483533, text=f"{admin_caption}\n\n💬 Текст: {message.text}", reply_markup=kb, parse_mode="HTML")
        
        print("Успешно отправлено админу!")
    except Exception as e:
        print(f"ОШИБКА ПРИ ОТПРАВКЕ АДМИНУ: {e}")

    await message.answer("✅ <b>Чек отправлен на модерацию!</b> Ожидайте проверки администратором.", parse_mode="HTML")
    await state.clear()


async def process_withdraw_amount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    u = get_user(user_id)
    text = message.text.lower().strip()
    amount = int(''.join(filter(str.isdigit, text)) or 0)

    if "gold" in text or "голд" in text:
        if amount < 100:
            await message.answer("❌ Минимум для вывода Gold — <b>100 Gold</b>.", parse_mode="HTML")
            return
        if u["balance_gold"] < amount:
            await message.answer(f"❌ Недостаточно средств! Баланс Gold: <b>{u['balance_gold']}</b>.", parse_mode="HTML")
            return
    elif "star" in text or "звезд" in text or "звёзд" in text:
        if amount < 50:
            await message.answer("❌ Минимум для вывода Stars — <b>50 Stars</b>.", parse_mode="HTML")
            return
        if u["balance_stars"] < amount:
            await message.answer(f"❌ Недостаточно средств! Баланс Stars: <b>{u['balance_stars']}</b>.", parse_mode="HTML")
            return
    else:
        await message.answer("❌ Укажите корректно валюту и количество (например: <code>100 Gold</code>)", parse_mode="HTML")
        return

    withdraw_request_text = message.text
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить вывод", callback_data=f"wd_accept_{user_id}_{withdraw_request_text}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd_reject_{user_id}")
    ]])

    username_text = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"

    admin_caption = (
        f"📤 <b>ЗАПРОС НА ВЫВОД!</b>\n\n"
        f"👤 Юзер: {username_text} (ID: <code>{user_id}</code>)\n\n"
        f"💰 <b>Баланс юзера:</b>\n"
        f"• Stars: <b>{u['balance_stars']} ⭐</b>\n"
        f"• Gold: <b>{u['balance_gold']} 🥇</b>\n"
        f"• NFT: <b>{len(u['nft_inventory'])} шт.</b>\n\n"
        f"📌 <b>Запрос:</b> <code>{withdraw_request_text}</code>"
    )
    await bot.send_message(ADMIN_ID, admin_caption, reply_markup=admin_kb, parse_mode="HTML")
    await message.answer("✅ <b>Запрос отправлен администратору.</b> Ожидайте.", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith(("adm_", "wd_")))
async def admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    parts = callback.data.split("_")
    action_type = parts[0]
    action = parts[1]
    target_user_id = int(parts[2])
    u = get_user(target_user_id)
    
    if action_type == "adm":
        if action == "accept":
            item_purchased = "_".join(parts[3:]) if len(parts) > 3 else ""
            if "Stars" in item_purchased:
                try: u["balance_stars"] += int(item_purchased.split()[0])
                except: pass
            elif "Gold" in item_purchased:
                try: u["balance_gold"] += int(item_purchased.split()[0])
                except: pass
            elif "NFT" in item_purchased or "грн" in item_purchased:
                u["nft_inventory"].append(item_purchased)
            
            if callback.message.photo or callback.message.document:
                await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ <b>Одобрено и зачислено!</b>", parse_mode="HTML")
            else:
                await callback.message.edit_text(text=callback.message.text + "\n\n✅ <b>Одобрено!</b>", parse_mode="HTML")
            await bot.send_message(target_user_id, "🎉 Ваша оплата подтверждена! Товар зачислен.", parse_mode="HTML")
        else:
            if callback.message.photo or callback.message.document:
                await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ <b>Отклонено.</b>", parse_mode="HTML")
            else:
                await callback.message.edit_text(text=callback.message.text + "\n\n❌ <b>Отклонено.</b>", parse_mode="HTML")
            await bot.send_message(target_user_id, "❌ Ваша оплата отклонена администратором.")

    elif action_type == "wd":
        if action == "accept":
            withdraw_text = "_".join(parts[3:]) if len(parts) > 3 else "средства"
            await callback.message.edit_text(text=callback.message.text + "\n\n✅ <b>ВЫВОД ПОДТВЕРЖДЕН</b>", parse_mode="HTML")
            await bot.send_message(target_user_id, f"🎉 Вывод подтвержден! Переведено: <b>{withdraw_text}</b>.", parse_mode="HTML")
        else:
            await callback.message.edit_text(text=callback.message.text + "\n\n❌ <b>ВЫВОД ОТКЛОНЕН</b>", parse_mode="HTML")
            await bot.send_message(target_user_id, "❌ Ваш запрос на вывод средств отклонен.")

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_http():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

async def main():
    threading.Thread(target=run_http, daemon=True).start()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main()) 
