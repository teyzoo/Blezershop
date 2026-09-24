import asyncio
import os
import sqlite3
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()
DB_PATH = os.getenv("DB_PATH", "/data/blezer.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not OWNER_ID_RAW.isdigit():
    raise RuntimeError("OWNER_ID is not set or invalid")

OWNER_ID = int(OWNER_ID_RAW)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admins (
            telegram_id INTEGER PRIMARY KEY,
            added_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            price_rub INTEGER NOT NULL,
            price_stars INTEGER NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            amount_rub INTEGER NOT NULL,
            amount_stars INTEGER NOT NULL,
            status TEXT NOT NULL,
            payment_method TEXT,
            code_requests INTEGER NOT NULL DEFAULT 0,
            product_code TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_percent INTEGER NOT NULL DEFAULT 0,
            discount_rub INTEGER NOT NULL DEFAULT 0,
            max_uses INTEGER NOT NULL DEFAULT 0,
            uses INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    conn.commit()
    conn.close()


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def add_user(message: Message):
    user = message.from_user

    conn = db()
    conn.execute(
        """
        INSERT INTO users
        (telegram_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """,
        (
            user.id,
            user.username,
            user.first_name,
            now(),
        ),
    )
    conn.commit()
    conn.close()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True

    conn = db()
    row = conn.execute(
        "SELECT telegram_id FROM admins WHERE telegram_id=?",
        (user_id,),
    ).fetchone()
    conn.close()

    return row is not None


def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Купить",
                    callback_data="shop",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Мои покупки",
                    callback_data="orders",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎟 Промокод",
                    callback_data="promo",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Поддержка",
                    callback_data="support",
                )
            ],
        ]
    )


def back_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="home",
                )
            ]
        ]
    )


def admin_menu():
    rows = [
        [
            InlineKeyboardButton(
                text="📦 Товары",
                callback_data="admin_products",
            ),
            InlineKeyboardButton(
                text="💳 Платежи",
                callback_data="admin_payments",
            ),
        ],
        [
            InlineKeyboardButton(
                text="👨‍💼 Администраторы",
                callback_data="admin_admins",
            ),
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data="admin_stats",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🎟 Промокоды",
                callback_data="admin_promos",
            ),
            InlineKeyboardButton(
                text="⚙️ Настройки",
                callback_data="admin_settings",
            ),
        ],
        [
            InlineKeyboardButton(
                text="⬅️ В магазин",
                callback_data="home",
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ============================================================
# START
# ============================================================

@dp.message(Command("start"))
async def start(message: Message):
    add_user(message)

    text = (
        "🛍 <b>BLEZER SHOP</b>\n\n"
        "Добро пожаловать в наш магазин!\n\n"
        "Здесь вы можете приобрести доступные товары, "
        "выбрать нужный вариант и удобный способ оплаты."
    )

    await message.answer(
        text,
        reply_markup=main_menu(),
    )


# ============================================================
# HOME
# ============================================================

@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "🛍 <b>BLEZER SHOP</b>\n\n"
        "Добро пожаловать в наш магазин!\n\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu(),
    )


# ============================================================
# SHOP
# ============================================================

@dp.callback_query(F.data == "shop")
async def shop(callback: CallbackQuery):
    await callback.answer()

    conn = db()
    countries = conn.execute(
        """
        SELECT DISTINCT country
        FROM products
        WHERE active=1 AND stock>0
        ORDER BY country
        """
    ).fetchall()
    conn.close()

    if not countries:
        await callback.message.edit_text(
            "🛒 <b>Магазин</b>\n\n"
            "Сейчас доступных товаров нет.",
            reply_markup=back_menu(),
        )
        return

    buttons = []

    for row in countries:
        country = row["country"]

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🌍 {country}",
                    callback_data=f"country:{country}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="home",
            )
        ]
    )

    await callback.message.edit_text(
        "🛒 <b>Выберите страну</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )


@dp.callback_query(F.data.startswith("country:"))
async def country(callback: CallbackQuery):
    await callback.answer()

    country_name = callback.data.split(":", 1)[1]

    conn = db()
    products = conn.execute(
        """
        SELECT *
        FROM products
        WHERE country=? AND active=1 AND stock>0
        ORDER BY id DESC
        """,
        (country_name,),
    ).fetchall()
    conn.close()

    buttons = []

    for product in products:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"📦 {product['title']} — "
                        f"{product['price_rub']} ₽"
                    ),
                    callback_data=f"product:{product['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="shop",
            )
        ]
    )

    await callback.message.edit_text(
        f"🌍 <b>{country_name}</b>\n\n"
        "Выберите товар:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )


# ============================================================
# PRODUCT
# ============================================================

@dp.callback_query(F.data.startswith("product:"))
async def product(callback: CallbackQuery):
    await callback.answer()

    product_id = int(callback.data.split(":", 1)[1])

    conn = db()
    item = conn.execute(
        "SELECT * FROM products WHERE id=?",
        (product_id,),
    ).fetchone()
    conn.close()

    if not item or not item["active"] or item["stock"] <= 0:
        await callback.message.edit_text(
            "❌ Этот товар сейчас недоступен.",
            reply_markup=back_menu(),
        )
        return

    text = (
        f"📦 <b>{item['title']}</b>\n\n"
        f"🌍 Страна: {item['country']}\n"
        f"💰 Цена: {item['price_rub']} ₽\n"
        f"⭐ Stars: {item['price_stars']}\n"
        f"📦 В наличии: {item['stock']}\n"
    )

    if item["description"]:
        text += f"\n📝 {item['description']}\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Купить",
                    callback_data=f"buy:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"country:{item['country']}",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
    )


