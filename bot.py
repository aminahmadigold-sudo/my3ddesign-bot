# -*- coding: utf-8 -*-
"""
ربات تلگرامی مدیریت سفارش طراحی سه‌بعدی
- کاربران عکس می‌فرستند -> ذخیره می‌شه و یک شماره سفارش می‌گیره
- ادمین می‌تونه لیست سفارش‌ها رو ببینه، وضعیت رو تغییر بده
- ادمین فایل طراحی سه‌بعدی رو برای کاربر ارسال می‌کنه
"""

import os
import sqlite3
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------------- تنظیمات ----------------------
TOKEN = os.environ.get("BOT_TOKEN", "8783453906:AAFWugnyAmDqQiPSIiFL11g2JNDN9hW9ux4")
ADMIN_IDS = [1356831142]  # آیدی عددی تلگرام ادمین(ها)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDERS_DIR = os.path.join(BASE_DIR, "orders")
DB_PATH = os.path.join(BASE_DIR, "orders.db")

os.makedirs(ORDERS_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "in_progress": "در حال طراحی",
    "done": "آماده و ارسال شده",
    "rejected": "رد شده",
}

# ---------------------- دیتابیس ----------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            photo_path TEXT,
            note TEXT,
            status TEXT DEFAULT 'pending',
            result_path TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_order(user_id, username, full_name, photo_path, note=""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """INSERT INTO orders (user_id, username, full_name, photo_path, note, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (user_id, username, full_name, photo_path, note, now, now),
    )
    conn.commit()
    order_id = cur.lastrowid
    conn.close()
    return order_id


def get_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_orders(status=None, limit=20):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if status:
        cur.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        )
    else:
        cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_status(order_id, status):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, order_id),
    )
    conn.commit()
    conn.close()


def set_result_path(order_id, result_path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "UPDATE orders SET result_path = ?, status = 'done', updated_at = ? WHERE id = ?",
        (result_path, now, order_id),
    )
    conn.commit()
    conn.close()


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ---------------------- هندلرهای کاربر ----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋\n"
        "برای ثبت سفارش طراحی سه‌بعدی، فقط کافیه عکس مورد نظرتون رو همینجا بفرستید.\n"
        "می‌تونید همراه عکس، توضیح هم به عنوان کپشن اضافه کنید.\n\n"
        "برای پیگیری سفارش‌های خودتون از دستور /myorders استفاده کنید."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]
    file = await photo.get_file()

    caption = update.message.caption or ""
    ext = "jpg"
    filename = f"{user.id}_{photo.file_unique_id}.{ext}"
    save_path = os.path.join(ORDERS_DIR, filename)
    await file.download_to_drive(save_path)

    order_id = add_order(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name or "",
        photo_path=save_path,
        note=caption,
    )

    await update.message.reply_text(
        f"✅ سفارش شما با شماره #{order_id} ثبت شد.\n"
        f"وضعیت فعلی: {STATUS_LABELS['pending']}\n"
        "به محض آماده شدن طراحی سه‌بعدی، همینجا براتون ارسال می‌شه."
    )

    # اطلاع به همه ادمین‌ها
    admin_text = (
        f"📥 سفارش جدید #{order_id}\n"
        f"کاربر: {user.full_name} (@{user.username or '-'})\n"
        f"آیدی عددی: {user.id}\n"
        f"توضیح: {caption or '-'}"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("در حال طراحی", callback_data=f"status:{order_id}:in_progress"),
            InlineKeyboardButton("رد سفارش", callback_data=f"status:{order_id}:rejected"),
        ]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=open(save_path, "rb"),
                caption=admin_text,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"ارسال به ادمین {admin_id} ناموفق بود: {e}")


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        await update.message.reply_text("شما هنوز سفارشی ثبت نکردید.")
        return

    lines = ["📋 سفارش‌های شما:\n"]
    for r in rows:
        lines.append(f"#{r['id']} — {STATUS_LABELS.get(r['status'], r['status'])} — {r['created_at']}")
    await update.message.reply_text("\n".join(lines))


# ---------------------- هندلرهای ادمین ----------------------

async def admin_only_guard(update: Update) -> bool:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین قابل استفاده است.")
        return False
    return True


async def orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return

    status_filter = None
    if context.args:
        status_filter = context.args[0]

    rows = list_orders(status=status_filter)
    if not rows:
        await update.message.reply_text("سفارشی یافت نشد.")
        return

    lines = ["📋 لیست سفارش‌ها:\n"]
    for r in rows:
        lines.append(
            f"#{r['id']} | {r['full_name']} (@{r['username'] or '-'}) | "
            f"{STATUS_LABELS.get(r['status'], r['status'])} | {r['created_at']}"
        )
    lines.append("\nراهنما: /order <شماره> برای جزئیات")
    await update.message.reply_text("\n".join(lines))


async def order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return

    if not context.args:
        await update.message.reply_text("استفاده: /order <شماره سفارش>")
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شماره سفارش نامعتبر است.")
        return

    order = get_order(order_id)
    if not order:
        await update.message.reply_text("سفارشی با این شماره یافت نشد.")
        return

    text = (
        f"سفارش #{order['id']}\n"
        f"کاربر: {order['full_name']} (@{order['username'] or '-'})\n"
        f"آیدی عددی: {order['user_id']}\n"
        f"وضعیت: {STATUS_LABELS.get(order['status'], order['status'])}\n"
        f"توضیح: {order['note'] or '-'}\n"
        f"تاریخ ثبت: {order['created_at']}\n"
        f"آخرین بروزرسانی: {order['updated_at']}\n\n"
        f"برای ارسال فایل طراحی نهایی، همین فایل رو ریپلای کنید با متن:\n"
        f"/deliver {order['id']}"
    )
    if order["photo_path"] and os.path.exists(order["photo_path"]):
        await update.message.reply_photo(photo=open(order["photo_path"], "rb"), caption=text)
    else:
        await update.message.reply_text(text)


async def deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ادمین یک فایل (سند/عکس) رو ریپلای می‌کنه و دستور /deliver <order_id> می‌زنه"""
    if not await admin_only_guard(update):
        return

    if not context.args:
        await update.message.reply_text("استفاده: این پیام باید ریپلای روی فایل طراحی باشه.\n/deliver <شماره سفارش>")
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شماره سفارش نامعتبر است.")
        return

    order = get_order(order_id)
    if not order:
        await update.message.reply_text("سفارشی با این شماره یافت نشد.")
        return

    replied = update.message.reply_to_message
    if not replied or not (replied.document or replied.photo):
        await update.message.reply_text(
            "باید این دستور رو روی یک پیام حاوی فایل (سند یا عکس) ریپلای کنید."
        )
        return

    # دانلود فایل نتیجه در سرور خودمون برای آرشیو
    if replied.document:
        tg_file = await replied.document.get_file()
        ext = os.path.splitext(replied.document.file_name or "result.stl")[1] or ".stl"
    else:
        tg_file = await replied.photo[-1].get_file()
        ext = ".jpg"

    result_filename = f"result_{order_id}{ext}"
    result_path = os.path.join(ORDERS_DIR, result_filename)
    await tg_file.download_to_drive(result_path)
    set_result_path(order_id, result_path)

    # ارسال برای مشتری
    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"🎉 طراحی سه‌بعدی سفارش #{order_id} شما آماده شد!",
        )
        if replied.document:
            await context.bot.send_document(chat_id=order["user_id"], document=open(result_path, "rb"))
        else:
            await context.bot.send_photo(chat_id=order["user_id"], photo=open(result_path, "rb"))
        await update.message.reply_text(f"✅ فایل با موفقیت برای مشتری سفارش #{order_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال به مشتری: {e}")


