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
ADMIN_ID = 7706483533  # Твой Telegram ID для получения чеков и заявок на вывод

CHANNELS = [
    {"name": "Основной канал", "url": "https://t.me/monolit_main", "chat_id": "@monolit_main"},
    {"name": "Отзывы", "url": "https://t.me/monolit_reviews", "chat_id": "@monolit_reviews"},
    {"name": "Инфо", "url": "https://t.me/monolit_inf", "chat_id": "@monolit_inf"}
]

SUPPORT_USERNAME = "@monolit_hq"

# База данных в памяти (для примера; в будущем можно подключить SQLite/Postgres)
# user_db[user_id] = {"balance_stars": 0, "balance_gold": 0, "nft_inventory": [], "refs": 0}
user_db = {}
user_languages = {}

# Состояния FSM
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
            "nft_inventory": ["Telegram Username @monolit_Vip", "Gift NFT #777"], # Пример инвентаря
            "refs": 0
        }
    return user_db[user_id]

# Тексты локализаций
TEXTS = {
    "ru": {
        "sub_title": "<b>MONOLIT</b>\n\nДля доступа к сервису, пожалуйста, подпишитесь на наши каналы:",
        "btn_check": "Я подписался ✅",
        "sub_not_ok": "❌ Вы подписались не на все каналы. Проверьте подписку и нажмите кнопку снова!",
        "menu_welcome": "⚡️ <b>Добро пожаловать в MONOLIT!</b>\nВыберите интересующий вас раздел в меню ниже:",
        "btn_stars": "🌟 Купить Stars",
        "btn_gold": "🥇 Купить Gold (Standoff 2)",
        "btn_nft": "🖼 Купить NFT",
        "btn_ref": "🎁 Рефералка",
        "btn_profile": "👤 Профиль",
        "btn_other": "🎮 Другие игры",
        "other_msg": f"🎮 По всем вопросам и заказу для других игр обращайтесь в ЛС: {SUPPORT_USERNAME}",
        "ref_msg": (
            "🎁 <b>Реферальная программа MONOLIT</b>\n\n"
            "1️⃣ Пригласи 10 активных друзей в бота.\n"
            "2️⃣ Напиши в чат канала @monolit_main сообщение вида:\n"
            "<code>пригласил @юз_кого_пригласил</code>\n"
            "3️⃣ За 7 приглашений получаешь подарок <b>«Мишка»</b>!\n\n"
            "⚠️ <i>Фейковые и неактивные аккаунты не учитываются!</i>\n"
            f"👥 Ваши приглашенные рефералы: <b>{{refs}}</b>"
        ),
        "profile_text": (
            "👤 <b>Ваш профиль MONOLIT</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "🌟 Баланс Stars: <b>{stars} ⭐</b>\n"
            "🥇 Баланс Gold: <b>{gold} 🥇</b>\n"
            "🖼 NFT в инвентаре: <b>{nft_count} шт.</b>\n"
            "🎁 Приглашено друзей: <b>{refs}</b>"
        ),
        "btn_withdraw": "📤 Вывести",
        "btn_top_up": "💳 Пополнить баланс",
        "select_custom": "⌨️ Введите нужное количество (числом) в ответном сообщении:",
        "ask_currency": "💳 <b>Вы выбрали:</b> {item}\n\nВыберите удобную валюту для оплаты:",
        "send_proof": (
            "📤 <b>Оплата заказа</b>\n\n"
            "Товар: <b>{item}</b>\n"
            "Валюта: <b>{currency}</b>\n\n"
            "Переведите средства и отправьте сюда <b>чек/квитанцию</b> (фото или PDF-файл).\n"
            "⏳ После отправки начнется модерация оплаты."
        ),
        "proof_sent": "✅ <b>Чек отправлен на модерацию!</b>\nАдминистратор скоро проверит платеж, и средства/товар поступят на ваш баланс.",
        "withdraw_menu": "📤 <b>Что именно вы хотите вывести из баланса?</b>",
        "withdraw_prompt_amount": "🔢 Введите количество для вывода ({item}):",
        "withdraw_select_nft": "🖼 Выберите NFT из вашего инвентаря для вывода:",
        "withdraw_success_sent": "⏳ <b>Заявка на вывод принята!</b>\nВывод обычно занимает от 15 минут до 2 часов.",
    }
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
async def process_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang
    await callback.message.delete()
    await send_subscription_check(callback.from_user.id, lang)

async def send_subscription_check(user_id: int, lang: str):
    t = TEXTS.get(lang, TEXTS["ru"])
    buttons = []
    for ch in CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["url"])])
    buttons.append([InlineKeyboardButton(text=t["btn_check"], callback_data="check_sub")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(user_id, t["sub_title"], reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ru")
    t = TEXTS.get(lang, TEXTS["ru"])
    
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
        await send_main_menu(user_id, lang)
    else:
        await callback.answer(t["sub_not_ok"], show_alert=True)

# --- ГЛАВНОЕ МЕНЮ ---
async def send_main_menu(user_id: int, lang: str):
    t = TEXTS.get(lang, TEXTS["ru"])
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_stars"]), KeyboardButton(text=t["btn_gold"])],
            [KeyboardButton(text=t["btn_nft"]), KeyboardButton(text=t["btn_profile"])],
            [KeyboardButton(text=t["btn_ref"]), KeyboardButton(text=t["btn_other"])]
        ],
        resize_keyboard=True
    )
    await bot.send_message(user_id, t["menu_welcome"], reply_markup=kb, parse_mode="HTML")

# --- КНОПКИ ГЛАВНОГО МЕНЮ ---
@dp.message(F.text.in_(["👤 Профиль", "👤 Профіль", "👤 Profile"]))
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    u = get_user(user_id)
    t = TEXTS["ru"]
    
    text = t["profile_text"].format(
        user_id=user_id,
        stars=u["balance_stars"],
        gold=u["balance_gold"],
        nft_count=len(u["nft_inventory"]),
        refs=u["refs"]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Вывести", callback_data="menu_withdraw")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.text.in_(["🎁 Рефералка", "🎁 Реферальна програма", "🎁 Referral"]))
async def show_ref(message: types.Message):
    user_id = message.from_user.id
    u = get_user(user_id)
    t = TEXTS["ru"]
    await message.answer(t["ref_msg"].format(refs=u["refs"]), parse_mode="HTML")

@dp.message(F.text.in_(["🎮 Другие игры", "🎮 Інші ігри", "🎮 Other Games"]))
async def show_other(message: types.Message):
    await message.answer(TEXTS["ru"]["other_msg"])

# --- ПОКУПКА (ВЫБОР ТОВАРА И КАСТОМНОЕ КОЛИЧЕСТВО) ---
@dp.message(F.text.in_(["🌟 Купить Stars", "🌟 Купити Stars", "🌟 Buy Stars"]))
async def buy_stars(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 ⭐", callback_data="item_Stars_50"), InlineKeyboardButton(text="100 ⭐", callback_data="item_Stars_100")],
        [InlineKeyboardButton(text="250 ⭐", callback_data="item_Stars_250"), InlineKeyboardButton(text="500 ⭐", callback_data="item_Stars_500")],
        [InlineKeyboardButton(text="✏️ Свое количество", callback_data="item_Stars_custom")]
    ])
    await message.answer("🌟 <b>Выберите пакет Telegram Stars или укажите свое количество:</b>", reply_markup=kb, parse_mode="HTML")

@dp.message(F.text.in_(["🥇 Купить Gold (Standoff 2)", "🥇 Купити Gold (Standoff 2)", "🥇 Buy Gold (Standoff 2)"]))
async def buy_gold(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="100 🥇", callback_data="item_Gold_100"), InlineKeyboardButton(text="500 🥇", callback_data="item_Gold_500")],
        [InlineKeyboardButton(text="1000 🥇", callback_data="item_Gold_1000"), InlineKeyboardButton(text="3000 🥇", callback_data="item_Gold_3000")],
        [InlineKeyboardButton(text="✏️ Свое количество", callback_data="item_Gold_custom")]
    ])
    await message.answer("🥇 <b>Выберите количество Gold или укажите свое:</b>", reply_markup=kb, parse_mode="HTML")

