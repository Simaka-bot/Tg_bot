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
            if line.startswith('⎯') or line.startswith('_') or line.startswith('*') or line.startswith('__') or line.startswith('____') or line.startswith('---'):
                continue
            
            # === УНИВЕРСАЛЬНОЕ ПРАВИЛО ===
            # Если в строке есть цена (цифры и/или знак валюты) — это товар.
            # Если в строке НЕТ цены и она НЕ начинается с флага страны без цифр — это заголовок.
            
            has_price = False
            # Проверяем наличие цены (цифры или символы ₽р$€)
            if re.search(r'\d+', line) or re.search(r'[₽р$€]', line):
                has_price = True
            
            is_header = False
            if not has_price:
                # Исключаем строки с флагами стран (они могут быть частью названия товара)
                if not line.startswith(('🇯🇵', '🇭🇰', '🇪🇺', '🇷🇺', '🇦🇪', '🇺🇸')):
                    # Дополнительная проверка: если строка содержит название бренда — это не заголовок
                    is_brand = False
                    lower_line = line.lower()
                    for brand in BRAND_KEYWORDS:
                        if brand in lower_line:
                            is_brand = True
                            break
                    
                    # Если это не бренд и не похоже на товар — это заголовок
                    if not is_brand and len(line) < 40:
                        is_header = True
            
            if is_header:
                current_header = line
                result["headers"].append(line)
                continue
            
            # === ПАРСИМ ТОВАР С ЦЕНОЙ ===
            price_match = None
            patterns = [
                r'[–—-]\s*(\d+[\s]*[₽р]?)',
                r'(\d+[\s]*[₽р]?)\s*$',
                r'(\d+[\s]*[₽р]?)\s*[–—-]',
                r'(\d+)\s*[₽р]',
                r'(\d+)\s*$',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    price_match = match
                    break
            
            if price_match:
                # Получаем цену как число
                price_str = price_match.group(1).replace(' ', '').replace('₽', '').replace('р', '')
                try:
                    price_val = int(price_str)
                except:
                    price_val = 0
                
                # === ДОБАВЛЯЕМ +2000 РУБЛЕЙ ===
                price_val += 2000
                
                # Форматируем обратно в строку с символом ₽
                price = f"{price_val} ₽"
                
                # Очищаем название товара от цены и лишних символов
                name = re.sub(price_match.group(1), '', line).strip()
                name = re.sub(r'[–—-]\s*$', '', name).strip()
                name = re.sub(r'^[•\-*\s]+', '', name).strip()
                name = re.sub(r'^[🎧🤩🎮🖥💨🤖🛡♻️📱💄🏠🔊🌀🍎💻⌚️📦📋]+\s*', '', name).strip()
                
                if name and len(name) > 2:
                    result["items"][name] = price
                    if current_header:
                        result["item_to_header"][name] = current_header
                continue
    
    except Exception as e:
        logger.error(f"Ошибка при парсинге {file_path}: {e}")
    
    return result

def load_all_prices():
    """Загружает все цены из файлов"""
    all_prices = {}
    loaded_files = []
    
    for category, filename in CATEGORY_FILES.items():
        file_path = os.path.join(os.getcwd(), filename)
        if os.path.exists(file_path):
            parsed_data = parse_price_file(file_path)
            if parsed_data["items"]:
                all_prices[category] = parsed_data
                loaded_files.append(f"{filename} ({len(parsed_data['items'])} товаров)")
                logger.info(f"Загружено {len(parsed_data['items'])} товаров из {filename}")
            else:
                logger.warning(f"В файле {filename} не найдено товаров")
        else:
            logger.warning(f"Файл {filename} не найден")
    
    print(f"\n📊 Загружено файлов: {len(all_prices)}")
    for f in loaded_files:
        print(f"   {f}")
    
    return all_prices

# Глобальная переменная для хранения цен
PRICES = {}

def get_main_keyboard():
    """Создает главное меню с категориями на основе загруженных файлов"""
    # Определяем, какие категории показывать (в строгом порядке из CATEGORY_FILES)
    active_categories = []
    
    # Сначала добавляем категории с ценами (в порядке из CATEGORY_FILES)
    for cat in CATEGORY_FILES.keys():
        if cat in PRICES:
            active_categories.append(cat)
    
    # Затем добавляем специальные категории (FAQ, Предзаказ)
    for cat in SPECIAL_CATEGORIES:
        if cat not in active_categories:
            active_categories.append(cat)
    
    # Формируем кнопки ровно в два столбца
    keyboard = []
    for i in range(0, len(active_categories), 2):
        row = []
        # Первая кнопка
        cat1 = active_categories[i]
        emoji1 = CATEGORY_EMOJIS.get(cat1, "")
        safe_cat1 = re.sub(r'[^a-zA-Z0-9_]', '_', cat1)
        row.append(InlineKeyboardButton(f"{emoji1} {cat1}", callback_data=f"cat_{safe_cat1}"))
        
        # Вторая кнопка (если есть)
        if i + 1 < len(active_categories):
            cat2 = active_categories[i + 1]
            emoji2 = CATEGORY_EMOJIS.get(cat2, "")
            safe_cat2 = re.sub(r'[^a-zA-Z0-9_]', '_', cat2)
            row.append(InlineKeyboardButton(f"{emoji2} {cat2}", callback_data=f"cat_{safe_cat2}"))
        
        keyboard.append(row)
    
    return InlineKeyboardMarkup(keyboard)

def get_price_text(category):
    """Возвращает отформатированный текст с ценами для категории (с группировкой по заголовкам)"""
    global PRICES
    
    if category not in PRICES or not PRICES[category]["items"]:
        return None
    
    data = PRICES[category]
    items = data["items"]
    item_to_header = data["item_to_header"]
    headers = data["headers"]
    
    # Сортируем товары
    sorted_items = items.items()
    
    # Группируем товары по заголовкам
    grouped_items = {}
    for item_name, price in sorted_items:
        header = item_to_header.get(item_name, None)
        if header not in grouped_items:
            grouped_items[header] = []
        grouped_items[header].append((item_name, price))
    
    # Формируем текст
    text_parts = []
    
    # 1. Сначала выводим товары без заголовка (если такие есть)
    if None in grouped_items and grouped_items[None]:
        for item_name, price in grouped_items[None]:
            text_parts.append(f"{item_name} – {price}")
        text_parts.append("")  # пустая строка для разделения
    
    # 2. Затем выводим товары, сгруппированные по заголовкам
    for header in headers:
        if header in grouped_items and grouped_items[header]:
            text_parts.append(f"\n{header}")
            for item_name, price in grouped_items[header]:
                text_parts.append(f"{item_name} – {price}")
    
    return "\n".join(text_parts)

def get_price_keyboard(category):
    """Создает клавиатуру с ценами для выбранной категории"""
    global PRICES
    
    if category not in PRICES or not PRICES[category]["items"]:
        return None
    
    items = PRICES[category]["items"]
    keyboard = []
    
    # Сортируем товары
    sorted_items = sorted(items.items())
    
    for item_name, price in sorted_items:
        # Ограничиваем длину названия
        display_name = item_name[:40] + "..." if len(item_name) > 40 else item_name
        
        # Создаем безопасный callback_data (используем хеш для длинных названий)
        safe_category = re.sub(r'[^a-zA-Z0-9_]', '_', category)
        safe_item = re.sub(r'[^a-zA-Z0-9_\-\s]', '_', item_name)
        
        # Если название слишком длинное, используем хеш
        if len(safe_item) > 30:
            safe_item = hashlib.md5(item_name.encode()).hexdigest()[:10]
        
        callback_data = f"item_{safe_category}_{safe_item}"
        
        # Проверяем длину callback_data (максимум 64 байта)
        if len(callback_data.encode()) > 64:
            # Если все еще слишком длинное, укорачиваем
            safe_item = hashlib.md5(item_name.encode()).hexdigest()[:8]
            callback_data = f"item_{safe_category}_{safe_item}"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{display_name} — {price}",
                callback_data=callback_data
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    
    return InlineKeyboardMarkup(keyboard)

async def send_morning_message(context: ContextTypes.DEFAULT_TYPE):
    if not CHANNEL_ID:
        logger.error("CHANNEL_ID не установлен!")
        return
    
    now = datetime.now(MOSCOW_TZ)
    months = {
        'January': 'января', 'February': 'февраля', 'March': 'марта',
        'April': 'апреля', 'May': 'мая', 'June': 'июня',
        'July': 'июля', 'August': 'августа', 'September': 'сентября',
        'October': 'октября', 'November': 'ноября', 'December': 'декабря'
    }
    month_name = months[now.strftime('%B')]
    date_str = f"{now.strftime('%d')} {month_name} {now.strftime('%Y')}"
    
    caption = f"""🗓 {date_str}

Добрый день! ☀️
Прайс выше обновлен ⤴️

Отличных продаж и ждём заказов! 🎁

Ваш ТехноДруг всегда на связи! 🤖"""

    try:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=InputFile(photo),
                    caption=caption
                )
            logger.info(f"Утреннее сообщение отправлено")
        else:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption
            )
    except Exception as e:
        logger.error(f"Ошибка: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PRICES
    PRICES = load_all_prices()
    
    user = update.effective_user
    chat_type = update.message.chat.type
    
    # Если команда вызвана в группе — отправляем ссылку на ЛС
    if chat_type != "private":
        await update.message.reply_text(
            "📦 *Для просмотра прайс-листа и заказа напишите мне в личные сообщения:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✉️ Перейти в ЛС", url=f"https://t.me/{context.bot.username}")]
            ])
        )
        return

    # Если в личных сообщениях — показываем полное меню
    welcome_text = f"""👋 Привет, {user.first_name}!

🏪 Добро пожаловать в магазин!
📱 Актуальный прайс-лист на технику.

Выберите категорию товара ниже:

Ваш ТехноДруг всегда на связи! 🤖"""

    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, 'rb') as photo:
            await update.message.reply_photo(
                photo=InputFile(photo),
                caption=welcome_text,
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
    else:
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PRICES
    query = update.callback_query
    await query.answer()
    data = query.data

    # --- УНИВЕРСАЛЬНАЯ ФУНКЦИЯ БЕЗОПАСНОГО ОТВЕТА ---
    async def safe_reply(text, markup=None, parse_mode="Markdown"):
        if query.message.text:
            await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=markup)
        else:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=markup
            )

    if data == "back":
        welcome_text = """📱 *Главное меню*

Выберите категорию товара:

Ваш ТехноДруг всегда на связи! 🤖"""
        await safe_reply(welcome_text, get_main_keyboard())
        return

    if data.startswith("cat_"):
        # Восстанавливаем оригинальное название категории из безопасного
        safe_cat = data[4:]
        category = None
        
        # Ищем оригинальное название среди всех категорий
        for cat in list(PRICES.keys()) + SPECIAL_CATEGORIES:
            if re.sub(r'[^a-zA-Z0-9_]', '_', cat) == safe_cat:
                category = cat
                break
        
        if not category:
            await safe_reply("❌ Категория не найдена. Попробуйте снова.", get_main_keyboard())
            return
        
        if category == "FAQ / Гарантия":
            faq_text = ""
            if os.path.exists("FAQ : Гарантия.txt"):
                with open("FAQ : Гарантия.txt", 'r', encoding='utf-8') as f:
                    faq_text = f.read()
            else:
                faq_text = "❗️ Информация временно недоступна."
            
            await safe_reply(
                f"📋 *FAQ / Гарантия*\n\n{faq_text}\n\nВаш ТехноДруг всегда на связи! 🤖",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])
            )
            return
        
        if category == "Предзаказ":
            # Загружаем текст из файла Предзаказ.txt
            preorder_text = ""
            if os.path.exists("Предзаказ.txt"):
                with open("Предзаказ.txt", 'r', encoding='utf-8') as f:
                    preorder_text = f.read()
            else:
                preorder_text = "❗️ Информация о предзаказе временно недоступна."
            
            # Отключаем парсинг Markdown для безопасности
            await safe_reply(
                f"📦 *Предзаказ*\n\n{preorder_text}",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]]),
                parse_mode=None
            )
            return
        
        # Показываем список товаров с ценами (с группировкой по заголовкам)
        price_text = get_price_text(category)
        if price_text:
            emoji = CATEGORY_EMOJIS.get(category, "📱")
            # Ограничиваем длину сообщения (Telegram имеет лимит 4096 символов)
            if len(price_text) > 4000:
                price_text = price_text[:4000] + "\n\n⚠️ Показана часть списка..."
            
            await safe_reply(
                f"{emoji} *{category}*\n\n{price_text}",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])
            )
        else:
            emoji = CATEGORY_EMOJIS.get(category, "📱")
            await safe_reply(
                f"{emoji} *{category}*\n\n📌 Информация скоро появится.\nСледите за обновлениями!\n\nВаш ТехноДруг всегда на связи! 🤖",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])
            )
        return

    if data.startswith("item_"):
        try:
            # Парсим callback_data
            parts = data[5:].split("_", 1)
            if len(parts) != 2:
                await safe_reply("❌ Ошибка формата данных.", get_main_keyboard())
                return
            
            safe_category, safe_item = parts
            
            # Восстанавливаем оригинальные названия
            category = None
            item_name = None
            
            # Ищем категорию
            for cat in PRICES.keys():
                if re.sub(r'[^a-zA-Z0-9_]', '_', cat) == safe_category:
                    category = cat
                    break
            
            if not category:
                await safe_reply("❌ Категория не найдена.", get_main_keyboard())
                return
            
            # Ищем товар по безопасному имени или хешу
            for name in PRICES[category]["items"].keys():
                safe_name = re.sub(r'[^a-zA-Z0-9_\-\s]', '_', name)
                if len(safe_name) > 30:
                    safe_name = hashlib.md5(name.encode()).hexdigest()[:10]
                
                if safe_name == safe_item:
                    item_name = name
                    break
            
            if not item_name:
                await safe_reply("❌ Товар не найден.", get_main_keyboard())
                return
            
            price = PRICES[category]["items"][item_name]
            
            emoji = CATEGORY_EMOJIS.get(category, "📱")
            await safe_reply(
                f"{emoji} *{category}*\n└ *{item_name}*\n\n💰 Цена: *{price}*\n\n📦 Для заказа обратитесь к менеджерам:",
                InlineKeyboardMarkup([
                    [InlineKeyboardButton("👤 Менеджер Максим", url="https://t.me/Sergeevich0699")],
                    [InlineKeyboardButton("👤 Менеджер Марсель", url="https://t.me/marsel_zay")],
                    [InlineKeyboardButton("🔙 К списку", callback_data=f"cat_{safe_category}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back")]
                ])
            )
            return
            
        except Exception as e:
            logger.error(f"Ошибка в item_handler: {e}")
            await safe_reply("❌ Произошла ошибка. Попробуйте снова.", get_main_keyboard())
            return

    await safe_reply("❌ Произошла ошибка. Попробуйте снова.", get_main_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Помощь*\n\n"
        "Используйте кнопки для навигации по прайс-листу.\n"
        "Выберите категорию, затем товар для просмотра цены.\n\n"
        "📞 По вопросам заказа обращайтесь к менеджерам.",
        parse_mode="Markdown"
    )

