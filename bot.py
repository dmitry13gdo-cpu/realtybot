import telebot
import requests
from datetime import datetime
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== НАСТРОЙКИ ==========
TOKEN = "8775872761:AAE_y3MuXpXcWR_Od6_ssGr2fh5xz45O1QE"
ADMIN_ID = 1855199521  # Ваш Telegram ID

# Данные Supabase (замените на свои!)
SUPABASE_URL = "https://supabase.com/eytqpgsbxnxtnsyloyfh"
SUPABASE_KEY = "sb_publishable_fWNj7e9FvWN7pyvV6lF0Ww_d59H0gv6"

bot = telebot.TeleBot(TOKEN)

# ========== HTTP-СЕРВЕР ДЛЯ RENDER ==========
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')
    def log_message(self, format, *args):
        pass

def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# ========== РАБОТА С SUPABASE ==========
def supabase_request(method, endpoint, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    if method == "GET":
        response = requests.get(url, headers=headers, params=data)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    return response.json() if response.status_code < 300 else None

def add_flat_to_db(address, price, rooms, floor, area, house_type, build_year, condition, description, photo_ids):
    # Добавляем квартиру
    flat_data = {
        "address": address, "price": price, "rooms": rooms,
        "floor": floor, "area": area, "house_type": house_type,
        "build_year": build_year, "condition": condition,
        "description": description, "status": "free"
    }
    result = supabase_request("POST", "flats", flat_data)
    if result and len(result) > 0:
        flat_id = result[0]["id"]
        # Добавляем фото
        for photo_id in photo_ids:
            supabase_request("POST", "photos", {"flat_id": flat_id, "photo_id": photo_id})
        return flat_id
    return None

# ========== КОМАНДЫ КЛИЕНТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Новый поиск", "📋 Мои запросы", "🏠 Все квартиры")
    bot.send_message(message.chat.id, 
                     "🏢 Добро пожаловать в агентство недвижимости!\n\n"
                     "Нажмите «Новый поиск», чтобы оставить запрос.",
                     reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔍 Новый поиск")
def new_search(message):
    msg = bot.send_message(message.chat.id, "💰 Введите максимальную цену:")
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    try:
        price = int(message.text)
        msg = bot.send_message(message.chat.id, "🚪 Сколько комнат?")
        bot.register_next_step_handler(msg, save_request, price)
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")
        new_search(message)

def save_request(message, price):
    rooms = message.text
    user_id = message.from_user.id
    
    # Сохраняем запрос в Supabase
    request_data = {
        "user_id": user_id,
        "max_price": price,
        "min_rooms": rooms,
        "is_active": True
    }
    supabase_request("POST", "requests", request_data)
    
    # Ищем подходящие квартиры
    filters = {"price": f"lte.{price}", "rooms": f"eq.{rooms}", "status": "eq.free"}
    flats = supabase_request("GET", "flats", filters)
    
    if flats:
        bot.send_message(message.chat.id, f"🏠 Нашёл {len(flats)} квартир(у):")
        for flat in flats:
            text = f"🏠 {flat['address']}\n💰 {flat['price']} руб.\n🚪 {flat['rooms']} комн."
            bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "😔 Пока нет квартир под ваш запрос.")
    
    bot.send_message(message.chat.id, "✅ Запрос сохранён! Когда появятся новые квартиры — сообщу.")

@bot.message_handler(func=lambda message: message.text == "🏠 Все квартиры")
def all_flats(message):
    flats = supabase_request("GET", "flats", {"status": "eq.free", "limit": 10})
    if not flats:
        bot.send_message(message.chat.id, "😔 Сейчас нет свободных квартир")
        return
    
    for flat in flats:
        text = f"🏠 {flat['address']}\n💰 {flat['price']} руб.\n🚪 {flat['rooms']} комн."
        bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == "📋 Мои запросы")
def my_requests(message):
    user_id = message.from_user.id
    requests_data = supabase_request("GET", "requests", {"user_id": f"eq.{user_id}", "is_active": "eq.true"})
    
    if not requests_data:
        bot.send_message(message.chat.id, "📭 У вас нет активных запросов")
        return
    
    text = "📋 Ваши запросы:\n\n"
    for r in requests_data:
        text += f"💰 до {r['max_price']} руб. | {r['min_rooms']} комн.\n"
    bot.send_message(message.chat.id, text)

# ========== АДМИН-КОМАНДЫ (упрощённая версия) ==========
@bot.message_handler(commands=['add_flat'])
def add_flat_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет доступа")
        return
    
    msg = bot.send_message(message.chat.id, "🏠 Введите адрес квартиры:")
    bot.register_next_step_handler(msg, add_address)

def add_address(message):
    bot.admin_data = {"address": message.text}
    msg = bot.send_message(message.chat.id, "💰 Введите цену:")
    bot.register_next_step_handler(msg, add_price)

def add_price(message):
    bot.admin_data["price"] = int(message.text)
    msg = bot.send_message(message.chat.id, "🚪 Введите количество комнат:")
    bot.register_next_step_handler(msg, add_rooms)

def add_rooms(message):
    bot.admin_data["rooms"] = message.text
    msg = bot.send_message(message.chat.id, "🖼️ Отправьте фото квартиры:")
    bot.register_next_step_handler(msg, add_photo)

def add_photo(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Отправьте фото!")
        return
    
    photo_id = message.photo[-1].file_id
    data = bot.admin_data
    
    # Сохраняем в Supabase
    flat_data = {
        "address": data["address"], "price": data["price"],
        "rooms": data["rooms"], "status": "free"
    }
    result = supabase_request("POST", "flats", flat_data)
    
    if result:
        flat_id = result[0]["id"]
        supabase_request("POST", "photos", {"flat_id": flat_id, "photo_id": photo_id})
        bot.send_message(message.chat.id, f"✅ Квартира добавлена!\n{data['address']}\n💰 {data['price']} руб.")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка при сохранении")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    # Принудительно удаляем вебхук
    bot.remove_webhook()
    # Пауза для гарантии
    time.sleep(1)
    # Запускаем с увеличенным таймаутом
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
