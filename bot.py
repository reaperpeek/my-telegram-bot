import asyncio
import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Точные значения
BOT_TOKEN = "8408315552:AAGrpQIl2CFfX6TWzw8iRbILzR94feL8XXo"
ADMIN_ID = 7786483533

# Реквизиты
CARD_PUMB = "4314140214993815"
CARD_SANTANDER = "4213523416991947"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

users_db = {}

class OrderState(StatesGroup):
    waiting_for_receipt = State()
    waiting_for_sell_stars = State()
    calc_uah = State()

def get_lang(user_id):
    return users_db.get(user_id, {}).get('lang', 'ru')

def main_kb(lang):
    if lang == 'uk':
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🛍 Товари"), KeyboardButton(text="💰 Продати Stars")],
            [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="🧮 Порахувати")],
            [KeyboardButton(text="💬 Відгуки"), KeyboardButton(text="👨‍💻 Підтримка / FAQ")]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🛍 Товары"), KeyboardButton(text="💰 Продать Stars")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🧮 Посчитать")],
            [KeyboardButton(text="💬 Отзывы"), KeyboardButton(text="👨‍💻 Поддержка / FAQ")]
        ], resize_keyboard=True)

# Цены подняты, чтобы твоя прибыль была выше 30 грн с продажи
NFT_DATA = {
    1: [
        ("🍭 439 грн", "nft_lollipop_439"), ("🧦 469 грн", "nft_sock_469"), ("🍦 469 грн", "nft_icecream_469"),
        ("🍜 489 грн", "nft_noodle_489"), ("🦩 469 грн", "nft_flamingo_469"), ("🐕 539 грн", "nft_dog_539"),
        ("☃️ 389 грн", "nft_snowman_389"), ("🎁 469 грн", "nft_gift_469")
    ],
    2: [
        ("🗽 489 грн", "nft_statue_489"), ("🗑 489 грн", "nft_trash_489"), ("🐍 429 грн", "nft_snake_429"),
        ("🏺 539 грн", "nft_pot_539"), ("🧦 439 грн", "nft_socks_439"), ("🚀 489 грн", "nft_rocket_489"),
        ("🍪 429 грн", "nft_cookie_429"), ("📓 459 грн", "nft_book_459")
    ],
    3: [
        ("🎉 429 грн", "nft_party_429"), ("🎒 439 грн", "nft_bag_439"), ("💩 489 грн", "nft_poop_489"),
        ("🍭 429 грн", "nft_candy_429"), ("💍 539 грн", "nft_ring_539"), ("🍄 529 грн", "nft_shroom_529"),
        ("🍿 569 грн", "nft_popcorn_569"), ("🧙‍♀️ 839 грн", "nft_witch_839")
    ],
    4: [
        ("🎂 469 грн", "nft_cake_469"), ("🥇 489 грн", "nft_medal_489"), ("🌙 579 грн", "nft_moon_579"),
        ("🧺 519 грн", "nft_basket_519"), ("🍀 519 грн", "nft_clover_519"), ("👁 669 грн", "nft_eye_669"),
        ("🐒 679 грн", "nft_monkey_679"), ("🪄 639 грн", "nft_wand_639")
    ],
    5: [
        ("🚬 1249 грн", "nft_cigar_1249"), ("🍬 389 грн", "nft_cane_389"), ("💐 539 грн", "nft_flowers_539")
    ]
}

def get_nft_kb(page=1):
    buttons = []
    items = NFT_DATA.get(page, [])
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(text=items[i][0], callback_data=f"buy_{items[i][1]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(text=items[i+1][0], callback_data=f"buy_{items[i+1][1]}"))
        buttons.append(row)
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"nft_page_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/5", callback_data="noop"))
    if page < 5:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"nft_page_{page+1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="cat_goods")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if uid not in users_db:
        users_db[uid] = {'balance_uah': 0, 'balance_stars': 0, 'lang': 'ru'}
        uname = message.from_user.username or "без юзернейма"
        await bot.send_message(ADMIN_ID, f"👤 **Новый пользователь зашел:**\nЮзер: @{uname} (`{uid}`)", parse_mode="Markdown")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_uk")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
    ])
    await message.answer("Оберіть мову / Выберите язык:", reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    users_db[callback.from_user.id]['lang'] = lang
    txt = "Ласкаво просимо до Reaperpeek Shop!" if lang == 'uk' else "Добро пожаловать в Reaperpeek Shop!"
    await callback.message.delete()
    await callback.message.answer(txt, reply_markup=main_kb(lang))

@dp.message(F.text.in_(["🛍 Товари", "🛍 Товары"]))
async def goods(message: types.Message):
    lang = get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐸 NFT Подарки", callback_data="cat_nft")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="cat_stars"), InlineKeyboardButton(text="💎 TG Premium", callback_data="cat_prem")]
    ])
    txt = "Оберіть категорію:" if lang == 'uk' else "Выберите категорию:"
    await message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "cat_goods")