@dp.message(F.text.in_(["🖼 Купить NFT", "🖼 Купити NFT", "🖼 Buy NFT"]))
async def buy_nft(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Telegram Usernames", callback_data="item_NFT_Usernames")],
        [InlineKeyboardButton(text="🖼 Telegram Numbers (+888)", callback_data="item_NFT_Numbers")],
        [InlineKeyboardButton(text="🎁 Telegram Gifts", callback_data="item_NFT_Gifts")]
    ])
    await message.answer("🖼 <b>Выберите категорию NFT для покупки:</b>", reply_markup=kb, parse_mode="HTML")

# --- ОБРАБОТКА ВЫБОРА ТОВАРА ИЛИ КАСТОМА ---
@dp.callback_query(F.data.startswith("item_"))
async def process_item_choice(callback: types.CallbackQuery, state: FSMContext):
    data_parts = callback.data.split("_")
    item_type = data_parts[1] # Stars, Gold, NFT
    value = data_parts[2] # число или custom / Usernames и т.д.
    
    if value == "custom":
        await state.update_data(item_type=item_type)
        await state.set_state(OrderState.waiting_for_custom_amount)
        await callback.message.answer(TEXTS["ru"]["select_custom"])
        await callback.answer()
        return
        
    item_name = f"{value} {item_type}"
    await state.update_data(chosen_item=item_name)
    await show_currency_selection(callback.message, item_name, edit=True)
    await callback.answer()