async def set_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only_guard(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "استفاده: /setstatus <شماره سفارش> <pending|in_progress|done|rejected>"
        )
        return
    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شماره سفارش نامعتبر است.")
        return
    status = context.args[1]
    if status not in STATUS_LABELS:
        await update.message.reply_text(f"وضعیت نامعتبر. گزینه‌ها: {', '.join(STATUS_LABELS)}")
        return
    update_status(order_id, status)
    await update.message.reply_text(f"وضعیت سفارش #{order_id} به «{STATUS_LABELS[status]}» تغییر کرد.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data  # format: status:order_id:new_status
    _, order_id, new_status = data.split(":")
    update_status(int(order_id), new_status)
    await query.edit_message_caption(
        caption=(query.message.caption or "") + f"\n\n✅ وضعیت به‌روزرسانی شد: {STATUS_LABELS.get(new_status, new_status)}"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await update.message.reply_text(
            "دستورات ادمین:\n"
            "/orders [status] - لیست سفارش‌ها\n"
            "/order <id> - جزئیات یک سفارش\n"
            "/setstatus <id> <status> - تغییر وضعیت\n"
            "/deliver <id> - (ریپلای روی فایل) ارسال طراحی نهایی به مشتری\n\n"
            f"وضعیت‌های معتبر: {', '.join(STATUS_LABELS.keys())}"
        )
    else:
        await update.message.reply_text(
            "برای ثبت سفارش، عکس مورد نظرتون رو بفرستید.\n"
            "/myorders برای دیدن وضعیت سفارش‌های خودتون."
        )


# ---------------------- main ----------------------

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # کاربر عادی
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myorders", my_orders))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # ادمین
    app.add_handler(CommandHandler("orders", orders_list))
    app.add_handler(CommandHandler("order", order_detail))
    app.add_handler(CommandHandler("setstatus", set_status_command))
    app.add_handler(CommandHandler("deliver", deliver))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
