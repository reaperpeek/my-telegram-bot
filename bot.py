import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# Токен подтягивается из переменных окружения Render или прописан здесь
BOT_TOKEN = os.getenv("8684030373:AAH3SBGRKk41DSydEJG1H8t05SX-N_uPrmw", "ТВОЙ_ТОКЕН")
ADMIN_ID = 7786483533  # Твой ID администратора

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class OrderState(StatesGroup):
    waiting_for_receipt = State()

class WithdrawState(StatesGroup):
    waiting_for_amount = State()

# База данных пользователей
users_db = {}

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"balance_stars": 100, "balance_gold": 200, "inventory": []}
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Купить Stars / Gold / NFT", callback_data="buy_menu")],
        [InlineKeyboardButton(text="📤 Вывести средства", callback_data="start_withdraw")]
    ])
    
    user_data = users_db[user_id]
    await message.answer(
        f"Добро пожаловать в Monolit Bot!\n\n"
        f"💰 Твой баланс:\n"
        f"• Stars: {user_data['balance_stars']}\n"
        f"• Gold: {user_data['balance_gold']}\n\n"
        f"Выбери нужный раздел:",
        reply_markup=kb
    )

@router.callback_query(F.data == "buy_menu")
async def buy_menu(call: CallbackQuery):
    await call.message.answer(
        "Напиши в чат товар, который хочешь приобрести (например: `Купить 200 Stars` или `Купить 100 Gold`), чтобы получить реквизиты ПУМБ.",
        parse_mode="Markdown"
    )

@router.message(F.text.lower().startswith("купить"))
async def start_payment(message: Message, state: FSMContext):
    item_name = message.text
    price = 42.0  # Сумма к оплате
    
    await state.set_state(OrderState.waiting_for_receipt)
    await state.update_data(item_name=item_name, price=price)
    
    await message.answer(
        f"Заказ: {item_name}\n"
        f"💳 К оплате: {price} UAH\n\n"
        f"Реквизиты для оплаты (ПУМБ):\n`4314140214993815`\n\n"
        f"📸 **После оплаты отправьте сюда скриншот или PDF-чек.**",
        parse_mode="Markdown"
    )

@router.message(OrderState.waiting_for_receipt, F.photo | F.document)
async def process_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    item_name = data.get("item_name")
    price = data.get("price")
    user = message.from_user

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Зачислить", callback_data=f"pay_confirm:{user.id}:{item_name}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pay_reject:{user.id}")
    ]])

    caption = (
        f"📥 **Новый чек на проверку!**\n\n"
        f"👤 Юзер: @{user.username or 'нет'} (ID: `{user.id}`)\n"
        f"📦 Товар: {item_name}\n"
        f"💵 Сумма: {price} UAH"
    )

    if message.photo:
        await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=admin_kb, parse_mode="Markdown")
    elif message.document:
        await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption, reply_markup=admin_kb, parse_mode="Markdown")

    await message.answer("✅ Чек отправлен администратору. Ожидайте подтверждения.")
    await state.clear()

@router.message(OrderState.waiting_for_receipt)
async def invalid_receipt(message: Message):
    await message.answer("Пожалуйста, отправьте именно скриншот (фото) или PDF-файл чека.")

@router.callback_query(F.data.startswith("pay_confirm:"))
async def confirm_payment(call: CallbackQuery):
    _, user_id_str, item_name = call.data.split(":", 2)
    user_id = int(user_id_str)

    if user_id not in users_db:
        users_db[user_id] = {"balance_stars": 0, "balance_gold": 0, "inventory": []}

    if "stars" in item_name.lower():
        users_db[user_id]["balance_stars"] += 200
    elif "gold" in item_name.lower():
        users_db[user_id]["balance_gold"] += 100

    try:
        await bot.send_message(
            user_id,
            f"🎉 **Оплата подтверждена!**\n"
            f"Товар/баланс ({item_name}) успешно зачислен.\n\n"
            f"Если хотите сделать вывод, воспользуйтесь кнопками в боте."
        )
    except Exception:
        pass

    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ **ОДОБРЕНО И ВЫДАНО**", parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_reject:"))
