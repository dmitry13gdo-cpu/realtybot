import telebot
import sqlite3
from datetime import datetime
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== ТОКЕНЫ ==========
TOKEN = "8852010858:AAGG6ZaFrhtr7OVM4Vl-0gNH0g5DX7Jok1g"
ADMIN_ID = 1855199521  # Ваш ID

bot = telebot.TeleBot(TOKEN)

# ========== HTTP-СЕРВЕР ДЛЯ RENDER ==========
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
    def log_message(self, format, *args):
        pass

def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # Таблица квартир (расширенная)
    c.execute('''CREATE TABLE IF NOT EXISTS flats (
        id INTEGER PRIMARY KEY, 
        address TEXT, 
        price INTEGER, 
        rooms INTEGER, 
        floor TEXT, 
        area INTEGER,
        house_type TEXT,
        build_year INTEGER,
        condition TEXT,
        description TEXT,
        status TEXT
    )''')
    
    # Таблица для фотографий (связь с квартирой)
    c.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY,
        flat_id INTEGER,
        photo_id TEXT,
        FOREIGN KEY (flat_id) REFERENCES flats (id)
    )''')
    
    # Таблица запросов клиентов
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
        user_id INTEGER, 
        max_price INTEGER, 
        min_rooms INTEGER,
        created_at TEXT, 
        is_active INTEGER
    )''')
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

init_db()

# Временное хранилище для добавления квартиры
temp_data = {}

# ========== КОМАНДЫ КЛИЕНТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Новый поиск", "📋 Мои запросы", "🏠 Все квартиры")
    bot.send_message(message.chat.id, 
                     "🏢 Добро пожаловать в агентство недвижимости!\n\n"
                     "Нажмите «Новый поиск», чтобы оставить запрос.\n"
                     "Как появятся подходящие квартиры — я сообщу!",
                     reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔍 Новый поиск")
def new_search(message):
    msg = bot.send_message(message.chat.id, "💰 Введите максимальную цену в рублях (только цифры):")
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    try:
        price = int(message.text)
        msg = bot.send_message(message.chat.id, "🚪 Сколько комнат? (1, 2, 3, 4+):")
        bot.register_next_step_handler(msg, save_request, price)
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")
        new_search(message)

def save_request(message, price):
    rooms = message.text
    user_id = message.from_user.id
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO requests (user_id, max_price, min_rooms, created_at, is_active) VALUES (?, ?, ?, ?, 1)",
              (user_id, price, rooms, datetime.now()))
    conn.commit()
    conn.close()
    
    # Сразу показываем подходящие квартиры
    show_matching_flats(message.chat.id, price, rooms)
    
    bot.send_message(message.chat.id, 
                     f"✅ Запрос сохранён!\n\n"
                     f"💰 до {price} руб.\n"
                     f"🚪 {rooms} комн.\n\n"
                     f"Я уже показал подходящие квартиры выше.\n"
                     f"Когда появятся новые — сообщу!")

def show_matching_flats(chat_id, max_price, min_rooms):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # Ищем квартиры по запросу
    c.execute("SELECT id, address, price, rooms, floor, area, house_type, build_year, condition, description FROM flats WHERE status='free' AND price <= ? AND rooms = ?", 
              (max_price, min_rooms))
    flats = c.fetchall()
    
    if not flats:
        bot.send_message(chat_id, "😔 Пока нет квартир под ваш запрос. Как появятся — сообщу!")
        return
    
    bot.send_message(chat_id, f"🏠 Нашёл {len(flats)} квартир(у/ы) под ваш запрос:")
    
    for flat in flats:
        flat_id, address, price, rooms, floor, area, house_type, build_year, condition, description = flat
        
        # Получаем фото для квартиры
        c.execute("SELECT photo_id FROM photos WHERE flat_id=?", (flat_id,))
        photos = c.fetchall()
        
        # Формируем текст
        text = f"🏠 *{address}*\n\n"
        text += f"💰 Цена: {price:,} руб.\n"
        text += f"🚪 Комнат: {rooms}\n"
        text += f"🏢 Этаж: {floor}\n"
        text += f"📐 Площадь: {area} м²\n"
        text += f"🏗️ Тип дома: {house_type}\n"
        text += f"📅 Год постройки: {build_year}\n"
        text += f"🔧 Состояние: {condition}\n"
        
        if description:
            text += f"\n📝 Описание: {description}\n"
        
        # Отправляем фото (если есть)
        if photos:
            # Первое фото отправляем с подписью
            bot.send_photo(chat_id, photos[0][0], caption=text, parse_mode='Markdown')
            # Остальные фото отправляем без подписи
            for photo in photos[1:]:
                bot.send_photo(chat_id, photo[0])
        else:
            bot.send_message(chat_id, text, parse_mode='Markdown')
    
    conn.close()

