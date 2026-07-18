# -*- coding: utf-8 -*-
"""
ربات تلگرامی مدیریت سفارش طراحی سه‌بعدی — نسخه کامل
ویژگی‌ها:
- عضویت اجباری در کانال قبل از استفاده
- ثبت خودکار کاربر (با آیدی تلگرام)
- منوی دکمه‌ای پایین صفحه برای مشتری
- ثبت سفارش: عکس -> سوال پرینت سه‌بعدی -> جزئیات (در صورت نیاز)
- ادمین: نوتیف سفارش جدید + امکان تعیین قیمت و ارسال به مشتری
- پنل ادمین با دکمه‌های داشبورد: سفارش‌های جدید / تکمیل‌شده / همه
"""

import os
import sqlite3
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------------------- تنظیمات ----------------------
TOKEN = os.environ.get("BOT_TOKEN", "8783453906:AAFWugnyAmDqQiPSIiFL11g2JNDN9hW9ux4")
ADMIN_IDS = [1356831142]
CHANNEL_USERNAME = "@AvineGroup0"  # کانال اجباری برای عضویت

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDERS_DIR = os.path.join(BASE_DIR, "orders")
DB_PATH = os.path.join(BASE_DIR, "orders.db")
os.makedirs(ORDERS_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "pending": "در انتظار بررسی",
    "priced": "قیمت ارسال شده",
    "in_progress": "در حال طراحی",
    "done": "تکمیل شده",
    "rejected": "رد شده",
}

# مراحل مکالمه ثبت سفارش
ASK_PRINT, ASK_DETAILS = range(2)
# مرحله دریافت قیمت از ادمین
ASK_PRICE = 10

# ---------------------- کیبوردها ----------------------

CUSTOMER_MENU = ReplyKeyboardMarkup(
    [["🆕 ثبت سفارش جدید"], ["📋 سفارش‌های من"], ["ℹ️ راهنما"]],
    resize_keyboard=True,
)

ADMIN_MENU = ReplyKeyboardMarkup(
    [
        ["📥 سفارش‌های جدید", "✅ سفارش‌های تکمیل‌شده"],
        ["📋 همه سفارش‌ها"],
    ],
    resize_keyboard=True,
)

PRINT_QUESTION_KB = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("بله، پرینت هم می‌خوام", callback_data="print:yes"),
            InlineKeyboardButton("نه، فقط طراحی", callback_data="print:no"),
        ]
    ]
)

# ---------------------- دیتابیس ----------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            joined_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            photo_path TEXT,
            wants_print INTEGER DEFAULT 0,
            print_details TEXT,
            price TEXT,
            status TEXT DEFAULT 'pending',
            result_path TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def upsert_user(user_id, username, full_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cur.fetchone():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO users (user_id, username, full_name, joined_at) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, now),
        )
        conn.commit()
    conn.close()