async def post_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    if not CHANNEL_ID:
        await update.message.reply_text(
            "❌ ID канала не задан!\nНапишите /set_channel -1001234567890"
        )
        return
    
    try:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=InputFile(photo),
                    caption="📱 *Актуальный прайс-лист*\n\nВыберите категорию:\n\nВаш ТехноДруг всегда на связи! 🤖",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard()
                )
        else:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text="📱 *Актуальный прайс-лист*\n\nВыберите категорию:\n\nВаш ТехноДруг всегда на связи! 🤖",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        await update.message.reply_text("✅ Прайс-лист опубликован!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    try:
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ Укажите ID канала\nПример: /set_channel -1001234567890"
            )
            return
        
        global CHANNEL_ID
        CHANNEL_ID = int(args[0])
        await update.message.reply_text(f"✅ ID канала установлен: {CHANNEL_ID}")
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")

async def test_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    await send_morning_message(context)
    await update.message.reply_text("✅ Тестовое сообщение отправлено!")

async def reload_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    global PRICES
    PRICES = load_all_prices()
    count = sum(len(data["items"]) for data in PRICES.values())
    await update.message.reply_text(
        f"✅ Прайс-лист перезагружен!\n📊 Загружено категорий: {len(PRICES)}\n📦 Всего товаров: {count}"
    )

