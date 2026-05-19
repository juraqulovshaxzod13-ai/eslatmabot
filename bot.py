import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import os

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
SHEETS_ID = os.getenv("SHEETS_ID")

def get_sheets_client():
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    creds.refresh(Request())
    return gspread.authorize(creds)

def get_sheet():
    client = get_sheets_client()
    return client.open_by_key(SHEETS_ID).sheet1

def get_all_clients():
    sheet = get_sheet()
    records = sheet.get_all_records()
    return records

def days_left(date_str):
    try:
        tulov = datetime.strptime(str(date_str), "%Y-%m-%d")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return (tulov - today).days
    except:
        return None

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class AddClient(StatesGroup):
    kabinet_id = State()
    kompaniya = State()
    tulov_sanasi = State()
    litsenziya = State()

class UpdatePayment(StatesGroup):
    yangi_sana = State()
    yangi_litsenziya = State()

class SearchClient(StatesGroup):
    qidiruv = State()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Xush kelibsiz!\n\n"
        "📋 Buyruqlar:\n"
        "/add — Yangi klient qo'shish\n"
        "/list — Yaqin to'lovlar\n"
        "/search — Klient qidirish\n"
        "/all — Barcha klientlar"
    )

@dp.message(Command("add"))
async def add_start(message: types.Message, state: FSMContext):
    await state.set_state(AddClient.kabinet_id)
    await message.answer("🔑 Kabinet ID ni kiriting:")

@dp.message(AddClient.kabinet_id)
async def add_kabinet(message: types.Message, state: FSMContext):
    await state.update_data(kabinet_id=message.text)
    await state.set_state(AddClient.kompaniya)
    await message.answer("🏢 Kompaniya nomini kiriting:")

@dp.message(AddClient.kompaniya)
async def add_kompaniya(message: types.Message, state: FSMContext):
    await state.update_data(kompaniya=message.text)
    await state.set_state(AddClient.tulov_sanasi)
    await message.answer("📅 To'lov sanasini kiriting (format: 2025-12-31):")

@dp.message(AddClient.tulov_sanasi)
async def add_sana(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
        await state.update_data(tulov_sanasi=message.text)
        await state.set_state(AddClient.litsenziya)
        await message.answer("📦 Litsenziya sonini kiriting:")
    except:
        await message.answer("❌ Format xato! Qaytadan kiriting (2025-12-31):")

@dp.message(AddClient.litsenziya)
async def add_litsenziya(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    try:
        sheet = get_sheet()
        sheet.append_row([
            data['kabinet_id'],
            data['kompaniya'],
            data['tulov_sanasi'],
            message.text
        ])
        kun = days_left(data['tulov_sanasi'])
        await message.answer(
            f"✅ Klient qo'shildi!\n\n"
            f"🔑 Kabinet ID: {data['kabinet_id']}\n"
            f"🏢 Kompaniya: {data['kompaniya']}\n"
            f"📅 To'lov sanasi: {data['tulov_sanasi']}\n"
            f"📦 Litsenziya: {message.text} ta\n"
            f"⏰ Qolgan muddat: {kun} kun"
        )
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

@dp.message(Command("list"))
async def list_expiring(message: types.Message):
    try:
        clients = get_all_clients()
        yaqin = []
        for c in clients:
            kun = days_left(c.get('Tulov sanasi', ''))
            if kun is not None and kun <= 30:
                yaqin.append((kun, c))
        yaqin.sort(key=lambda x: x[0])
        if not yaqin:
            await message.answer("✅ 30 kun ichida to'lov sanasi tugaydigan klient yo'q!")
            return
        text = "⚠️ Yaqin to'lovlar:\n\n"
        for kun, c in yaqin:
            emoji = "🔴" if kun <= 2 else "🟡" if kun <= 5 else "🟠" if kun <= 10 else "🟢"
            text += (
                f"{emoji} {c.get('Kompaniya nomi')}\n"
                f"   🔑 {c.get('Kabinet ID')} | 📦 {c.get('Litsenziya soni')} ta\n"
                f"   📅 {c.get('Tulov sanasi')} ({kun} kun qoldi)\n\n"
            )
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

@dp.message(Command("all"))
async def all_clients(message: types.Message):
    try:
        clients = get_all_clients()
        if not clients:
            await message.answer("📋 Klientlar yo'q!")
            return
        text = f"📋 Barcha klientlar ({len(clients)} ta):\n\n"
        for c in clients:
            kun = days_left(c.get('Tulov sanasi', ''))
            text += (
                f"🏢 {c.get('Kompaniya nomi')}\n"
                f"   🔑 {c.get('Kabinet ID')} | 📦 {c.get('Litsenziya soni')} ta\n"
                f"   📅 {c.get('Tulov sanasi')} ({kun} kun)\n\n"
            )
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

@dp.message(Command("search"))
async def search_start(message: types.Message, state: FSMContext):
    await state.set_state(SearchClient.qidiruv)
    await message.answer("🔍 Kabinet ID yoki kompaniya nomini kiriting:")

@dp.message(SearchClient.qidiruv)
async def search_do(message: types.Message, state: FSMContext):
    await state.clear()
    qidiruv = message.text.strip().lower()
    try:
        clients = get_all_clients()
        topilgan = [
            c for c in clients
            if qidiruv in str(c.get('Kabinet ID', '')).lower()
            or qidiruv in str(c.get('Kompaniya nomi', '')).lower()
        ]
        if not topilgan:
            await message.answer("❌ Klient topilmadi!")
            return
        for c in topilgan:
            kun = days_left(c.get('Tulov sanasi', ''))
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="✅ To'landi",
                    callback_data=f"tolandi_{c.get('Kabinet ID')}"
                )
            ]])
            await message.answer(
                f"✅ Topildi!\n\n"
                f"🏢 Kompaniya: {c.get('Kompaniya nomi')}\n"
                f"🔑 Kabinet ID: {c.get('Kabinet ID')}\n"
                f"📅 To'lov sanasi: {c.get('Tulov sanasi')}\n"
                f"📦 Litsenziya: {c.get('Litsenziya soni')} ta\n"
                f"⏰ Qolgan: {kun} kun",
                reply_markup=keyboard
            )
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

