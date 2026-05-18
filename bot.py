import telebot
import sqlite3
from datetime import datetime
import time
import os

TOKEN = "8852010858:AAGG6ZaFrhtr7OVM4Vl-0gNH0g5DX7Jok1g"  # Вставьте ваш токен
ADMIN_ID = 1855199521  # Вставьте ваш ID

bot = telebot.TeleBot(TOKEN)

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
    print("✅ База данных готова")

init_db()

# Словарь для временного хранения данных при добавлении квартиры
user_data = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Новый поиск", "📋 Мои запросы", "🏠 Все квартиры")
    bot.send_message(message.chat.id, 
                     "🏢 Добро пожаловать!\nНажмите «Новый поиск», чтобы оставить запрос.",
                     reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔍 Новый поиск")
def new_search(message):
    msg = bot.send_message(message.chat.id, "💰 Введите максимальную цену в рублях (только цифры):")
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    try:
        price = int(message.text)
        msg = bot.send_message(message.chat.id, "🚪 Сколько комнат? (1, 2, 3, 4+):")
        bot.register_next_step_handler(msg, get_rooms, price)
    except:
        bot.send_message(message.chat.id, "❌ Введите число! Попробуйте ещё раз.")
        new_search(message)

def get_rooms(message, price):
    rooms = message.text
    msg = bot.send_message(message.chat.id, "🚇 Ближайшее метро:")
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
                     f"✅ Запрос сохранён!\n💰 до {price} руб.\n🚪 {rooms} комн.\n🚇 м. {metro}\n\nКак появятся квартиры — сообщу!")

@bot.message_handler(func=lambda message: message.text == "🏠 Все квартиры")
def all_flats(message):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT address, price, rooms, metro, photo_id FROM flats WHERE status='free' LIMIT 10")
    flats = c.fetchall()
    conn.close()
    if not flats:
        bot.send_message(message.chat.id, "😔 Сейчас нет свободных квартир")
        return
    for flat in flats:
        address, price, rooms, metro, photo_id = flat
        text = f"🏠 {address}\n💰 {price} руб.\n🚪 {rooms} комн.\n🚇 {metro}"
        if photo_id:
            bot.send_photo(message.chat.id, photo_id, caption=text)
        else:
            bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == "📋 Мои запросы")