# ============================================================
# BUY
# ============================================================

@dp.callback_query(F.data.startswith("buy:"))
async def buy(callback: CallbackQuery):
    await callback.answer()

    product_id = int(callback.data.split(":", 1)[1])

    conn = db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id=? AND active=1 AND stock>0
        """,
        (product_id,),
    ).fetchone()

    if not product:
        conn.close()

        await callback.message.edit_text(
            "❌ Товар уже закончился.",
            reply_markup=back_menu(),
        )
        return

    cursor = conn.execute(
        """
        INSERT INTO orders
        (
            user_id,
            product_id,
            quantity,
            amount_rub,
            amount_stars,
            status,
            created_at
        )
        VALUES (?, ?, 1, ?, ?, 'awaiting_payment', ?)
        """,
        (
            callback.from_user.id,
            product_id,
            product["price_rub"],
            product["price_stars"],
            now(),
        ),
    )

    order_id = cursor.lastrowid

    conn.execute(
        """
        UPDATE products
        SET stock=stock-1
        WHERE id=? AND stock>0
        """,
        (product_id,),
    )

    conn.commit()
    conn.close()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Оплатить Stars",
                    callback_data=f"stars:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Оплатить переводом",
                    callback_data=f"bank:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="shop",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        f"🧾 <b>Заказ #{order_id}</b>\n\n"
        f"📦 {product['title']}\n"
        f"💰 {product['price_rub']} ₽\n"
        f"⭐ {product['price_stars']} Stars\n\n"
        "Выберите способ оплаты:",
        reply_markup=keyboard,
    )


# ============================================================
# STARS
# ============================================================

@dp.callback_query(F.data.startswith("stars:"))
async def stars(callback: CallbackQuery):
    await callback.answer()

    order_id = int(callback.data.split(":", 1)[1])

    conn = db()
    order = conn.execute(
        """
        SELECT o.*, p.title
        FROM orders o
        JOIN products p ON p.id=o.product_id
        WHERE o.id=? AND o.user_id=?
        """,
        (order_id, callback.from_user.id),
    ).fetchone()
    conn.close()

    if not order:
        await callback.message.edit_text(
            "❌ Заказ не найден.",
            reply_markup=back_menu(),
        )
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Blezer Shop — {order['title']}",
        description=f"Оплата заказа #{order_id}",
        payload=f"order:{order_id}",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Товар",
                amount=order["amount_stars"],
            )
        ],
    )


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payment = message.successful_payment

    if not payment:
        return

    payload = payment.invoice_payload

    if not payload.startswith("order:"):
        return

    order_id = int(payload.split(":", 1)[1])

    conn = db()

    order = conn.execute(
        "SELECT * FROM orders WHERE id=?",
        (order_id,),
    ).fetchone()

    if order:
        conn.execute(
            """
            UPDATE orders
            SET status='paid',
                payment_method='stars'
            WHERE id=?
            """,
            (order_id,),
        )
        conn.commit()

    conn.close()

    await message.answer(
        f"✅ <b>Оплата получена</b>\n\n"
        f"Заказ #{order_id} оплачен.\n"
        "Откройте «Мои покупки», чтобы посмотреть заказ."
    )


# ============================================================
# BANK PAYMENT
# ============================================================

@dp.callback_query(F.data.startswith("bank:"))
async def bank(callback: CallbackQuery):
    await callback.answer()

    order_id = int(callback.data.split(":", 1)[1])

    conn = db()
    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id=? AND user_id=?
        """,
        (order_id, callback.from_user.id),
    ).fetchone()

    bank_name = conn.execute(
        "SELECT value FROM settings WHERE key='bank_name'"
    ).fetchone()

    recipient = conn.execute(
        "SELECT value FROM settings WHERE key='bank_recipient'"
    ).fetchone()

    card = conn.execute(
        "SELECT value FROM settings WHERE key='bank_card'"
    ).fetchone()

    conn.close()

    if not order:
        await callback.message.edit_text(
            "❌ Заказ не найден.",
            reply_markup=back_menu(),
        )
        return

    bank_name = bank_name["value"] if bank_name else "Не настроено"
    recipient = recipient["value"] if recipient else "Не настроено"
    card = card["value"] if card else "Не настроено"

    await callback.message.edit_text(
        "💳 <b>ОПЛАТА ПЕРЕВОДОМ</b>\n\n"
        f"🧾 Заказ: #{order_id}\n"
        f"💰 К оплате: {order['amount_rub']} ₽\n\n"
        f"🏦 Банк: {bank_name}\n"
        f"👤 Получатель: {recipient}\n"
        f"💳 Номер карты: {card}\n\n"
        "После перевода нажмите кнопку ниже "
        "и отправьте PDF-чек из приложения банка.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📄 Я оплатил",
                        callback_data=f"paid:{order_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"checkout:{order_id}",
                    )
                ],
            ]
        ),
    )


