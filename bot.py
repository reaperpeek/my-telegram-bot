import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardMarkup
)

BOT_TOKEN = "8684030373:AAH3SBGRKk41DSydEJG1H8t05SX-N_uPrmw"

CHANNELS = [
    {"name": "Основной канал", "url": "https://t.me/monolit_main", "chat_id": "@monolit_main"},
    {"name": "Отзывы", "url": "https://t.me/monolit_reviews", "chat_id": "@monolit_reviews"},
    {"name": "Инфо", "url": "https://t.me/monolit_inf", "chat_id": "@monolit_inf"}
]

SUPPORT_USERNAME = "@monolit_hq"

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
        "btn_other": "🎮 Другие игры",
        "other_msg": f"🎮 По всем вопросам и заказу для других игр обращайтесь в ЛС: {SUPPORT_USERNAME}",
        "ref_msg": f"🎁 <b>Реферальная программа MONOLIT</b>\n\nПригласи 10 друзей и получи подарок <b>«Мишка» (15⭐)</b>!\n\nДля подтверждения инвайтов и получения подарка пишите в поддержку: {SUPPORT_USERNAME}",
        "select_item_stars": "🌟 <b>Выберите количество Telegram Stars:</b>",
        "select_item_gold": "🥇 <b>Выберите количество Gold (Standoff 2):</b>",
        "select_item_nft": "🖼 <b>Выберите категорию NFT:</b>",
        "select_currency": "💳 <b>Вы выбрали:</b> {item}\n\nТеперь выберите удобную валюту для оплаты:",
        "pay_final": "✅ <b>Заявка оформлена!</b>\n\n<b>Товар:</b> {item}\n<b>Валюта:</b> {currency}\n\nДля завершения оплаты и получения товара нажмите кнопку ниже:",
        "btn_pay_manager": "👨‍💻 Оплатить через менеджер",
        "btn_back": "⬅️ Назад"
    },
    "ua": {
        "sub_title": "<b>MONOLIT</b>\n\nДля доступу до сервісу, будь ласка, підпишіться на наші канали:",
        "btn_check": "Я підписався ✅",
        "sub_not_ok": "❌ Ви підписалися не на всі канали. Перевірте підписку та натисніть кнопку знову!",
        "menu_welcome": "⚡️ <b>Ласкаво просимо до MONOLIT!</b>\nОберіть потрібний розділ у меню нижче:",
        "btn_stars": "🌟 Купити Stars",
        "btn_gold": "🥇 Купити Gold (Standoff 2)",
        "btn_nft": "🖼 Купити NFT",
        "btn_ref": "🎁 Рефералка",
        "btn_other": "🎮 Інші ігри",
        "other_msg": f"🎮 З усіх питань та щодо замовлень для інших ігор звертайтесь у ЛС: {SUPPORT_USERNAME}",
        "ref_msg": f"🎁 <b>Реферальна програма MONOLIT</b>\n\nЗапроси 10 друзів та отримай подарунок <b>«Ведмедик» (15⭐)</b>!\n\nДля підтвердження інвайтів та отримання подарунка пишіть у підтримку: {SUPPORT_USERNAME}",
        "select_item_stars": "🌟 <b>Оберіть кількість Telegram Stars:</b>",
        "select_item_gold": "🥇 <b>Оберіть кількість Gold (Standoff 2):</b>",
        "select_item_nft": "🖼 <b>Оберіть категорію NFT:</b>",
        "select_currency": "💳 <b>Ви обрали:</b> {item}\n\nТепер оберіть зручну валюту для оплати:",
        "pay_final": "✅ <b>Заявку сформовано!</b>\n\n<b>Товар:</b> {item}\n<b>Валюта:</b> {currency}\n\nДля завершення оплати та отримання товару натисніть кнопку нижче:",
        "btn_pay_manager": "👨‍💻 Оплатити через менеджера",
        "btn_back": "⬅️ Назад"
    },
    "en": {
        "sub_title": "<b>MONOLIT</b>\n\nTo access the service, please subscribe to our channels:",
        "btn_check": "I subscribed ✅",
        "sub_not_ok": "❌ You are not subscribed to all channels. Please check and try again!",
        "menu_welcome": "⚡️ <b>Welcome to MONOLIT!</b>\nSelect a section from the menu below:",
        "btn_stars": "🌟 Buy Stars",
        "btn_gold": "🥇 Buy Gold (Standoff 2)",
        "btn_nft": "🖼 Buy NFT",
        "btn_ref": "🎁 Referral",
        "btn_other": "🎮 Other Games",
        "other_msg": f"🎮 For any questions regarding other games, contact support: {SUPPORT_USERNAME}",
        "ref_msg": f"🎁 <b>MONOLIT Referral Program</b>\n\nInvite 10 friends and receive a <b>«Mishka» gift (15⭐)</b>!\n\nTo claim your gift, contact support: {SUPPORT_USERNAME}",
        "select_item_stars": "🌟 <b>Select Telegram Stars package:</b>",
        "select_item_gold": "🥇 <b>Select Gold amount (Standoff 2):</b>",
        "select_item_nft": "🖼 <b>Select NFT category:</b>",
        "select_currency": "💳 <b>You selected:</b> {item}\n\nNow select your payment currency:",
        "pay_final": "✅ <b>Order Created!</b>\n\n<b>Item:</b> {item}\n<b>Currency:</b> {currency}\n\nTo complete payment, click the button below:",
        "btn_pay_manager": "👨‍💻 Pay via Manager",
        "btn_back": "⬅️ Back"
    }
}