def my_requests(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT max_price, min_rooms, metro FROM requests WHERE user_id=? AND is_active=1", (user_id,))
    requests = c.fetchall()
    conn.close()
    if not requests:
        bot.send_message(message.chat.id, "📭 У вас нет активных запросов")
        return
    text = "📋 Ваши запросы:\n\n"
    for r in requests:
        text += f"💰 до {r[0]} руб. | {r[1]} комн. | м. {r[2]}\n"
    bot.send_message(message.chat.id, text)

# ========== АДМИН: ДОБАВЛЕНИЕ КВАРТИРЫ (ИСПРАВЛЕННАЯ ВЕРСИЯ) ==========
@bot.message_handler(commands=['add_flat'])
def add_flat_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ У вас нет доступа")
        return
    
    user_data[message.from_user.id] = {}
    msg = bot.send_message(message.chat.id, "🏠 Введите адрес квартиры:")
    bot.register_next_step_handler(msg, add_address)

def add_address(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_data[message.from_user.id]['address'] = message.text
    msg = bot.send_message(message.chat.id, "💰 Введите цену (только цифры):")
    bot.register_next_step_handler(msg, add_price)

def add_price(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_data[message.from_user.id]['price'] = int(message.text)
        msg = bot.send_message(message.chat.id, "🚪 Введите количество комнат (1,2,3,4):")
        bot.register_next_step_handler(msg, add_rooms)
    except:
        bot.send_message(message.chat.id, "❌ Введите число! Попробуйте ещё раз.")
        msg = bot.send_message(message.chat.id, "💰 Введите цену (только цифры):")
        bot.register_next_step_handler(msg, add_price)

def add_rooms(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_data[message.from_user.id]['rooms'] = message.text
    msg = bot.send_message(message.chat.id, "🚇 Введите ближайшее метро:")
    bot.register_next_step_handler(msg, add_metro)

def add_metro(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_data[message.from_user.id]['metro'] = message.text
    msg = bot.send_message(message.chat.id, "📐 Введите площадь (в м², только цифры):")
    bot.register_next_step_handler(msg, add_area)

def add_area(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_data[message.from_user.id]['area'] = int(message.text)
        msg = bot.send_message(message.chat.id, "🖼️ Отправьте фото квартиры:")
        bot.register_next_step_handler(msg, add_photo)
    except:
        bot.send_message(message.chat.id, "❌ Введите число! Попробуйте ещё раз.")
        msg = bot.send_message(message.chat.id, "📐 Введите площадь (в м², только цифры):")
        bot.register_next_step_handler(msg, add_area)

def add_photo(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте фото!")
        msg = bot.send_message(message.chat.id, "🖼️ Отправьте фото квартиры:")
        bot.register_next_step_handler(msg, add_photo)
        return
    
    photo_id = message.photo[-1].file_id
    data = user_data[message.from_user.id]
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("""INSERT INTO flats (address, price, rooms, floor, metro, area, photo_id, status) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, 'free')""",
              (data['address'], data['price'], data['rooms'], "не указан", 
               data['metro'], data['area'], photo_id))
    conn.commit()
    conn.close()
    
    # Очищаем временные данные
    del user_data[message.from_user.id]
    
    bot.send_message(message.chat.id, 
                     f"✅ Квартира добавлена!\n"
                     f"🏠 {data['address']}\n"
                     f"💰 {data['price']} руб.\n"
                     f"🚪 {data['rooms']} комн.\n"
                     f"🚇 {data['metro']}\n"
                     f"📐 {data['area']} м²")
    
    # Рассылаем уведомления клиентам
    notify_users_about_new_flat(data['price'], data['rooms'], data['metro'], photo_id, data['address'])

def notify_users_about_new_flat(price, rooms, metro, photo_id, address):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM requests WHERE is_active=1 AND max_price>=? AND min_rooms=?", (price, rooms))
    users = c.fetchall()
    conn.close()
    
    text = f"🏠 НОВАЯ КВАРТИРА ПОД ВАШ ЗАПРОС!\n\n{address}\n💰 {price} руб.\n🚪 {rooms} комн.\n🚇 {metro}"
    
    for user in users:
        try:
            if photo_id:
                bot.send_photo(user[0], photo_id, caption=text)
            else:
                bot.send_message(user[0], text)
        except:
            pass

@bot.message_handler(commands=['help_admin'])
def help_admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, 
                     "👑 Админ-команды:\n"
                     "/add_flat - добавить квартиру\n"
                     "/list_flats - показать все квартиры\n"
                     "/stats - статистика\n"
                     "/help_admin - это меню")

@bot.message_handler(commands=['list_flats'])
def list_flats(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT id, address, price, rooms FROM flats WHERE status='free'")
    flats = c.fetchall()
    conn.close()
    if not flats:
        bot.send_message(message.chat.id, "Нет квартир")
        return
    text = "📋 Список квартир:\n\n"
    for flat in flats:
        text += f"ID: {flat[0]} | {flat[1]} | {flat[2]} руб. | {flat[3]} комн.\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM flats WHERE status='free'")
    flats_count = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT user_id) FROM requests WHERE is_active=1")
    clients_count = c.fetchone()[0]
    conn.close()
    bot.send_message(message.chat.id, 
                     f"📊 Статистика:\n\n"
                     f"🏠 Квартир в базе: {flats_count}\n"
                     f"👥 Активных клиентов: {clients_count}")

if __name__ == "__main__":
    print("🚀 Бот запущен!")
    bot.remove_webhook()
    bot.infinity_polling()
