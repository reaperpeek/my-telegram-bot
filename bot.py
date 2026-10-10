import asyncio
import logging
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

BOT_TOKEN = "8684030373:AAH3SBGRKk41DSydEJG1H8t05SX-N_uPrmw"
ADMIN_ID = 7706483533

# Точные реквизиты
CARD_PUMB = "4314140214993815"       # UAH (Гривны)
CARD_PLN = "4213523416991947"        # PLN (Злотые)

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
            "balance_stars": 0,
            "balance_gold": 0,
            "nft_inventory": [],
            "refs": 0
        }
    return user_db[user_id]

# NFT Подарки по страницам (+20 грн наценка)
NFT_PAGES = {
    1: [
        ("🍭 419 грн", "419_грн_Lollipop"), ("🧦 449 грн", "449_грн_Sock"),
        ("🍦 449 грн", "449_грн_IceCream"), ("🍜 469 грн", "469_грн_Noodles"),
        ("🦩 449 грн", "449_грн_Flamingo"), ("🐶 519 грн", "519_грн_Dog"),
        ("❄️ 369 грн", "369_грн_2025"),     ("🎁 449 грн", "449_грн_Gift")
    ],
    2: [
        ("🗽 469 грн", "469_грн_Statue"),   ("🍿 469 грн", "469_грн_Popcorn"),
        ("🐍 409 грн", "409_грн_Snake"),    ("🧙‍♂️ 519 грн", "519_грн_Leprechaun"),
        ("🧦 419 грн", "419_грн_Sock2"),    ("🚀 469 грн", "469_грн_Rocket"),
        ("🍪 409 грн", "409_грн_Ginger"),   ("📖 439 грн", "439_грн_Book")
    ],
    3: [
        ("📦 409 грн", "409_грн_Box"),      ("🎒 419 грн", "419_грн_Backpack"),
        ("💩 469 грн", "469_грн_Poop"),     ("🍭 409 грн", "409_грн_Lollipop2"),
        ("🔘 519 грн", "519_грн_Button"),   ("🍄 509 грн", "509_грн_Mushroom"),
        ("🌻 549 грн", "549_грн_Seeds"),    ("🎩 819 грн", "819_грн_Hat")
    ],
    4: [
        ("🎂 449 грн", "449_грн_Cake"),     ("🏅 469 грн", "469_грн_Medal"),
        ("🌙 559 грн", "559_грн_Moon"),     ("🐰 499 грн", "499_грн_Rabbit"),
        ("🍀 499 грн", "499_грн_Clover"),   ("👁 649 грн", "649_грн_Eye"),
        ("🐒 659 грн", "659_грн_Monkey"),   ("⚔️ 619 грн", "619_грн_Sword")
    ],
    5: [
        ("🚬 1219 грн", "1219_грн_Cigar"),  ("🦯 369 грн", "369_грн_Cane"),
        ("💐 519 грн", "519_грн_Bouquet")
    ]
}

# --- СТАРТ И ВЫБОР ЯЗЫКА ---
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

# --- ГЛАВНОЕ МЕНЮ ---
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
        [InlineKeyboardButton(text="📤 Вывести", callback_data="menu_withdraw")]
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
        "⚠️ <i>Фейковые и неактивные аккаунты не учитываются!</i>\n"
        f"👥 Ваши приглашенные рефералы: <b>{u['refs']}</b>"
    )
    await message.answer(ref_text, parse_mode="HTML")

@dp.message(F.text == "🎮 Другие игры")
async def show_other(message: types.Message):
    await message.answer(f"🎮 По всем вопросам и заказу для других игр обращайтесь в ЛС: {SUPPORT_USERNAME}")

# --- ПОКУПКА ---
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

# --- ПОКУПКА NFT (ПАГИНАЦИЯ) ---
@dp.message(F.text == "🖼 Купить NFT")
async def buy_nft(message: types.Message):
    await send_nft_page(message, page=1, edit=False)

async def send_nft_page(message: types.Message, page: int, edit: bool = False):
    items = NFT_PAGES.get(page, [])
    buttons = []
    
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(text=items[i][0], callback_data=f"item_NFT_{items[i][1]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(text=items[i+1][0], callback_data=f"item_NFT_{items[i+1][1]}"))
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

# --- ВЫБОР ТОВАРОВ И КАСТОМНОГО КОЛИЧЕСТВА ---
@dp.callback_query(F.data.startswith("item_"))
async def process_item_choice(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    item_type = parts[1]
    value = "_".join(parts[2:])
    
    if value == "custom":
        await state.update_data(item_type=item_type)
        await state.set_state(OrderState.waiting_for_custom_amount)
        await callback.message.answer("⌨️ Введите нужное количество (числом) в ответном сообщении:")
        await callback.answer()
        return
        
    item_name = f"{value.replace('_', ' ')} {item_type}"
    await state.update_data(chosen_item=item_name)
    await show_currency_selection(callback.message, item_name, edit=True)
    await callback.answer()

@dp.message(OrderState.waiting_for_custom_amount)
async def process_custom_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item_type = data.get("item_type", "Item")
    amount = message.text.strip()
    
    if not amount.isdigit():
        await message.answer("❌ Пожалуйста, введите корректное число!")
        return
        
    item_name = f"{amount} {item_type}"
    await state.update_data(chosen_item=item_name)
    await show_currency_selection(message, item_name, edit=False)
    await state.set_state(None)

async def show_currency_selection(message: types.Message, item_name: str, edit: bool = False):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇵🇱 PLN (Blik / Card)", callback_data="pay_PLN")],
        [InlineKeyboardButton(text="🇺🇦 UAH (Гривны ПУМБ)", callback_data="pay_UAH")],
        [InlineKeyboardButton(text="💎 Crypto (USDT / TON)", callback_data="pay_Crypto")],
        [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="pay_Stars")],
        [InlineKeyboardButton(text="💵 USD / 💶 EUR", callback_data="pay_USD_EUR")]
    ])
    text = f"💳 <b>Вы выбрали:</b> {item_name}\n\nВыберите удобную валюту для оплаты:"
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