async def cat_goods_cb(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐸 NFT Подарки", callback_data="cat_nft")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="cat_stars"), InlineKeyboardButton(text="💎 TG Premium", callback_data="cat_prem")]
    ])
    await callback.message.edit_text("Выберите категорию:", reply_markup=kb)

@dp.callback_query(F.data == "cat_nft")
async def cat_nft_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🐸 **NFT Подарки**\n\nВыберите NFT:", parse_mode="Markdown", reply_markup=get_nft_kb(1))

@dp.callback_query(F.data.startswith("nft_page_"))
async def cat_nft_page(callback: types.CallbackQuery):
    p = int(callback.data.split("_")[2])
    await callback.message.edit_text("🐸 **NFT Подарки**\n\nВыберите NFT:", parse_mode="Markdown", reply_markup=get_nft_kb(p))

@dp.callback_query(F.data == "cat_prem")
async def cat_prem(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 3 месяца - 669 грн", callback_data="buy_prem_3m_669")],
        [InlineKeyboardButton(text="💎 6 месяцев - 999 грн", callback_data="buy_prem_6m_999")],
        [InlineKeyboardButton(text="💎 12 месяцев - 1699 грн", callback_data="buy_prem_12m_1699")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="cat_goods")]
    ])
    await callback.message.edit_text("💎 **TG Premium**\n\nВыберите нужный срок:", parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "cat_stars")
async def cat_stars(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 20 Stars - 21 грн", callback_data="buy_stars_20_21")],
        [InlineKeyboardButton(text="⭐ 50 Stars - 50 грн", callback_data="buy_stars_50_50")],
        [InlineKeyboardButton(text="⭐ 100 Stars - 88 грн", callback_data="buy_stars_100_88")],
        [InlineKeyboardButton(text="⭐ 200 Stars - 160 грн", callback_data="buy_stars_200_160")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="cat_goods")]
    ])
    await callback.message.edit_text("⭐ **Telegram Stars**\n\nВыберите количество:", parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def choose_bank(callback: types.CallbackQuery, state: FSMContext):
    raw_item = callback.data.replace("buy_", "")
    parts = raw_item.split("_")
    price = parts[-1]
    item_title = " ".join(parts[:-1]).upper()
    
    await state.update_data(item_name=item_title, price=price)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 Оплата на ПУМБ", callback_data="pay_pumb")],
        [InlineKeyboardButton(text="💳 Santander / Erste", callback_data="pay_santander")],
        [InlineKeyboardButton(text="↩️ Отмена", callback_data="cat_goods")]
    ])
    await callback.message.edit_text(f"🛒 **Заказ:** {item_title}\n💰 **Сумма:** {price}.00 UAH\n\nВыберите способ оплаты:", parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(F.data == "pay_pumb")
async def pay_pumb_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get('price', '0')
    
    text = (
        f"🏦 **Инструкция по оплате ПУМБ:**\n\n"
        f"1️⃣ Нажмите на номер карты ниже, чтобы скопировать:\n`{CARD_PUMB}`\n\n"
        f"2️⃣ Переведите ровно **{price}.00 UAH** в приложении вашего банка.\n"
        f"3️⃣ Обязательно сохраните скриншот чека/квитанции о переводе.\n\n"
        f"💬 **Не проходит оплата?** Выберите другой банк или напишите в поддержку!\n\n"
        f"📩 **После оплаты отправьте скриншот чека прямо в этот чат!**"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Как получить квитанцию?", callback_data="how_get_receipt")],
        [InlineKeyboardButton(text="Изменить способ оплаты", callback_data="cat_goods")]
    ])
    
    await callback.message.delete()
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await state.set_state(OrderState.waiting_for_receipt)

@dp.callback_query(F.data == "pay_santander")
async def pay_santander_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get('price', '0')
    
    text = (
        f"💳 **Инструкция по оплате Santander / Erste:**\n\n"
        f"1️⃣ Нажмите на номер карты ниже, чтобы скопировать:\n`{CARD_SANTANDER}`\n\n"
        f"2️⃣ Откройте приложение банка и переведите **{price}.00 UAH** (или эквивалент).\n"
        f"3️⃣ Обязательно сохраните чек / квитанцию об оплате.\n\n"
        f"📩 **После оплаты отправьте скриншот чека прямо в этот чат!**"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Как получить квитанцию?", callback_data="how_get_receipt")],
        [InlineKeyboardButton(text="Изменить способ оплаты", callback_data="cat_goods")]
    ])
    
    await callback.message.delete()
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await state.set_state(OrderState.waiting_for_receipt)