@dp.message(OrderState.waiting_for_custom_amount)
async def process_custom_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item_type = data.get("item_type", "Item")
    amount = message.text.strip()
    item_name = f"{amount} {item_type}"
    
    await state.update_data(chosen_item=item_name)
    await show_currency_selection(message, item_name, edit=False)
    await state.set_state(None)

async def show_currency_selection(message: types.Message, item_name: str, edit: bool = False):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇵🇱 PLN (Blik / Card)", callback_data="pay_PLN")],
        [InlineKeyboardButton(text="🇺🇦 UAH (Гривны)", callback_data="pay_UAH")],
        [InlineKeyboardButton(text="💎 Crypto (USDT / TON)", callback_data="pay_Crypto")],
        [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="pay_Stars")],
        [InlineKeyboardButton(text="💵 USD / 💶 EUR", callback_data="pay_USD_EUR")]
    ])
    text = TEXTS["ru"]["ask_currency"].format(item=item_name)
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

# --- ВЫБОР ВАЛЮТЫ И ЗАПРОС ЧЕКА ---
@dp.callback_query(F.data.startswith("pay_"))
async def process_currency_choice(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.replace("pay_", "").replace("_", "/")
    await state.update_data(chosen_currency=currency)
    
    data = await state.get_data()
    item = data.get("chosen_item", "Товар")
    
    await state.set_state(OrderState.waiting_for_payment_proof)
    text = TEXTS["ru"]["send_proof"].format(item=item, currency=currency)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# --- ПОЛУЧЕНИЕ ЧЕКА ОТ ПОЛЬЗОВАТЕЛЯ И ПЕРЕСЫЛКА АДМИНУ ---
@dp.message(OrderState.waiting_for_payment_proof, F.photo | F.document)
async def receive_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item = data.get("chosen_item", "Товар")
    currency = data.get("chosen_currency", "Валюта")
    user = message.from_user
    
    # Кнопки для админа: принять / отклонить
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять (Начислить)", callback_data=f"adm_accept_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject_{user.id}")
        ]
    ])
    
    admin_caption = (
        f"📥 <b>Новая оплата на модерацию!</b>\n\n"
        f"👤 Пользователь: @{user.username} (ID: <code>{user.id}</code>)\n"
        f"📦 Товар: <b>{item}</b>\n"
        f"💳 Валюта: <b>{currency}</b>"
    )
    
    # Пересылаем чек админу
    if message.photo:
        await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
    elif message.document:
        await bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id, caption=admin_caption, reply_markup=kb, parse_mode="HTML")
        
    await message.answer(TEXTS["ru"]["proof_sent"], parse_mode="HTML")
    await state.clear()