user_languages = {}
# Временное хранение выборов пользователей
user_orders = {}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- СТАРТ И ЯЗЫК ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
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
async def check_subscription(callback: types.CallbackQuery):
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
            [KeyboardButton(text=t["btn_nft"]), KeyboardButton(text=t["btn_ref"])],
            [KeyboardButton(text=t["btn_other"])]
        ],
        resize_keyboard=True
    )
    await bot.send_message(user_id, t["menu_welcome"], reply_markup=kb, parse_mode="HTML")

# --- ВЫБОР ТОВАРОВ ---
@dp.message()
async def handle_menu_click(message: types.Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, "ru")
    t = TEXTS.get(lang, TEXTS["ru"])
    text = message.text

    if text in [TEXTS["ru"]["btn_other"], TEXTS["ua"]["btn_other"], TEXTS["en"]["btn_other"]]:
        await message.answer(t["other_msg"])
        
    elif text in [TEXTS["ru"]["btn_ref"], TEXTS["ua"]["btn_ref"], TEXTS["en"]["btn_ref"]]:
        await message.answer(t["ref_msg"], parse_mode="HTML")

    # ВЫБОР STARS
    elif text in [TEXTS["ru"]["btn_stars"], TEXTS["ua"]["btn_stars"], TEXTS["en"]["btn_stars"]]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="50 ⭐", callback_data="buy_50_Stars"), InlineKeyboardButton(text="100 ⭐", callback_data="buy_100_Stars")],
            [InlineKeyboardButton(text="250 ⭐", callback_data="buy_250_Stars"), InlineKeyboardButton(text="500 ⭐", callback_data="buy_500_Stars")],
            [InlineKeyboardButton(text="1000 ⭐", callback_data="buy_1000_Stars")]
        ])
        await message.answer(t["select_item_stars"], reply_markup=kb, parse_mode="HTML")

    # ВЫБОР GOLD
    elif text in [TEXTS["ru"]["btn_gold"], TEXTS["ua"]["btn_gold"], TEXTS["en"]["btn_gold"]]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="100 🥇 Gold", callback_data="buy_100_Gold"), InlineKeyboardButton(text="500 🥇 Gold", callback_data="buy_500_Gold")],
            [InlineKeyboardButton(text="1000 🥇 Gold", callback_data="buy_1000_Gold"), InlineKeyboardButton(text="3000 🥇 Gold", callback_data="buy_3000_Gold")]
        ])
        await message.answer(t["select_item_gold"], reply_markup=kb, parse_mode="HTML")

    # ВЫБОР NFT
    elif text in [TEXTS["ru"]["btn_nft"], TEXTS["ua"]["btn_nft"], TEXTS["en"]["btn_nft"]]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖼 Telegram Usernames", callback_data="buy_NFT_Usernames")],
            [InlineKeyboardButton(text="🖼 Telegram Numbers (+888)", callback_data="buy_NFT_Numbers")],
            [InlineKeyboardButton(text="🖼 Gifts NFT", callback_data="buy_NFT_Gifts")]
        ])
        await message.answer(t["select_item_nft"], reply_markup=kb, parse_mode="HTML")

# --- ВЫБОР ВАЛЮТЫ ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_item_select(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ru")
    t = TEXTS.get(lang, TEXTS["ru"])
    
    item = callback.data.replace("buy_", "").replace("_", " ")
    user_orders[user_id] = {"item": item}
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇵🇱 PLN (Blik / Card)", callback_data="pay_PLN")],
        [InlineKeyboardButton(text="🇺🇦 UAH (Гривны)", callback_data="pay_UAH")],
        [InlineKeyboardButton(text="💎 Crypto (USDT / TON)", callback_data="pay_Crypto")],
        [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="pay_Stars")],
        [InlineKeyboardButton(text="💵 USD / 💶 EUR", callback_data="pay_USD_EUR")]
    ])
    
    await callback.message.edit_text(t["select_currency"].format(item=item), reply_markup=kb, parse_mode="HTML")

# --- ИТОГОВЫЙ ЭКРАН ОПЛАТЫ ---
@dp.callback_query(F.data.startswith("pay_"))
async def process_currency_select(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ru")
    t = TEXTS.get(lang, TEXTS["ru"])
    
    currency = callback.data.replace("pay_", "").replace("_", "/")
    order = user_orders.get(user_id, {"item": "Товар"})
    item = order["item"]
    
    manager_url = f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}?text=Привет!_Хочу_купить_{item}_за_{currency}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_pay_manager"], url=manager_url)]
    ])
    
    await callback.message.edit_text(
        t["pay_final"].format(item=item, currency=currency),
        reply_markup=kb,
        parse_mode="HTML"
    )

async def main():
    logging.basicConfig(level=logging.INFO)
    print("MONOLIT Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