def add_order(user_id, username, full_name, photo_path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        """INSERT INTO orders (user_id, username, full_name, photo_path, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
        (user_id, username, full_name, photo_path, now, now),
    )
    conn.commit()
    order_id = cur.lastrowid
    conn.close()
    return order_id


def update_order(order_id, **fields):
    if not fields:
        return
    fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [order_id]
    cur.execute(f"UPDATE orders SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


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


def is_admin(user_id):
    return user_id in ADMIN_IDS


# ---------------------- بررسی عضویت کانال ----------------------

async def is_channel_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status not in ("left", "kicked")
    except Exception as e:
        logger.warning(f"خطا در بررسی عضویت کانال: {e}")
        return False


def join_channel_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
            [InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_join")],
        ]
    )


async def require_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """اگه ادمین باشه نیازی به چک نیست"""
    user = update.effective_user
    if is_admin(user.id):
        return True
    if await is_channel_member(context, user.id):
        return True
    await update.effective_message.reply_text(
        "برای استفاده از ربات، اول باید عضو کانال ما بشید:",
        reply_markup=join_channel_keyboard(),
    )
    return False


# ---------------------- شروع ----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username or "", user.full_name or "")

    if is_admin(user.id):
        await update.message.reply_text(
            f"سلام {user.first_name} 👋\nپنل مدیریت فعاله.", reply_markup=ADMIN_MENU
        )
        return

    if not await require_membership(update, context):
        return

    await update.message.reply_text(
        "سلام 👋 خوش اومدید!\n"
        "از منوی پایین می‌تونید سفارش طراحی سه‌بعدی ثبت کنید یا وضعیت سفارش‌های قبلیتون رو ببینید.",
        reply_markup=CUSTOMER_MENU,
    )


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    if await is_channel_member(context, user.id):
        await query.answer("عضویت تایید شد ✅")
        await query.edit_message_text("عضویت شما تایید شد ✅ حالا می‌تونید از ربات استفاده کنید.")
        await context.bot.send_message(
            chat_id=user.id, text="از منوی پایین شروع کنید:", reply_markup=CUSTOMER_MENU
        )
    else:
        await query.answer("هنوز عضو کانال نشدید!", show_alert=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        await update.message.reply_text(
            "دستورات/دکمه‌های ادمین:\n"
            "📥 سفارش‌های جدید — لیست سفارش‌های در انتظار بررسی\n"
            "✅ سفارش‌های تکمیل‌شده — لیست سفارش‌های done\n"
            "📋 همه سفارش‌ها — همه‌ی سفارش‌ها\n"
            "روی هر سفارش بزنید تا جزئیات و گزینه‌های تعیین قیمت/تحویل رو ببینید."
        )
    else:
        await update.message.reply_text(
            "🆕 ثبت سفارش جدید — ارسال عکس برای سفارش طراحی سه‌بعدی\n"
            "📋 سفارش‌های من — دیدن وضعیت سفارش‌های قبلی"
        )


# ---------------------- فلوی ثبت سفارش (مشتری) ----------------------

async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_membership(update, context):
        return ConversationHandler.END
    await update.message.reply_text("لطفاً عکس مورد نظر برای طراحی سه‌بعدی رو بفرستید 📷")
    return ASK_PRINT  # منتظر عکس می‌مونیم، بعد سراغ سوال پرینت می‌ریم


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]
    file = await photo.get_file()

    filename = f"{user.id}_{photo.file_unique_id}.jpg"
    save_path = os.path.join(ORDERS_DIR, filename)
    await file.download_to_drive(save_path)

    context.user_data["pending_photo_path"] = save_path

    await update.message.reply_text(
        "آیا علاوه بر طراحی سه‌بعدی، پرینت سه‌بعدیش رو هم می‌خواید انجام بدیم؟",
        reply_markup=PRINT_QUESTION_KB,
    )
    return ASK_DETAILS


async def print_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":")[1]  # yes / no

    photo_path = context.user_data.get("pending_photo_path")
    if not photo_path:
        await query.edit_message_text("مشکلی پیش اومد، لطفاً دوباره از منو شروع کنید.")
        return ConversationHandler.END

    user = query.from_user

    if choice == "yes":
        context.user_data["wants_print"] = True
        await query.edit_message_text("لطفاً جزئیات پرینت رو بنویسید (سایز، جنس، تعداد و ...):")
        return ASK_DETAILS
    else:
        context.user_data["wants_print"] = False
        order_id = finalize_order(user, photo_path, wants_print=False, details="")
        await query.edit_message_text(f"✅ سفارش شما با شماره #{order_id} ثبت شد.")
        await notify_admins_new_order(context, order_id)
        context.user_data.clear()
        return ConversationHandler.END


async def print_details_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_path = context.user_data.get("pending_photo_path")
    if not photo_path:
        await update.message.reply_text("مشکلی پیش اومد، لطفاً دوباره از منو شروع کنید.", reply_markup=CUSTOMER_MENU)
        return ConversationHandler.END

    details = update.message.text
    user = update.effective_user
    order_id = finalize_order(user, photo_path, wants_print=True, details=details)

    await update.message.reply_text(
        f"✅ سفارش شما با شماره #{order_id} (همراه با پرینت) ثبت شد.", reply_markup=CUSTOMER_MENU
    )
    await notify_admins_new_order(context, order_id)
    context.user_data.clear()
    return ConversationHandler.END


def finalize_order(user, photo_path, wants_print, details):
    order_id = add_order(user.id, user.username or "", user.full_name or "", photo_path)
    update_order(order_id, wants_print=1 if wants_print else 0, print_details=details)
    return order_id


async def notify_admins_new_order(context: ContextTypes.DEFAULT_TYPE, order_id: int):
    order = get_order(order_id)
    print_text = "بله" if order["wants_print"] else "خیر"
    text = (
        f"📥 سفارش جدید #{order_id}\n"
        f"کاربر: {order['full_name']} (@{order['username'] or '-'})\n"
        f"آیدی عددی: {order['user_id']}\n"
        f"پرینت سه‌بعدی: {print_text}\n"
        f"جزئیات: {order['print_details'] or '-'}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 تعیین قیمت", callback_data=f"setprice:{order_id}")],
            [InlineKeyboardButton("🔧 در حال طراحی", callback_data=f"status:{order_id}:in_progress")],
        ]
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=open(order["photo_path"], "rb"),
                caption=text,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"ارسال به ادمین {admin_id} ناموفق بود: {e}")


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = update.effective_user
    menu = ADMIN_MENU if is_admin(user.id) else CUSTOMER_MENU
    await update.message.reply_text("لغو شد.", reply_markup=menu)
    return ConversationHandler.END


# ---------------------- سفارش‌های من (مشتری) ----------------------

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_membership(update, context):
        return
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        await update.message.reply_text("شما هنوز سفارشی ثبت نکردید.")
        return

    lines = ["📋 سفارش‌های شما:\n"]
    for r in rows:
        price_text = f" — قیمت: {r['price']}" if r["price"] else ""
        lines.append(f"#{r['id']} — {STATUS_LABELS.get(r['status'], r['status'])}{price_text}")
    await update.message.reply_text("\n".join(lines))


# ---------------------- پنل ادمین ----------------------

async def admin_orders_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await send_orders_list(update, status="pending")


async def admin_orders_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await send_orders_list(update, status="done")


async def admin_orders_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await send_orders_list(update, status=None)


async def send_orders_list(update: Update, status):
    rows = list_orders(status=status)
    if not rows:
        await update.message.reply_text("سفارشی یافت نشد.")
        return

    buttons = []
    for r in rows:
        label = f"#{r['id']} | {r['full_name']} | {STATUS_LABELS.get(r['status'], r['status'])}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"view:{r['id']}")])

    await update.message.reply_text(
        "روی هر سفارش بزنید تا جزئیاتش رو ببینید:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def view_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    order_id = int(query.data.split(":")[1])
    order = get_order(order_id)
    if not order:
        await query.message.reply_text("سفارش یافت نشد.")
        return

    print_text = "بله" if order["wants_print"] else "خیر"
    text = (
        f"سفارش #{order['id']}\n"
        f"کاربر: {order['full_name']} (@{order['username'] or '-'})\n"
        f"آیدی عددی: {order['user_id']}\n"
        f"وضعیت: {STATUS_LABELS.get(order['status'], order['status'])}\n"
        f"پرینت سه‌بعدی: {print_text}\n"
        f"جزئیات: {order['print_details'] or '-'}\n"
        f"قیمت: {order['price'] or 'تعیین نشده'}\n"
        f"تاریخ ثبت: {order['created_at']}\n\n"
        f"برای ارسال فایل طراحی نهایی، این پیام رو ریپلای کنید با متن:\n/deliver {order['id']}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 تعیین/تغییر قیمت", callback_data=f"setprice:{order_id}")],
            [
                InlineKeyboardButton("🔧 در حال طراحی", callback_data=f"status:{order_id}:in_progress"),
                InlineKeyboardButton("❌ رد سفارش", callback_data=f"status:{order_id}:rejected"),
            ],
        ]
    )
    if order["photo_path"] and os.path.exists(order["photo_path"]):
        await query.message.reply_photo(photo=open(order["photo_path"], "rb"), caption=text, reply_markup=keyboard)
    else:
        await query.message.reply_text(text, reply_markup=keyboard)


async def status_change_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    _, order_id, new_status = query.data.split(":")
    update_order(int(order_id), status=new_status)
    await query.message.reply_text(f"وضعیت سفارش #{order_id} به «{STATUS_LABELS.get(new_status, new_status)}» تغییر کرد.")


# ---------------------- تعیین قیمت ----------------------

async def setprice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    order_id = int(query.data.split(":")[1])
    context.user_data["awaiting_price_for"] = order_id
    await query.message.reply_text(f"قیمت سفارش #{order_id} رو بنویسید (مثلاً: 1500000 تومان):")
    return ASK_PRICE


async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("awaiting_price_for")
    if not order_id:
        return ConversationHandler.END

    price_text = update.message.text
    order = get_order(order_id)
    if not order:
        await update.message.reply_text("سفارش یافت نشد.")
        return ConversationHandler.END

    update_order(order_id, price=price_text, status="priced")

    try:
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"💰 قیمت سفارش #{order_id} شما: {price_text}\nبرای تایید و ادامه کار با ما در ارتباط باشید.",
        )
        await update.message.reply_text(f"✅ قیمت برای مشتری سفارش #{order_id} ارسال شد.", reply_markup=ADMIN_MENU)
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال قیمت به مشتری: {e}")

    context.user_data.clear()
    return ConversationHandler.END


# ---------------------- تحویل فایل نهایی ----------------------

async def deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
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
        await update.message.reply_text("باید این دستور رو روی یک پیام حاوی فایل ریپلای کنید.")
        return

    if replied.document:
        tg_file = await replied.document.get_file()
        ext = os.path.splitext(replied.document.file_name or "result.stl")[1] or ".stl"
    else:
        tg_file = await replied.photo[-1].get_file()
        ext = ".jpg"

    result_path = os.path.join(ORDERS_DIR, f"result_{order_id}{ext}")
    await tg_file.download_to_drive(result_path)
    update_order(order_id, result_path=result_path, status="done")

    try:
        await context.bot.send_message(chat_id=order["user_id"], text=f"🎉 طراحی سه‌بعدی سفارش #{order_id} شما آماده شد!")
        if replied.document:
            await context.bot.send_document(chat_id=order["user_id"], document=open(result_path, "rb"))
        else:
            await context.bot.send_photo(chat_id=order["user_id"], photo=open(result_path, "rb"))
        await update.message.reply_text(f"✅ فایل برای مشتری سفارش #{order_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال به مشتری: {e}")


# ---------------------- main ----------------------

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # مکالمه ثبت سفارش مشتری
    order_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🆕 ثبت سفارش جدید$"), new_order_start)],
        states={
            ASK_PRINT: [MessageHandler(filters.PHOTO, photo_received)],
            ASK_DETAILS: [
                CallbackQueryHandler(print_choice_callback, pattern=r"^print:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, print_details_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    # مکالمه تعیین قیمت (ادمین)
    price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(setprice_callback, pattern=r"^setprice:")],
        states={
            ASK_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("deliver", deliver))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(view_order_callback, pattern=r"^view:"))
    app.add_handler(CallbackQueryHandler(status_change_callback, pattern=r"^status:"))

    app.add_handler(order_conv)
    app.add_handler(price_conv)

    app.add_handler(MessageHandler(filters.Regex("^📋 سفارش‌های من$"), my_orders))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ راهنما$"), help_command))
    app.add_handler(MessageHandler(filters.Regex("^📥 سفارش‌های جدید$"), admin_orders_new))
    app.add_handler(MessageHandler(filters.Regex("^✅ سفارش‌های تکمیل‌شده$"), admin_orders_done))
    app.add_handler(MessageHandler(filters.Regex("^📋 همه سفارش‌ها$"), admin_orders_all))

    logger.info("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
