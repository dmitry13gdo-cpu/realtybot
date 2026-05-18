import telebot
import sqlite3
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = "8852010858:AAGG6ZaFrhtr7OVM4Vl-0gNH0g5DX7Jok1g"  # Вставьте токен от BotFather
ADMIN_ID = 1855199521  # Вставьте ваш ID (узнайте у @userinfobot)

bot = telebot.TeleBot(TOKEN)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS flats
                 (id INTEGER PRIMARY KEY, address TEXT, price INTEGER, 
                  rooms INTEGER, floor TEXT, metro TEXT, area INTEGER, 
                  photo_id TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS requests
                 (user_id INTEGER, max_price INTEGER, min_rooms INTEGER,
                  metro TEXT, created_at TEXT, is_active INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# ========== КОМАНДА /start ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Новый поиск", "📋 Мои запросы", "🏠 Все квартиры")
    bot.send_message(user_id, 
                     "🏢 Добро пожаловать в агентство недвижимости!\n\n"
                     "Я буду искать квартиры специально для вас.\n"
                     "Нажмите «Новый поиск», чтобы оставить запрос.",
                     reply_markup=markup)

# ========== НОВЫЙ ПОИСК ==========
@bot.message_handler(func=lambda message: message.text == "🔍 Новый поиск")
def new_search(message):
    msg = bot.send_message(message.chat.id, "💰 Введите максимальную цену в рублях:")
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    try:
        price = int(message.text)
        msg = bot.send_message(message.chat.id, "🚪 Сколько комнат? (1, 2, 3, 4+)")
        bot.register_next_step_handler(msg, get_rooms, price)
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")
        new_search(message)

def get_rooms(message, price):
    rooms = message.text
    msg = bot.send_message(message.chat.id, "🚇 Какое метро ближе всего?")
    bot.register_next_step_handler(msg, save_request, price, rooms)

def save_request(message, price, rooms):
    metro = message.text
    user_id = message.from_user.id
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO requests (user_id, max_price, min_rooms, metro, created_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
              (user_id, price, rooms, metro, datetime.now()))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, 
                     f"✅ Запрос сохранён!\n\n"
                     f"💰 до {price} руб.\n"
                     f"🚪 {rooms} комн.\n"
                     f"🚇 м. {metro}\n\n"
                     f"Как появятся подходящие квартиры — я сообщу!")

# ========== ВСЕ КВАРТИРЫ ==========
@bot.message_handler(func=lambda message: message.text == "🏠 Все квартиры")
def all_flats(message):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT address, price, rooms, floor, metro, area, photo_id FROM flats WHERE status='free' LIMIT 10")
    flats = c.fetchall()
    conn.close()
    
    if not flats:
        bot.send_message(message.chat.id, "😔 Сейчас нет свободных квартир")
        return
    
    for flat in flats:
        address, price, rooms, floor, flat_metro, area, photo_id = flat
        text = f"🏠 {address}\n💰 {price} руб.\n🚪 {rooms} комн.\n🚇 {flat_metro}"
        if photo_id:
            bot.send_photo(message.chat.id, photo_id, caption=text)
        else:
            bot.send_message(message.chat.id, text)

# ========== МОИ ЗАПРОСЫ ==========
@bot.message_handler(func=lambda message: message.text == "📋 Мои запросы")
def my_requests(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT max_price, min_rooms, metro, created_at FROM requests WHERE user_id=? AND is_active=1", (user_id,))
    requests = c.fetchall()
    conn.close()
    
    if not requests:
        bot.send_message(message.chat.id, "📭 У вас нет активных запросов. Нажмите «Новый поиск»")
        return
    
    text = "📋 Ваши активные запросы:\n\n"
    for r in requests:
        text += f"💰 до {r[0]} руб. | {r[1]} комн. | м. {r[2]}\n"
    bot.send_message(message.chat.id, text)

# ========== КОМАНДА ДЛЯ АДМИНА: ДОБАВИТЬ КВАРТИРУ ==========
@bot.message_handler(commands=['add_flat'])
def add_flat_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет доступа")
        return
    msg = bot.send_message(message.chat.id, "🏠 Введите адрес квартиры:")
    bot.register_next_step_handler(msg, add_address)

def add_address(message):
    address = message.text
    msg = bot.send_message(message.chat.id, "💰 Введите цену:")
    bot.register_next_step_handler(msg, add_price, address)

def add_price(message, address):
    try:
        price = int(message.text)
        msg = bot.send_message(message.chat.id, "🚪 Введите количество комнат (1,2,3,4):")
        bot.register_next_step_handler(msg, add_rooms, address, price)
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")
        add_flat_start(message)

def add_rooms(message, address, price):
    rooms = message.text
    msg = bot.send_message(message.chat.id, "🏢 Введите этаж (например 3/5):")
    bot.register_next_step_handler(msg, add_floor, address, price, rooms)

def add_floor(message, address, price, rooms):
    floor = message.text
    msg = bot.send_message(message.chat.id, "🚇 Введите ближайшее метро:")
    bot.register_next_step_handler(msg, add_metro, address, price, rooms, floor)

def add_metro(message, address, price, rooms, floor):
    metro = message.text
    msg = bot.send_message(message.chat.id, "📐 Введите площадь в м²:")
    bot.register_next_step_handler(msg, add_area, address, price, rooms, floor, metro)

def add_area(message, address, price, rooms, floor, metro):
    try:
        area = int(message.text)
        msg = bot.send_message(message.chat.id, "🖼️ Отправьте фото квартиры (одно фото):")
        bot.register_next_step_handler(msg, add_photo, address, price, rooms, floor, metro, area)
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")
        add_metro(message, address, price, rooms, floor)

def add_photo(message, address, price, rooms, floor, metro, area):
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO flats (address, price, rooms, floor, metro, area, photo_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'free')",
              (address, price, rooms, floor, metro, area, photo_id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ Квартира добавлена!\n{address} за {price} руб.")
    
    # Рассылаем уведомления всем подходящим клиентам
    notify_all_users()

# ========== АВТОРАССЫЛКА ПРИ ДОБАВЛЕНИИ КВАРТИРЫ ==========
def notify_all_users():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    c.execute("SELECT address, price, rooms, metro, photo_id FROM flats WHERE status='free' ORDER BY id DESC LIMIT 1")
    new_flat = c.fetchone()
    
    if new_flat:
        address, price, rooms, metro, photo_id = new_flat
        c.execute("SELECT DISTINCT user_id FROM requests WHERE is_active=1 AND max_price>=? AND min_rooms=?", (price, rooms))
        users = c.fetchall()
        
        text = f"🏠 НОВАЯ КВАРТИРА ПОД ВАШ ЗАПРОС!\n\n{address}\n💰 {price} руб.\n🚪 {rooms} комн.\n🚇 {metro}"
        
        for user in users:
            try:
                if photo_id:
                    bot.send_photo(user[0], photo_id, caption=text)
                else:
                    bot.send_message(user[0], text)
            except:
                pass
    
    conn.close()

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("✅ Бот запущен!")
    bot.infinity_polling()
