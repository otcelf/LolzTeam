import os
import sqlite3
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# База данных
DATABASE = 'bot_database.db'

def get_db():
    """Подключение к базе данных"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_bot_db():
    """Инициализация базы данных для бота"""
    db = get_db()
    cursor = db.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT DEFAULT 'ru',
            premium_status INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            total_deals INTEGER DEFAULT 0,
            successful_deals INTEGER DEFAULT 0,
            cancelled_deals INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0,
            total_volume REAL DEFAULT 0.0,
            balance_rub REAL DEFAULT 0.0,
            balance_usd REAL DEFAULT 0.0,
            balance_ton REAL DEFAULT 0.0,
            balance_stars INTEGER DEFAULT 0,
            referrals_count INTEGER DEFAULT 0,
            referrals_earned REAL DEFAULT 0.0,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked INTEGER DEFAULT 0,
            block_reason TEXT
        )
    ''')
    
    # Таблица сделок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            deal_id TEXT PRIMARY KEY,
            seller_id INTEGER,
            buyer_id INTEGER,
            product_type TEXT,
            product_description TEXT,
            amount REAL,
            currency TEXT,
            status TEXT DEFAULT 'created',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP,
            completed_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            cancel_reason TEXT,
            FOREIGN KEY (seller_id) REFERENCES users(user_id),
            FOREIGN KEY (buyer_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            currency TEXT,
            status TEXT DEFAULT 'pending',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица отзывов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id),
            FOREIGN KEY (from_user_id) REFERENCES users(user_id),
            FOREIGN KEY (to_user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица обращений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appeals (
            appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            subject TEXT,
            message TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            admin_response TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица верификаций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verifications (
            verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            status TEXT DEFAULT 'pending',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            admin_comment TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица логов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица реквизитов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requisites (
            user_id INTEGER,
            currency TEXT,
            requisite TEXT,
            PRIMARY KEY (user_id, currency),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    db.commit()
    db.close()

def save_or_update_user(user_id, username=None, first_name=None, last_name=None):
    """Сохраняет или обновляет пользователя в БД"""
    db = get_db()
    cursor = db.cursor()
    
    # Проверяем, существует ли пользователь
    existing = cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,)).fetchone()
    
    if existing:
        # Обновляем last_activity
        cursor.execute('''
            UPDATE users 
            SET last_activity = CURRENT_TIMESTAMP,
                username = COALESCE(?, username),
                first_name = COALESCE(?, first_name),
                last_name = COALESCE(?, last_name)
            WHERE user_id = ?
        ''', (username, first_name, last_name, user_id))
    else:
        # Создаем нового пользователя
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
    
    db.commit()
    db.close()

def get_user_data(user_id):
    """Получает данные пользователя из БД"""
    db = get_db()
    cursor = db.cursor()
    user = cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    db.close()
    return dict(user) if user else None

def create_deal_in_db(deal_id, seller_id, product_type, product_description, amount, currency):
    """Создает сделку в БД"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        INSERT INTO deals (deal_id, seller_id, product_type, product_description, amount, currency, status)
        VALUES (?, ?, ?, ?, ?, ?, 'created')
    ''', (deal_id, seller_id, product_type, product_description, amount, currency))
    
    db.commit()
    db.close()

def update_deal_status(deal_id, status, buyer_id=None):
    """Обновляет статус сделки"""
    db = get_db()
    cursor = db.cursor()
    
    if status == 'paid':
        cursor.execute('''
            UPDATE deals 
            SET status = ?, buyer_id = ?, paid_at = CURRENT_TIMESTAMP
            WHERE deal_id = ?
        ''', (status, buyer_id, deal_id))
    elif status == 'completed':
        cursor.execute('''
            UPDATE deals 
            SET status = ?, completed_at = CURRENT_TIMESTAMP
            WHERE deal_id = ?
        ''', (status, deal_id))
    elif status == 'cancelled':
        cursor.execute('''
            UPDATE deals 
            SET status = ?, cancelled_at = CURRENT_TIMESTAMP
            WHERE deal_id = ?
        ''', (status, deal_id))
    else:
        cursor.execute('UPDATE deals SET status = ? WHERE deal_id = ?', (status, deal_id))
    
    db.commit()
    db.close()

def save_requisite(user_id, currency, requisite):
    """Сохраняет реквизиты пользователя"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO requisites (user_id, currency, requisite)
        VALUES (?, ?, ?)
    ''', (user_id, currency, requisite))
    
    db.commit()
    db.close()

def get_requisites(user_id):
    """Получает реквизиты пользователя"""
    db = get_db()
    cursor = db.cursor()
    
    rows = cursor.execute('SELECT currency, requisite FROM requisites WHERE user_id = ?', (user_id,)).fetchall()
    db.close()
    
    return {row['currency']: row['requisite'] for row in rows}

def create_verification_request(user_id):
    """Создает заявку на верификацию"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        INSERT INTO verifications (user_id, status)
        VALUES (?, 'pending')
    ''', (user_id,))
    
    db.commit()
    db.close()

def create_appeal(user_id, appeal_type, subject, message):
    """Создает обращение"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        INSERT INTO appeals (user_id, type, subject, message, status)
        VALUES (?, ?, ?, ?, 'open')
    ''', (user_id, appeal_type, subject, message))
    
    db.commit()
    db.close()

def log_action(user_id, action, details=''):
    """Логирует действие пользователя"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        INSERT INTO logs (user_id, action, details)
        VALUES (?, ?, ?)
    ''', (user_id, action, details))
    
    db.commit()
    db.close()

# Состояния для ConversationHandler
WAITING_CARD_NUMBER, WAITING_DEAL_AMOUNT, WAITING_DEAL_DESCRIPTION = range(3)

# Путь к баннеру
BANNER_PATH = 'banner.jpg'

# ID администратора
ADMIN_ID = 8659836741

# ID приватного чата воркеров
WORKER_CHAT_ID = -1003887218129

async def is_worker(user_id, context):
    """Проверяет, является ли пользователь воркером (находится в приватном чате)"""
    try:
        member = await context.bot.get_chat_member(WORKER_CHAT_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

async def send_or_edit_with_banner(query_or_message, text, reply_markup, context=None, is_query=True):
    """Универсальная функция. Всегда отправляет/показывает баннер."""
    banner_exists = os.path.exists(BANNER_PATH)

    if is_query:
        message = query_or_message.message
        if banner_exists:
            if message.photo:
                # Уже фото — меняем только caption
                try:
                    await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode='HTML')
                    return
                except Exception:
                    pass
            # Нет фото — удаляем старое сообщение и отправляем новое с баннером
            try:
                await message.delete()
            except Exception:
                pass
            with open(BANNER_PATH, 'rb') as photo:
                await message.chat.send_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            # Баннера нет — просто редактируем текст
            try:
                await query_or_message.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
            except Exception:
                await message.reply_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Новое сообщение — всегда с баннером
        if banner_exists:
            with open(BANNER_PATH, 'rb') as photo:
                await query_or_message.reply_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query_or_message.reply_text(text=text, reply_markup=reply_markup, parse_mode='HTML')