async def reject_payment(call: CallbackQuery):
    _, user_id_str = call.data.split(":")
    user_id = int(user_id_str)

    try:
        await bot.send_message(user_id, "❌ Ваша оплата не подтверждена. Обратитесь в поддержку @monolit_hq.")
    except Exception:
        pass

    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ **ОТКЛОНЕНО**", parse_mode="Markdown")

# Блок вывода с лимитами и проверкой баланса
@router.callback_query(F.data == "start_withdraw")
async def start_withdraw(call: CallbackQuery, state: FSMContext):
    await state.set_state(WithdrawState.waiting_for_amount)
    await call.message.answer(
        "Укажите, что именно хотите вывести (например: `100 Gold` или `50 Stars`).\n"
        "Лимиты: минимум **100 Gold**, минимум **50 Stars**.",
        parse_mode="Markdown"
    )

@router.message(WithdrawState.waiting_for_amount)
async def process_withdraw_request(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users_db:
        users_db[user_id] = {"balance_stars": 0, "balance_gold": 0, "inventory": []}
    
    user_data = users_db[user_id]
    text = message.text.lower().strip()
    amount = int(''.join(filter(str.isdigit, text)) or 0)

    if "gold" in text or "голд" in text:
        if amount < 100:
            await message.answer("❌ Минимальная сумма для вывода Gold — **100 Gold**.")
            return
        if user_data["balance_gold"] < amount:
            await message.answer(f"❌ Недостаточно средств! Ваш баланс Gold: {user_data['balance_gold']}.")
            return
    elif "star" in text or "звезд" in text or "звёзд" in text:
        if amount < 50:
            await message.answer("❌ Минимальная сумма для вывода Stars — **50 Stars**.")
            return
        if user_data["balance_stars"] < amount:
            await message.answer(f"❌ Недостаточно средств! Ваш баланс Stars: {user_data['balance_stars']}.")
            return
    else:
        await message.answer("❌ Укажите корректно валюту (Gold или Stars) и количество.")
        return

    withdraw_text = message.text
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить вывод", callback_data=f"wd_confirm:{user_id}:{withdraw_text}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"wd_reject:{user_id}")
    ]])

    caption = (
        f"📤 **ЗАПРОС НА ВЫВОД!**\n\n"
        f"👤 **Профиль:** @{message.from_user.username or 'нет'}\n"
        f"🆔 **ID:** `{user_id}`\n\n"
        f"💰 **Баланс в боте:**\n"
        f"• Stars: {user_data['balance_stars']}\n"
        f"• Gold: {user_data['balance_gold']}\n\n"
        f"📌 **Запрос:** {withdraw_text}"
    )

    await bot.send_message(ADMIN_ID, caption, reply_markup=admin_kb, parse_mode="Markdown")
    await message.answer("Заявка на вывод отправлена администратору. Ожидайте обработку!")
    await state.clear()

@router.callback_query(F.data.startswith("wd_confirm:"))
async def confirm_withdraw(call: CallbackQuery):
    _, user_id_str, withdraw_text = call.data.split(":", 2)
    user_id = int(user_id_str)

    try:
        await bot.send_message(
            user_id,
            f"🎉 **Вывод подтвержден!**\n\n"
            f"Вам переведено: **{withdraw_text}**.\n"
            f"Если хотите сделать еще операцию, воспользуйтесь кнопками ниже."
        )
    except Exception:
        pass

    await call.message.edit_text(text=call.message.text + "\n\n✅ **ВЫВОД ПОДТВЕРЖДЕН**", parse_mode="Markdown")

@router.callback_query(F.data.startswith("wd_reject:"))
async def reject_withdraw(call: CallbackQuery):
    _, user_id_str = call.data.split(":")
    user_id = int(user_id_str)

    try:
        await bot.send_message(user_id, "❌ Ваш запрос на вывод отклонен. Обратитесь в поддержку @monolit_hq.")
    except Exception:
        pass

    await call.message.edit_text(text=call.message.text + "\n\n❌ **Отклонено**", parse_mode="Markdown")

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