# --- ВЫДАЧА РЕКВИЗИТОВ И ОЖИДАНИЕ ЧЕКА ---
@dp.callback_query(F.data.startswith("pay_"))
async def process_currency_choice(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.replace("pay_", "").replace("_", "/")
    await state.update_data(chosen_currency=currency)
    data = await state.get_data()
    item = data.get("chosen_item", "Товар")
    
    card_info = ""
    if "UAH" in currency:
        card_info = f"<code>{CARD_PUMB}</code>\n\n💬 Bank: <b>ПУМБ (Украина)</b>"
    elif "PLN" in currency:
        card_info = f"<code>{CARD_PLN}</code>\n\n💬 Card / Blik (Польша)"
    else:
        card_info = f"Для получения реквизитов напишите оператору: {SUPPORT_USERNAME}"
        
    text = (
        f"<b>Заказ:</b> {item}\n\n"
        f"<b>Реквизиты для оплаты:</b>\n{card_info}\n\n"
        f"💬 <i>Не проходит оплата? Выберите другой банк или пишите в поддержку!</i>\n\n"
        f"🏦 <b>После оплаты отправьте сюда в чат скриншот оплаты или PDF-чек 👇</b>"
    )
    
    await state.set_state(OrderState.waiting_for_payment_proof)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# --- ПОЛУЧЕНИЕ ЧЕКА ---
@dp.message(OrderState.waiting_for_payment_proof, F.photo | F.document)
async def receive_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item = data.get("chosen_item", "Товар")
    currency = data.get("chosen_currency", "Валюта")
    user = message.from_user
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять (Начислить)", callback_data=f"adm_accept_{user.id}_{item}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject_{user.id}")
        ]
    ])
    
    admin_caption = (
        f"📥 <b>Новая оплата на модерацию!</b>\n\n"
        f"👤 Пользователь: @{user.username} (ID: <code>{user.id}</code>)\n"
        f"📦 Товар: <b>{item}</b>\n"
        f"💳 Валюта: <b>{currency}</b>"
    )
    
    if message.photo:
        await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
    elif message.document:
        await bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
        
    await message.answer("✅ <b>Чек отправлен на модерацию!</b>\nОжидайте подтверждения администратора.", parse_mode="HTML")
    await state.clear()

# --- ДЕЙСТВИЯ АДМИНА ПО ЧЕКУ ---
@dp.callback_query(F.data.startswith("adm_accept_") | F.data.startswith("adm_reject_"))
async def admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    parts = callback.data.split("_")
    action = parts[1]
    target_user_id = int(parts[2])
    
    u = get_user(target_user_id)
    
    if action == "accept":
        item_purchased = "_".join(parts[3:]) if len(parts) > 3 else ""
        
        # Начисление на баланс пользователя при подтверждении оплаты
        if "Stars" in item_purchased:
            try:
                amt = int(item_purchased.split()[0])
                u["balance_stars"] += amt
            except Exception:
                pass
        elif "Gold" in item_purchased:
            try:
                amt = int(item_purchased.split()[0])
                u["balance_gold"] += amt
            except Exception:
                pass
        elif "грн" in item_purchased or "NFT" in item_purchased:
            u["nft_inventory"].append(item_purchased)
            
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ <b>Оплата одобрена! Средства/NFT зачислены на баланс.</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, "🎉 Ваша оплата подтверждена! Товар зачислен в ваш профиль.")
    else:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ <b>Оплата отклонена.</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, f"❌ Оплата отклонена. Свяжитесь с поддержкой: {SUPPORT_USERNAME}")
        
    await callback.answer()

