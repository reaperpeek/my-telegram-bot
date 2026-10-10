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

# --- РЕКВІЗИТИ ТА КУРСИ ---
CARD_PUMB = "4314140214993815"       # UAH (Гривні)
CARD_PLN = "4213523416991947"        # PLN (Злоті)

PRICE_PER_GOLD_UAH = 0.42  # 1 Gold = 0.42 грн
PRICE_PER_GOLD_PLN = 0.045 # 1 Gold = 0.045 PLN

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

# Расчет цены Stars (базовый курс + 20 грн наценка)
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
        return f"{round(total_uah / 10.0, 2)} PLN"
    elif "Crypto" in currency:
        return f"{round(total_uah / 41.0, 2)} USDT"
    else:
        return f"{total_uah} UAH (эквивалент)"

# Расчет цены Gold (0.42 UAH)
def calculate_gold_price(amount: int, currency: str) -> str:
    total_uah = round(amount * PRICE_PER_GOLD_UAH, 2)
    if "UAH" in currency:
        return f"{total_uah} UAH"
    elif "PLN" in currency:
        return f"{round(amount * PRICE_PER_GOLD_PLN, 2)} PLN"
    elif "Crypto" in currency:
        return f"{round(total_uah / 41.0, 2)} USDT"
    else:
        return f"{total_uah} UAH"

# NFT Подарки (5 страниц)
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

# --- СТАРТ И ПОДПИСКА ---
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

# --- ВЫБОР NFT ---
@dp.callback_query(F.data.startswith("nftitem_"))
async def process_