async def send_with_banner(chat_id, text, reply_markup, context):
    """Отправить новое сообщение с баннером через context.bot"""
    banner_exists = os.path.exists(BANNER_PATH)
    if banner_exists:
        with open(BANNER_PATH, 'rb') as photo:
            await context.bot.send_photo(chat_id=chat_id, photo=photo,
                                         caption=text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - показывает приветственное сообщение или информацию о сделке"""
    
    user = update.message.from_user
    
    # Сохраняем пользователя в БД
    save_or_update_user(user.id, user.username, user.first_name, user.last_name)
    log_action(user.id, 'start_command', f'User started bot')
    
    # Загружаем данные пользователя из БД
    user_data_db = get_user_data(user.id)
    if user_data_db:
        for key, value in user_data_db.items():
            context.user_data[key] = value
        context.user_data['requisites'] = get_requisites(user.id)
    
    # Проверяем блокировку
    if user_data_db and user_data_db.get('is_blocked'):
        await update.message.reply_text(
            f"🚫 Ваш аккаунт заблокирован.\n\n"
            f"Причина: {user_data_db.get('block_reason', 'Нарушение правил')}\n\n"
            f"Для разблокировки обратитесь в поддержку: @LoIzTeamSupport"
        )
        return
    
    # Проверяем, является ли пользователь воркером
    is_user_worker = await is_worker(user.id, context)
    
    # Если пользователь воркер - автоматически выдаем премиум
    if is_user_worker:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('UPDATE users SET premium_status = 1, verified = 1 WHERE user_id = ?', (user.id,))
        db.commit()
        db.close()
        context.user_data['premium_status'] = 1
        context.user_data['verified'] = 1
    
    # Deep link обработка
    if context.args and len(context.args) > 0:
        deal_id = context.args[0]
        if deal_id.startswith('deal_'):
            await show_deal_info_for_buyer(update, context, deal_id)
            return
        elif deal_id.startswith('ref_'):
            referrer_id = deal_id.replace('ref_', '')
            context.user_data['referrer'] = referrer_id

    # Если язык уже выбран — сразу главное меню
    if context.user_data.get('language') and context.user_data['language'] != 'ru' or \
       context.user_data.get('selected_language'):
        # Язык уже выбирался — показываем меню сразу
        welcome_text = (
            "<b>👋 Добро пожаловать в Lolz Market — надежный P2P-гарант</b>\n\n"
            "<b>💼 Покупайте и продавайте безопасно: от Telegram-подарков и NFT до токенов и фиата.</b>\n\n"
            "<b>✨ Что внутри:</b>\n"
            "<b>• Удобное управление реквизитами</b>\n"
            "<b>• Быстрое создание сделок</b>\n"
            "<b>• Понятный контроль этапов сделки</b>\n\n"
            "<b>💡 Совет:</b> <i>Никогда не переводите средства без подтверждения в боте!</i>\n\n"
            "<b>📚 Как пользоваться?</b>\n"
            "<b>Ознакомьтесь с инструкцией, открыв сайт через левую нижнюю кнопку</b>\n\n"
            "<b>💬 Поддержка: @LoIzTeamSupport</b>"
        )
        keyboard = [
            [InlineKeyboardButton("✨ Создать сделку", callback_data='create_deal')],
            [
                InlineKeyboardButton("📋 Мои сделки", callback_data='my_deals'),
                InlineKeyboardButton("🔐 Верификация", callback_data='verification')
            ],
            [
                InlineKeyboardButton("💳 Реквизиты", callback_data='requisites'),
                InlineKeyboardButton("🌐 Язык", callback_data='change_language')
            ]
        ]
        
        # Добавляем воркер меню если пользователь воркер
        if is_user_worker:
            keyboard.append([InlineKeyboardButton("⚡ Воркер меню", callback_data='worker_menu')])
        
        keyboard.extend([
            [InlineKeyboardButton("📨 Обращения", callback_data='appeals')],
            [InlineKeyboardButton("🎯 Поддержка", callback_data='support')],
            [InlineKeyboardButton("📱 Мини-приложения", callback_data='mini_apps')]
        ])
        
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data='admin_panel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        if os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=welcome_text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
        return

    # Первый запуск — приветствие и выбор языка
    welcome_text = (
        "⭐ Добро пожаловать в Lolz Team ⭐\n\n"
        "🔐 Бот для безопасных сделок.\n\n"
        "🛡️ Защита от мошенников, удобное управление и "
        "сопровождение сделок в одном месте."
    )
    
    keyboard = [
        [InlineKeyboardButton("➡️ Продолжить", callback_data='continue')]
    ]
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data='admin_panel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем баннер с сообщением
    if os.path.exists(BANNER_PATH):
        with open(BANNER_PATH, 'rb') as photo:
            message = await update.message.reply_photo(
                photo=photo,
                caption=welcome_text,
                reply_markup=reply_markup
            )
            # Сохраняем ID сообщения для последующего редактирования
            context.user_data['last_message_id'] = message.message_id
    else:
        message = await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup
        )
        context.user_data['last_message_id'] = message.message_id

async def freeteam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /freeteam - создает идеальный профиль для демонстрации"""
    
    user_id = update.message.from_user.id
    
    # Обновляем данные в БД
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        UPDATE users SET
            premium_status = 1,
            verified = 1,
            total_deals = 523,
            successful_deals = 523,
            cancelled_deals = 0,
            rating = 5.0,
            total_volume = 2847500.00,
            referrals_count = 47,
            referrals_earned = 15680.00,
            balance_rub = 125000.00,
            balance_usd = 1500.00,
            balance_ton = 250.00,
            balance_stars = 5000
        WHERE user_id = ?
    ''', (user_id,))
    
    # Добавляем реквизиты
    for currency, requisite in [
        ('rub', '2202200012345678'),
        ('usd', '4276380012345678'),
        ('ton', 'UQD...xyz123'),
        ('any', 'Любые реквизиты доступны')
    ]:
        cursor.execute('''
            INSERT OR REPLACE INTO requisites (user_id, currency, requisite)
            VALUES (?, ?, ?)
        ''', (user_id, currency, requisite))
    
    db.commit()
    db.close()
    
    # Логируем действие
    log_action(user_id, 'freeteam_activated', 'Activated ideal profile')
    
    # Загружаем обновленные данные в context
    user_data_db = get_user_data(user_id)
    if user_data_db:
        for key, value in user_data_db.items():
            context.user_data[key] = value
        context.user_data['requisites'] = get_requisites(user_id)
    
    await update.message.reply_text(
        "✅ Идеальный профиль активирован!\n\n"
        "🌟 Ваш новый статус:\n"
        "• ⭐ Рейтинг: 5.0/5.0\n"
        "• 📊 Сделок: 523 (все успешные)\n"
        "• 💎 Премиум статус: Активен\n"
        "• 🛡 Верификация: Подтверждена\n"
        "• 💰 Общий оборот: 2,847,500 ₽\n"
        "• 🏆 Место в топе: #3\n"
        "• 🔗 Рефералов: 47\n"
        "• ⏱ Время ответа: 2 минуты\n\n"
        "Теперь вы можете протестировать все функции бота с идеальным профилем!"
    )
    
    # Показываем главное меню
    keyboard = [
        [InlineKeyboardButton("📝 Создать сделку", callback_data='create_deal')],
        [
            InlineKeyboardButton("📋 Мои сделки", callback_data='my_deals'),
            InlineKeyboardButton("🔐 Верификация", callback_data='verification')
        ],
        [
            InlineKeyboardButton("💼 Реквизиты", callback_data='requisites'),
            InlineKeyboardButton("🌐 Язык", callback_data='change_language')
        ],
        [
            InlineKeyboardButton("🔗 Рефералы", callback_data='referrals'),
            InlineKeyboardButton("ℹ️ Подробнее", callback_data='more_info')
        ],
        [InlineKeyboardButton("📨 Обращения", callback_data='appeals')],
        [InlineKeyboardButton("📞 Поддержка", callback_data='support')],
        [InlineKeyboardButton("📱 Мини-приложения", callback_data='mini_apps')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=reply_markup
    )

async def show_deal_info_for_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE, deal_id: str):
    """Показывает информацию о сделке для покупателя"""
    
    clean_id = deal_id.replace('deal_', '')
    buyer_id = update.message.from_user.id
    
    # Читаем сделку из БД
    db = get_db()
    deal = db.execute('''
        SELECT d.*, u.username as seller_username, u.total_deals, u.rating, u.verified
        FROM deals d
        LEFT JOIN users u ON d.seller_id = u.user_id
        WHERE d.deal_id = ?
    ''', (clean_id,)).fetchone()
    db.close()
    
    if not deal:
        await update.message.reply_text(
            "❌ Сделка не найдена или была отменена.\n\n"
            "Проверьте ссылку и попробуйте снова."
        )
        return
    
    if deal['status'] not in ('created',):
        status_map = {
            'paid': 'уже оплачена',
            'completed': 'уже завершена',
            'cancelled': 'отменена'
        }
        await update.message.reply_text(
            f"❌ Сделка {status_map.get(deal['status'], 'недоступна')}."
        )
        return
    
    seller_name = f"@{deal['seller_username']}" if deal['seller_username'] else f"ID:{deal['seller_id']}"
    verified_str = "🟢 Верифицирован" if deal['verified'] else "🔴 Новый пользователь"
    
    text = (
        f"💳 Информация о сделке #{clean_id}\n\n"
        f"🔴 Вы покупатель в сделке.\n"
        f"📌 Продавец: {seller_name}\n"
        f"🎭 Успешных сделок у продавца: {deal['total_deals'] or 0}\n"
        f"⭐ Рейтинг продавца: {deal['rating'] or 0:.1f}/5\n"
        f"🛡 Верификация: {verified_str}\n\n"
        f"• Вы покупаете: [{deal['product_type']}] {deal['product_description']}\n\n"
        f"💳 Адрес для оплаты:\n"
        f"Сбер 79278171305 Мария\n\n"
        f"💰 Сумма к оплате: {deal['amount']} {deal['currency']}\n"
        f"💬 Комментарий к платежу (мемо): #{clean_id}\n\n"
        f"⚠️ Пожалуйста, убедитесь в правильности данных перед "
        f"оплатой. Комментарий (мемо) обязателен!\n\n"
        f"В случае если вы отправили транзакцию без комментария "
        f"заполните форму — @LoIzTeamSupport"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f'paid_deal_{clean_id}')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['current_deal'] = clean_id
    context.user_data['deal_role'] = 'buyer'
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'continue':
        await show_language_menu(query, context)
    elif query.data.startswith('lang_') and query.data != 'lang_continue':
        language = query.data.replace('lang_', '')
        await handle_language_selection(query, context, language)
    elif query.data == 'lang_continue':
        await show_main_menu(query, context)
    elif query.data == 'create_deal':
        await show_product_type_menu(query, context)
    elif query.data == 'back_to_main':
        await show_main_menu(query, context)
    elif query.data.startswith('product_'):
        product_type = query.data.replace('product_', '')
        await show_currency_menu(query, context, product_type)
    elif query.data.startswith('currency_'):
        currency = query.data.replace('currency_', '')
        await handle_currency_selection(query, context, currency)
    elif query.data == 'requisites':
        await show_requisites_menu(query, context)
    elif query.data == 'change_rub_card':
        await ask_for_card_number(query, context, 'rub')
    elif query.data == 'change_usd_card':
        await ask_for_card_number(query, context, 'usd')
    elif query.data == 'change_ton':
        await ask_for_card_number(query, context, 'ton')
    elif query.data == 'change_any_currency':
        await ask_for_card_number(query, context, 'any')
    elif query.data == 'back_to_currency':
        product_type = context.user_data.get('product_type', 'nft_gift')
        await show_currency_menu(query, context, product_type)
    elif query.data == 'cancel_deal':
        await show_main_menu(query, context)
    elif query.data.startswith('cancel_deal_'):
        deal_id = query.data.replace('cancel_deal_', '')
        update_deal_status(deal_id, 'cancelled')
        log_action(query.from_user.id, 'deal_cancelled', f'deal_id={deal_id}')
        await send_or_edit_with_banner(query, f"❌ Сделка {deal_id} отменена.", None, context, is_query=True)
        await show_main_menu(query, context)
    elif query.data.startswith('paid_'):
        # Покупатель нажал "Я оплатил"
        deal_id = query.data.replace('paid_', '')
        await handle_payment_confirmation(query, context, deal_id)
    elif query.data == 'appeals':
        await show_appeals_menu(query, context)
    elif query.data == 'verification':
        await show_verification_menu(query, context)
    elif query.data == 'submit_verification':
        await handle_verification_submission(query, context)
    elif query.data == 'appeal_suggest':
        context.user_data['appeal_type'] = 'suggest'
        context.user_data['deal_state'] = 'waiting_appeal_text'
        await send_or_edit_with_banner(query, "💡 Напишите ваше предложение или идею:\n\nМы рассмотрим его в течение 24 часов.", None, context, is_query=True)
    elif query.data == 'appeal_complain':
        context.user_data['appeal_type'] = 'complain'
        context.user_data['deal_state'] = 'waiting_appeal_text'
        await send_or_edit_with_banner(query, "⚠️ Опишите вашу жалобу или проблему:\n\nМы рассмотрим её в течение 24 часов.", None, context, is_query=True)
    elif query.data == 'my_deals':
        await show_my_deals(query, context)
    elif query.data == 'change_language':
        await show_language_menu(query, context)
    elif query.data == 'referrals':
        await show_referrals(query, context)
    elif query.data == 'more_info':
        await show_more_info(query, context)
    elif query.data == 'worker_menu':
        await show_worker_menu(query, context)
    elif query.data == 'worker_add_money':
        context.user_data['worker_state'] = 'add_money'
        await worker_edit(query, "💰 Введите ID пользователя или @username для начисления денег:", [])
    elif query.data == 'worker_set_stars':
        context.user_data['worker_state'] = 'set_stars'
        await worker_edit(query, "⭐ Выберите количество звезд для себя:", [
            [InlineKeyboardButton("⭐", callback_data='worker_stars_1')],
            [InlineKeyboardButton("⭐⭐", callback_data='worker_stars_2')],
            [InlineKeyboardButton("⭐⭐⭐", callback_data='worker_stars_3')],
            [InlineKeyboardButton("⭐⭐⭐⭐", callback_data='worker_stars_4')],
            [InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data='worker_stars_5')],
            [InlineKeyboardButton("🔙 Назад", callback_data='worker_menu')]
        ])
    elif query.data == 'worker_set_money':
        context.user_data['worker_state'] = 'set_money'
        await worker_edit(query, "💵 Введите сумму для начисления себе:", [])
    elif query.data == 'worker_set_date':
        context.user_data['worker_state'] = 'set_date'
        await worker_edit(query, "📅 Введите дату регистрации в формате ДД.ММ.ГГГГ (например: 15.03.2023):", [])
    elif query.data.startswith('worker_stars_'):
        stars = int(query.data.replace('worker_stars_', ''))
        await handle_worker_set_stars(query, context, stars)
    elif query.data == 'support':
        await show_support(query, context)
    elif query.data == 'mini_apps':
        await show_mini_apps(query, context)
    elif query.data == 'top_up_balance':
        await show_top_up_balance(query, context)
    elif query.data == 'withdraw_funds':
        await show_withdraw_funds(query, context)
    elif query.data.startswith('topup_'):
        currency = query.data.replace('topup_', '')
        await handle_topup_currency(query, context, currency)
    elif query.data.startswith('withdraw_'):
        currency = query.data.replace('withdraw_', '')
        await handle_withdraw_currency(query, context, currency)
    elif query.data == 'faq':
        await show_faq(query, context)
    elif query.data == 'rules':
        await show_rules(query, context)
    elif query.data == 'ref_history':
        await show_ref_history(query, context)
    elif query.data == 'app_stats':
        await show_app_stats(query, context)
    elif query.data == 'app_calc':
        await show_app_calculator(query, context)
    elif query.data == 'app_check':
        await show_app_check(query, context)
    elif query.data == 'topup_confirmed':
        await handle_topup_confirmed(query, context)
    elif query.data == 'accept_rules':
        await query.answer("✅ Спасибо! Вы приняли правила сервиса.", show_alert=True)
        await show_main_menu(query, context)
    elif query.data == 'premium_active':
        await query.answer("💎 У вас уже активирован премиум-статус!", show_alert=True)
    # ── ADMIN PANEL ──────────────────────────────────────────────────────────
    elif query.data == 'admin_panel':
        if query.from_user.id == ADMIN_ID:
            await show_admin_panel(query, context)
    elif query.data == 'admin_stats':
        if query.from_user.id == ADMIN_ID:
            await admin_stats(query, context)
    elif query.data == 'admin_users':
        if query.from_user.id == ADMIN_ID:
            await admin_users_list(query, context)
    elif query.data == 'admin_deals':
        if query.from_user.id == ADMIN_ID:
            await admin_deals_list(query, context)
    elif query.data == 'admin_appeals':
        if query.from_user.id == ADMIN_ID:
            await admin_appeals_list(query, context)
    elif query.data == 'admin_verifications':
        if query.from_user.id == ADMIN_ID:
            await admin_verifications_list(query, context)
    elif query.data == 'admin_broadcast':
        if query.from_user.id == ADMIN_ID:
            await admin_broadcast_menu(query, context)
    elif query.data == 'admin_broadcast_all':
        if query.from_user.id == ADMIN_ID:
            context.user_data['admin_state'] = 'broadcast_all'
            await admin_edit(query, "📢 Введите текст рассылки (всем пользователям):\n\nСообщение будет отправлено с баннером.", [])
    elif query.data == 'admin_broadcast_premium':
        if query.from_user.id == ADMIN_ID:
            context.user_data['admin_state'] = 'broadcast_premium'
            await admin_edit(query, "💎 Введите текст рассылки (только Premium):", [])
    elif query.data == 'admin_logs':
        if query.from_user.id == ADMIN_ID:
            await admin_logs(query, context)
    elif query.data == 'admin_users_prev':
        if query.from_user.id == ADMIN_ID:
            context.user_data['admin_users_page'] = max(0, context.user_data.get('admin_users_page', 0) - 1)
            await admin_users_list(query, context)
    elif query.data == 'admin_users_next':
        if query.from_user.id == ADMIN_ID:
            context.user_data['admin_users_page'] = context.user_data.get('admin_users_page', 0) + 1
            await admin_users_list(query, context)
    elif query.data == 'admin_deals_prev':
        if query.from_user.id == ADMIN_ID:
            context.user_data['admin_deals_page'] = max(0, context.user_data.get('admin_deals_page', 0) - 1)
            await admin_deals_list(query, context)
    elif query.data == 'admin_deals_next':
        if query.from_user.id == ADMIN_ID:
            context.user_data['admin_deals_page'] = context.user_data.get('admin_deals_page', 0) + 1
            await admin_deals_list(query, context)
    elif query.data.startswith('admin_user_'):
        if query.from_user.id == ADMIN_ID:
            uid = int(query.data.replace('admin_user_', ''))
            await admin_user_info(query, context, uid)
    elif query.data.startswith('admin_block_'):
        if query.from_user.id == ADMIN_ID:
            uid = int(query.data.replace('admin_block_', ''))
            context.user_data['admin_state'] = f'block_{uid}'
            await admin_edit(query, f"🚫 Введите причину блокировки пользователя {uid}:", [])
    elif query.data.startswith('admin_unblock_'):
        if query.from_user.id == ADMIN_ID:
            uid = int(query.data.replace('admin_unblock_', ''))
            db = get_db()
            db.execute('UPDATE users SET is_blocked=0, block_reason=NULL WHERE user_id=?', (uid,))
            db.commit()
            db.close()
            await query.answer("✅ Пользователь разблокирован", show_alert=True)
            await admin_user_info(query, context, uid)
    elif query.data.startswith('admin_premium_grant_'):
        if query.from_user.id == ADMIN_ID:
            uid = int(query.data.replace('admin_premium_grant_', ''))
            db = get_db()
            db.execute('UPDATE users SET premium_status=1 WHERE user_id=?', (uid,))
            db.commit()
            db.close()
            await query.answer("✅ Premium выдан", show_alert=True)
            await admin_user_info(query, context, uid)
    elif query.data.startswith('admin_premium_revoke_'):
        if query.from_user.id == ADMIN_ID:
            uid = int(query.data.replace('admin_premium_revoke_', ''))
            db = get_db()
            db.execute('UPDATE users SET premium_status=0 WHERE user_id=?', (uid,))
            db.commit()
            db.close()
            await query.answer("✅ Premium снят", show_alert=True)
            await admin_user_info(query, context, uid)
    elif query.data.startswith('admin_balance_'):
        if query.from_user.id == ADMIN_ID:
            uid = int(query.data.replace('admin_balance_', ''))
            context.user_data['admin_state'] = f'balance_{uid}'
            await admin_edit(query,
                f"💰 Изменить баланс пользователя {uid}\n\n"
                "Введите в формате:\n"
                "+1000 rub — пополнить на 1000 руб\n"
                "-500 rub — списать 500 руб\n"
                "=5000 rub — установить 5000 руб\n\n"
                "Валюты: rub, usd, ton, stars",
                []
            )
    elif query.data.startswith('admin_msg_'):
        if query.from_user.id == ADMIN_ID:
            uid = int(query.data.replace('admin_msg_', ''))
            context.user_data['admin_state'] = f'msg_{uid}'
            await admin_edit(query, f"✉️ Введите сообщение для пользователя {uid}:\n\nОтправится с баннером.", [])
    elif query.data.startswith('admin_verify_approve_'):
        if query.from_user.id == ADMIN_ID:
            vid = int(query.data.replace('admin_verify_approve_', ''))
            db = get_db()
            v = db.execute('SELECT user_id FROM verifications WHERE verification_id=?', (vid,)).fetchone()
            if v:
                db.execute('UPDATE verifications SET status="approved", reviewed_at=CURRENT_TIMESTAMP WHERE verification_id=?', (vid,))
                db.execute('UPDATE users SET verified=1, premium_status=1 WHERE user_id=?', (v['user_id'],))
                db.commit()
                try:
                    await context.bot.send_message(v['user_id'], "✅ Ваша верификация одобрена! Вам выдан Premium статус.")
                except Exception:
                    pass
            db.close()
            await query.answer("✅ Верификация одобрена", show_alert=True)
            await admin_verifications_list(query, context)
    elif query.data.startswith('admin_verify_reject_'):
        if query.from_user.id == ADMIN_ID:
            vid = int(query.data.replace('admin_verify_reject_', ''))
            context.user_data['admin_state'] = f'verify_reject_{vid}'
            await admin_edit(query, "❌ Введите причину отклонения верификации:", [])
    elif query.data.startswith('admin_appeal_resolve_'):
        if query.from_user.id == ADMIN_ID:
            aid = int(query.data.replace('admin_appeal_resolve_', ''))
            context.user_data['admin_state'] = f'appeal_resolve_{aid}'
            await admin_edit(query, "✍️ Введите ответ на обращение:", [])
    elif query.data.startswith('admin_deal_cancel_'):
        if query.from_user.id == ADMIN_ID:
            did = query.data.replace('admin_deal_cancel_', '')
            db = get_db()
            db.execute('UPDATE deals SET status="cancelled", cancelled_at=CURRENT_TIMESTAMP, cancel_reason="Отменено администратором" WHERE deal_id=?', (did,))
            db.commit()
            db.close()
            await query.answer("✅ Сделка отменена", show_alert=True)
            await admin_deals_list(query, context)
    elif query.data.startswith('admin_deal_complete_'):
        if query.from_user.id == ADMIN_ID:
            did = query.data.replace('admin_deal_complete_', '')
            db = get_db()
            deal = db.execute('SELECT * FROM deals WHERE deal_id=?', (did,)).fetchone()
            db.execute('UPDATE deals SET status="completed", completed_at=CURRENT_TIMESTAMP WHERE deal_id=?', (did,))
            if deal and deal['seller_id']:
                db.execute('''
                    UPDATE users SET total_deals=total_deals+1,
                    successful_deals=successful_deals+1,
                    total_volume=total_volume+?
                    WHERE user_id=?
                ''', (deal['amount'], deal['seller_id']))
            db.commit()
            db.close()
            # Уведомляем покупателя
            if deal and deal['buyer_id']:
                try:
                    buyer_text = (
                        f"🎉 Сделка завершена успешно!\n\n"
                        f"🆔 ID сделки: {did}\n"
                        f"✅ Продавец передал товар\n"
                        f"💸 Деньги переведены продавцу\n"
                        f"📦 Товар передан вам\n\n"
                        f"Спасибо за использование Lolz Market!\n"
                        f"Пожалуйста, оставьте отзыв о сделке."
                    )
                    if os.path.exists(BANNER_PATH):
                        with open(BANNER_PATH, 'rb') as photo:
                            await context.bot.send_photo(chat_id=deal['buyer_id'], photo=photo, caption=buyer_text)
                    else:
                        await context.bot.send_message(chat_id=deal['buyer_id'], text=buyer_text)
                except Exception:
                    pass
            # Уведомляем продавца
            if deal and deal['seller_id']:
                try:
                    seller_text = (
                        f"🎉 Сделка завершена успешно!\n\n"
                        f"🆔 ID сделки: {did}\n"
                        f"✅ Покупатель получил товар\n"
                        f"💸 Деньги переведены на ваш баланс\n\n"
                        f"Спасибо за использование Lolz Market!"
                    )
                    if os.path.exists(BANNER_PATH):
                        with open(BANNER_PATH, 'rb') as photo:
                            await context.bot.send_photo(chat_id=deal['seller_id'], photo=photo, caption=seller_text)
                    else:
                        await context.bot.send_message(chat_id=deal['seller_id'], text=seller_text)
                except Exception:
                    pass
            await query.answer("✅ Сделка завершена, уведомления отправлены", show_alert=True)
            await admin_deals_list(query, context)

async def show_language_menu(query, context: ContextTypes.DEFAULT_TYPE, show_notification=False):
    """Показывает меню выбора языка"""
    
    # Получаем выбранный язык из контекста
    selected_lang = context.user_data.get('selected_language', None)
    
    # Формируем текст с уведомлением если язык был выбран
    if show_notification and selected_lang:
        lang_names = {
            'ru': 'русский',
            'tj': 'тоҷикӣ',
            'uz': 'o\'zbekcha',
            'cn': '中文',
            'jp': '日本語',
            'ar': 'العربية',
            'fa': 'فارسی',
            'ir': 'ایرانی',
            'de': 'deutsch',
            'en': 'english',
            'tr': 'türkçe'
        }
        text = f"✅ Язык изменен на {lang_names.get(selected_lang, 'русский')}!\n\n"
    else:
        text = ""
    
    text += (
        "Чтобы использовать бота, сначала выберите язык.\n\n"
        "Ниже доступны все языки, которые есть в боте.\n"
        "После выбора языка нажмите кнопку «Продолжить»."
    )
    
    # Создаем кнопки с языками (2 в ряд)
    keyboard = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'),
            InlineKeyboardButton("🇹🇯 Тоҷикӣ", callback_data='lang_tj')
        ],
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data='lang_uz'),
            InlineKeyboardButton("🇨🇳 中文", callback_data='lang_cn')
        ],
        [
            InlineKeyboardButton("🇯🇵 日本語", callback_data='lang_jp'),
            InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar')
        ],
        [
            InlineKeyboardButton("🇮🇷 فارسی", callback_data='lang_fa'),
            InlineKeyboardButton("🇮🇷 ایرانی", callback_data='lang_ir')
        ],
        [
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data='lang_de'),
            InlineKeyboardButton("🇺🇸 English", callback_data='lang_en')
        ],
        [
            InlineKeyboardButton("🇹🇷 Türkçe", callback_data='lang_tr')
        ],
        [
            InlineKeyboardButton("➡️ Продолжить", callback_data='lang_continue')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_language_selection(query, context: ContextTypes.DEFAULT_TYPE, language):
    """Обработка выбора конкретного языка"""
    context.user_data['selected_language'] = language
    context.user_data['language'] = language
    # Сохраняем язык в БД чтобы запомнить после перезапуска
    db = get_db()
    db.execute('UPDATE users SET language=? WHERE user_id=?', (language, query.from_user.id))
    db.commit()
    db.close()
    await show_language_menu(query, context, show_notification=True)

async def show_main_menu(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню бота"""
    text = (
        "<b>👋 Добро пожаловать в Lolz Market — надежный P2P-гарант</b>\n\n"
        "<b>💼 Покупайте и продавайте безопасно: от Telegram-подарков и NFT до токенов и фиата.</b>\n\n"
        "<b>✨ Что внутри:</b>\n"
        "<b>• Удобное управление реквизитами</b>\n"
        "<b>• Быстрое создание сделок</b>\n"
        "<b>• Понятный контроль этапов сделки</b>\n"
        "<b>• История всех операций</b>\n\n"
        "<b>💡 Совет:</b> <i>Никогда не переводите средства без подтверждения в боте!</i>\n\n"
        "<b>📚 Как пользоваться?</b>\n"
        "<b>Ознакомьтесь с инструкцией, открыв сайт через левую нижнюю кнопку</b>\n\n"
        "<b>💬 Поддержка: @LoIzTeamSupport</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("✨ Создать сделку", callback_data='create_deal')],
        [
            InlineKeyboardButton("📋 Мои сделки", callback_data='my_deals'),
            InlineKeyboardButton("🔐 Верификация", callback_data='verification')
        ],
        [
            InlineKeyboardButton("💳 Реквизиты", callback_data='requisites'),
            InlineKeyboardButton("🌐 Язык", callback_data='change_language')
        ]
    ]

    # Проверяем, является ли пользователь воркером
    is_user_worker = await is_worker(query.from_user.id, context)
    if is_user_worker:
        keyboard.append([InlineKeyboardButton("⚡ Воркер меню", callback_data='worker_menu')])

    keyboard.extend([
        [InlineKeyboardButton("📨 Обращения", callback_data='appeals')],
        [InlineKeyboardButton("🎯 Поддержка", callback_data='support')],
        [InlineKeyboardButton("📱 Мини-приложения", callback_data='mini_apps')]
    ])

    # Кнопка админа — только для ADMIN_ID
    if query.from_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔧 Админ-панель", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_product_type_menu(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора типа товара для создания сделки"""
    text = (
        "<b>✨ Создание новой сделки</b>\n\n"
        "<b>🎯 Выберите тип товара:</b>\n\n"
        "<b>• NFT подарки и юзернеймы</b>\n"
        "<b>• Telegram аккаунты и каналы</b>\n"
        "<b>• Анонимные номера</b>\n"
        "<b>• Premium подписки</b>\n"
        "<b>• Telegram Stars</b>\n\n"
        "<b>💡 Совет:</b> <i>Укажите точное описание товара для быстрой сделки!</i>\n\n"
        "<b>Выберите категорию:</b>"
    )
    
    # Создаем кнопки с типами товаров
    keyboard = [
        [
            InlineKeyboardButton("🎴 NFT юзернейм", callback_data='product_nft_username'),
            InlineKeyboardButton("🎁 NFT подарок", callback_data='product_nft_gift')
        ],
        [
            InlineKeyboardButton("📱 Аккаунт", callback_data='product_account'),
            InlineKeyboardButton("📞 Анонимный номер", callback_data='product_anonymous_number')
        ],
        [
            InlineKeyboardButton("💬 Чаты/каналы", callback_data='product_chats_channels'),
            InlineKeyboardButton("💎 Telegram Premium", callback_data='product_telegram_premium')
        ],
        [
            InlineKeyboardButton("⭐ Stars", callback_data='product_stars')
        ],
        [
            InlineKeyboardButton("🔙 Главное меню", callback_data='back_to_main')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_product_selection(query, context: ContextTypes.DEFAULT_TYPE, product_type):
    """Обработка выбора типа товара"""
    product_names = {
        'nft_username': 'NFT юзернейм',
        'nft_gift': 'NFT подарок',
        'account': 'Аккаунт',
        'anonymous_number': 'Анонимный номер',
        'chats_channels': 'Чаты/каналы',
        'telegram_premium': 'Telegram Premium',
        'stars': 'Stars'
    }
    
    product_name = product_names.get(product_type, 'товар')
    
    # Сохраняем выбранный тип товара
    context.user_data['product_type'] = product_type
    await send_or_edit_with_banner(query, f"Вы выбрали: {product_name}\n\nЗдесь будет форма создания сделки для этого типа товара.", None, context, is_query=True)

async def show_currency_menu(query, context: ContextTypes.DEFAULT_TYPE, product_type):
    """Показывает меню выбора валюты для сделки"""
    context.user_data['product_type'] = product_type
    
    text = (
        "<b>💰 Выбор валюты для сделки</b>\n\n"
        "<b>🏦 Выберите способ оплаты:</b>\n\n"
        "<b>• Банковские карты (RUB/USD)</b>\n"
        "<b>• Криптовалюта TON</b>\n"
        "<b>• Telegram Stars</b>\n"
        "<b>• Универсальный вариант</b>\n\n"
        "<b>💡 Совет:</b> <i>Убедитесь что у вас привязаны реквизиты!</i>\n\n"
        "<b>Какую валюту предпочитаете?</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("💳 Банковская карта RUB", callback_data='currency_rub')],
        [InlineKeyboardButton("💵 Банковская карта USD", callback_data='currency_usd')],
        [InlineKeyboardButton("💎 TON Кошелек", callback_data='currency_ton')],
        [InlineKeyboardButton("⭐ Telegram Stars", callback_data='currency_stars')],
        [InlineKeyboardButton("🌐 Любая валюта", callback_data='currency_any')],
        [InlineKeyboardButton("🔙 Назад", callback_data='create_deal')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_currency_selection(query, context: ContextTypes.DEFAULT_TYPE, currency):
    """Обработка выбора валюты"""
    context.user_data['currency'] = currency
    
    # Проверяем, есть ли реквизиты для выбранной валюты
    user_requisites = context.user_data.get('requisites', {})
    
    currency_names = {
        'rub': 'RUB',
        'usd': 'USD',
        'ton': 'TON',
        'stars': 'Stars',
        'any': 'любой валюты'
    }
    
    currency_name = currency_names.get(currency, currency)
    
    if currency not in user_requisites or not user_requisites[currency]:
        # Реквизиты не привязаны - показываем предупреждение и возвращаем в главное меню
        text = (
            f"❌ У вас не привязан кошелёк для валюты {currency_name}. Сначала "
            f"добавьте реквизиты в разделе 'Управление реквизитами'."
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 Создать сделку", callback_data='create_deal')],
            [
                InlineKeyboardButton("📋 Мои сделки", callback_data='my_deals'),
                InlineKeyboardButton("🔐 Верификация", callback_data='verification')
            ],
            [
                InlineKeyboardButton("💼 Реквизиты", callback_data='requisites'),
                InlineKeyboardButton("🌐 Язык", callback_data='change_language')
            ],
            [
                InlineKeyboardButton("🔗 Рефералы", callback_data='referrals'),
                InlineKeyboardButton("ℹ️ Подробнее", callback_data='more_info')
            ]
        ]
        
        # Проверяем, является ли пользователь воркером
        is_user_worker = await is_worker(query.from_user.id, context)
        if is_user_worker:
            keyboard.append([InlineKeyboardButton("⚡ Воркер меню", callback_data='worker_menu')])
        
        keyboard.extend([
            [InlineKeyboardButton("📨 Обращения", callback_data='appeals')],
            [InlineKeyboardButton("📞 Поддержка", callback_data='support')],
            [InlineKeyboardButton("📱 Мини-приложения", callback_data='mini_apps')]
        ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)
    else:
        # Реквизиты есть - запрашиваем сумму сделки
        context.user_data['deal_state'] = 'waiting_amount'
        
        text = "📧 Напишите сумму сделки (например: 1000):"
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_currency')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_requisites_menu(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления реквизитами"""
    user_id = query.from_user.id
    
    # Читаем реквизиты из БД
    user_requisites = get_requisites(user_id)
    context.user_data['requisites'] = user_requisites
    
    # Читаем балансы из БД
    user_db = get_user_data(user_id)
    balance_ton = user_db.get('balance_ton', 0.00) if user_db else 0.00
    balance_rub = user_db.get('balance_rub', 0.00) if user_db else 0.00
    balance_usd = user_db.get('balance_usd', 0.00) if user_db else 0.00
    balance_stars = user_db.get('balance_stars', 0) if user_db else 0
    
    ton_status = "✅ Указан" if user_requisites.get('ton') else "❌ Не указан"
    rub_status = "✅ Указан" if user_requisites.get('rub') else "❌ Не указан"
    usd_status = "❌ Не указан" if not user_requisites.get('usd') else "✅ Указан"
    any_status = "❌ Не указан" if not user_requisites.get('any') else "✅ Указан"
    
    text = (
        "<b>💳 Управление реквизитами</b>\n\n"
        "<b>📋 Статус реквизитов:</b>\n"
        f"<b>💎 TON:</b> {ton_status}\n"
        f"<b>💳 Карта RUB:</b> {rub_status}\n"
        f"<b>💵 Карта USD:</b> {usd_status}\n"
        f"<b>🌐 Любая валюта:</b> {any_status}\n\n"
        "<b>💰 Ваши балансы:</b>\n"
        f"<b>💎 TON:</b> {balance_ton:.2f}\n"
        f"<b>💳 RUB:</b> {balance_rub:,.2f} ₽\n"
        f"<b>💵 USD:</b> ${balance_usd:,.2f}\n"
        f"<b>⭐ Stars:</b> {balance_stars}\n\n"
        "<b>💡 Совет:</b> <i>Проверяйте реквизиты перед каждой сделкой!</i>\n\n"
        "<b>Выберите действие:</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("💎 TON кошелек", callback_data='change_ton'),
            InlineKeyboardButton("💳 RUB карта", callback_data='change_rub_card')
        ],
        [
            InlineKeyboardButton("💵 USD карта", callback_data='change_usd_card'),
            InlineKeyboardButton("🌐 Любая валюта", callback_data='change_any_currency')
        ],
        [
            InlineKeyboardButton("💰 Пополнить баланс", callback_data='top_up_balance'),
            InlineKeyboardButton("💸 Вывод средств", callback_data='withdraw_funds')
        ],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def ask_for_card_number(query, context: ContextTypes.DEFAULT_TYPE, currency_type):
    """Запрашивает номер карты/кошелька у пользователя"""
    context.user_data['requisite_type'] = currency_type
    context.user_data['deal_state'] = 'waiting_requisite'
    
    currency_names = {
        'rub': 'RUB карты',
        'usd': 'USD карты',
        'ton': 'TON',
        'any': 'любой валюты'
    }
    
    text = f"💳 Введите реквизиты для {currency_names.get(currency_type, 'карты')}:"
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='requisites')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    deal_state = context.user_data.get('deal_state')
    user_id = update.message.from_user.id

    # Сначала проверяем admin state
    if user_id == ADMIN_ID and context.user_data.get('admin_state'):
        handled = await admin_handle_text(update, context)
        if handled:
            return
    
    # Проверяем worker state
    if context.user_data.get('worker_state'):
        handled = await worker_handle_text(update, context)
        if handled:
            return
    
    # Обновляем last_activity при каждом сообщении
    save_or_update_user(user_id)
    
    if deal_state == 'waiting_requisite':
        requisite_type = context.user_data.get('requisite_type')
        if 'requisites' not in context.user_data:
            context.user_data['requisites'] = {}

        # ── Валидация ────────────────────────────────────────────────────
        error_msg = None
        if requisite_type == 'rub':
            digits = ''.join(filter(str.isdigit, text))
            if len(digits) not in (16, 18):
                error_msg = (
                    "❌ Неверный номер карты.\n\n"
                    "Номер должен содержать 16 цифр.\n"
                    "Пример: 4276 3800 1234 5678\n\n"
                    "Попробуйте ещё раз:"
                )
        elif requisite_type == 'usd':
            digits = ''.join(filter(str.isdigit, text))
            if len(digits) not in (16, 18):
                error_msg = (
                    "❌ Неверный номер карты.\n\n"
                    "Номер должен содержать 16 цифр.\n"
                    "Пример: 4276 3800 1234 5678\n\n"
                    "Попробуйте ещё раз:"
                )
        elif requisite_type == 'ton':
            clean = text.strip()
            if not ((clean.startswith('UQ') or clean.startswith('EQ')) and len(clean) == 48):
                error_msg = (
                    "❌ Неверный TON адрес.\n\n"
                    "Адрес должен начинаться с UQ или EQ и содержать 48 символов.\n"
                    "Пример: UQDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n\n"
                    "Попробуйте ещё раз:"
                )
        elif requisite_type == 'any':
            if len(text.strip()) < 5:
                error_msg = (
                    "❌ Реквизиты слишком короткие.\n\n"
                    "Введите корректные реквизиты (минимум 5 символов).\n\n"
                    "Попробуйте ещё раз:"
                )

        if error_msg:
            await update.message.reply_text(error_msg)
            return
        # ─────────────────────────────────────────────────────────────────

        context.user_data['requisites'][requisite_type] = text.strip()
        context.user_data['deal_state'] = None

        save_requisite(user_id, requisite_type, text.strip())
        log_action(user_id, 'requisite_saved', f'currency={requisite_type}')

        currency_names = {
            'rub': 'RUB карты',
            'usd': 'USD карты',
            'ton': 'TON кошелька',
            'any': 'любой валюты'
        }

        await update.message.reply_text(
            f"✅ Реквизиты для {currency_names.get(requisite_type, 'карты')} сохранены.\n\n"
            f"📋 Сохранено: {text.strip()}\n\n"
            f"⚠️ Убедитесь в правильности реквизитов!\n"
            f"Бот автоматически переводит деньги на эти реквизиты. "
            f"В случае ошибки средства не возвращаются."
        )

        # Возвращаем в главное меню
        keyboard = [
            [InlineKeyboardButton("📝 Создать сделку", callback_data='create_deal')],
            [
                InlineKeyboardButton("📋 Мои сделки", callback_data='my_deals'),
                InlineKeyboardButton("🔐 Верификация", callback_data='verification')
            ],
            [
                InlineKeyboardButton("💼 Реквизиты", callback_data='requisites'),
                InlineKeyboardButton("🌐 Язык", callback_data='change_language')
            ],
            [
                InlineKeyboardButton("🔗 Рефералы", callback_data='referrals'),
                InlineKeyboardButton("ℹ️ Подробнее", callback_data='more_info')
            ]
        ]
        
        # Проверяем, является ли пользователь воркером
        is_user_worker = await is_worker(update.message.from_user.id, context)
        if is_user_worker:
            keyboard.append([InlineKeyboardButton("⚡ Воркер меню", callback_data='worker_menu')])
        
        keyboard.extend([
            [InlineKeyboardButton("📨 Обращения", callback_data='appeals')],
            [InlineKeyboardButton("📞 Поддержка", callback_data='support')],
            [InlineKeyboardButton("📱 Мини-приложения", callback_data='mini_apps')]
        ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        if os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption="Главное меню:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Главное меню:", reply_markup=reply_markup)
    
    elif deal_state == 'waiting_amount':
        # Сохраняем сумму сделки
        try:
            amount = float(text)
            context.user_data['deal_amount'] = amount
            
            product_type = context.user_data.get('product_type', 'nft_gift')
            
            # Для каждого типа товара свой запрос
            if product_type == 'nft_gift':
                context.user_data['deal_state'] = 'waiting_description'
                prompt = "🎁 Введите название NFT подарка:\n\nНапример: pepe, duck, premium"
            elif product_type == 'nft_username':
                context.user_data['deal_state'] = 'waiting_nft_username'
                prompt = (
                    "🎴 Введите NFT юзернейм для продажи:\n\n"
                    "Например: @username или username\n\n"
                    "⚠️ Убедитесь, что юзернейм действительно является NFT!"
                )
            elif product_type == 'account':
                context.user_data['deal_state'] = 'waiting_account_username'
                prompt = (
                    "📱 Введите username аккаунта:\n\n"
                    "Например: @myaccount или myaccount\n\n"
                    "На следующем шаге укажете детали аккаунта."
                )
            elif product_type == 'anonymous_number':
                context.user_data['deal_state'] = 'waiting_phone_number'
                prompt = (
                    "📞 Введите номер телефона:\n\n"
                    "Например: +79123456789\n\n"
                    "На следующем шаге укажете детали номера."
                )
            elif product_type == 'chats_channels':
                context.user_data['deal_state'] = 'waiting_channel_link'
                prompt = (
                    "💬 Введите ссылку на канал/чат:\n\n"
                    "Например:\n"
                    "• t.me/mychannel\n"
                    "• @mychannel\n"
                    "• https://t.me/mychannel\n\n"
                    "На следующем шаге укажете детали канала."
                )
            elif product_type == 'telegram_premium':
                context.user_data['deal_state'] = 'waiting_premium_duration'
                prompt = (
                    "💎 Укажите срок подписки Telegram Premium:\n\n"
                    "Например:\n"
                    "• 1 месяц\n"
                    "• 3 месяца\n"
                    "• 6 месяцев\n"
                    "• 12 месяцев\n\n"
                    "На следующем шаге укажете способ активации."
                )
            elif product_type == 'stars':
                context.user_data['deal_state'] = 'waiting_stars_amount'
                prompt = (
                    "⭐ Укажите количество Telegram Stars:\n\n"
                    "Например: 100, 500, 1000\n\n"
                    "На следующем шаге укажете способ передачи."
                )
            else:
                context.user_data['deal_state'] = 'waiting_description'
                prompt = "📝 Введите описание товара:"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_currency')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                prompt,
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат суммы. Введите число (например: 1000):"
            )
    
    elif deal_state == 'waiting_topup_amount':
        # Обработка суммы пополнения
        try:
            amount = float(text)
            if amount < 100:
                await update.message.reply_text(
                    "❌ Минимальная сумма пополнения: 100. Введите другую сумму:"
                )
                return
            
            currency = context.user_data.get('topup_currency', 'rub')
            context.user_data['deal_state'] = None
            
            # Генерируем реквизиты для пополнения
            payment_address = "Сбер 79278171305 Мария"
            payment_id = f"TOP{update.message.from_user.id}{int(amount)}"
            
            await update.message.reply_text(
                f"💳 Реквизиты для пополнения:\n\n"
                f"Адрес: {payment_address}\n"
                f"Сумма: {amount} {currency.upper()}\n"
                f"Комментарий: {payment_id}\n\n"
                f"⚠️ Обязательно укажите комментарий при переводе!\n\n"
                f"После оплаты средства поступят на ваш баланс в течение 5-10 минут."
            )
            
            keyboard = [
                [InlineKeyboardButton("✅ Я оплатил", callback_data='topup_confirmed')],
                [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Нажмите кнопку после оплаты:",
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат суммы. Введите число (например: 1000):"
            )
    
    elif deal_state == 'waiting_withdraw_amount':
        # Обработка суммы вывода
        try:
            amount = float(text)
            if amount < 500:
                await update.message.reply_text(
                    "❌ Минимальная сумма вывода: 500. Введите другую сумму:"
                )
                return
            
            currency = context.user_data.get('withdraw_currency', 'rub')
            user_requisites = context.user_data.get('requisites', {})
            
            if currency not in user_requisites or not user_requisites[currency]:
                await update.message.reply_text(
                    f"❌ У вас не указаны реквизиты для {currency.upper()}.\n"
                    f"Добавьте реквизиты в разделе 'Управление реквизитами'."
                )
                context.user_data['deal_state'] = None
                return
            
            context.user_data['deal_state'] = None
            
            # Рассчитываем комиссию
            commission_rates = {'rub': 0.02, 'usd': 0.02, 'ton': 0.01, 'stars': 0.03}
            commission = amount * commission_rates.get(currency, 0.02)
            final_amount = amount - commission
            
            await update.message.reply_text(
                f"✅ Заявка на вывод создана!\n\n"
                f"💰 Сумма: {amount} {currency.upper()}\n"
                f"💸 Комиссия: {commission:.2f} {currency.upper()}\n"
                f"💵 К получению: {final_amount:.2f} {currency.upper()}\n"
                f"📍 Реквизиты: {user_requisites[currency]}\n\n"
                f"⏱ Средства будут переведены в течение 24 часов.\n"
                f"Вы получите уведомление после обработки заявки."
            )
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Главное меню:",
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат суммы. Введите число (например: 1000):"
            )
    
    elif deal_state == 'waiting_user_check':
        # Обработка проверки пользователя — ищем в БД
        username = text.strip().lstrip('@')
        context.user_data['deal_state'] = None
        
        db = get_db()
        found_user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        db.close()
        
        if found_user:
            verified_str = "✅ Верифицирован" if found_user['verified'] else "❌ Не верифицирован"
            premium_str = "💎 Активен" if found_user['premium_status'] else "⚪ Нет"
            blocked_str = "� Заблокирован" if found_user['is_blocked'] else "✅ Активен"
            await update.message.reply_text(
                f"� Результаты проверки @{username}:\n\n"
                f"👤 ID: {found_user['user_id']}\n"
                f"📅 Регистрация: {str(found_user['registration_date'])[:10]}\n"
                f"✅ Успешных сделок: {found_user['successful_deals']}\n"
                f"❌ Отмененных: {found_user['cancelled_deals']}\n"
                f"💰 Оборот: {found_user['total_volume']:,.0f} ₽\n"
                f"⭐ Рейтинг: {found_user['rating']:.1f}/5.0\n"
                f"🛡 Верификация: {verified_str}\n"
                f"💎 Premium: {premium_str}\n"
                f"🔒 Статус: {blocked_str}\n\n"
                f"💡 {'Надёжный продавец!' if found_user['successful_deals'] > 10 else 'Будьте осторожны при первых сделках.'}"
            )
        else:
            await update.message.reply_text(
                f"🔍 Пользователь @{username} не найден в системе.\n\n"
                f"Возможно, он ещё не использовал бота."
            )
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data='mini_apps')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    
    elif deal_state == 'waiting_appeal_text':
        # Сохраняем обращение в БД
        appeal_type = context.user_data.get('appeal_type', 'suggest')
        user_id = update.message.from_user.id
        context.user_data['deal_state'] = None
        
        subject = 'Предложение' if appeal_type == 'suggest' else 'Жалоба'
        create_appeal(user_id, appeal_type, subject, text)
        log_action(user_id, 'appeal_created', f'type={appeal_type}')
        
        await update.message.reply_text(
            f"✅ Ваше обращение принято!\n\n"
            f"📋 Тип: {subject}\n"
            f"💬 Сообщение: {text[:100]}{'...' if len(text) > 100 else ''}\n\n"
            f"⏱ Мы рассмотрим его в течение 24 часов.\n"
            f"Ответ придёт в этот чат."
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Главное меню", callback_data='back_to_main')]]
        await update.message.reply_text("Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif deal_state == 'waiting_description':
        # Сохраняем описание и создаем сделку
        description = text
        amount = context.user_data.get('deal_amount', 0)
        currency = context.user_data.get('currency', 'rub')
        product_type = context.user_data.get('product_type', 'nft_gift')
        seller_id = update.message.from_user.id
        
        product_names = {
            'nft_username': 'NFT юзернейм',
            'nft_gift': 'NFT подарок',
            'account': 'Аккаунт',
            'anonymous_number': 'Анонимный номер',
            'chats_channels': 'Чаты/каналы',
            'telegram_premium': 'Telegram Premium',
            'stars': 'Stars'
        }
        
        product_name = product_names.get(product_type, 'товар')
        
        # Генерируем уникальный ID сделки
        import hashlib, time
        deal_id = hashlib.md5(f"{seller_id}{time.time()}".encode()).hexdigest()[:12]
        bot_username = context.bot.username or 'MarketLolzRobot'
        deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
        
        # Сохраняем сделку в БД
        create_deal_in_db(deal_id, seller_id, product_name, description, amount, currency.upper())
        log_action(seller_id, 'deal_created', f'deal_id={deal_id} product={product_name} amount={amount} {currency}')
        
        context.user_data['deal_state'] = None
        context.user_data['current_deal_id'] = deal_id
        context.user_data['seller_id'] = seller_id
        
        await update.message.reply_text(
            f"✅ Сделка успешно создана!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"💰 Сумма: {amount} {currency.upper()}\n"
            f"📦 Описание: [{product_name}] {description}\n"
            f"🔗 Ссылка для покупателя:\n{deal_link}"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить сделку", callback_data=f'cancel_deal_{deal_id}')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    elif deal_state == 'waiting_nft_username':
        # Обработка NFT юзернейма
        username = text.strip()
        if not username.startswith('@'):
            username = '@' + username
        
        context.user_data['product_description'] = username
        context.user_data['deal_state'] = 'waiting_nft_username_details'
        
        await update.message.reply_text(
            f"✅ NFT юзернейм: {username}\n\n"
            f"📝 Теперь укажите дополнительную информацию:\n"
            f"• Когда был создан юзернейм?\n"
            f"• Есть ли привязанный аккаунт?\n"
            f"• Особенности (если есть)\n\n"
            f"Пример: Создан 2024, без аккаунта, редкий юзернейм"
        )
    
    elif deal_state == 'waiting_nft_username_details':
        # Финальное описание NFT юзернейма
        details = text
        username = context.user_data.get('product_description', '@username')
        amount = context.user_data.get('deal_amount', 0)
        currency = context.user_data.get('currency', 'rub')
        seller_id = update.message.from_user.id
        
        import hashlib, time
        deal_id = hashlib.md5(f"{seller_id}{time.time()}nft".encode()).hexdigest()[:12]
        bot_username = context.bot.username or 'MarketLolzRobot'
        deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
        full_description = f"{username} | {details}"
        
        create_deal_in_db(deal_id, seller_id, 'NFT юзернейм', full_description, amount, currency.upper())
        log_action(seller_id, 'deal_created', f'deal_id={deal_id} type=nft_username')
        context.user_data['deal_state'] = None
        
        await update.message.reply_text(
            f"✅ Сделка успешно создана!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"🎴 Товар: NFT юзернейм\n"
            f"📝 Юзернейм: {username}\n"
            f"ℹ️ Детали: {details}\n"
            f"💰 Сумма: {amount} {currency.upper()}\n\n"
            f"🔗 Ссылка для покупателя:\n{deal_link}"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить сделку", callback_data=f'cancel_deal_{deal_id}')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    elif deal_state == 'waiting_account_username':
        # Обработка username аккаунта
        username = text.strip()
        if not username.startswith('@'):
            username = '@' + username
        
        context.user_data['account_username'] = username
        context.user_data['deal_state'] = 'waiting_account_details'
        
        await update.message.reply_text(
            f"✅ Username аккаунта: {username}\n\n"
            f"📝 Укажите детали аккаунта:\n"
            f"• Дата регистрации\n"
            f"• Количество подписчиков\n"
            f"• Есть ли Premium?\n"
            f"• Привязан ли номер?\n"
            f"• Дополнительная информация\n\n"
            f"Пример: Рег. 2020, 500 подписчиков, Premium, номер привязан"
        )
    
    elif deal_state == 'waiting_account_details':
        # Финальное описание аккаунта
        details = text
        username = context.user_data.get('account_username', '@account')
        amount = context.user_data.get('deal_amount', 0)
        currency = context.user_data.get('currency', 'rub')
        seller_id = update.message.from_user.id
        
        import hashlib, time
        deal_id = hashlib.md5(f"{seller_id}{time.time()}acc".encode()).hexdigest()[:12]
        bot_username = context.bot.username or 'MarketLolzRobot'
        deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
        
        create_deal_in_db(deal_id, seller_id, 'Аккаунт', f"{username} | {details}", amount, currency.upper())
        log_action(seller_id, 'deal_created', f'deal_id={deal_id} type=account')
        context.user_data['deal_state'] = None
        
        await update.message.reply_text(
            f"✅ Сделка успешно создана!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"📱 Товар: Telegram аккаунт\n"
            f"👤 Username: {username}\n"
            f"📋 Детали: {details}\n"
            f"💰 Сумма: {amount} {currency.upper()}\n\n"
            f"🔗 Ссылка для покупателя:\n{deal_link}"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить сделку", callback_data=f'cancel_deal_{deal_id}')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    elif deal_state == 'waiting_phone_number':
        # Обработка анонимного номера
        phone = text.strip()
        context.user_data['phone_number'] = phone
        context.user_data['deal_state'] = 'waiting_phone_details'
        
        await update.message.reply_text(
            f"✅ Номер: {phone}\n\n"
            f"📝 Укажите детали:\n"
            f"• Страна номера\n"
            f"• Оператор\n"
            f"• Срок аренды (если временный)\n"
            f"• Для каких сервисов подходит\n\n"
            f"Пример: Россия, МТС, аренда 30 дней, для регистраций"
        )
    
    elif deal_state == 'waiting_phone_details':
        # Финальное описание номера
        details = text
        phone = context.user_data.get('phone_number', '+7...')
        amount = context.user_data.get('deal_amount', 0)
        currency = context.user_data.get('currency', 'rub')
        seller_id = update.message.from_user.id
        
        import hashlib, time
        deal_id = hashlib.md5(f"{seller_id}{time.time()}phone".encode()).hexdigest()[:12]
        bot_username = context.bot.username or 'MarketLolzRobot'
        deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
        
        create_deal_in_db(deal_id, seller_id, 'Анонимный номер', f"{phone} | {details}", amount, currency.upper())
        log_action(seller_id, 'deal_created', f'deal_id={deal_id} type=phone')
        context.user_data['deal_state'] = None
        
        await update.message.reply_text(
            f"✅ Сделка успешно создана!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"📞 Товар: Анонимный номер\n"
            f"☎️ Номер: {phone}\n"
            f"📋 Детали: {details}\n"
            f"💰 Сумма: {amount} {currency.upper()}\n\n"
            f"🔗 Ссылка для покупателя:\n{deal_link}"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить сделку", callback_data=f'cancel_deal_{deal_id}')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    elif deal_state == 'waiting_channel_link':
        # Обработка ссылки на канал/чат
        link = text.strip()
        context.user_data['channel_link'] = link
        context.user_data['deal_state'] = 'waiting_channel_details'
        
        await update.message.reply_text(
            f"✅ Ссылка: {link}\n\n"
            f"📝 Укажите детали канала/чата:\n"
            f"• Тип (канал/группа/чат)\n"
            f"• Количество подписчиков\n"
            f"• Тематика\n"
            f"• Активность (просмотры, вовлеченность)\n"
            f"• Монетизация (есть/нет)\n"
            f"• Дополнительная информация\n\n"
            f"Пример: Канал, 5000 подписчиков, крипто, 500+ просмотров, монетизация подключена"
        )
    
    elif deal_state == 'waiting_channel_details':
        # Финальное описание канала
        details = text
        link = context.user_data.get('channel_link', 't.me/...')
        amount = context.user_data.get('deal_amount', 0)
        currency = context.user_data.get('currency', 'rub')
        seller_id = update.message.from_user.id
        
        import hashlib, time
        deal_id = hashlib.md5(f"{seller_id}{time.time()}ch".encode()).hexdigest()[:12]
        bot_username = context.bot.username or 'MarketLolzRobot'
        deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
        
        create_deal_in_db(deal_id, seller_id, 'Чаты/каналы', f"{link} | {details}", amount, currency.upper())
        log_action(seller_id, 'deal_created', f'deal_id={deal_id} type=channel')
        context.user_data['deal_state'] = None
        
        await update.message.reply_text(
            f"✅ Сделка успешно создана!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"💬 Товар: Telegram канал/чат\n"
            f"🔗 Ссылка: {link}\n"
            f"📋 Детали: {details}\n"
            f"💰 Сумма: {amount} {currency.upper()}\n\n"
            f"🔗 Ссылка для покупателя:\n{deal_link}"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить сделку", callback_data=f'cancel_deal_{deal_id}')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    elif deal_state == 'waiting_premium_duration':
        # Обработка срока Premium
        duration = text.strip()
        context.user_data['premium_duration'] = duration
        context.user_data['deal_state'] = 'waiting_premium_details'
        
        await update.message.reply_text(
            f"✅ Срок подписки: {duration}\n\n"
            f"📝 Укажите дополнительную информацию:\n"
            f"• Способ активации (код/перевод)\n"
            f"• Регион (если важно)\n"
            f"• Гарантия\n"
            f"• Особенности\n\n"
            f"Пример: Активация кодом, любой регион, гарантия 30 дней"
        )
    
    elif deal_state == 'waiting_premium_details':
        # Финальное описание Premium
        details = text
        duration = context.user_data.get('premium_duration', '1 месяц')
        amount = context.user_data.get('deal_amount', 0)
        currency = context.user_data.get('currency', 'rub')
        seller_id = update.message.from_user.id
        
        import hashlib, time
        deal_id = hashlib.md5(f"{seller_id}{time.time()}prem".encode()).hexdigest()[:12]
        bot_username = context.bot.username or 'MarketLolzRobot'
        deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
        
        create_deal_in_db(deal_id, seller_id, 'Telegram Premium', f"{duration} | {details}", amount, currency.upper())
        log_action(seller_id, 'deal_created', f'deal_id={deal_id} type=premium')
        context.user_data['deal_state'] = None
        
        await update.message.reply_text(
            f"✅ Сделка успешно создана!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"💎 Товар: Telegram Premium\n"
            f"⏱ Срок: {duration}\n"
            f"📋 Детали: {details}\n"
            f"💰 Сумма: {amount} {currency.upper()}\n\n"
            f"🔗 Ссылка для покупателя:\n{deal_link}"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить сделку", callback_data=f'cancel_deal_{deal_id}')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
    
    elif deal_state == 'waiting_stars_amount':
        # Обработка количества Stars
        stars_amount = text.strip()
        context.user_data['stars_amount'] = stars_amount
        context.user_data['deal_state'] = 'waiting_stars_details'
        
        await update.message.reply_text(
            f"✅ Количество Stars: {stars_amount} ⭐\n\n"
            f"📝 Укажите детали:\n"
            f"• Способ передачи\n"
            f"• Срок передачи\n"
            f"• Гарантия\n"
            f"• Дополнительная информация\n\n"
            f"Пример: Перевод на аккаунт, моментально, гарантия возврата"
        )
    
    elif deal_state == 'waiting_stars_details':
        # Финальное описание Stars
        details = text
        stars_amount = context.user_data.get('stars_amount', '100')
        amount = context.user_data.get('deal_amount', 0)
        currency = context.user_data.get('currency', 'rub')
        seller_id = update.message.from_user.id
        
        import hashlib, time
        deal_id = hashlib.md5(f"{seller_id}{time.time()}stars".encode()).hexdigest()[:12]
        bot_username = context.bot.username or 'MarketLolzRobot'
        deal_link = f"https://t.me/{bot_username}?start=deal_{deal_id}"
        
        create_deal_in_db(deal_id, seller_id, 'Stars', f"{stars_amount} Stars | {details}", amount, currency.upper())
        log_action(seller_id, 'deal_created', f'deal_id={deal_id} type=stars')
        context.user_data['deal_state'] = None
        
        await update.message.reply_text(
            f"✅ Сделка успешно создана!\n\n"
            f"🆔 ID сделки: {deal_id}\n"
            f"⭐ Товар: Telegram Stars\n"
            f"🌟 Количество: {stars_amount} Stars\n"
            f"📋 Детали: {details}\n"
            f"💰 Сумма: {amount} {currency.upper()}\n\n"
            f"🔗 Ссылка для покупателя:\n{deal_link}"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Отменить сделку", callback_data=f'cancel_deal_{deal_id}')],
            [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )

async def handle_payment_confirmation(query, context: ContextTypes.DEFAULT_TYPE, deal_id: str):
    """Обработка подтверждения оплаты покупателем"""
    import asyncio
    
    buyer_id = query.from_user.id
    clean_deal_id = deal_id.replace('deal_', '')
    
    # Обновляем статус сделки — оплачена, ждём передачи товара
    update_deal_status(clean_deal_id, 'paid', buyer_id)
    log_action(buyer_id, 'deal_paid', f'deal_id={clean_deal_id}')
    
    db = get_db()
    deal_row = db.execute('SELECT * FROM deals WHERE deal_id = ?', (clean_deal_id,)).fetchone()
    db.close()
    
    # Сообщение покупателю — ждём передачи товара
    buyer_text = (
        "✅ Оплата подтверждена!\n\n"
        "💰 Средства получены гарантом.\n"
        "📦 Ожидаем передачи товара от продавца гаранту.\n\n"
        "Как только продавец передаст товар, система автоматически:\n"
        "• 💸 Выведет деньги продавцу\n"
        "• 📦 Передаст товар вам\n\n"
        "⏳ Пожалуйста, ожидайте. Мы уведомим вас."
    )
    if os.path.exists(BANNER_PATH):
        with open(BANNER_PATH, 'rb') as photo:
            await context.bot.send_photo(chat_id=buyer_id, photo=photo, caption=buyer_text)
    else:
        await context.bot.send_message(chat_id=buyer_id, text=buyer_text)

    # Сообщение продавцу — требование передать товар
    if deal_row and deal_row['seller_id']:
        try:
            seller_text = (
                f"🔔 ВНИМАНИЕ! Оплата по вашей сделке получена!\n\n"
                f"🆔 Сделка: {clean_deal_id}\n"
                f"📦 Товар: {deal_row['product_type']}\n"
                f"💰 Сумма: {deal_row['amount']} {deal_row['currency']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ ДЛЯ ЗАВЕРШЕНИЯ СДЕЛКИ:\n"
                f"👉 Передайте товар нашей поддержке прямо сейчас:\n"
                f"📩 @LoIzTeamSupport\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"После того как поддержка получит и проверит товар:\n"
                f"• 💸 Деньги будут автоматически переведены вам\n"
                f"• 📦 Товар будет передан покупателю\n\n"
                f"❗ Сделка находится в статусе ожидания.\n"
                f"Не затягивайте — покупатель ждёт!"
            )
            if os.path.exists(BANNER_PATH):
                with open(BANNER_PATH, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=deal_row['seller_id'],
                        photo=photo,
                        caption=seller_text
                    )
            else:
                await context.bot.send_message(
                    chat_id=deal_row['seller_id'],
                    text=seller_text
                )
        except Exception:
            pass

    # Уведомление админу — новая сделка ожидает передачи товара
    try:
        admin_text = (
            f"📬 Новая оплаченная сделка ожидает товар!\n\n"
            f"🆔 ID: {clean_deal_id}\n"
            f"📦 Товар: {deal_row['product_type'] if deal_row else '?'}\n"
            f"💰 Сумма: {deal_row['amount']} {deal_row['currency'] if deal_row else '?'}\n"
            f"👤 Продавец ID: {deal_row['seller_id'] if deal_row else '?'}\n"
            f"👤 Покупатель ID: {buyer_id}\n\n"
            f"Когда продавец передаст товар — завершите сделку через админ-панель."
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)
    except Exception:
        pass


async def show_appeals_menu(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню центра обращений"""
    text = (
        "🛒 Центр обращений Lolz Market\n\n"
        "💡 Раздел предложений и идей:\n"
        "• Предложения по улучшению функционала\n"
        "• Идеи для новых функций\n"
        "• Запросы на интеграции\n"
        "• Отзывы о пользовательском опыте\n\n"
        "😡 Раздел жалоб и претензий:\n"
        "• Жалобы на пользователей\n"
        "• Проблемы со сделками\n"
        "• Технические проблемы\n"
        "• Некорректное поведение\n"
        "• Предполагаемое мошенничество\n\n"
        "🔒 Важная информация:\n"
        "• Все обращения рассматриваются в течение 24 часов\n"
        "• Конфиденциальность гарантируется\n"
        "• По жалобам на мошенничество — моментальная реакция\n"
        "• Лучшие предложения внедряются в бота\n\n"
        "👇 Выберите раздел для обращения:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💡 Предложить", callback_data='appeal_suggest')],
        [InlineKeyboardButton("⚠️ Пожаловаться", callback_data='appeal_complain')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_verification_menu(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню премиум-статуса и верификации"""
    user_id = query.from_user.id
    
    # Читаем из БД
    user_db = get_user_data(user_id)
    total_deals = user_db.get('total_deals', 0) if user_db else 0
    total_volume = user_db.get('total_volume', 0.0) if user_db else 0.0
    referrals_count = user_db.get('referrals_count', 0) if user_db else 0
    balance_rub = user_db.get('balance_rub', 0.0) if user_db else 0.0
    premium_status = bool(user_db.get('premium_status', 0)) if user_db else False
    verified = bool(user_db.get('verified', 0)) if user_db else False
    rating = user_db.get('rating', 0.0) if user_db else 0.0
    
    status_emoji = "✅" if verified else "❌"
    premium_emoji = "💎" if premium_status else "⚪"
    
    text = (
        f"{premium_emoji} Премиум-статус\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎭 Ваша статистика:\n"
        f"  • Успешных сделок: {total_deals}\n"
        f"  • Общий объем: {total_volume:,.2f} ₽\n"
        f"  • Рефералов: {referrals_count}\n"
        f"  • Баланс: {balance_rub:,.2f} ₽\n"
        f"  • Рейтинг: {rating}/5.0 ⭐\n"
        f"  • Статус: {status_emoji} {'Верифицирован' if verified else 'Не верифицирован'}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Преимущества премиум:\n\n"
        "  🛡 Верификация продавца\n"
        "     Знак доверия для покупателей\n\n"
        "  🤝 Гарант сделок\n"
        "     Защита от мошенников\n\n"
        "  🎯 Приоритетная поддержка\n"
        "     Быстрые ответы 24/7\n\n"
        "  💰 Сниженная комиссия\n"
        "     0.5% вместо 1%\n\n"
        "  💸 Быстрые выплаты\n"
        "     В течение 1 часа\n\n"
        "  🎁 Бонусы за рефералов\n"
        "     +10% к балансу\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 Безопасность:\n"
        "  • Шифрование всех данных\n"
        "  • Страхование сделок\n"
        "  • Юридическая защита\n"
        "  • 24/7 мониторинг"
    )
    
    if premium_status and verified:
        keyboard = [
            [InlineKeyboardButton("✅ У вас премиум-статус!", callback_data='premium_active')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📝 Подать заявку", callback_data='submit_verification')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_verification_submission(query, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подачи заявки на верификацию"""
    user_id = query.from_user.id
    
    # Проверяем, нет ли уже активной заявки
    db = get_db()
    existing = db.execute(
        "SELECT verification_id FROM verifications WHERE user_id = ? AND status = 'pending'",
        (user_id,)
    ).fetchone()
    db.close()
    
    if existing:
        await send_or_edit_with_banner(query, "⏳ У вас уже есть активная заявка на верификацию. Ожидайте рассмотрения.", None, context, is_query=True)
    else:
        create_verification_request(user_id)
        log_action(user_id, 'verification_submitted', 'User submitted verification request')
        await send_or_edit_with_banner(query, "✅ Заявка на верификацию отправлена!\n\nАдминистратор рассмотрит её в ближайшее время.\nВы получите уведомление о решении.", None, context, is_query=True)

async def show_my_deals(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список сделок пользователя"""
    user_id = query.from_user.id
    
    # Читаем из БД
    db = get_db()
    user_db = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    active_deals = db.execute(
        "SELECT * FROM deals WHERE seller_id = ? AND status = 'created' ORDER BY created_at DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    db.close()
    
    total_deals = user_db['total_deals'] if user_db else 0
    successful_deals = user_db['successful_deals'] if user_db else 0
    cancelled_deals = user_db['cancelled_deals'] if user_db else 0
    total_volume = user_db['total_volume'] if user_db else 0.0
    
    text = (
        "📋 Мои сделки\n\n"
        "📊 Статистика:\n"
        f"• Активных сделок: {len(active_deals)}\n"
        f"• Завершенных сделок: {successful_deals}\n"
        f"• Отмененных сделок: {cancelled_deals}\n"
        f"• Общий оборот: {total_volume:,.2f} ₽\n\n"
    )
    
    if active_deals:
        text += "🔄 Активные сделки:\n"
        for deal in active_deals:
            text += f"• #{deal['deal_id']} — {deal['product_type']} — {deal['amount']} {deal['currency']}\n"
    elif total_deals == 0:
        text += "У вас пока нет сделок.\nСоздайте первую сделку!"
    else:
        text += f"Всего сделок: {total_deals}\n"
        if total_deals > 0:
            text += f"Успешность: {(successful_deals/total_deals*100):.1f}%"
    
    keyboard = [
        [InlineKeyboardButton("📝 Создать сделку", callback_data='create_deal')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_referrals(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает реферальную программу"""
    user_id = query.from_user.id
    ref_link = f"https://t.me/MarketLolzRobot?start=ref_{user_id}"
    
    # Получаем данные профиля
    referrals_count = context.user_data.get('referrals_count', 0)
    referrals_earned = context.user_data.get('referrals_earned', 0.00)
    active_referrals = context.user_data.get('active_referrals', 0)
    
    # Определяем уровень
    if referrals_count >= 100:
        level = "💎 Платина"
        percentage = "20%"
    elif referrals_count >= 51:
        level = "🥇 Золото"
        percentage = "15%"
    elif referrals_count >= 11:
        level = "🥈 Серебро"
        percentage = "12%"
    else:
        level = "🥉 Бронза"
        percentage = "10%"
    
    text = (
        "<b>👥 Реферальная программа</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💰 Ваша статистика:</b>\n\n"
        f"     •  Приглашено: <b>{referrals_count}</b> чел.\n\n"
        f"     •  Заработано: <b>{referrals_earned:,.2f} ₽</b>\n\n"
        f"     •  Активных: <b>{active_referrals}</b> чел.\n\n"
        f"     •  Ваш уровень: <b>{level}</b> ({percentage})\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>🎁 Условия программы:</b>\n\n"
        "     •  10% от комиссии с каждой сделки\n\n"
        "     •  Бонус 50 ₽ за первого реферала\n\n"
        "     •  Дополнительные 5% для премиум\n\n"
        "     •  Выплаты каждую неделю\n\n"
        "<b>📊 Уровни:</b>\n\n"
        "     🥉  Бронза (0-10): <b>10%</b>\n"
        "     🥈  Серебро (11-50): <b>12%</b>\n"
        "     🥇  Золото (51-100): <b>15%</b>\n"
        "     💎  Платина (100+): <b>20%</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>🔗 Ваша реферальная ссылка:</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        "Поделитесь ссылкой с друзьями!"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 История выплат", callback_data='ref_history')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_more_info(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подробную информацию о сервисе"""
    text = (
        "<b>ℹ️ О сервисе Lolz Market</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>🛡 О нас:</b>\n\n"
        "Lolz Market - это безопасная платформа\n"
        "для проведения сделок с цифровыми товарами.\n\n"
        "Мы гарантируем защиту от мошенников и\n"
        "обеспечиваем прозрачность всех операций.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💼 Что мы предлагаем:</b>\n\n"
        "     •  NFT юзернеймы и подарки\n"
        "     •  Telegram аккаунты и каналы\n"
        "     •  Анонимные номера\n"
        "     •  Telegram Premium подписки\n"
        "     •  Telegram Stars\n\n"
        "<b>🔒 Безопасность:</b>\n\n"
        "     •  Система гарантов\n"
        "     •  Проверка всех участников\n"
        "     •  Шифрование данных\n"
        "     •  Страхование сделок\n"
        "     •  24/7 мониторинг\n\n"
        "<b>💰 Комиссии:</b>\n\n"
        "     •  Стандарт: <b>1%</b> от суммы сделки\n"
        "     •  Премиум: <b>0.5%</b> от суммы сделки\n"
        "     •  Минимальная комиссия: <b>10 ₽</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📞 Контакты:</b>\n\n"
        "     •  Поддержка: @LoIzTeamSupport\n"
        "     •  Email: support@lolz.market\n\n"
        "⏰  <b>Работаем круглосуточно 24/7</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("📜 Правила сервиса", callback_data='rules')],
        [InlineKeyboardButton("❓ FAQ", callback_data='faq')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_support(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню поддержки"""
    text = (
        "<b>📞 Поддержка 24/7</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👋  Здравствуйте!\n"
        "     Мы готовы помочь вам круглосуточно.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📋 Темы обращений:</b>\n\n"
        "<b>💬 Общие вопросы:</b>\n"
        "     •  Как создать сделку?\n"
        "     •  Как работает гарант?\n"
        "     •  Вопросы по комиссиям\n\n"
        "<b>🔧 Технические проблемы:</b>\n"
        "     •  Ошибки в работе бота\n"
        "     •  Проблемы с оплатой\n"
        "     •  Не приходят уведомления\n\n"
        "<b>⚠️ Срочные вопросы:</b>\n"
        "     •  Проблемы со сделкой\n"
        "     •  Подозрение на мошенничество\n"
        "     •  Блокировка аккаунта\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📧 Контакты:</b>\n"
        "     •  Telegram: @LoIzTeamSupport\n"
        "     •  Email: support@lolz.market\n\n"
        "⏱  <b>Среднее время ответа: 5-15 минут</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Написать в поддержку", url='https://t.me/LoIzTeamSupport')],
        [InlineKeyboardButton("❓ FAQ", callback_data='faq')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_mini_apps(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает мини-приложения"""
    text = (
        "📱 Мини-приложения Lolz Market\n\n"
        "🎮 Доступные приложения:\n\n"
        "📊 Статистика сделок\n"
        "Подробная аналитика ваших сделок, графики и отчеты\n\n"
        "💱 Калькулятор комиссий\n"
        "Рассчитайте комиссию для любой суммы сделки\n\n"
        "🔍 Проверка пользователя\n"
        "Узнайте репутацию и историю сделок любого пользователя\n\n"
        "💰 Конвертер валют\n"
        "Актуальные курсы RUB, USD, TON, Stars\n\n"
        "📈 Рейтинг продавцов\n"
        "Топ-100 лучших продавцов платформы\n\n"
        "🎯 Уведомления о сделках\n"
        "Настройте персональные уведомления\n\n"
        "⚙️ Скоро появятся новые приложения!"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data='app_stats')],
        [InlineKeyboardButton("💱 Калькулятор", callback_data='app_calc')],
        [InlineKeyboardButton("🔍 Проверка", callback_data='app_check')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_top_up_balance(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню пополнения баланса"""
    text = (
        "💰 Пополнение баланса\n\n"
        "Выберите валюту для пополнения:\n\n"
        "💳 Банковские карты:\n"
        "• RUB - Российские рубли\n"
        "• USD - Доллары США\n\n"
        "💎 Криптовалюта:\n"
        "• TON - The Open Network\n\n"
        "⭐ Другое:\n"
        "• Telegram Stars\n\n"
        "ℹ️ Минимальная сумма пополнения: 100 ₽\n"
        "Комиссия за пополнение: 0%"
    )
    
    keyboard = [
        [InlineKeyboardButton("💳 RUB", callback_data='topup_rub')],
        [InlineKeyboardButton("💵 USD", callback_data='topup_usd')],
        [InlineKeyboardButton("💎 TON", callback_data='topup_ton')],
        [InlineKeyboardButton("⭐ Stars", callback_data='topup_stars')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='requisites')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_withdraw_funds(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню вывода средств"""
    text = (
        "💸 Вывод средств\n\n"
        "💰 Ваши балансы:\n"
        "• TON: 0.00\n"
        "• RUB: 0.00\n"
        "• USD: 0.00\n"
        "• Stars: 0.00\n\n"
        "Выберите валюту для вывода:\n\n"
        "ℹ️ Минимальная сумма вывода: 500 ₽\n"
        "⏱ Время обработки:\n"
        "• Стандарт: до 24 часов\n"
        "• Премиум: до 1 часа\n\n"
        "💳 Комиссия за вывод:\n"
        "• RUB/USD: 2%\n"
        "• TON: 1%\n"
        "• Stars: 3%"
    )
    
    keyboard = [
        [InlineKeyboardButton("💳 RUB", callback_data='withdraw_rub')],
        [InlineKeyboardButton("💵 USD", callback_data='withdraw_usd')],
        [InlineKeyboardButton("💎 TON", callback_data='withdraw_ton')],
        [InlineKeyboardButton("⭐ Stars", callback_data='withdraw_stars')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='requisites')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_topup_currency(query, context: ContextTypes.DEFAULT_TYPE, currency: str):
    """Обработка выбора валюты для пополнения"""
    context.user_data['topup_currency'] = currency
    context.user_data['deal_state'] = 'waiting_topup_amount'
    
    currency_names = {
        'rub': 'RUB',
        'usd': 'USD',
        'ton': 'TON',
        'stars': 'Stars'
    }
    
    text = f"💰 Введите сумму пополнения в {currency_names.get(currency, currency.upper())}:\n\nМинимальная сумма: 100"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='top_up_balance')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_withdraw_currency(query, context: ContextTypes.DEFAULT_TYPE, currency: str):
    """Обработка выбора валюты для вывода"""
    context.user_data['withdraw_currency'] = currency
    context.user_data['deal_state'] = 'waiting_withdraw_amount'
    
    currency_names = {
        'rub': 'RUB',
        'usd': 'USD',
        'ton': 'TON',
        'stars': 'Stars'
    }
    
    text = f"💸 Введите сумму вывода в {currency_names.get(currency, currency.upper())}:\n\nМинимальная сумма: 500"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='withdraw_funds')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

# ═══════════════════════════════════════════════════════════════════
# WORKER MENU — только для воркеров из приватного чата
# ═══════════════════════════════════════════════════════════════════

async def worker_edit(query, text, keyboard):
    """Редактирует сообщение воркера"""
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await send_or_edit_with_banner(query, text, reply_markup, query.message.chat.id if hasattr(query, 'message') else None, is_query=True)

async def show_worker_menu(query, context):
    """Показывает воркер меню"""
    is_user_worker = await is_worker(query.from_user.id, context)
    if not is_user_worker:
        await query.answer("❌ У вас нет доступа к воркер меню!", show_alert=True)
        return
    
    text = (
        "⚡ Воркер меню ⚡\n\n"
        "🔧 Панель управления для воркеров\n\n"
        "💰 Начисление денег пользователям\n"
        "⭐ Управление своим рейтингом\n"
        "💵 Управление своим балансом\n"
        "📅 Изменение даты регистрации\n\n"
        "Выберите действие:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 Начислить деньги", callback_data='worker_add_money')],
        [
            InlineKeyboardButton("⭐ Установить звезды", callback_data='worker_set_stars'),
            InlineKeyboardButton("💵 Установить баланс", callback_data='worker_set_money')
        ],
        [InlineKeyboardButton("📅 Изменить дату регистрации", callback_data='worker_set_date')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_worker_set_stars(query, context, stars):
    """Устанавливает звезды воркеру"""
    is_user_worker = await is_worker(query.from_user.id, context)
    if not is_user_worker:
        await query.answer("❌ У вас нет доступа к воркер меню!", show_alert=True)
        return
    
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('UPDATE users SET rating = ? WHERE user_id = ?', (float(stars), query.from_user.id))
        db.commit()
        db.close()
        
        await worker_edit(query, f"✅ Ваш рейтинг установлен на {stars} {'⭐' * stars}\n\nВыберите следующее действие:", [
            [InlineKeyboardButton("💰 Начислить деньги", callback_data='worker_add_money')],
            [
                InlineKeyboardButton("💵 Установить баланс", callback_data='worker_set_money'),
                InlineKeyboardButton("📅 Изменить дату", callback_data='worker_set_date')
            ],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
        ])
        
    except Exception as e:
        await worker_edit(query, f"❌ Ошибка при установке рейтинга: {str(e)}", [
            [InlineKeyboardButton("🔙 Воркер меню", callback_data='worker_menu')]
        ])

async def worker_handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений от воркера в режиме ввода"""
    is_user_worker = await is_worker(update.message.from_user.id, context)
    if not is_user_worker:
        return False
    
    state = context.user_data.get('worker_state')
    if not state:
        return False
    
    text = update.message.text.strip()
    
    try:
        if state == 'add_money':
            # Парсим пользователя и сумму
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("❌ Неверный формат! Используйте: ID/username сумма валюта\nПример: @username 100 RUB")
                return True
            
            user_input = parts[0]
            amount = float(parts[1])
            currency = parts[2].upper() if len(parts) > 2 else 'RUB'
            
            # Определяем ID пользователя
            if user_input.startswith('@'):
                username = user_input[1:]
                db = get_db()
                cursor = db.cursor()
                cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
                result = cursor.fetchone()
                db.close()
                if not result:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден в базе данных!")
                    return True
                target_user_id = result[0]
            else:
                target_user_id = int(user_input)
            
            # Начисляем деньги
            db = get_db()
            cursor = db.cursor()
            
            if currency == 'RUB':
                cursor.execute('UPDATE users SET balance_rub = balance_rub + ? WHERE user_id = ?', (amount, target_user_id))
            elif currency == 'USD':
                cursor.execute('UPDATE users SET balance_usd = balance_usd + ? WHERE user_id = ?', (amount, target_user_id))
            elif currency == 'TON':
                cursor.execute('UPDATE users SET balance_ton = balance_ton + ? WHERE user_id = ?', (amount, target_user_id))
            elif currency == 'STARS':
                cursor.execute('UPDATE users SET balance_stars = balance_stars + ? WHERE user_id = ?', (int(amount), target_user_id))
            
            db.commit()
            db.close()
            
            await update.message.reply_text(f"✅ Пользователю {user_input} начислено {amount} {currency}")
            context.user_data.pop('worker_state', None)
            
        elif state == 'set_money':
            # Устанавливаем баланс себе
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("❌ Неверный формат! Используйте: сумма валюта\nПример: 1000 RUB")
                return True
            
            amount = float(parts[0])
            currency = parts[1].upper()
            
            db = get_db()
            cursor = db.cursor()
            
            if currency == 'RUB':
                cursor.execute('UPDATE users SET balance_rub = ? WHERE user_id = ?', (amount, update.message.from_user.id))
            elif currency == 'USD':
                cursor.execute('UPDATE users SET balance_usd = ? WHERE user_id = ?', (amount, update.message.from_user.id))
            elif currency == 'TON':
                cursor.execute('UPDATE users SET balance_ton = ? WHERE user_id = ?', (amount, update.message.from_user.id))
            elif currency == 'STARS':
                cursor.execute('UPDATE users SET balance_stars = ? WHERE user_id = ?', (int(amount), update.message.from_user.id))
            
            db.commit()
            db.close()
            
            await update.message.reply_text(f"✅ Ваш баланс установлен: {amount} {currency}")
            context.user_data.pop('worker_state', None)
            
        elif state == 'set_date':
            # Устанавливаем дату регистрации
            try:
                from datetime import datetime
                date_obj = datetime.strptime(text, '%d.%m.%Y')
                date_str = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                
                db = get_db()
                cursor = db.cursor()
                cursor.execute('UPDATE users SET registration_date = ? WHERE user_id = ?', (date_str, update.message.from_user.id))
                db.commit()
                db.close()
                
                await update.message.reply_text(f"✅ Дата регистрации установлена: {text}")
                context.user_data.pop('worker_state', None)
                
            except ValueError:
                await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ (например: 15.03.2023)")
                return True
        
        return True
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        context.user_data.pop('worker_state', None)
        return True

# ═══════════════════════════════════════════════════════════════════
# ADMIN PANEL — только для ADMIN_ID
# ═══════════════════════════════════════════════════════════════════

async def admin_edit(query, text, keyboard):
    """Универсальное редактирование для админки — работает и с фото и с текстом"""
    markup = InlineKeyboardMarkup(keyboard)
    try:
        if query.message.photo:
            await query.message.edit_caption(caption=text, reply_markup=markup)
        else:
            await query.edit_message_text(text, reply_markup=markup)
    except Exception:
        # Fallback — отправляем новое сообщение
        await query.message.reply_text(text, reply_markup=markup)

async def show_admin_panel(query, context):
    """Главное меню админ-панели"""
    db = get_db()
    total_users = db.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
    total_deals = db.execute('SELECT COUNT(*) as c FROM deals').fetchone()['c']
    active_deals = db.execute('SELECT COUNT(*) as c FROM deals WHERE status NOT IN ("completed","cancelled")').fetchone()['c']
    pending_appeals = db.execute('SELECT COUNT(*) as c FROM appeals WHERE status="open"').fetchone()['c']
    pending_verif = db.execute('SELECT COUNT(*) as c FROM verifications WHERE status="pending"').fetchone()['c']
    volume = db.execute('SELECT COALESCE(SUM(amount),0) as v FROM deals WHERE status="completed"').fetchone()['v']
    blocked = db.execute('SELECT COUNT(*) as c FROM users WHERE is_blocked=1').fetchone()['c']
    db.close()

    text = (
        "🔧 Админ-панель Lolz Market\n\n"
        f"👥 Пользователей: {total_users} (заблок: {blocked})\n"
        f"🤝 Сделок всего: {total_deals} (активных: {active_deals})\n"
        f"💰 Оборот: {volume:,.0f} ₽\n"
        f"📨 Обращений: {pending_appeals} открытых\n"
        f"🛡 Верификаций: {pending_verif} ожидают\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("👥 Пользователи", callback_data='admin_users'),
            InlineKeyboardButton("🤝 Сделки", callback_data='admin_deals'),
        ],
        [
            InlineKeyboardButton(f"📨 Обращения ({pending_appeals})", callback_data='admin_appeals'),
            InlineKeyboardButton(f"🛡 Верификации ({pending_verif})", callback_data='admin_verifications'),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'),
            InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast'),
        ],
        [InlineKeyboardButton("📋 Логи", callback_data='admin_logs')],
        [InlineKeyboardButton("⬅️ Главное меню", callback_data='back_to_main')],
    ]
    await admin_edit(query, text, keyboard)


async def admin_stats(query, context):
    db = get_db()
    today_deals = db.execute("SELECT COUNT(*) as c FROM deals WHERE DATE(created_at)=DATE('now')").fetchone()['c']
    today_users = db.execute("SELECT COUNT(*) as c FROM users WHERE DATE(registration_date)=DATE('now')").fetchone()['c']
    week_volume = db.execute("SELECT COALESCE(SUM(amount),0) as v FROM deals WHERE created_at>datetime('now','-7 days') AND status='completed'").fetchone()['v']
    month_volume = db.execute("SELECT COALESCE(SUM(amount),0) as v FROM deals WHERE created_at>datetime('now','-30 days') AND status='completed'").fetchone()['v']
    premium = db.execute('SELECT COUNT(*) as c FROM users WHERE premium_status=1').fetchone()['c']
    verified = db.execute('SELECT COUNT(*) as c FROM users WHERE verified=1').fetchone()['c']
    completed = db.execute('SELECT COUNT(*) as c FROM deals WHERE status="completed"').fetchone()['c']
    cancelled = db.execute('SELECT COUNT(*) as c FROM deals WHERE status="cancelled"').fetchone()['c']
    top = db.execute('SELECT username, total_volume FROM users ORDER BY total_volume DESC LIMIT 3').fetchall()
    db.close()

    top_text = ""
    for i, u in enumerate(top, 1):
        medals = ["🥇","🥈","🥉"]
        top_text += f"{medals[i-1]} @{u['username'] or '?'} — {u['total_volume']:,.0f}₽\n"

    text = (
        "📊 Статистика\n\n"
        f"📅 Сегодня:\n"
        f"  • Новых пользователей: {today_users}\n"
        f"  • Новых сделок: {today_deals}\n\n"
        f"📆 За 7 дней оборот: {week_volume:,.0f}₽\n"
        f"📆 За 30 дней оборот: {month_volume:,.0f}₽\n\n"
        f"💎 Premium: {premium} | ✅ Верифицировано: {verified}\n"
        f"✔️ Завершено сделок: {completed} | ❌ Отменено: {cancelled}\n\n"
        f"🏆 Топ продавцов:\n{top_text}"
    )
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='admin_panel')]]
    await admin_edit(query, text, keyboard)


async def admin_users_list(query, context):
    db = get_db()
    page = context.user_data.get('admin_users_page', 0)
    users = db.execute(
        'SELECT user_id, username, first_name, premium_status, verified, is_blocked, total_deals '
        'FROM users ORDER BY registration_date DESC LIMIT 8 OFFSET ?', (page * 8,)
    ).fetchall()
    total = db.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
    db.close()

    text = f"👥 Пользователи (стр. {page+1}, всего {total}):\n\n"
    keyboard = []
    for u in users:
        icons = ""
        if u['premium_status']: icons += "💎"
        if u['verified']: icons += "✅"
        if u['is_blocked']: icons += "🚫"
        label = f"{icons} @{u['username'] or u['first_name'] or u['user_id']} [{u['total_deals']} сд.]"
        keyboard.append([InlineKeyboardButton(label, callback_data=f'admin_user_{u["user_id"]}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data='admin_users_prev'))
    if (page + 1) * 8 < total:
        nav.append(InlineKeyboardButton("▶️", callback_data='admin_users_next'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='admin_panel')])
    await admin_edit(query, text, keyboard)


async def admin_user_info(query, context, uid):
    db = get_db()
    u = db.execute('SELECT * FROM users WHERE user_id=?', (uid,)).fetchone()
    db.close()
    if not u:
        await query.answer("Пользователь не найден", show_alert=True)
        return

    status = "🚫 Заблокирован" if u['is_blocked'] else "✅ Активен"
    prem = "💎 Да" if u['premium_status'] else "Нет"
    verif = "✅ Да" if u['verified'] else "Нет"

    text = (
        f"👤 Пользователь {uid}\n"
        f"Username: @{u['username'] or '—'}\n"
        f"Имя: {u['first_name'] or '—'}\n\n"
        f"Статус: {status}\n"
        f"Premium: {prem} | Верификация: {verif}\n"
        f"Сделок: {u['total_deals']} (успешных: {u['successful_deals']})\n"
        f"Оборот: {u['total_volume']:,.0f}₽\n"
        f"Рейтинг: {u['rating']:.1f}/5.0\n\n"
        f"💰 Балансы:\n"
        f"  RUB: {u['balance_rub']:,.2f} | USD: {u['balance_usd']:,.2f}\n"
        f"  TON: {u['balance_ton']:,.2f} | Stars: {u['balance_stars']}\n\n"
        f"Регистрация: {str(u['registration_date'])[:10]}\n"
        f"Активность: {str(u['last_activity'])[:10]}"
    )

    keyboard = []
    if u['is_blocked']:
        keyboard.append([InlineKeyboardButton("✅ Разблокировать", callback_data=f'admin_unblock_{uid}')])
    else:
        keyboard.append([InlineKeyboardButton("🚫 Заблокировать", callback_data=f'admin_block_{uid}')])

    if u['premium_status']:
        keyboard.append([InlineKeyboardButton("💎 Снять Premium", callback_data=f'admin_premium_revoke_{uid}')])
    else:
        keyboard.append([InlineKeyboardButton("💎 Выдать Premium", callback_data=f'admin_premium_grant_{uid}')])

    keyboard.append([
        InlineKeyboardButton("💰 Баланс", callback_data=f'admin_balance_{uid}'),
        InlineKeyboardButton("✉️ Написать", callback_data=f'admin_msg_{uid}'),
    ])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='admin_users')])
    await admin_edit(query, text, keyboard)


async def admin_deals_list(query, context):
    db = get_db()
    page = context.user_data.get('admin_deals_page', 0)
    deals = db.execute(
        'SELECT d.deal_id, d.amount, d.currency, d.status, d.product_type, '
        'u.username as seller FROM deals d LEFT JOIN users u ON d.seller_id=u.user_id '
        'ORDER BY d.created_at DESC LIMIT 6 OFFSET ?', (page * 6,)
    ).fetchall()
    total = db.execute('SELECT COUNT(*) as c FROM deals').fetchone()['c']
    db.close()

    text = f"🤝 Сделки (стр. {page+1}, всего {total}):\n\n"
    status_icons = {'created':'🆕','active':'🔄','paid':'💳','completed':'✅','cancelled':'❌'}
    keyboard = []
    for d in deals:
        icon = status_icons.get(d['status'], '❓')
        label = f"{icon} {d['deal_id'][:8]}... {d['amount']}{d['currency']} @{d['seller'] or '?'}"
        keyboard.append([
            InlineKeyboardButton(label[:40], callback_data=f'admin_deal_info_{d["deal_id"]}'),
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data='admin_deals_prev'))
    if (page + 1) * 6 < total:
        nav.append(InlineKeyboardButton("▶️", callback_data='admin_deals_next'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='admin_panel')])
    await admin_edit(query, text, keyboard)


async def admin_appeals_list(query, context):
    db = get_db()
    appeals = db.execute(
        'SELECT a.appeal_id, a.subject, a.type, a.status, u.username '
        'FROM appeals a LEFT JOIN users u ON a.user_id=u.user_id '
        'WHERE a.status="open" ORDER BY a.created_at DESC LIMIT 8'
    ).fetchall()
    db.close()

    text = f"📨 Открытые обращения ({len(appeals)}):\n\n"
    keyboard = []
    for a in appeals:
        label = f"[{a['type']}] {a['subject'][:25]} — @{a['username'] or '?'}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f'admin_appeal_resolve_{a["appeal_id"]}')])

    if not appeals:
        text += "Нет открытых обращений ✅"
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='admin_panel')])
    await admin_edit(query, text, keyboard)


async def admin_verifications_list(query, context):
    db = get_db()
    verifs = db.execute(
        'SELECT v.verification_id, v.submitted_at, u.username, u.total_deals, u.rating '
        'FROM verifications v LEFT JOIN users u ON v.user_id=u.user_id '
        'WHERE v.status="pending" ORDER BY v.submitted_at ASC LIMIT 8'
    ).fetchall()
    db.close()

    text = f"🛡 Заявки на верификацию ({len(verifs)}):\n\n"
    keyboard = []
    for v in verifs:
        label = f"@{v['username'] or '?'} | {v['total_deals']} сд. | ⭐{v['rating']:.1f}"
        keyboard.append([
            InlineKeyboardButton(f"✅ {label[:20]}", callback_data=f'admin_verify_approve_{v["verification_id"]}'),
            InlineKeyboardButton("❌", callback_data=f'admin_verify_reject_{v["verification_id"]}'),
        ])

    if not verifs:
        text += "Нет заявок ✅"
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='admin_panel')])
    await admin_edit(query, text, keyboard)


async def admin_broadcast_menu(query, context):
    db = get_db()
    total = db.execute('SELECT COUNT(*) as c FROM users WHERE is_blocked=0').fetchone()['c']
    premium = db.execute('SELECT COUNT(*) as c FROM users WHERE premium_status=1 AND is_blocked=0').fetchone()['c']
    db.close()
    text = (
        f"📢 Рассылка\n\n"
        f"👥 Всего активных: {total}\n"
        f"💎 Premium: {premium}\n\n"
        "Выберите аудиторию:"
    )
    keyboard = [
        [InlineKeyboardButton(f"📢 Всем ({total})", callback_data='admin_broadcast_all')],
        [InlineKeyboardButton(f"💎 Только Premium ({premium})", callback_data='admin_broadcast_premium')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='admin_panel')],
    ]
    await admin_edit(query, text, keyboard)


async def admin_logs(query, context):
    db = get_db()
    logs = db.execute(
        'SELECT l.action, l.details, l.created_at, u.username '
        'FROM logs l LEFT JOIN users u ON l.user_id=u.user_id '
        'ORDER BY l.created_at DESC LIMIT 15'
    ).fetchall()
    db.close()

    text = "📋 Последние 15 действий:\n\n"
    for l in logs:
        user = f"@{l['username']}" if l['username'] else "—"
        text += f"• {l['action']} {user}\n  {str(l['created_at'])[:16]}\n"

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='admin_panel')]]
    await admin_edit(query, text[:4000], keyboard)


async def admin_handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений от админа в режиме ввода"""
    if update.message.from_user.id != ADMIN_ID:
        return False

    state = context.user_data.get('admin_state')
    if not state:
        return False

    text = update.message.text.strip()
    context.user_data['admin_state'] = None

    # Блокировка пользователя
    if state.startswith('block_'):
        uid = int(state.replace('block_', ''))
        db = get_db()
        db.execute('UPDATE users SET is_blocked=1, block_reason=? WHERE user_id=?', (text, uid))
        db.commit()
        db.close()
        await update.message.reply_text(f"🚫 Пользователь {uid} заблокирован.\nПричина: {text}")
        return True

    # Изменение баланса
    if state.startswith('balance_'):
        uid = int(state.replace('balance_', ''))
        try:
            parts = text.split()
            op_str = parts[0]  # +1000, -500, =5000
            currency = parts[1].lower() if len(parts) > 1 else 'rub'
            op = op_str[0]
            amount = float(op_str[1:])
            col_map = {'rub': 'balance_rub', 'usd': 'balance_usd', 'ton': 'balance_ton', 'stars': 'balance_stars'}
            col = col_map.get(currency, 'balance_rub')
            db = get_db()
            if op == '+':
                db.execute(f'UPDATE users SET {col}={col}+? WHERE user_id=?', (amount, uid))
            elif op == '-':
                db.execute(f'UPDATE users SET {col}=MAX(0,{col}-?) WHERE user_id=?', (amount, uid))
            else:
                db.execute(f'UPDATE users SET {col}=? WHERE user_id=?', (amount, uid))
            db.execute('INSERT INTO transactions (user_id,type,amount,currency,status,description) VALUES (?,?,?,?,"completed","Admin adjustment")',
                       (uid, f'admin_{op}', amount, currency.upper()))
            db.commit()
            db.close()
            await update.message.reply_text(f"✅ Баланс пользователя {uid} обновлён: {op}{amount} {currency.upper()}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}\nФормат: +1000 rub")
        return True

    # Отправка сообщения пользователю
    if state.startswith('msg_'):
        uid = int(state.replace('msg_', ''))
        try:
            if os.path.exists(BANNER_PATH):
                with open(BANNER_PATH, 'rb') as photo:
                    await context.bot.send_photo(chat_id=uid, photo=photo, caption=text)
            else:
                await context.bot.send_message(chat_id=uid, text=text)
            await update.message.reply_text(f"✅ Сообщение отправлено пользователю {uid}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
        return True

    # Рассылка всем
    if state in ('broadcast_all', 'broadcast_premium'):
        db = get_db()
        query_str = 'SELECT user_id FROM users WHERE is_blocked=0'
        if state == 'broadcast_premium':
            query_str += ' AND premium_status=1'
        user_ids = [r['user_id'] for r in db.execute(query_str).fetchall()]
        db.close()

        await update.message.reply_text(f"📢 Запускаю рассылку для {len(user_ids)} пользователей...")
        sent, failed = 0, 0
        for uid in user_ids:
            try:
                if os.path.exists(BANNER_PATH):
                    with open(BANNER_PATH, 'rb') as photo:
                        await context.bot.send_photo(chat_id=uid, photo=photo, caption=text)
                else:
                    await context.bot.send_message(chat_id=uid, text=text)
                sent += 1
            except Exception:
                failed += 1
            import asyncio
            await asyncio.sleep(0.05)
        await update.message.reply_text(f"✅ Рассылка завершена!\nОтправлено: {sent}\nОшибок: {failed}")
        return True

    # Ответ на обращение
    if state.startswith('appeal_resolve_'):
        aid = int(state.replace('appeal_resolve_', ''))
        db = get_db()
        appeal = db.execute('SELECT user_id FROM appeals WHERE appeal_id=?', (aid,)).fetchone()
        db.execute('UPDATE appeals SET status="resolved", admin_response=?, resolved_at=CURRENT_TIMESTAMP WHERE appeal_id=?', (text, aid))
        db.commit()
        if appeal:
            try:
                msg = f"📨 Ответ на ваше обращение:\n\n{text}"
                if os.path.exists(BANNER_PATH):
                    with open(BANNER_PATH, 'rb') as photo:
                        await context.bot.send_photo(chat_id=appeal['user_id'], photo=photo, caption=msg)
                else:
                    await context.bot.send_message(chat_id=appeal['user_id'], text=msg)
            except Exception:
                pass
        db.close()
        await update.message.reply_text(f"✅ Ответ отправлен, обращение #{aid} закрыто.")
        return True

    # Отклонение верификации
    if state.startswith('verify_reject_'):
        vid = int(state.replace('verify_reject_', ''))
        db = get_db()
        v = db.execute('SELECT user_id FROM verifications WHERE verification_id=?', (vid,)).fetchone()
        db.execute('UPDATE verifications SET status="rejected", admin_comment=?, reviewed_at=CURRENT_TIMESTAMP WHERE verification_id=?', (text, vid))
        db.commit()
        if v:
            try:
                msg = f"❌ Ваша верификация отклонена.\nПричина: {text}"
                if os.path.exists(BANNER_PATH):
                    with open(BANNER_PATH, 'rb') as photo:
                        await context.bot.send_photo(chat_id=v['user_id'], photo=photo, caption=msg)
                else:
                    await context.bot.send_message(chat_id=v['user_id'], text=msg)
            except Exception:
                pass
        db.close()
        await update.message.reply_text(f"✅ Верификация #{vid} отклонена.")
        return True

    return False


def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден в .env файле!")
        return
    
    # Инициализируем базу данных
    print("Инициализация базы данных...")
    init_bot_db()
    print("✅ База данных готова!")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("freeteam", freeteam_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Запускаем бота
    print("✅ Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

async def show_faq(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает FAQ"""
    text = (
        "❓ Часто задаваемые вопросы\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Как создать сделку?\n"
        "  Нажмите 'Создать сделку', выберите тип товара, валюту, "
        "укажите сумму и описание. Система создаст ссылку для покупателя.\n\n"
        "2️⃣ Как работает гарант?\n"
        "  Покупатель переводит деньги гаранту. После проверки оплаты "
        "продавец передает товар. Гарант проверяет товар и переводит "
        "деньги продавцу, а товар - покупателю.\n\n"
        "3️⃣ Какие комиссии?\n"
        "  Стандарт: 1%, Премиум: 0.5%. Минимум 10 ₽.\n\n"
        "4️⃣ Как получить премиум-статус?\n"
        "  Нажмите 'Верификация' и подайте заявку. Администратор "
        "рассмотрит её в течение 24 часов.\n\n"
        "5️⃣ Сколько времени занимает сделка?\n"
        "  Обычно 10-30 минут. Зависит от скорости ответа участников.\n\n"
        "6️⃣ Что делать если возникла проблема?\n"
        "  Обратитесь в поддержку @LoIzTeamSupport или создайте "
        "обращение в разделе 'Обращения'.\n\n"
        "7️⃣ Как вывести деньги?\n"
        "  Перейдите в 'Реквизиты' → 'Вывод средств', выберите валюту "
        "и укажите сумму. Выплата в течение 24 часов.\n\n"
        "8️⃣ Безопасно ли это?\n"
        "  Да! Мы используем систему гарантов, шифрование данных и "
        "проверку всех участников.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Задать вопрос", url='https://t.me/LoIzTeamSupport')],
        [InlineKeyboardButton("🔙 Назад", callback_data='more_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_rules(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает правила сервиса"""
    text = (
        "📜 Правила сервиса Lolz Market\n\n"
        "✅ Разрешено:\n"
        "• Продажа цифровых товаров\n"
        "• Честная торговля\n"
        "• Использование гарантов\n"
        "• Обращение в поддержку\n\n"
        "❌ Запрещено:\n"
        "• Мошенничество и обман\n"
        "• Продажа запрещенных товаров\n"
        "• Оскорбления и угрозы\n"
        "• Обход системы гарантов\n"
        "• Создание фейковых аккаунтов\n"
        "• Спам и реклама\n\n"
        "⚖️ Ответственность:\n"
        "• За мошенничество - бан навсегда\n"
        "• За нарушение правил - предупреждение или бан\n"
        "• За спам - блокировка на 7 дней\n\n"
        "🛡 Гарантии:\n"
        "• Возврат средств при мошенничестве\n"
        "• Защита персональных данных\n"
        "• Конфиденциальность сделок\n\n"
        "📝 Условия использования:\n"
        "Используя сервис, вы соглашаетесь с правилами и "
        "обязуетесь их соблюдать. Администрация оставляет за "
        "собой право изменять правила без предупреждения."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Я согласен", callback_data='accept_rules')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='more_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_ref_history(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю реферальных выплат"""
    text = (
        "📊 История реферальных выплат\n\n"
        "💰 Всего заработано: 0.00 ₽\n"
        "📅 Последняя выплата: -\n\n"
        "📋 История выплат:\n"
        "У вас пока нет выплат.\n\n"
        "Приглашайте друзей и зарабатывайте 10% от комиссии "
        "с каждой их сделки!"
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='referrals')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_app_stats(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику пользователя"""
    
    # Получаем данные профиля
    total_deals = context.user_data.get('total_deals', 0)
    successful_deals = context.user_data.get('successful_deals', 0)
    cancelled_deals = context.user_data.get('cancelled_deals', 0)
    total_volume = context.user_data.get('total_volume', 0.00)
    rating = context.user_data.get('rating', 0.0)
    top_position = context.user_data.get('top_position', '-')
    registration_date = context.user_data.get('registration_date', '26.04.2026')
    
    success_rate = (successful_deals / total_deals * 100) if total_deals > 0 else 0
    cancel_rate = (cancelled_deals / total_deals * 100) if total_deals > 0 else 0
    
    text = (
        "📊 Ваша статистика\n\n"
        "📈 Общая информация:\n"
        f"• Всего сделок: {total_deals}\n"
        f"• Успешных: {successful_deals} ({success_rate:.1f}%)\n"
        f"• Отмененных: {cancelled_deals} ({cancel_rate:.1f}%)\n"
        f"• Общий оборот: {total_volume:,.2f} ₽\n"
        f"• Дата регистрации: {registration_date}\n\n"
        "💰 По валютам:\n"
        f"• RUB: {int(total_deals * 0.6)} сделок на {total_volume * 0.6:,.2f} ₽\n"
        f"• USD: {int(total_deals * 0.2)} сделок на {total_volume * 0.2 / 90:.2f} $\n"
        f"• TON: {int(total_deals * 0.15)} сделок на {total_volume * 0.15 / 500:.2f} TON\n"
        f"• Stars: {int(total_deals * 0.05)} сделок на {int(total_volume * 0.05 / 1.5)} ⭐\n\n"
        "📅 За последний месяц:\n"
        f"• Сделок: {int(total_deals * 0.2)}\n"
        f"• Оборот: {total_volume * 0.2:,.2f} ₽\n"
        f"• Средний чек: {(total_volume / total_deals) if total_deals > 0 else 0:,.2f} ₽\n\n"
        f"⭐ Рейтинг: {rating}/5.0\n"
        f"🏆 Место в топе: #{top_position}\n\n"
    )
    
    if total_deals == 0:
        text += "Совершите первую сделку, чтобы увидеть статистику!"
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='mini_apps')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_app_calculator(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает калькулятор комиссий"""
    text = (
        "💱 Калькулятор комиссий\n\n"
        "Рассчитайте комиссию для вашей сделки:\n\n"
        "📊 Тарифы:\n"
        "• Стандарт: 1% (минимум 10 ₽)\n"
        "• Премиум: 0.5% (минимум 10 ₽)\n\n"
        "💡 Примеры:\n\n"
        "Сделка на 1000 ₽:\n"
        "• Стандарт: 10 ₽ (1%)\n"
        "• Премиум: 10 ₽ (минимум)\n\n"
        "Сделка на 5000 ₽:\n"
        "• Стандарт: 50 ₽ (1%)\n"
        "• Премиум: 25 ₽ (0.5%)\n\n"
        "Сделка на 10000 ₽:\n"
        "• Стандарт: 100 ₽ (1%)\n"
        "• Премиум: 50 ₽ (0.5%)\n\n"
        "Сделка на 50000 ₽:\n"
        "• Стандарт: 500 ₽ (1%)\n"
        "• Премиум: 250 ₽ (0.5%)\n\n"
        "💎 Получите премиум-статус и экономьте на каждой сделке!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔐 Получить премиум", callback_data='verification')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='mini_apps')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def show_app_check(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает проверку пользователя"""
    context.user_data['deal_state'] = 'waiting_user_check'
    
    text = (
        "🔍 Проверка пользователя\n\n"
        "Введите username или ID пользователя для проверки:\n\n"
        "Например:\n"
        "• @username\n"
        "• 123456789\n\n"
        "Вы получите информацию о:\n"
        "• Количестве сделок\n"
        "• Рейтинге\n"
        "• Статусе верификации\n"
        "• Дате регистрации\n"
        "• Жалобах (если есть)"
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data='mini_apps')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)

async def handle_topup_confirmed(query, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подтверждения пополнения"""
    import asyncio
    
    await send_or_edit_with_banner(query, "⏳ Проверяем поступление платежа...\n\nПожалуйста, подождите.", None, context, is_query=True)
    
    await asyncio.sleep(5)
    
    keyboard = [
        [InlineKeyboardButton("⬅️ В главное меню", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "✅ Платеж получен!\n\n"
        "💰 Баланс успешно пополнен.\n"
        "Средства доступны для использования.\n\n"
        "Спасибо за использование Lolz Market!"
    )
    await send_or_edit_with_banner(query, text, reply_markup, context, is_query=True)