# --- ВЫВОД ИЗ ПРОФИЛЯ С ПРОВЕРКОЙ БАЛАНСА ---
@dp.callback_query(F.data == "menu_withdraw")
async def menu_withdraw_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="wd_type_Stars")],
        [InlineKeyboardButton(text="🥇 Gold (Standoff 2)", callback_data="wd_type_Gold")],
        [InlineKeyboardButton(text="🖼 NFT из инвентаря", callback_data="wd_type_NFT")]
    ])
    await callback.message.edit_text("📤 <b>Что именно вы хотите вывести из баланса?</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("wd_type_"))
async def withdraw_type_chosen(callback: types.CallbackQuery, state: FSMContext):
    wd_type = callback.data.replace("wd_type_", "")
    user_id = callback.from_user.id
    u = get_user(user_id)
    
    if wd_type == "NFT":
        if not u["nft_inventory"]:
            await callback.answer("❌ Вы не приобрели этот NFT!", show_alert=True)
            return
        buttons = [[InlineKeyboardButton(text=f"🖼 {nft}", callback_data=f"wd_nft_{idx}")] for idx, nft in enumerate(u["nft_inventory"])]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text("🖼 Выберите NFT для вывода:", reply_markup=kb, parse_mode="HTML")
    else:
        # Проверка баланса перед вводом суммы
        if wd_type == "Stars" and u["balance_stars"] < 50:
            await callback.answer("❌ Недостаточно звезд на балансе! Минимальный вывод: 50 ⭐", show_alert=True)
            return
        elif wd_type == "Gold" and u["balance_gold"] <= 0:
            await callback.answer("❌ Недостаточно Gold на балансе!", show_alert=True)
            return
            
        await state.update_data(withdraw_type=wd_type)
        await state.set_state(OrderState.waiting_for_withdraw_amount)
        min_text = " (минимум 50)" if wd_type == "Stars" else ""
        await callback.message.edit_text(f"🔢 Введите количество {wd_type} для вывода{min_text}:", parse_mode="HTML")
        
    await callback.answer()

@dp.message(OrderState.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    wd_type = data.get("withdraw_type", "Stars")
    amount_text = message.text.strip()
    user_id = message.from_user.id
    u = get_user(user_id)
    
    if not amount_text.isdigit():
        await message.answer("❌ Введите корректное число!")
        return
        
    amount = int(amount_text)
    
    # Проверки по суммам и балансу
    if wd_type == "Stars":
        if amount < 50:
            await message.answer("❌ Минимальная сумма вывода — 50 Stars!")
            return
        if u["balance_stars"] < amount:
            await message.answer("❌ Недостаточно звезд на балансе!")
            return
            
    elif wd_type == "Gold":
        if u["balance_gold"] < amount:
            await message.answer("❌ Недостаточно gold на балансе!")
            return
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выведено", callback_data=f"wd_done_{user_id}_{wd_type}_{amount}"),
            InlineKeyboardButton(text="❌ Отклонено", callback_data=f"wd_rej_{user_id}")
        ]
    ])
    
    admin_text = (
        f"📤 <b>Заявка на вывод средств!</b>\n\n"
        f"👤 Пользователь: @{message.from_user.username} (ID: <code>{user_id}</code>)\n"
        f"📦 Выводит: <b>{amount} {wd_type}</b>"
    )
    
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=kb, parse_mode="HTML")
    await message.answer("⏳ <b>Заявка принята! Вывод длится от 15 минут до 2 часов.</b>", parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("wd_nft_"))
async def process_withdraw_nft(callback: types.CallbackQuery):
    nft_idx = int(callback.data.replace("wd_nft_", ""))
    user_id = callback.from_user.id
    u = get_user(user_id)
    
    if nft_idx >= len(u["nft_inventory"]):
        await callback.answer("❌ Вы не приобрели этот NFT!", show_alert=True)
        return
        
    nft_item = u["nft_inventory"][nft_idx]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выведено", callback_data=f"wd_done_{user_id}_NFT_{nft_idx}"),
            InlineKeyboardButton(text="❌ Отклонено", callback_data=f"wd_rej_{user_id}")
        ]
    ])
    
    admin_text = (
        f"📤 <b>Заявка на вывод NFT!</b>\n\n"
        f"👤 Пользователь: @{callback.from_user.username} (ID: <code>{user_id}</code>)\n"
        f"🖼 NFT: <b>{nft_item}</b>"
    )
    
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=kb, parse_mode="HTML")
    await callback.message.edit_text("⏳ <b>Заявка принята! Вывод длится от 15 минут до 2 часов.</b>", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("wd_done_") | F.data.startswith("wd_rej_"))
async def admin_withdraw_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    parts = callback.data.split("_")
    action = parts[1]
    target_user_id = int(parts[2])
    u = get_user(target_user_id)
    
    if action == "done":
        item_type = parts[3]
        
        # Списание средств/NFT с баланса после одобрения вывода
        if item_type == "Stars":
            amt = int(parts[4])
            u["balance_stars"] = max(0, u["balance_stars"] - amt)
        elif item_type == "Gold":
            amt = int(parts[4])
            u["balance_gold"] = max(0, u["balance_gold"] - amt)
        elif item_type == "NFT":
            nft_idx = int(parts[4])
            if nft_idx < len(u["nft_inventory"]):
                u["nft_inventory"].pop(nft_idx)
                
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Выведено! Средства списаны с профиля.</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, "🎉 Ваш вывод успешно выполнен!")
    else:
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Отклонено.</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, f"❌ Заявка на вывод отклонена. Поддержка: {SUPPORT_USERNAME}")
        
    await callback.answer()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("MONOLIT Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
