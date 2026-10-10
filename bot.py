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

# Токен бота
BOT_TOKEN = "8684030373:AAH3SBGRKk41DSydEJG1H8t05SX-N_uPrmw"

# Список каналов для проверки (ID или юзернеймы с @)
CHANNELS = [
    {"name": "Основной канал", "url": "https://t.me/monolit_main", "chat_id": "@monolit_main"},
    {"name": "Отзывы", "url": "https://t.me/monolit_reviews", "chat_id": "@monolit_reviews"},
    {"name": "Инфо", "url": "https://t.me/monolit_inf", "chat_id": "@monolit_inf"}
]

SUPPORT_USERNAME = "@monolit_hq"

# Текстовые локализации
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
        "currency_select": "<b>Выберите валюту для оплаты:</b>\n\nПринимаем: UAH, PLN, Crypto (USDT/TON), Telegram Stars, USD, EUR.",
        "buy_stars_title": "🌟 <b>Покупка Telegram Stars</b>\n\nВыберите нужный пакет или обратитесь в саппорт:",
        "buy_gold_title": "🥇 <b>Покупка Gold (Standoff 2)</b>\n\nВыбор объема и оплата через оператора:",
        "buy_nft_title": "🖼 <b>Покупка NFT</b>\n\nКаталог и оформление сделок через саппорт:",
        "pay_currencies": "💳 Доступные варианты оплаты:\n• 🇵🇱 PLN (Злотые / Blik / Card)\n• 🇺🇦 UAH (Гривны)\n• 💎 Crypto (USDT / TON)\n• 🌟 Telegram Stars\n• 💵 USD ($) / 💶 EUR (€)\n\nДля быстрого оформления сделки пишите: " + SUPPORT_USERNAME
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
        "currency_select": "<b>Оберіть валюту для оплати:</b>\n\nПриймаємо: UAH, PLN, Crypto (USDT/TON), Telegram Stars, USD, EUR.",
        "buy_stars_title": "🌟 <b>Купівля Telegram Stars</b>\n\nОберіть потрібний пакет або зверніться до сапорту:",
        "buy_gold_title": "🥇 <b>Купівля Gold (Standoff 2)</b>\n\nВибір об'єму та оплата через оператора:",
        "buy_nft_title": "🖼 <b>Купівля NFT</b>\n\nКаталог та оформлення угод через сапорт:",
        "pay_currencies": "💳 Доступні варіанти оплати:\n• 🇵🇱 PLN (Злоті / Blik / Card)\n• 🇺🇦 UAH (Гривні)\n• 💎 Crypto (USDT / TON)\n• 🌟 Telegram Stars\n• 💵 USD ($) / 💶 EUR (€)\n\nДля швидкого оформления звертайтесь: " + SUPPORT_USERNAME
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
        "currency_select": "<b>Select payment currency:</b>\n\nWe accept: UAH, PLN, Crypto (USDT/TON), Telegram Stars, USD, EUR.",
        "buy_stars_title": "🌟 <b>Buy Telegram Stars</b>\n\nChoose a package or contact support:",
        "buy_gold_title": "🥇 <b>Buy Gold (Standoff 2)</b>\n\nSelect amount and process via operator:",
        "buy_nft_title": "🖼 <b>Buy NFT</b>\n\nCatalog and deals via support:",
        "pay_currencies": "💳 Payment options available:\n• 🇵🇱 PLN (Zloty / Blik / Card)\n• 🇺🇦 UAH (Hryvnia)\n• 💎 Crypto (USDT / TON)\n• 🌟 Telegram Stars\n• 💵 USD ($) / 💶 EUR (€)\n\nTo place an order, contact: " + SUPPORT_USERNAME
    }
}

# Хранилище языка пользователей (в оперативной памяти)
user_languages = {}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ВЫБОР ЯЗЫКА ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])
    await message.answer("<b>Выберите язык / Оберіть мову / Choose language:</b>", reply_markup=kb, parse_mode="HTML")

# --- ПОСЛЕ ВЫБОРА ЯЗЫКА (УДАЛЕНИЕ СООБЩЕНИЯ И ПОДПИСКА) ---
@dp.callback_query(F.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang
    
    # Удаляем сообщение с выбором языка
    await callback.message.delete()
    
    # Отправляем проверку подписки
    await send_subscription_check(callback.from_user.id, lang)

async def send_subscription_check(user_id: int, lang: str):
    t = TEXTS.get(lang, TEXTS["ru"])
    buttons = []
    
    for ch in CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["url"])])
    
    buttons.append([InlineKeyboardButton(text=t["btn_check"], callback_data="check_sub")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await bot.send_message(user_id, t["sub_title"], reply_markup=kb, parse_mode="HTML")

# --- ПРОВЕРКА ПОДПИСКИ ---
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
            # Если бот ещё не админ в канале, пропускаем проверку для тестов
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

# --- ОБРАБОТКА НАЖАТИЙ КНОПОК МЕНЮ ---
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
        
    elif text in [TEXTS["ru"]["btn_stars"], TEXTS["ua"]["btn_stars"], TEXTS["en"]["btn_stars"]]:
        msg = f"{t['buy_stars_title']}\n\n{t['pay_currencies']}"
        await message.answer(msg, parse_mode="HTML")
        
    elif text in [TEXTS["ru"]["btn_gold"], TEXTS["ua"]["btn_gold"], TEXTS["en"]["btn_gold"]]:
        msg = f"{t['buy_gold_title']}\n\n{t['pay_currencies']}"
        await message.answer(msg, parse_mode="HTML")
        
    elif text in [TEXTS["ru"]["btn_nft"], TEXTS["ua"]["btn_nft"], TEXTS["en"]["btn_nft"]]:
        msg = f"{t['buy_nft_title']}\n\n{t['pay_currencies']}"
        await message.answer(msg, parse_mode="HTML")

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("MONOLIT Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
