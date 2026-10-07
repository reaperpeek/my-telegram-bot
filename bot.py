import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ⚙️ НАСТРОЙКИ
BOT_TOKEN = "8408315552:AAEv_A-kJpkUyGdIH--RDYNDTJS4I1BACiI"
ADMIN_ID = 7786483533  # ⚠️ ЗАМЕНИ НА СВОЙ TELEGRAM ID (можно узнать через @userinfobot)

# Наценка (например, 1.10 = +10% к ценам Лютера)
MARGIN = 1.10 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# База данных в памяти (БД)
users_db = {}

# Состояния для ФСМ (загрузка чека)
class OrderState(StatesGroup):
    waiting_for_receipt = State()
    confirm_receipt = State()

def get_user_lang(user_id):
    return users_db.get(user_id, {}).get('lang', 'ru')

# Главное меню
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

# 1. СТАРТ
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {'balance_uah': 0, 'balance_stars': 0, 'lang': 'ru'}
        
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="set_lang_uk")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")]
    ])
    await message.answer("Оберіть мову / Выберите язык:", reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("set_lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    users_db[user_id]['lang'] = lang
    
    text = "Ласкаво просимо до Reaperpeek Shop!" if lang == 'uk' else "Добро пожаловать в Reaperpeek Shop!"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=main_kb(lang))

# 2. ПРОФИЛЬ
@dp.message(F.text.in_(["👤 Профіль", "👤 Профиль"]))
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    u = users_db.get(user_id, {'balance_uah': 0, 'balance_stars': 0})
    lang = get_user_lang(user_id)
    
    if lang == 'uk':
        text = f"ℹ️ **Інформація про вас:**\n\n🆔 ID: `{user_id}`\n✨ Баланс: {u['balance_uah']} UAH ~ {u['balance_stars']} ⭐"
    else:
        text = f"ℹ️ **Информация о вас:**\n\n🆔 ID: `{user_id}`\n✨ Баланс: {u['balance_uah']} UAH ~ {u['balance_stars']} ⭐"
        
    prof_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="deposit")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=prof_kb)

# 3. ПОПОЛНЕНИЕ БАЛАНСА
@dp.callback_query(F.data == "deposit")
async def deposit_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "💳 **Реквизиты для оплаты:**\n\n"
        "🇺🇦 Монобанк: `4441 1111 2222 3333`\n"
        "🇵🇱 BLIK / Zloty: По запросу в ЛС\n\n"
        "Отправьте **скриншот или файл квитанции** в этот чат после оплаты:",
        parse_mode="Markdown"
    )
    await state.set_state(OrderState.waiting_for_receipt)

# 4. ПОЛУЧЕНИЕ ЧЕКА И ОТПРАВКА АДМИНУ
@dp.message(OrderState.waiting_for_receipt, F.photo | F.document)
async def process_receipt(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
    
    # Пересылаем чек админу (тебе)
    admin_markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить +100 грн", callback_data=f"confirm_dep_{user_id}_100"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_dep_{user_id}")
        ]
    ])
    
    await bot.send_message(
        ADMIN_ID,
        f"🔔 **Новый чек на проверку!**\n\nПользователь: {username}\nID: `{user_id}`",
        parse_mode="Markdown"
    )
    
    if message.photo:
        await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, reply_markup=admin_markup)
    elif message.document:
        await bot.send_document(ADMIN_ID, message.document.file_id, reply_markup=admin_markup)
        
    await message.answer("⏳ **Чек получен!** Оператор проверяет поступление средств. Ожидайте начисления.")
    await state.clear()

# 5. ОБРАБОТКА АДМИН-КНОПОК
@dp.callback_query(F.data.startswith("confirm_dep_"))
async def admin_confirm(callback: types.CallbackQuery):
    _, _, user_id, amount = callback.data.split("_")
    user_id = int(user_id)
    amount = int(amount)
    
    if user_id in users_db:
        users_db[user_id]['balance_uah'] += amount
        
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ **ОДОБРЕНО** (+{amount} UAH)")
    await bot.send_message(user_id, f"🎉 **Баланс успешно пополнен на {amount} UAH!**")

@dp.callback_query(F.data.startswith("reject_dep_"))
async def admin_reject(callback: types.CallbackQuery):
    _, _, user_id = callback.data.split("_")
    user_id = int(user_id)
    
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ **ОТКЛОНЕНО**")
    await bot.send_message(user_id, "❌ **Квитанция отклонена.** Оплата не найдена или чек недействителен.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