@dp.message(OrderState.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    uname = message.from_user.username or "без юзернейма"
    photo_id = message.photo[-1].file_id
    
    await bot.send_photo(
        ADMIN_ID, 
        photo_id, 
        caption=f"🧾 **НОВЫЙ ЧЕК ОБ ОПЛАТЕ!**\n\nПользователь: @{uname} (`{uid}`)\nТовар: {data.get('item_name')}\nСумма: {data.get('price')} UAH", 
        parse_mode="Markdown"
    )
    
    await message.answer("✅ **Чек получен и отправлен на проверку!**\nАдминистратор проверит платеж и выдаст заказ в ближайшее время.")
    await state.clear()

@dp.message(OrderState.waiting_for_receipt)
async def process_receipt_wrong(message: types.Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно **фотографию/скриншот** чека!")

@dp.message(F.text.in_(["💰 Продати Stars", "💰 Продать Stars"]))
async def sell_stars_msg(message: types.Message, state: FSMContext):
    await message.answer("💰 **Продажа Stars**\n\nМинимальное количество: **500 ⭐**\nКурс: **500 ⭐ = 360 UAH**\n\nВведите количество звезд, которое хотите продать:")
    await state.set_state(OrderState.waiting_for_sell_stars)

@dp.message(OrderState.waiting_for_sell_stars)
async def process_sell_stars(message: types.Message, state: FSMContext):
    try:
        val = int(message.text)
        if val < 500:
            await message.answer("❌ Минимальная сумма продажи — 500 ⭐. Введите еще раз:")
            return
        payout = int((val / 500) * 360)
        await state.update_data(item_name=f"Продажа {val} ⭐", price=payout)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить заявку", callback_data="confirm_sell")]
        ])
        await message.answer(f"За **{val} ⭐** вы получите **{payout} UAH**.\n\nНажмите кнопку ниже для связи с менеджером.", parse_mode="Markdown", reply_markup=kb)
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")

@dp.callback_query(F.data == "confirm_sell")
async def confirm_sell_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = callback.from_user.id
    uname = callback.from_user.username or "без юзернейма"
    await bot.send_message(ADMIN_ID, f"🔔 **НОВАЯ ЗАЯВКА НА ПРОДАЖУ STARS!**\n\nПользователь: @{uname} (`{uid}`)\nСделка: {data.get('item_name')}\nК выплате: {data.get('price')} UAH", parse_mode="Markdown")
    await callback.message.edit_text("✅ Заявка отправлена администратору! Скоро с вами свяжутся.")
    await state.clear()

@dp.message(F.text.in_(["👤 Профіль", "👤 Профиль"]))
async def profile(message: types.Message):
    uid = message.from_user.id
    u = users_db.get(uid, {'balance_uah': 0, 'balance_stars': 0})
    await message.answer(f"ℹ️ **Информация о вас:**\n\n🆔 ID: `{uid}`\n✨ Баланс: {u['balance_uah']} UAH ~ {u['balance_stars']} ⭐", parse_mode="Markdown")

@dp.message(F.text.in_(["🧮 Порахувати", "🧮 Посчитать"]))
async def calc_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Порахувати гривні в зірках", callback_data="calc_uah_to_stars")]
    ])
    await message.answer("Оберіть варіант нижче ⤵️", reply_markup=kb)

@dp.callback_query(F.data == "calc_uah_to_stars")
async def ask_uah(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть суму в UAH:")
    await state.set_state(OrderState.calc_uah)

@dp.message(OrderState.calc_uah)
async def res_uah(message: types.Message, state: FSMContext):
    try:
        val = float(message.text)
        stars = int(val * 1.25)
        await message.answer(f"За {val} UAH ви отримаєте ~{stars} ⭐")
    except ValueError:
        await message.answer("Будь ласка, введіть число.")
    await state.clear()

@dp.message(F.text.in_(["👨‍💻 Підтримка / FAQ", "👨‍💻 Поддержка / FAQ"]))
async def faq(message: types.Message):
    await message.answer("💬 **FAQ:**\n\nПо всем вопросам: @reaperpeek", parse_mode="Markdown")

@dp.message(F.text.in_(["💬 Відгуки", "💬 Отзывы"]))
async def reviews(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отзывы ➡️", url="https://t.me/telegram")]
    ])
    await message.answer("💬 **Отзывы покупателей:**", reply_markup=kb)

@dp.callback_query(F.data == "how_get_receipt")
async def how_get_receipt_cb(callback: types.CallbackQuery):
    await callback.answer(
        "Зайдите в банк ➔ Найдите перевод ➔ Нажмите 'Квитанция' или 'Скачать чек' и сделайте скриншот.", 
        show_alert=True
    )

@dp.callback_query(F.data == "noop")
async def noop_cb(callback: types.CallbackQuery):
    await callback.answer()

# Веб-сервер для Render
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Dummy HTTP server started on port {port}")

async def main():
    await start_web_server()
    await bot.delete_my_commands()
    await bot.set_my_commands([BotCommand(command="start", description="Запустить бота")])
    logging.info("Starting Telegram Bot Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