@dp.callback_query(F.data.startswith("tolandi_"))
async def tolandi_boshlash(callback: types.CallbackQuery, state: FSMContext):
    kabinet_id = callback.data.replace("tolandi_", "")
    await state.update_data(kabinet_id=kabinet_id)
    await state.set_state(UpdatePayment.yangi_sana)
    await callback.message.answer(f"📅 {kabinet_id} uchun yangi to'lov sanasini kiriting (2025-12-31):")
    await callback.answer()

@dp.message(UpdatePayment.yangi_sana)
async def update_sana(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
        await state.update_data(yangi_sana=message.text)
        await state.set_state(UpdatePayment.yangi_litsenziya)
        await message.answer("📦 Yangi litsenziya sonini kiriting:")
    except:
        await message.answer("❌ Format xato! Qaytadan kiriting (2025-12-31):")

@dp.message(UpdatePayment.yangi_litsenziya)
async def update_litsenziya(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    kabinet_id = data['kabinet_id']
    yangi_sana = data['yangi_sana']
    yangi_litsenziya = message.text
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        for i, row in enumerate(records, start=2):
            if str(row.get('Kabinet ID')) == str(kabinet_id):
                sheet.update_cell(i, 3, yangi_sana)
                sheet.update_cell(i, 4, yangi_litsenziya)
                kun = days_left(yangi_sana)
                await message.answer(
                    f"✅ Yangilandi!\n\n"
                    f"🔑 Kabinet ID: {kabinet_id}\n"
                    f"📅 Yangi sana: {yangi_sana}\n"
                    f"📦 Litsenziya: {yangi_litsenziya} ta\n"
                    f"⏰ Qolgan: {kun} kun"
                )
                return
        await message.answer("❌ Klient topilmadi!")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")

async def kunlik_tekshirish():
    while True:
        now = datetime.now()
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            clients = get_all_clients()
            for c in clients:
                kun = days_left(c.get('Tulov sanasi', ''))
                if kun in [10, 5, 2, 1]:
                    emoji = "🔴" if kun <= 2 else "🟡" if kun <= 5 else "🟠"
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="✅ To'landi",
                            callback_data=f"tolandi_{c.get('Kabinet ID')}"
                        )
                    ]])
                    chat_id = os.getenv("ADMIN_CHAT_ID")
                    if chat_id:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"{emoji} Ogohlantirish!\n\n"
                                f"🏢 {c.get('Kompaniya nomi')}\n"
                                f"🔑 Kabinet ID: {c.get('Kabinet ID')}\n"
                                f"📅 To'lov sanasi: {c.get('Tulov sanasi')}\n"
                                f"📦 Litsenziya: {c.get('Litsenziya soni')} ta\n"
                                f"⏰ {kun} kun qoldi!"
                            ),
                            reply_markup=keyboard
                        )
        except Exception as e:
            logging.error(f"Kunlik tekshirish xatosi: {e}")

async def main():
    asyncio.create_task(kunlik_tekshirish())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