@bot.message_handler(func=lambda message: message.text == "🏠 Все квартиры")
def all_flats(message):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT id, address, price, rooms, floor, area, house_type, build_year, condition, description FROM flats WHERE status='free' LIMIT 10")
    flats = c.fetchall()
    
    if not flats:
        bot.send_message(message.chat.id, "😔 Сейчас нет свободных квартир")
        conn.close()
        return
    
    for flat in flats:
        flat_id, address, price, rooms, floor, area, house_type, build_year, condition, description = flat
        
        # НОВОЕ ПОДКЛЮЧЕНИЕ ДЛЯ ФОТО (НЕ используем старое c)
        conn2 = sqlite3.connect('bot.db')
        c2 = conn2.cursor()
        c2.execute("SELECT photo_id FROM photos WHERE flat_id=?", (flat_id,))
        photos = c2.fetchall()
        conn2.close()
        
        text = f"🏠 *{address}*\n\n💰 {price:,} руб.\n🚪 {rooms} комн.\n🏢 {floor} эт.\n📐 {area} м²\n🏗️ {house_type}\n🔧 {condition}"
        
        if photos:
            bot.send_photo(message.chat.id, photos[0][0], caption=text, parse_mode='Markdown')
            for photo in photos[1:3]:
                bot.send_photo(message.chat.id, photo[0])
        else:
            bot.send_message(message.chat.id, text, parse_mode='Markdown')
    
    conn.close()