@dp.callback_query(F.data.startswith("paid:"))
async def paid(callback: CallbackQuery):
    await callback.answer()

    order_id = int(callback.data.split(":", 1)[1])

    conn = db()
    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE id=? AND user_id=?
        """,
        (order_id, callback.from_user.id),
    ).fetchone()
    conn.close()

    if not order:
        await callback.message.edit_text(
            "❌ Заказ не найден.",
            reply_markup=back_menu(),
        )
        return

    await callback.message.edit_text(
        f"📄 <b>Заказ #{order_id}</b>\n\n"
        "Отправьте сюда PDF-чек из приложения банка.",
        reply_markup=back_menu(),
    )


@dp.message(F.document)
async def bank_receipt(message: Message):
    if not message.document:
        return

    if message.document.mime_type != "application/pdf":
        return

    conn = db()

    order = conn.execute(
        """
        SELECT *
        FROM orders
        WHERE user_id=?
        AND status='awaiting_payment'
        ORDER BY id DESC
        LIMIT 1
        """,
        (message.from_user.id,),
    ).fetchone()

    if not order:
        conn.close()
        return

    conn.execute(
        """
        UPDATE orders
        SET status='payment_check',
            payment_method='bank'
        WHERE id=?
        """,
        (order["id"],),
    )

    conn.commit()
    conn.close()

    await message.answer(
        f"📄 Чек получен.\n\n"
        f"Заказ #{order['id']} отправлен на проверку.\n"
        "После проверки вы получите уведомление."
    )

    if is_admin(message.from_user.id):
        return

    await bot.send_message(
        OWNER_ID,
        f"💳 <b>Новый платёж на проверку</b>\n\n"
        f"Заказ: #{order['id']}\n"
        f"Пользователь: {message.from_user.id}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=f"approve:{order['id']}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"reject:{order['id']}",
                    ),
                ]
            ]
        ),
    )

    await bot.send_document(
        OWNER_ID,
        message.document.file_id,
    )


# ============================================================
# MY ORDERS
# ============================================================

@dp.callback_query(F.data == "orders")
async def orders(callback: CallbackQuery):
    await callback.answer()

    conn = db()
    rows = conn.execute(
        """
        SELECT o.*, p.title
        FROM orders o
        JOIN products p ON p.id=o.product_id
        WHERE o.user_id=?
        ORDER BY o.id DESC
        LIMIT 20
        """,
        (callback.from_user.id,),
    ).fetchall()
    conn.close()

    if not rows:
        await callback.message.edit_text(
            "📦 <b>Мои покупки</b>\n\n"
            "У вас пока нет заказов.",
            reply_markup=back_menu(),
        )
        return

    text = "📦 <b>Мои покупки</b>\n\n"

    for order in rows:
        text += (
            f"🧾 #{order['id']} — {order['title']}\n"
            f"💰 {order['amount_rub']} ₽\n"
            f"📌 {order['status']}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=back_menu(),
    )


# ============================================================
# PROMO
# ============================================================

@dp.callback_query(F.data == "promo")
async def promo(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "🎟 <b>Промокод</b>\n\n"
        "Введите промокод следующим сообщением.",
        reply_markup=back_menu(),
    )


# ============================================================
# SUPPORT
# ============================================================

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "💬 <b>Поддержка</b>\n\n"
        "Напишите ваш вопрос, предложение или сообщение "
        "следующим сообщением.\n\n"
        "Сообщение будет передано администрации.",
        reply_markup=back_menu(),
    )


@dp.message()
async def text_message(message: Message):
    if not message.text:
        return

    if message.text.startswith("/"):
        return

    conn = db()

    conn.execute(
        """
        INSERT INTO support_messages
        (user_id, text, status, created_at)
        VALUES (?, ?, 'new', ?)
        """,
        (
            message.from_user.id,
            message.text,
            now(),
        ),
    )

    conn.commit()
    conn.close()

    await message.answer(
        "💬 Сообщение отправлено администрации."
    )

    await bot.send_message(
        OWNER_ID,
        "💬 <b>Новое сообщение в поддержку</b>\n\n"
        f"👤 Пользователь: {message.from_user.id}\n\n"
        f"{message.text}",
    )


# ============================================================
# ADMIN
# ============================================================

@dp.message(Command("admin"))
async def admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    title = (
        "👑 <b>OWNER PANEL</b>"
        if is_owner(message.from_user.id)
        else "👨‍💼 <b>ADMIN PANEL</b>"
    )

    await message.answer(
        title + "\n\nВыберите раздел:",
        reply_markup=admin_menu(),
    )


# ============================================================
# ADMIN — STATS
# ============================================================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    conn = db()

    users = conn.execute(
        "SELECT COUNT(*) AS c FROM users"
    ).fetchone()["c"]

    orders_count = conn.execute(
        "SELECT COUNT(*) AS c FROM orders"
    ).fetchone()["c"]

    paid = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM orders
        WHERE status='paid'
        """
    ).fetchone()["c"]

    revenue = conn.execute(
        """
        SELECT COALESCE(SUM(amount_rub), 0) AS total
        FROM orders
        WHERE status='paid'
        """
    ).fetchone()["total"]

    conn.close()

    await callback.answer()

    await callback.message.edit_text(
        "📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 Пользователи: {users}\n"
        f"🧾 Заказы: {orders_count}\n"
        f"✅ Оплачено: {paid}\n"
        f"💰 Выручка: {revenue} ₽",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin_back",
                    )
                ]
            ]
        ),
    )