# --- ДЕЙСТВИЯ АДМИНА ПО ОПЛАТЕ ---
@dp.callback_query(F.data.startswith("adm_accept_") | F.data.startswith("adm_reject_"))
async def admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    parts = callback.data.split("_")
    action = parts[1] # accept или reject
    target_user_id = int(parts[2])
    
    if action == "accept":
        # Начисляем на условный баланс (если это звезды или голда)
        u = get_user(target_user_id)
        u["balance_stars"] += 100 # Пример начисления (можно настроить автоматику по тексту)
        
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ <b>Оплата одобрена и начислена!</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, "✅ Ваша оплата прошла модерацию! Товар/средства зачислены на ваш баланс в профиле.")
    else:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ <b>Оплата отклонена.</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, "❌ К сожалению, ваша оплата была отклонена администратором. Обратитесь в поддержку: " + SUPPORT_USERNAME)
        
    await callback.answer()

# --- МЕНЮ ВЫВОДА ИЗ ПРОФИЛЯ ---
@dp.callback_query(F.data == "menu_withdraw")
async def menu_withdraw_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="wd_type_Stars")],
        [InlineKeyboardButton(text="🥇 Gold (Standoff 2)", callback_data="wd_type_Gold")],
        [InlineKeyboardButton(text="🖼 NFT из инвентаря", callback_data="wd_type_NFT")]
    ])
    await callback.message.edit_text(TEXTS["ru"]["withdraw_menu"], reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("wd_type_"))
async def withdraw_type_chosen(callback: types.CallbackQuery, state: FSMContext):
    wd_type = callback.data.replace("wd_type_", "")
    user_id = callback.from_user.id
    u = get_user(user_id)
    
    if wd_type == "NFT":
        if not u["nft_inventory"]:
            await callback.answer("У вас нет NFT в инвентаре!", show_alert=True)
            return
        # Показываем список инвентаря для вывода
        buttons = []
        for nft in u["nft_inventory"]:
            buttons.append([InlineKeyboardButton(text=f"🖼 {nft}", callback_data=f"wd_nft_{nft}")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(TEXTS["ru"]["withdraw_select_nft"], reply_markup=kb, parse_mode="HTML")
    else:
        await state.update_data(withdraw_type=wd_type)
        await state.set_state(OrderState.waiting_for_withdraw_amount)
        await callback.message.edit_text(TEXTS["ru"]["withdraw_prompt_amount"].format(item=wd_type), parse_mode="HTML")
        
    await callback.answer()

@dp.message(OrderState.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    wd_type = data.get("withdraw_type", "Stars")
    amount = message.text.strip()
    user = message.from_user
    
    # Отправляем заявку админу
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выведено", callback_data=f"wd_done_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонено", callback_data=f"wd_rej_{user.id}")
        ]
    ])
    
    admin_text = (
        f"📤 <b>Заявка на вывод средств!</b>\n\n"
        f"👤 Пользователь: @{user.username} (ID: <code>{user.id}</code>)\n"
        f"📦 Что выводит: <b>{amount} {wd_type}</b>"
    )
    
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=kb, parse_mode="HTML")
    await message.answer(TEXTS["ru"]["withdraw_success_sent"], parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("wd_nft_"))
async def process_withdraw_nft(callback: types.CallbackQuery):
    nft_name = callback.data.replace("wd_nft_", "")
    user = callback.from_user
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выведено", callback_data=f"wd_done_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонено", callback_data=f"wd_rej_{user.id}")
        ]
    ])
    
    admin_text = (
        f"📤 <b>Заявка на вывод NFT!</b>\n\n"
        f"👤 Пользователь: @{user.username} (ID: <code>{user.id}</code>)\n"
        f"🖼 NFT: <b>{nft_name}</b>"
    )
    
    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=kb, parse_mode="HTML")
    await callback.message.edit_text(TEXTS["ru"]["withdraw_success_sent"], parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("wd_done_") | F.data.startswith("wd_rej_"))
async def admin_withdraw_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    parts = callback.data.split("_")
    action = parts[1] # done или rej
    target_user_id = int(parts[2])
    
    if action == "done":
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Вывод успешно выполнен!</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, "🎉 Ваш заказ/вывод успешно выполнен администратором!")
    else:
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Вывод отклонен.</b>", parse_mode="HTML")
        await bot.send_message(target_user_id, "❌ Заявка на вывод была отклонена. Обратитесь в поддержку: " + SUPPORT_USERNAME)
        
    await callback.answer()

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("MONOLIT Bot (Advanced) is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
