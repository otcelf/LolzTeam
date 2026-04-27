"""
Админ-панель для Lolz Market Bot
Веб-интерфейс для управления ботом
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from functools import wraps
import sqlite3
import hashlib
import os
import csv
import io
import asyncio
import threading
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Конфигурация
DATABASE = 'bot_database.db'
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
BANNER_PATH = 'banner.jpg'

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class Admin(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return Admin(user_id)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cursor = db.cursor()
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            broadcast_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    db.commit()
    db.close()

def get_pending_counts():
    """Возвращает счётчики для сайдбара"""
    try:
        db = get_db()
        pending_appeals = db.execute('SELECT COUNT(*) as c FROM appeals WHERE status="open"').fetchone()['c']
        pending_verifications = db.execute('SELECT COUNT(*) as c FROM verifications WHERE status="pending"').fetchone()['c']
        db.close()
        return pending_appeals, pending_verifications
    except Exception:
        return 0, 0

def log_admin_action(action, details=''):
    try:
        db = get_db()
        db.execute('INSERT INTO logs (user_id, action, details, ip_address) VALUES (0, ?, ?, ?)',
                   (f'[ADMIN] {action}', details, request.remote_addr))
        db.commit()
        db.close()
    except Exception:
        pass


# ─── МАРШРУТЫ ───────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(Admin(1))
            flash('Успешный вход!', 'success')
            return redirect(url_for('dashboard'))
        flash('Неверные учетные данные', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/')
@admin_required
def dashboard():
    db = get_db()
    stats = {
        'total_users': db.execute('SELECT COUNT(*) as c FROM users').fetchone()['c'],
        'active_users': db.execute('SELECT COUNT(*) as c FROM users WHERE last_activity > datetime("now","-7 days")').fetchone()['c'],
        'premium_users': db.execute('SELECT COUNT(*) as c FROM users WHERE premium_status=1').fetchone()['c'],
        'verified_users': db.execute('SELECT COUNT(*) as c FROM users WHERE verified=1').fetchone()['c'],
        'total_deals': db.execute('SELECT COUNT(*) as c FROM deals').fetchone()['c'],
        'active_deals': db.execute('SELECT COUNT(*) as c FROM deals WHERE status="active"').fetchone()['c'],
        'completed_deals': db.execute('SELECT COUNT(*) as c FROM deals WHERE status="completed"').fetchone()['c'],
        'total_volume': db.execute('SELECT COALESCE(SUM(amount),0) as t FROM deals WHERE status="completed"').fetchone()['t'],
        'pending_appeals': db.execute('SELECT COUNT(*) as c FROM appeals WHERE status="open"').fetchone()['c'],
        'pending_verifications': db.execute('SELECT COUNT(*) as c FROM verifications WHERE status="pending"').fetchone()['c'],
        'new_users_today': db.execute('SELECT COUNT(*) as c FROM users WHERE DATE(registration_date)=DATE("now")').fetchone()['c'],
        'deals_today': db.execute('SELECT COUNT(*) as c FROM deals WHERE DATE(created_at)=DATE("now")').fetchone()['c'],
    }
    recent_users = db.execute('SELECT user_id,username,first_name,registration_date,premium_status,verified FROM users ORDER BY registration_date DESC LIMIT 10').fetchall()
    recent_deals = db.execute('''
        SELECT d.deal_id,d.product_type,d.amount,d.currency,d.status,d.created_at,
               u1.username as seller_username,u2.username as buyer_username
        FROM deals d
        LEFT JOIN users u1 ON d.seller_id=u1.user_id
        LEFT JOIN users u2 ON d.buyer_id=u2.user_id
        ORDER BY d.created_at DESC LIMIT 10
    ''').fetchall()
    activity_data = db.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM deals WHERE created_at > datetime("now","-7 days")
        GROUP BY DATE(created_at) ORDER BY date
    ''').fetchall()
    reg_data = db.execute('''
        SELECT DATE(registration_date) as date, COUNT(*) as count
        FROM users WHERE registration_date > datetime("now","-7 days")
        GROUP BY DATE(registration_date) ORDER BY date
    ''').fetchall()
    db.close()
    pa, pv = get_pending_counts()
    return render_template('dashboard.html', stats=stats, recent_users=recent_users,
                           recent_deals=recent_deals, activity_data=activity_data,
                           reg_data=reg_data, pending_appeals=pa, pending_verifications=pv)

@app.route('/users')
@admin_required
def users():
    db = get_db()
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    sort = request.args.get('sort', 'registration_date')
    order = request.args.get('order', 'DESC')
    page = max(1, int(request.args.get('page', 1)))
    per_page = 25

    allowed_sorts = ['registration_date','last_activity','total_deals','total_volume','rating','user_id']
    if sort not in allowed_sorts:
        sort = 'registration_date'
    if order not in ['ASC','DESC']:
        order = 'DESC'

    query = 'SELECT * FROM users WHERE 1=1'
    params = []
    if search:
        query += ' AND (username LIKE ? OR first_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?)'
        s = f'%{search}%'
        params += [s, s, s]
    if status == 'premium':
        query += ' AND premium_status=1'
    elif status == 'verified':
        query += ' AND verified=1'
    elif status == 'blocked':
        query += ' AND is_blocked=1'
    elif status == 'active':
        query += ' AND last_activity > datetime("now","-7 days")'

    total = db.execute(f'SELECT COUNT(*) as c FROM ({query})', params).fetchone()['c']
    query += f' ORDER BY {sort} {order} LIMIT ? OFFSET ?'
    params += [per_page, (page-1)*per_page]
    users_list = db.execute(query, params).fetchall()
    db.close()
    pa, pv = get_pending_counts()
    total_pages = (total + per_page - 1) // per_page
    return render_template('users.html', users=users_list, search=search, status=status,
                           sort=sort, order=order, page=page, total_pages=total_pages,
                           total=total, pending_appeals=pa, pending_verifications=pv)

@app.route('/user/<int:user_id>')
@admin_required
def user_detail(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone()
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('users'))
    deals = db.execute('''
        SELECT d.*,u1.username as seller_username,u2.username as buyer_username
        FROM deals d
        LEFT JOIN users u1 ON d.seller_id=u1.user_id
        LEFT JOIN users u2 ON d.buyer_id=u2.user_id
        WHERE d.seller_id=? OR d.buyer_id=?
        ORDER BY d.created_at DESC
    ''', (user_id, user_id)).fetchall()
    transactions = db.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 50', (user_id,)).fetchall()
    reviews = db.execute('''
        SELECT r.*,u.username as from_username FROM reviews r
        LEFT JOIN users u ON r.from_user_id=u.user_id
        WHERE r.to_user_id=? ORDER BY r.created_at DESC
    ''', (user_id,)).fetchall()
    appeals = db.execute('SELECT * FROM appeals WHERE user_id=? ORDER BY created_at DESC', (user_id,)).fetchall()
    logs = db.execute('SELECT * FROM logs WHERE user_id=? ORDER BY created_at DESC LIMIT 30', (user_id,)).fetchall()
    db.close()
    pa, pv = get_pending_counts()
    return render_template('user_detail.html', user=user, deals=deals, transactions=transactions,
                           reviews=reviews, appeals=appeals, logs=logs,
                           pending_appeals=pa, pending_verifications=pv)

@app.route('/deals')
@admin_required
def deals():
    db = get_db()
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    page = max(1, int(request.args.get('page', 1)))
    per_page = 25

    query = '''
        SELECT d.*,u1.username as seller_username,u1.user_id as s_id,
               u2.username as buyer_username,u2.user_id as b_id
        FROM deals d
        LEFT JOIN users u1 ON d.seller_id=u1.user_id
        LEFT JOIN users u2 ON d.buyer_id=u2.user_id
        WHERE 1=1
    '''
    params = []
    if search:
        query += ' AND (d.deal_id LIKE ? OR u1.username LIKE ? OR u2.username LIKE ?)'
        s = f'%{search}%'
        params += [s, s, s]
    if status != 'all':
        query += ' AND d.status=?'
        params.append(status)

    total = db.execute(f'SELECT COUNT(*) as c FROM ({query})', params).fetchone()['c']
    query += ' ORDER BY d.created_at DESC LIMIT ? OFFSET ?'
    params += [per_page, (page-1)*per_page]
    deals_list = db.execute(query, params).fetchall()
    db.close()
    pa, pv = get_pending_counts()
    total_pages = (total + per_page - 1) // per_page
    return render_template('deals.html', deals=deals_list, search=search, status=status,
                           page=page, total_pages=total_pages, total=total,
                           pending_appeals=pa, pending_verifications=pv)

@app.route('/deal/<deal_id>')
@admin_required
def deal_detail(deal_id):
    db = get_db()
    deal = db.execute('''
        SELECT d.*,
               u1.username as seller_username,u1.user_id as seller_id,u1.rating as seller_rating,
               u2.username as buyer_username,u2.user_id as buyer_id,u2.rating as buyer_rating
        FROM deals d
        LEFT JOIN users u1 ON d.seller_id=u1.user_id
        LEFT JOIN users u2 ON d.buyer_id=u2.user_id
        WHERE d.deal_id=?
    ''', (deal_id,)).fetchone()
    if not deal:
        flash('Сделка не найдена', 'error')
        return redirect(url_for('deals'))
    db.close()
    pa, pv = get_pending_counts()
    return render_template('deal_detail.html', deal=deal, pending_appeals=pa, pending_verifications=pv)

@app.route('/appeals')
@admin_required
def appeals():
    db = get_db()
    status = request.args.get('status', 'all')
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    query = '''
        SELECT a.*,u.username,u.user_id FROM appeals a
        LEFT JOIN users u ON a.user_id=u.user_id WHERE 1=1
    '''
    params = []
    if status != 'all':
        query += ' AND a.status=?'
        params.append(status)
    total = db.execute(f'SELECT COUNT(*) as c FROM ({query})', params).fetchone()['c']
    query += ' ORDER BY a.created_at DESC LIMIT ? OFFSET ?'
    params += [per_page, (page-1)*per_page]
    appeals_list = db.execute(query, params).fetchall()
    db.close()
    pa, pv = get_pending_counts()
    total_pages = (total + per_page - 1) // per_page
    return render_template('appeals.html', appeals=appeals_list, status=status,
                           page=page, total_pages=total_pages, total=total,
                           pending_appeals=pa, pending_verifications=pv)

@app.route('/verifications')
@admin_required
def verifications():
    db = get_db()
    status = request.args.get('status', 'pending')
    verifications_list = db.execute('''
        SELECT v.*,u.username,u.user_id,u.total_deals,u.rating FROM verifications v
        LEFT JOIN users u ON v.user_id=u.user_id
        WHERE v.status=? ORDER BY v.submitted_at DESC
    ''', (status,)).fetchall()
    db.close()
    pa, pv = get_pending_counts()
    return render_template('verifications.html', verifications=verifications_list, status=status,
                           pending_appeals=pa, pending_verifications=pv)

@app.route('/statistics')
@admin_required
def statistics():
    db = get_db()
    today = db.execute("SELECT COUNT(*) as deals,COALESCE(SUM(amount),0) as volume FROM deals WHERE DATE(created_at)=DATE('now')").fetchone()
    week = db.execute("SELECT COUNT(*) as deals,COALESCE(SUM(amount),0) as volume FROM deals WHERE created_at>datetime('now','-7 days')").fetchone()
    month = db.execute("SELECT COUNT(*) as deals,COALESCE(SUM(amount),0) as volume FROM deals WHERE created_at>datetime('now','-30 days')").fetchone()
    top_sellers = db.execute('SELECT user_id,username,total_deals,total_volume,rating FROM users WHERE total_deals>0 ORDER BY total_volume DESC LIMIT 10').fetchall()
    popular_products = db.execute("SELECT product_type,COUNT(*) as count,COALESCE(SUM(amount),0) as volume FROM deals WHERE status='completed' GROUP BY product_type ORDER BY count DESC").fetchall()
    currency_stats = db.execute("SELECT currency,COUNT(*) as count,COALESCE(SUM(amount),0) as volume FROM deals WHERE status='completed' GROUP BY currency").fetchall()
    daily_stats = db.execute('''
        SELECT DATE(created_at) as date,COUNT(*) as deals,COALESCE(SUM(amount),0) as volume
        FROM deals WHERE created_at>datetime('now','-30 days')
        GROUP BY DATE(created_at) ORDER BY date
    ''').fetchall()
    user_growth = db.execute('''
        SELECT DATE(registration_date) as date,COUNT(*) as count
        FROM users WHERE registration_date>datetime('now','-30 days')
        GROUP BY DATE(registration_date) ORDER BY date
    ''').fetchall()
    db.close()
    pa, pv = get_pending_counts()
    return render_template('statistics.html', today=today, week=week, month=month,
                           top_sellers=top_sellers, popular_products=popular_products,
                           currency_stats=currency_stats, daily_stats=daily_stats,
                           user_growth=user_growth, pending_appeals=pa, pending_verifications=pv)

@app.route('/logs')
@admin_required
def logs():
    db = get_db()
    page = max(1, int(request.args.get('page', 1)))
    per_page = 50
    search = request.args.get('search', '')
    query = 'SELECT l.*,u.username FROM logs l LEFT JOIN users u ON l.user_id=u.user_id WHERE 1=1'
    params = []
    if search:
        query += ' AND (l.action LIKE ? OR l.details LIKE ?)'
        s = f'%{search}%'
        params += [s, s]
    total = db.execute(f'SELECT COUNT(*) as c FROM ({query})', params).fetchone()['c']
    query += ' ORDER BY l.created_at DESC LIMIT ? OFFSET ?'
    params += [per_page, (page-1)*per_page]
    logs_list = db.execute(query, params).fetchall()
    db.close()
    pa, pv = get_pending_counts()
    total_pages = (total + per_page - 1) // per_page
    return render_template('logs.html', logs=logs_list, page=page, total_pages=total_pages,
                           total=total, search=search, pending_appeals=pa, pending_verifications=pv)

@app.route('/broadcast', methods=['GET', 'POST'])
@admin_required
def broadcast():
    db = get_db()
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        target = request.form.get('target', 'all')
        with_banner = request.form.get('with_banner', 'on') == 'on'
        if not message:
            flash('Сообщение не может быть пустым', 'error')
        else:
            db.execute('INSERT INTO broadcasts (message, status) VALUES (?, "pending")', (message,))
            db.commit()
            broadcast_id = db.execute('SELECT last_insert_rowid() as id').fetchone()['id']
            log_admin_action('broadcast_created', f'id={broadcast_id} target={target}')
            # Запускаем рассылку в фоне
            users_query = 'SELECT user_id FROM users WHERE is_blocked=0'
            if target == 'premium':
                users_query += ' AND premium_status=1'
            elif target == 'verified':
                users_query += ' AND verified=1'
            user_ids = [r['user_id'] for r in db.execute(users_query).fetchall()]
            thread = threading.Thread(
                target=run_broadcast,
                args=(broadcast_id, message, user_ids, with_banner),
                daemon=True
            )
            thread.start()
            flash(f'Рассылка запущена для {len(user_ids)} пользователей', 'success')
            db.close()
            return redirect(url_for('broadcast'))

    broadcasts_list = db.execute('SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT 20').fetchall()
    total_users = db.execute('SELECT COUNT(*) as c FROM users WHERE is_blocked=0').fetchone()['c']
    premium_users = db.execute('SELECT COUNT(*) as c FROM users WHERE premium_status=1 AND is_blocked=0').fetchone()['c']
    verified_users = db.execute('SELECT COUNT(*) as c FROM users WHERE verified=1 AND is_blocked=0').fetchone()['c']
    db.close()
    pa, pv = get_pending_counts()
    return render_template('broadcast.html', broadcasts=broadcasts_list,
                           total_users=total_users, premium_users=premium_users,
                           verified_users=verified_users,
                           pending_appeals=pa, pending_verifications=pv)

def run_broadcast(broadcast_id, message, user_ids, with_banner=True):
    """Запускает рассылку через Telegram Bot API"""
    import requests as req
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv('BOT_TOKEN', '')
    if not token:
        return
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            if with_banner and os.path.exists(BANNER_PATH):
                with open(BANNER_PATH, 'rb') as photo:
                    resp = req.post(
                        f'https://api.telegram.org/bot{token}/sendPhoto',
                        data={'chat_id': uid, 'caption': message},
                        files={'photo': photo},
                        timeout=10
                    )
            else:
                resp = req.post(
                    f'https://api.telegram.org/bot{token}/sendMessage',
                    json={'chat_id': uid, 'text': message},
                    timeout=10
                )
            if resp.status_code == 200:
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        import time
        time.sleep(0.05)  # ~20 msg/sec

    db = sqlite3.connect(DATABASE)
    db.execute('UPDATE broadcasts SET sent_count=?,failed_count=?,status="completed",completed_at=CURRENT_TIMESTAMP WHERE broadcast_id=?',
               (sent, failed, broadcast_id))
    db.commit()
    db.close()

@app.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    db = get_db()
    if request.method == 'POST':
        for key, value in request.form.items():
            db.execute('INSERT OR REPLACE INTO settings (key,value,updated_at) VALUES (?,?,CURRENT_TIMESTAMP)', (key, value))
        db.commit()
        log_admin_action('settings_updated')
        flash('Настройки сохранены', 'success')
    settings_data = {r['key']: r['value'] for r in db.execute('SELECT key,value FROM settings').fetchall()}
    db.close()
    pa, pv = get_pending_counts()
    return render_template('settings.html', settings=settings_data, pending_appeals=pa, pending_verifications=pv)


# ─── API ENDPOINTS ───────────────────────────────────────────────────────────

@app.route('/api/user/<int:user_id>/block', methods=['POST'])
@admin_required
def api_block_user(user_id):
    db = get_db()
    reason = request.json.get('reason', 'Нарушение правил')
    db.execute('UPDATE users SET is_blocked=1,block_reason=? WHERE user_id=?', (reason, user_id))
    db.commit()
    db.close()
    log_admin_action('user_blocked', f'user_id={user_id} reason={reason}')
    return jsonify({'success': True, 'message': 'Пользователь заблокирован'})

@app.route('/api/user/<int:user_id>/unblock', methods=['POST'])
@admin_required
def api_unblock_user(user_id):
    db = get_db()
    db.execute('UPDATE users SET is_blocked=0,block_reason=NULL WHERE user_id=?', (user_id,))
    db.commit()
    db.close()
    log_admin_action('user_unblocked', f'user_id={user_id}')
    return jsonify({'success': True, 'message': 'Пользователь разблокирован'})

@app.route('/api/user/<int:user_id>/premium', methods=['POST'])
@admin_required
def api_toggle_premium(user_id):
    db = get_db()
    data = request.json or {}
    action = data.get('action', 'grant')
    val = 1 if action == 'grant' else 0
    db.execute('UPDATE users SET premium_status=? WHERE user_id=?', (val, user_id))
    db.commit()
    db.close()
    log_admin_action(f'premium_{action}', f'user_id={user_id}')
    msg = 'Premium выдан' if val else 'Premium снят'
    return jsonify({'success': True, 'message': msg})

@app.route('/api/user/<int:user_id>/balance', methods=['POST'])
@admin_required
def api_adjust_balance(user_id):
    db = get_db()
    data = request.json or {}
    currency = data.get('currency', 'rub')
    amount = float(data.get('amount', 0))
    operation = data.get('operation', 'add')  # add / subtract / set
    col_map = {'rub': 'balance_rub', 'usd': 'balance_usd', 'ton': 'balance_ton', 'stars': 'balance_stars'}
    col = col_map.get(currency)
    if not col:
        return jsonify({'success': False, 'message': 'Неверная валюта'})
    if operation == 'add':
        db.execute(f'UPDATE users SET {col}={col}+? WHERE user_id=?', (amount, user_id))
    elif operation == 'subtract':
        db.execute(f'UPDATE users SET {col}=MAX(0,{col}-?) WHERE user_id=?', (amount, user_id))
    else:
        db.execute(f'UPDATE users SET {col}=? WHERE user_id=?', (amount, user_id))
    # Записываем транзакцию
    db.execute('INSERT INTO transactions (user_id,type,amount,currency,status,description) VALUES (?,?,?,?,"completed",?)',
               (user_id, f'admin_{operation}', amount, currency.upper(), f'Admin balance adjustment'))
    db.commit()
    db.close()
    log_admin_action('balance_adjusted', f'user_id={user_id} {operation} {amount} {currency}')
    return jsonify({'success': True, 'message': 'Баланс обновлён'})

@app.route('/api/user/<int:user_id>/edit', methods=['POST'])
@admin_required
def api_edit_user(user_id):
    db = get_db()
    data = request.json or {}
    allowed = ['username', 'first_name', 'last_name', 'rating', 'total_deals',
               'successful_deals', 'cancelled_deals', 'total_volume', 'referrals_count']
    sets = []
    vals = []
    for k, v in data.items():
        if k in allowed:
            sets.append(f'{k}=?')
            vals.append(v)
    if sets:
        vals.append(user_id)
        db.execute(f'UPDATE users SET {",".join(sets)} WHERE user_id=?', vals)
        db.commit()
    db.close()
    log_admin_action('user_edited', f'user_id={user_id} fields={list(data.keys())}')
    return jsonify({'success': True, 'message': 'Данные обновлены'})

@app.route('/api/deal/<deal_id>/status', methods=['POST'])
@admin_required
def api_change_deal_status(deal_id):
    db = get_db()
    data = request.json or {}
    new_status = data.get('status')
    allowed_statuses = ['created', 'active', 'paid', 'completed', 'cancelled']
    if new_status not in allowed_statuses:
        return jsonify({'success': False, 'message': 'Неверный статус'})
    ts_map = {
        'paid': 'paid_at=CURRENT_TIMESTAMP,',
        'completed': 'completed_at=CURRENT_TIMESTAMP,',
        'cancelled': 'cancelled_at=CURRENT_TIMESTAMP,'
    }
    extra = ts_map.get(new_status, '')
    db.execute(f'UPDATE deals SET {extra}status=? WHERE deal_id=?', (new_status, deal_id))
    db.commit()
    db.close()
    log_admin_action('deal_status_changed', f'deal_id={deal_id} status={new_status}')
    return jsonify({'success': True, 'message': f'Статус изменён на {new_status}'})

@app.route('/api/deal/<deal_id>/cancel', methods=['POST'])
@admin_required
def api_cancel_deal(deal_id):
    db = get_db()
    reason = (request.json or {}).get('reason', 'Отменено администратором')
    db.execute('UPDATE deals SET status="cancelled",cancelled_at=CURRENT_TIMESTAMP,cancel_reason=? WHERE deal_id=?',
               (reason, deal_id))
    db.commit()
    db.close()
    log_admin_action('deal_cancelled', f'deal_id={deal_id}')
    return jsonify({'success': True, 'message': 'Сделка отменена'})

@app.route('/api/verification/<int:verification_id>/approve', methods=['POST'])
@admin_required
def api_approve_verification(verification_id):
    db = get_db()
    v = db.execute('SELECT user_id FROM verifications WHERE verification_id=?', (verification_id,)).fetchone()
    if v:
        db.execute('UPDATE verifications SET status="approved",reviewed_at=CURRENT_TIMESTAMP WHERE verification_id=?', (verification_id,))
        db.execute('UPDATE users SET verified=1,premium_status=1 WHERE user_id=?', (v['user_id'],))
        db.commit()
        log_admin_action('verification_approved', f'verification_id={verification_id} user_id={v["user_id"]}')
    db.close()
    return jsonify({'success': True, 'message': 'Верификация одобрена'})

@app.route('/api/verification/<int:verification_id>/reject', methods=['POST'])
@admin_required
def api_reject_verification(verification_id):
    db = get_db()
    comment = (request.json or {}).get('comment', '')
    db.execute('UPDATE verifications SET status="rejected",reviewed_at=CURRENT_TIMESTAMP,admin_comment=? WHERE verification_id=?',
               (comment, verification_id))
    db.commit()
    db.close()
    log_admin_action('verification_rejected', f'verification_id={verification_id}')
    return jsonify({'success': True, 'message': 'Верификация отклонена'})

@app.route('/api/appeal/<int:appeal_id>/respond', methods=['POST'])
@admin_required
def api_respond_appeal(appeal_id):
    db = get_db()
    response = (request.json or {}).get('response', '')
    db.execute('UPDATE appeals SET admin_response=? WHERE appeal_id=?', (response, appeal_id))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'Ответ сохранён'})

@app.route('/api/appeal/<int:appeal_id>/in_progress', methods=['POST'])
@admin_required
def api_appeal_in_progress(appeal_id):
    db = get_db()
    db.execute('UPDATE appeals SET status="in_progress" WHERE appeal_id=?', (appeal_id,))
    db.commit()
    db.close()
    return jsonify({'success': True, 'message': 'В работе'})

@app.route('/api/appeal/<int:appeal_id>/resolve', methods=['POST'])
@admin_required
def api_resolve_appeal(appeal_id):
    db = get_db()
    response = (request.json or {}).get('response', '')
    db.execute('UPDATE appeals SET status="resolved",admin_response=?,resolved_at=CURRENT_TIMESTAMP WHERE appeal_id=?',
               (response, appeal_id))
    db.commit()
    db.close()
    log_admin_action('appeal_resolved', f'appeal_id={appeal_id}')
    return jsonify({'success': True, 'message': 'Обращение решено'})

@app.route('/api/send_message', methods=['POST'])
@admin_required
def api_send_message():
    """Отправить сообщение конкретному пользователю через бота (с баннером)"""
    import requests as req
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv('BOT_TOKEN', '')
    data = request.json or {}
    user_id = data.get('user_id')
    message = data.get('message', '').strip()
    with_banner = data.get('with_banner', True)
    if not token or not user_id or not message:
        return jsonify({'success': False, 'message': 'Не хватает данных'})
    try:
        if with_banner and os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, 'rb') as photo:
                resp = req.post(
                    f'https://api.telegram.org/bot{token}/sendPhoto',
                    data={'chat_id': user_id, 'caption': message},
                    files={'photo': photo},
                    timeout=10
                )
        else:
            resp = req.post(
                f'https://api.telegram.org/bot{token}/sendMessage',
                json={'chat_id': user_id, 'text': message},
                timeout=10
            )
        if resp.status_code == 200:
            log_admin_action('message_sent', f'to={user_id}')
            return jsonify({'success': True, 'message': 'Сообщение отправлено'})
        return jsonify({'success': False, 'message': f'Ошибка Telegram: {resp.text}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ─── ЭКСПОРТ CSV ─────────────────────────────────────────────────────────────

@app.route('/export/users')
@admin_required
def export_users():
    db = get_db()
    rows = db.execute('SELECT user_id,username,first_name,last_name,total_deals,successful_deals,rating,total_volume,premium_status,verified,is_blocked,registration_date,last_activity FROM users').fetchall()
    db.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Username','Имя','Фамилия','Сделок','Успешных','Рейтинг','Оборот','Premium','Верифицирован','Заблокирован','Регистрация','Активность'])
    for r in rows:
        writer.writerow(list(r))
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=users.csv'})

@app.route('/export/deals')
@admin_required
def export_deals():
    db = get_db()
    rows = db.execute('''
        SELECT d.deal_id,u1.username,u2.username,d.product_type,d.product_description,
               d.amount,d.currency,d.status,d.created_at,d.completed_at
        FROM deals d
        LEFT JOIN users u1 ON d.seller_id=u1.user_id
        LEFT JOIN users u2 ON d.buyer_id=u2.user_id
    ''').fetchall()
    db.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID сделки','Продавец','Покупатель','Тип','Описание','Сумма','Валюта','Статус','Создана','Завершена'])
    for r in rows:
        writer.writerow(list(r))
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=deals.csv'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