def main():
    global PRICES
    PRICES = load_all_prices()
    
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("post", post_price))
    application.add_handler(CommandHandler("set_channel", set_channel))
    application.add_handler(CommandHandler("test_morning", test_morning))
    application.add_handler(CommandHandler("reload", reload_prices))
    application.add_handler(CallbackQueryHandler(button_handler))

    job_queue = application.job_queue
    if job_queue:
        morning_time = time(hour=10, minute=5, tzinfo=MOSCOW_TZ)
        job_queue.run_daily(
            send_morning_message,
            time=morning_time,
            name="morning_message"
        )
        logger.info("⏰ Запланирована ежедневная отправка в 10:05")

    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН")
    print("=" * 50)
    print(f"🖼 Логотип: {LOGO_PATH} {'✅' if os.path.exists(LOGO_PATH) else '❌'}")
    print(f"📊 Загружено категорий: {len(PRICES)}")
    print(f"📦 Всего товаров: {sum(len(data['items']) for data in PRICES.values())}")
    print("=" * 50)
    print("\n⏰ Автоматическая рассылка: каждый день в 10:05 по Москве")
    print("\n📌 Доступные команды для админа:")
    print("  /set_channel - Установить ID канала")
    print("  /post - Опубликовать прайс-лист")
    print("  /reload - Перезагрузить прайс-лист")
    print("  /test_morning - Тестовая рассылка")

    # Добавляем таймаут для запросов
    application.run_polling(timeout=30)

if __name__ == "__main__":
    main()