# ============================================================
# ADMIN — ADMINS
# ============================================================

@dp.callback_query(F.data == "admin_admins")
async def admin_admins(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer(
            "Только владелец",
            show_alert=True,
        )
        return

    conn = db()

    rows = conn.execute(
        """
        SELECT telegram_id
        FROM admins
        ORDER BY telegram_id
        """
    ).fetchall()

    conn.close()

    text = "👨‍💼 <b>АДМИНИСТРАТОРЫ</b>\n\n"

    if rows:
        for row in rows:
            text += f"• <code>{row['telegram_id']}</code>\n"
    else:
        text += "Администраторов пока нет.\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить",
                    callback_data="add_admin",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin_back",
                )
            ],
        ]
    )

    await callback.answer()
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
    )


@dp.callback_query(F.data == "add_admin")
async def add_admin(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer(
            "Только владелец",
            show_alert=True,
        )
        return

    await callback.answer()

    await callback.message.edit_text(
        "👨‍💼 <b>Добавление администратора</b>\n\n"
        "Отправьте Telegram ID пользователя следующим сообщением.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin_admins",
                    )
                ]
            ]
        ),
    )


# ============================================================
# ADMIN — PRODUCTS
# ============================================================

@dp.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Доступ запрещён",
            show_alert=True,
        )
        return

    conn = db()

    count = conn.execute(
        "SELECT COUNT(*) AS c FROM products"
    ).fetchone()["c"]

    available = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM products
        WHERE active=1 AND stock>0
        """
    ).fetchone()["c"]

    conn.close()

    await callback.answer()

    await callback.message.edit_text(
        "📦 <b>ТОВАРЫ</b>\n\n"
        f"Всего позиций: {count}\n"
        f"Доступных: {available}\n\n"
        "Управление товарами будет доступно здесь.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin_back",
                    )
                ]
            ]
        ),
    )


# ============================================================
# ADMIN — PAYMENTS
# ============================================================

@dp.callback_query(F.data == "admin_payments")
async def admin_payments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Доступ запрещён",
            show_alert=True,
        )
        return

    conn = db()

    rows = conn.execute(
        """
        SELECT id, user_id, amount_rub, status
        FROM orders
        WHERE status='payment_check'
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    text = "💳 <b>ПЛАТЕЖИ НА ПРОВЕРКЕ</b>\n\n"

    if not rows:
        text += "Новых платежей нет."

    for row in rows:
        text += (
            f"🧾 #{row['id']}\n"
            f"👤 {row['user_id']}\n"
            f"💰 {row['amount_rub']} ₽\n\n"
        )

    await callback.answer()

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="admin_back",
                    )
                ]
            ]
        ),
    )


