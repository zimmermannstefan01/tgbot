import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import requests
import asyncio
import json
import subprocess
from datetime import datetime
# Завантажуємо змінні середовища з файлу .env
load_dotenv()

# Токен вашого Telegram-бота
BOT_TOKEN = os.getenv("YOUR_TELEGRAM_BOT_TOKEN")

# Список дозволених користувачів за їхніми ID
ALLOWED_USERS = list(map(int, os.getenv("ALLOWED_USERS", "").split(",")))

# Функція для збереження оператора в файл
def save_operator(operator_id):
    with open("operator.json", "w") as file:
        json.dump({"operator": operator_id}, file)

# Функція для завантаження оператора з файлу
def load_operator():
    try:
        with open("operator.json", "r") as file:
            data = json.load(file)
            return data.get("operator")
    except FileNotFoundError:
        return None  # Якщо файл не знайдений, повертаємо None

# Ініціалізація бота та диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Змінна для оператора, яка буде зберігатися в файлі
operator = load_operator()

# Функція для отримання статусу монітора
async def fetch_uptime():
    global operator
    if operator is None:
        return "Operator is not set."
    
    monitor_url = f"https://monitor.sophon.xyz/nodes?operators={operator}"

    try:
        response = requests.get(monitor_url)
        response.raise_for_status()
        data = response.json()

        if "nodes" in data and len(data["nodes"]) > 0:
            node = data["nodes"][0]
            operator_name = node.get("operator", "N/A")
            status = "Online" if node.get("status", False) else "Offline"
            rewards = node.get("rewards", "0")
            fee = node.get("fee", 0)
            uptime = node.get("uptime", 0)

            return (f"Operator: {operator_name}\n"
                    f"Status: {status}\n"
                    f"Rewards: {rewards}\n"
                    f"Fee: {fee}%\n"
                    f"Uptime: {uptime:.2f}%")
        else:
            return "No data available."
    except Exception as e:
        return f"Error fetching data: {e}"

# Функція для перевірки статусу контейнера "sophon-light-node"
def get_container_status():
    try:
        # Використовуємо docker inspect для отримання часу запуску контейнера
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.StartedAt}}", "sophon-light-node"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode == 0:
            started_at = result.stdout.strip()
            if started_at:
                # Видаляємо мікросекунди і намагаємося конвертувати ISO 8601 без них
                started_at = started_at.split('.')[0]  # Обрізаємо мікросекунди
                start_time = datetime.fromisoformat(started_at)  # Конвертуємо в datetime
                current_time = datetime.utcnow()  # Поточний час у UTC
                uptime = current_time - start_time  # Обчислюємо час роботи

                # Форматуємо результат
                days = uptime.days
                hours, remainder = divmod(uptime.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                return (f"Container 'sophon-light-node' has been running for: "
                        f"{days} days, {hours} hours, {minutes} minutes, and {seconds} seconds.")
            else:
                return "Container 'sophon-light-node' is not running."
        else:
            return "Error fetching container status: " + result.stderr.strip()
    except Exception as e:
        return f"Error fetching container status: {e}"

# Команда для налаштування оператора
@dp.message(Command("set_operator"))
async def set_operator(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("You are not authorized to use this bot.")
        return

    global operator
    # Отримуємо оператор із тексту повідомлення (після команди)
    operator = message.text.split(" ", 1)[-1]
    if operator:
        save_operator(operator)  # Зберігаємо новий оператор у файл
        await message.answer(f"Operator set to: {operator}")
    else:
        await message.answer("Please provide a valid operator.")

# Команда /start
@dp.message(Command("start"))
async def send_welcome(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("You are not authorized to use this bot.")
        return

    # Створюємо кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Check Status", callback_data="check_status")],
        [InlineKeyboardButton(text="Set Operator", callback_data="set_operator")],
        [InlineKeyboardButton(text="Container Status", callback_data="container_status")]
    ])
    await message.answer("Welcome! Use the button below to check the node status or set the operator.", reply_markup=keyboard)

# Обробник для кнопки "Set Operator"
@dp.callback_query(lambda callback_query: callback_query.data == "set_operator")
async def handle_set_operator_button(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ALLOWED_USERS:
        await callback_query.answer("You are not authorized to use this bot.", show_alert=True)
        return

    await callback_query.message.answer("Please send me the new operator in the following format:\n/set_operator <operator_id>")

# Обробник для кнопки "Check Status"
@dp.callback_query(lambda callback_query: callback_query.data == "check_status")
async def handle_status_button(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ALLOWED_USERS:
        await callback_query.answer("You are not authorized to use this bot.", show_alert=True)
        return

    status = await fetch_uptime()
    await callback_query.message.answer(status)
    await callback_query.answer()  # Закриває "годинник" на кнопці

# Обробник для кнопки "Container Status"
@dp.callback_query(lambda callback_query: callback_query.data == "container_status")
async def handle_container_status_button(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in ALLOWED_USERS:
        await callback_query.answer("You are not authorized to use this bot.", show_alert=True)
        return

    container_status = get_container_status()
    await callback_query.message.answer(container_status)
    await callback_query.answer()  # Закриває "годинник" на кнопці

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
