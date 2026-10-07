import asyncio
import os
import logging
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

# Новый токен подставлен
BOT_TOKEN = os.getenv("BOT_TOKEN", "8408315552:AAGrpQIl2CFfX6TWzw8iRbILzR94feL8XXo")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7786483533"))

# Сюда вставишь file_id видео после того, как скинешь его боту
PUMB_VIDEO_FILE_ID = None 

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

NFT_DATA = {
    1: [
        ("🍭 399 грн", "nft_lollipop_399"), ("🧦 429 грн", "nft_sock_429"), ("🍦 429 грн", "nft_icecream_429"),
        ("🍜 449 грн", "nft_noodle_449"), ("🦩 429 грн", "nft_flamingo_429"), ("🐕 499 грн", "nft_dog_499"),
        ("☃️ 349 грн", "nft_snowman_349"), ("🎁 429 грн", "nft_gift_429")
    ],
    2: [
        ("🗽 449 грн", "nft_statue_449"), ("🗑 449 грн", "nft_trash_449"), ("🐍 389 грн", "nft_snake_389"),
        ("🏺 499 грн", "nft_pot_499"), ("🧦 399 грн", "nft_socks_399"), ("🚀 449 грн", "nft_rocket_449"),
        ("🍪 389 грн", "nft_cookie_389"), ("📓 419 грн", "nft_book_419")
    ],
    3: [
        ("🎉 389 грн", "nft_party_389"), ("🎒 399 грн", "nft_bag_399"), ("💩 449 грн", "nft_poop_449"),
        ("🍭 389 грн", "nft_candy_389"), ("💍 499 грн", "nft_ring_499"), ("🍄 489 грн", "nft_shroom_489"),
        ("🍿 529 грн", "nft_popcorn_529"), ("🧙‍♀️ 799 грн", "nft_witch_799")
    ],
    4: [
        ("🎂 429 грн", "nft_cake_429"), ("🥇 449 грн", "nft_medal_449"), ("🌙 539 грн", "nft_moon_539"),
        ("🧺 479 грн", "nft_basket_479"), ("🍀 479 грн", "nft_clover_479"), ("👁 629 грн", "nft_eye_629"),
        ("🐒 639 грн", "nft_monkey_639"), ("🪄 599 грн", "nft_wand_599")
    ],
    5: [
        ("🚬 1199 грн", "nft_cigar_1199"), ("🍬 349 грн", "nft_cane_349"), ("💐 499 грн", "nft_flowers_499")
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
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    if uid not in users_db:
        users_db[uid] = {'balance_uah': 0, 'balance_stars': 0, 'lang': 'ru'}
        uname = message.from_user.username or "без юзернейма"
        await bot.send_message(ADMIN_ID, f"👤 **Новый пользователь запустил бота!**\nЮзер: @{uname} (`{uid}`)", parse_mode="Markdown")

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

# Выбор банка при покупке
@dp.callback_query(F.data.startswith("buy_"))
async def choose_bank(callback: types.CallbackQuery, state: FSMContext):
    raw_item = callback.data.replace("buy_", "")
    parts = raw_item.split("_")
    price = parts[-1]
    item_title = " ".join(parts[:-1]).upper()
    
    await state.update_data(item_name=item_title, price=price)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 Оплата на ПУМБ (с видео)", callback_data="pay_pumb")],
        [InlineKeyboardButton(text="💳 Santander / Erste (Инструкция)", callback_data="pay_santander")],
        [InlineKeyboardButton(text="↩️ Отмена", callback_data="cat_goods")]
    ])
    await callback.message.edit_text(f"🛒 **Заказ:** {item_title}\n💰 **Сумма:** {price}.00 UAH\n\nВыберите способ оплаты:", parse_mode="Markdown", reply_markup=kb)

# Оплата через ПУМБ
@dp.callback_query(F.data == "pay_pumb")
async def pay_pumb_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get('price', '0')
    
    caption_text = (
        f"`{CARD_PUMB}`\n\n"
        f"💬 **Не проходить оплата?**\n"
        f"-Виберіть інший банк, або пишіть у підтримку!\n\n"
        f"💰 **До сплати: {price}.00 грн**\n\n"
        f"🏦 **Після оплати, відправте, сюди в чат, скріншот оплати як на прикладі вище ☝️**"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Як отримати квитанцію?", callback_data="how_get_receipt")],
        [InlineKeyboardButton(text="Змінити спосіб оплати", callback_data="cat_goods")]
    ])
    
    await callback.message.delete()
    if PUMB_VIDEO_FILE_ID:
        await callback.message.answer_video(video=PUMB_VIDEO_FILE_ID, caption=caption_text, parse_mode="Markdown", reply_markup=kb)
    else:
        await callback.message.answer(caption_text, parse_mode="Markdown", reply_markup=kb)
        
    await state.set_state(OrderState.waiting_for_receipt)

# Оплата через Santander / Erste
@dp.callback_query(F.data == "pay_santander")
async def pay_santander_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get('price', '0')
    
    text = (
        f"`{CARD_SANTANDER}`\n\n"
        f"🏦 **Інструкція з оплати (Santander / Erste):**\n"
        f"1. Скопіюйте номер картки вище (натисніть на нього).\n"
        f"2. Відкрийте додаток вашого банку та перекажіть **{price}.00 UAH** (або еквівалент).\n"
        f"3. Обов'язково збережіть чек / квитанцію про оплату.\n\n"
        f"📩 **Після оплати відправте скріншот чека прямо в цей чат!**"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Як отримати квитанцію?", callback_data="how_get_receipt")],
        [InlineKeyboardButton(text="Змінити спосіб оплати", callback_data="cat_goods")]
    ])
    
    await callback.message.delete()
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await state.set_state(OrderState.waiting_for_receipt)