# ============================================================
# APPROVE / REJECT PAYMENT
# ============================================================

@dp.callback_query(F.data.startswith("approve:"))
async def approve_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Доступ запрещён",
            show_alert=True,
        )
        return

    order_id = int(callback.data.split(":", 1)[1])

    conn = db()

    order = conn.execute(
        "SELECT * FROM orders WHERE id=?",
        (order_id,),
    ).fetchone()

    if order:
        conn.execute(
            """
            UPDATE orders
            SET status='paid'
            WHERE id=?
            """,
            (order_id,),
        )
        conn.commit()

    conn.close()

    await callback.answer("Платёж подтверждён")

    if order:
        await bot.send_message(
            order["user_id"],
            f"✅ <b>Оплата заказа #{order_id} подтверждена.</b>\n\n"
            "Заказ готов к дальнейшей обработке.",
        )

    await callback.message.edit_text(
        f"✅ Платёж заказа #{order_id} подтверждён."
    )


@dp.callback_query(F.data.startswith("reject:"))
async def reject_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Доступ запрещён",
            show_alert=True,
        )
        return

    order_id = int(callback.data.split(":", 1)[1])

    conn = db()

    order = conn.execute(
        "SELECT * FROM orders WHERE id=?",
        (order_id,),
    ).fetchone()

    if order:
        conn.execute(
            """
            UPDATE orders
            SET status='payment_rejected'
            WHERE id=?
            """,
            (order_id,),
        )
        conn.commit()

    conn.close()

    await callback.answer("Платёж отклонён")

    if order:
        await bot.send_message(
            order["user_id"],
            f"❌ <b>Платёж заказа #{order_id} отклонён.</b>",
        )

    await callback.message.edit_text(
        f"❌ Платёж заказа #{order_id} отклонён."
    )


# ============================================================
# ADMIN BACK
# ============================================================

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "Доступ запрещён",
            show_alert=True,
        )
        return

    await callback.answer()

    title = (
        "👑 <b>OWNER PANEL</b>"
        if is_owner(callback.from_user.id)
        else "👨‍💼 <b>ADMIN PANEL</b>"
    )

    await callback.message.edit_text(
        title + "\n\nВыберите раздел:",
        reply_markup=admin_menu(),
    )


# ============================================================
# STARTUP
# ============================================================

async def main():
    init_db()

    logging.info("Blezer Shop started")
    logging.info("Owner ID: %s", OWNER_ID)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