@bot.message_handler(func=lambda message: message.text == "📋 Мои запросы")
def my_requests(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute("SELECT max_price, min_rooms, created_at FROM requests WHERE user_id=? AND is_active=1", (user_id,))
    requests = c.fetchall()
    conn.close()
    
    if not requests:
        bot.send_message(message.chat.id, "📭 У вас нет активных запросов. Нажмите «Новый поиск»")
        return
    
    text = "📋 Ваши активные запросы:\n\n"
    for r in requests:
        text += f"💰 до {r[0]} руб. | {r[1]} комн.\n"
    bot.send_message(message.chat.id, text)

# ========== АДМИН-КОМАНДЫ ==========
@bot.message_handler(commands=['add_flat'])
def add_flat_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Нет доступа")
        return
    
    temp_data[message.from_user.id] = {}
    temp_data[message.from_user.id]['photos'] = []
    
    msg = bot.send_message(message.chat.id, "🏠 Введите адрес квартиры:")
    bot.register_next_step_handler(msg, get_address)

def get_address(message):
    temp_data[message.from_user.id]['address'] = message.text
    msg = bot.send_message(message.chat.id, "💰 Введите цену (только цифры):")
    bot.register_next_step_handler(msg, get_price_flat)

def get_price_flat(message):
    try:
        temp_data[message.from_user.id]['price'] = int(message.text)
        msg = bot.send_message(message.chat.id, "🚪 Введите количество комнат (1,2,3,4):")
        bot.register_next_step_handler(msg, get_rooms_flat)
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")
        add_flat_start(message)

def get_rooms_flat(message):
    temp_data[message.from_user.id]['rooms'] = message.text
    msg = bot.send_message(message.chat.id, "🏢 Введите этаж (например: 3/5 или '3 из 5'):")
    bot.register_next_step_handler(msg, get_floor)

def get_floor(message):
    temp_data[message.from_user.id]['floor'] = message.text
    msg = bot.send_message(message.chat.id, "📐 Введите площадь в м² (только цифры):")
    bot.register_next_step_handler(msg, get_area)

def get_area(message):
    try:
        temp_data[message.from_user.id]['area'] = int(message.text)
        msg = bot.send_message(message.chat.id, "🏗️ Тип дома (панель/кирпич/монолит/дерево):")
        bot.register_next_step_handler(msg, get_house_type)
    except:
        bot.send_message(message.chat.id, "❌ Введите число!")
        get_area(message)

def get_house_type(message):
    temp_data[message.from_user.id]['house_type'] = message.text
    msg = bot.send_message(message.chat.id, "📅 Год постройки (4 цифры):")
    bot.register_next_step_handler(msg, get_build_year)

def get_build_year(message):
    try:
        temp_data[message.from_user.id]['build_year'] = int(message.text)
        msg = bot.send_message(message.chat.id, "🔧 Состояние (черновая/чистовая/с ремонтом/евроремонт):")
        bot.register_next_step_handler(msg, get_condition)
    except:
        bot.send_message(message.chat.id, "❌ Введите 4 цифры!")
        get_build_year(message)

def get_condition(message):
    temp_data[message.from_user.id]['condition'] = message.text
    msg = bot.send_message(message.chat.id, "📝 Дополнительное описание (или отправьте '-' чтобы пропустить):")
    bot.register_next_step_handler(msg, get_description)

def get_description(message):
    desc = message.text
    if desc == "-":
        desc = ""
    temp_data[message.from_user.id]['description'] = desc
    
    msg = bot.send_message(message.chat.id, "🖼️ Отправьте ФОТО квартиры (можно несколько, по одному за раз). Когда закончите, отправьте слово 'готово':")
    bot.register_next_step_handler(msg, get_photos)

def get_photos(message):
    if message.text and message.text.lower() == 'готово':
        # Сохраняем квартиру
        save_flat(message)
        return
    
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Отправьте ФОТО (не файл) или напишите 'готово'")
        msg = bot.send_message(message.chat.id, "🖼️ Отправьте фото или 'готово':")
        bot.register_next_step_handler(msg, get_photos)
        return
    
    photo_id = message.photo[-1].file_id
    temp_data[message.from_user.id]['photos'].append(photo_id)
    
    bot.send_message(message.chat.id, f"✅ Фото {len(temp_data[message.from_user.id]['photos'])} добавлено! Отправьте ещё или напишите 'готово'")
    msg = bot.send_message(message.chat.id, "📸 Следующее фото или 'готово':")
    bot.register_next_step_handler(msg, get_photos)

def save_flat(message):
    user_id = message.from_user.id
    data = temp_data[user_id]
    
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    c.execute("""INSERT INTO flats (address, price, rooms, floor, area, house_type, build_year, condition, description, status) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'free')""",
              (data['address'], data['price'], data['rooms'], data['floor'], 
               data['area'], data['house_type'], data['build_year'], 
               data['condition'], data['description']))
    
    flat_id = c.lastrowid
    
    # Сохраняем фото
    for photo in data['photos']:
        c.execute("INSERT INTO photos (flat_id, photo_id) VALUES (?, ?)", (flat_id, photo))
    
    conn.commit()
    conn.close()
    
    bot.send_message(user_id, f"✅ Квартира добавлена!\n{data['address']}\n💰 {data['price']} руб.\n📸 Фото: {len(data['photos'])} шт.")
    
    # Рассылаем уведомления
    notify_users(data['price'], data['rooms'], flat_id)
    
    del temp_data[user_id]

def notify_users(price, rooms, flat_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # Получаем фото
    c.execute("SELECT photo_id FROM photos WHERE flat_id=? LIMIT 1", (flat_id,))
    photo = c.fetchone()
    
    # Получаем данные квартиры
    c.execute("SELECT address, floor, area, house_type, condition FROM flats WHERE id=?", (flat_id,))
    flat = c.fetchone()
    
    # Ищем подходящих клиентов
    c.execute("SELECT DISTINCT user_id FROM requests WHERE is_active=1 AND max_price>=? AND min_rooms=?", (price, rooms))
    users = c.fetchall()
    conn.close()
    
    text = f"🏠 НОВАЯ КВАРТИРА ПОД ВАШ ЗАПРОС!\n\n"
    text += f"📍 {flat[0]}\n"
    text += f"💰 {price:,} руб.\n"
    text += f"🚪 {rooms} комн.\n"
    text += f"🏢 {flat[1]} этаж\n"
    text += f"📐 {flat[2]} м²\n"
    text += f"🏗️ {flat[3]}\n"
    text += f"🔧 {flat[4]}"
    
    for user in users:
        try:
            if photo:
                bot.send_photo(user[0], photo[0], caption=text)
            else:
                bot.send_message(user[0], text)
        except:
            pass

@bot.message_handler(commands=['list_flats'])
def list_flats_admin(message):
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

@bot.message_handler(commands=['help_admin'])
def help_admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, 
                     "👑 АДМИН-КОМАНДЫ:\n\n"
                     "/add_flat - добавить квартиру\n"
                     "/list_flats - список всех квартир\n"
                     "/stats - статистика\n"
                     "/help_admin - это меню")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    bot.remove_webhook()
    bot.infinity_polling()
