import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime, time
import pytz
import os
import re
import hashlib

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "8975782591:AAGPaUt9ciaI0Mp2tiG_Zq0ioPfzs_5_VHw"

# ID владельца для администрирования
OWNER_ID = "7899158641"

# ID канала (устанавливается через /set_channel)
CHANNEL_ID = None

# Часовой пояс Москва
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Путь к логотипу
LOGO_PATH = "logo.png"

# --- СООТВЕТСТВИЕ КАТЕГОРИЙ И ФАЙЛОВ (ваши оригинальные имена) ---
CATEGORY_FILES = {
    "11 / 12 / 13 / 14": "11:12:13:14.txt",
    "15 / 15+ / 15 Pro / 15 Pro Max": "15:15+:15pro:15promax.txt",
    "16 / 16+ / 16 Pro / 16 Pro Max": "16:16+:16pro:16promax.txt",
    "17 / iPhone Air": "17:iPhoneAir.txt",
    "17 Pro": "17Pro.txt",
    "17 Pro Max": "17ProMax.txt",
    "AI / RayBan / DJI / GoPro": "AI : RayBan : DJI : GoPro.txt",
    "AirPods / Наушники": "AirPods:Наушники.txt",
    "Apple аксессуары": "Apple аксессуары.txt",
    "Б/У телефоны": "Б:У телефоны.txt",
    "Б/У MacBook": "Б:У MacBook.txt",
    "Быт техника": "Быттехника.txt",
    "Dyson": "Dyson.txt",
    "Gaming": "Gaming.txt",
    "Honor / Huawei": "Honor : Huawei.txt",
    "iPad": "iPad.txt",
    "Красота и здоровье": "Красота и здоровье.txt",
    "MacBook / iMac": "MacBook : iMac.txt",
    "OnePlus / Pixel": "OnePlus : Pixel.txt",
    "Pitaka / Benks / Orig case": "Pitaka : benks : Orig case.txt",
    "Samsung": "Samsung.txt",
    "Texet": "texet.txt",
    "Watch": "Watch.txt",
    "Xiaomi": "Xiaomi.txt",
    "Яндекс / Акустика": "Яндекс : Акустика.txt",
}

# Специальные категории (не из файлов)
SPECIAL_CATEGORIES = ["FAQ / Гарантия", "Предзаказ"]

# Эмодзи для категорий
CATEGORY_EMOJIS = {
    "FAQ / Гарантия": "📋",
    "Красота и здоровье": "💄",
    "Быт техника": "🏠",
    "Яндекс / Акустика": "🔊",
    "Texet": "📱",
    "Gaming": "🎮",
    "Dyson": "🌀",
    "OnePlus / Pixel": "📱",
    "Samsung": "📱",
    "Xiaomi": "📱",
    "Honor / Huawei": "📱",
    "Pitaka / Benks / Orig case": "🛡",
    "Apple аксессуары": "🍎",
    "MacBook / iMac": "💻",
    "iPad": "📱",
    "Watch": "⌚️",
    "AirPods / Наушники": "🎧",
    "11 / 12 / 13 / 14": "📱",
    "15 / 15+ / 15 Pro / 15 Pro Max": "📱",
    "16 / 16+ / 16 Pro / 16 Pro Max": "📱",
    "17 / iPhone Air": "📱",
    "17 Pro": "📱",
    "17 Pro Max": "📱",
    "AI / RayBan / DJI / GoPro": "🤖",
    "Б/У телефоны": "♻️",
    "Б/У MacBook": "♻️",
    "Предзаказ": "📦",
}

# Список брендов, которые НЕ должны быть заголовками (даже без цены)
BRAND_KEYWORDS = [
    "iphone", "ipad", "samsung", "xiaomi", "honor", "huawei", 
    "oneplus", "pixel", "google", "macbook", "imac", "apple",
    "dyson", "sony", "nintendo", "microsoft", "asus", "lenovo",
    "hp", "dell", "acer", "msi", "gigabyte", "razer", "logitech"
]

def parse_price_file(file_path):
    """
    Парсит файл с ценами и возвращает структурированный словарь.
    Возвращает: {
        "items": {"Название товара": "Цена", ...},
        "headers": ["Заголовок 1", "Заголовок 2", ...],
        "item_to_header": {"Название товара": "Заголовок", ...}
    }
    """
    result = {
        "items": {},
        "headers": [],
        "item_to_header": {}
    }
    
    if not os.path.exists(file_path):
        logger.warning(f"Файл {file_path} не найден")
        return result
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        current_header = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Пропускаем служебные строки-разделители
            if line.startswith('⎯') or line.startswith('_') or line.startswith('*') or line.startswith('__') or line.startswith('____') or line