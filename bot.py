"""
╔══════════════════════════════════════════╗
║   POSTCHANNEL BOT — Bot API 9.4 EDITION  ║
║   Built by ENI for LO 💕                 ║
╚══════════════════════════════════════════╝
"""

import asyncio
import json
import os
import uuid
import ssl
import aiohttp
from datetime import datetime
from typing import Optional

# ─── SSL FIX (провайдер режет TLS к Telegram) ────────────────────────────────
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE
# TCPConnector создаётся внутри async-функций, не здесь!

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8415596205:AAHxvAXbAm12Ki7db4elld3bF8WpMftkSxY")
CHANNEL_ID  = "@postchannelanonc"           # канал для проверки подписки
CHANNEL_URL = "https://t.me/postchannelanonc"

# Premium emoji IDs используемые в боте
EMO_WELCOME    = "5413694143601842851"   # приветствие
EMO_THANKS     = "5456149049214249060"   # спасибо за подписку
EMO_CHOOSE     = "5280881372418816002"   # выберите действие
EMO_WHAT_POST  = "5449875850046481967"   # что выкладываем / опубликовать?

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ─── HISTORY STORAGE (in-memory + JSON persistence) ──────────────────────────
HISTORY_FILE = "history.json"

def load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(data: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# { user_id: [ {id, type, text, buttons, media_url, created_at, channel_posted} ] }
history: dict = load_history()

# ─── USER STATE MACHINE ───────────────────────────────────────────────────────
user_states: dict = {}
user_drafts: dict = {}

# ─── HTTP HELPERS ─────────────────────────────────────────────────────────────

async def api_call(method: str, payload: dict) -> dict:
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_ctx)) as s:
        async with s.post(f"{API}/{method}", json=payload) as r:
            return await r.json()

async def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await api_call("sendMessage", payload)


async def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await api_call("editMessageText", payload)

async def answer_callback(callback_id: str, text: str = "", alert: bool = False):
    await api_call("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": alert,
    })

async def check_subscription(user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на CHANNEL_ID"""
    r = await api_call("getChatMember", {
        "chat_id": CHANNEL_ID,
        "user_id": user_id,
    })
    if r.get("ok"):
        status = r["result"]["status"]
        return status in ("member", "administrator", "creator", "restricted")
    return False

# ─── KEYBOARD BUILDERS ────────────────────────────────────────────────────────

def kb_subscribe():
    """Кнопка подписки + кнопка проверки"""
    return {
        "inline_keyboard": [
            [{"text": "📢 Подписаться на канал", "url": CHANNEL_URL}],
            [{"text": "✅ Проверить подписку", "callback_data": "check_sub",
              "style": "success"}],
        ]
    }

def kb_main_menu(has_channel: bool):
    """Главное меню после подписки"""
    rows = []
    if has_channel:
        rows.append([
            {
                "text": "✏️ Сделать пост",
                "callback_data": "make_post",
                "style": "primary",
                "icon_custom_emoji_id": "5285430309720966085",
            },
            {
                "text": "📋 История",
                "callback_data": "history",
                "icon_custom_emoji_id": "5285032475490273112",
            },
        ])
        rows.append([
            {
                "text": "🤝 Поддержка",
                "callback_data": "support",
                "style": "danger",
                "icon_custom_emoji_id": "5310169226856644648",
            }
        ])
    else:
        rows.append([
            {
                "text": "🤝 Поддержка",
                "callback_data": "support",
                "style": "danger",
                "icon_custom_emoji_id": "5310169226856644648",
            }
        ])
        rows.append([
            {
                "text": "➕ Добавить бота в канал",
                "callback_data": "add_channel",
                "style": "success",
                "icon_custom_emoji_id": "5310076249404621168",
            }
        ])
    return {"inline_keyboard": rows}

def kb_post_types():
    return {
        "inline_keyboard": [
            [
                {"text": "💬 Сообщение",  "callback_data": "pt_text",    "style": "primary"},
                {"text": "🎉 Конкурс",    "callback_data": "pt_contest"},
            ],
            [
                {"text": "🎬 Гифку",      "callback_data": "pt_gif"},
                {"text": "🖼 Фотку",      "callback_data": "pt_photo"},
                {"text": "🎥 Видео",      "callback_data": "pt_video"},
            ],
            [{"text": "« Назад", "callback_data": "main_menu"}],
        ]
    }

def kb_add_button_or_skip(is_contest=False):
    if is_contest:
        return {
            "inline_keyboard": [
                [{"text": "➡️ Продолжить (без доп. кнопок)", "callback_data": "skip_buttons", "style": "primary"}],
                [{"text": "« Назад", "callback_data": "choose_post_type"}],
            ]
        }
    return {
        "inline_keyboard": [
            [{"text": "➕ Добавить кнопку", "callback_data": "add_button", "style": "success"}],
            [{"text": "➡️ Продолжить", "callback_data": "skip_buttons", "style": "primary"}],
            [{"text": "« Назад", "callback_data": "choose_post_type"}],
        ]
    }

def kb_button_colors():
    return {
        "inline_keyboard": [
            [
                {"text": "🔵 Синяя (primary)",   "callback_data": "btncolor_primary",  "style": "primary"},
                {"text": "🟢 Зелёная (success)", "callback_data": "btncolor_success",  "style": "success"},
            ],
            [
                {"text": "🔴 Красная (danger)",  "callback_data": "btncolor_danger",   "style": "danger"},
                {"text": "⚪️ Стандартная",       "callback_data": "btncolor_default"},
            ],
        ]
    }

def kb_confirm_publish():
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Да, опубликовать!", "callback_data": "publish_yes", "style": "success",
                 "icon_custom_emoji_id": "5310076249404621168"},
                {"text": "💾 Сохранить в историю", "callback_data": "publish_no"},
            ],
            [{"text": "« Назад", "callback_data": "choose_post_type"}],
        ]
    }

def kb_history_list(user_id: int):
    items = history.get(str(user_id), [])
    if not items:
        return None
    rows = []
    for item in items[-10:]:  # последние 10
        label = f"[{item['type'].upper()}] {item['text'][:25]}..."
        rows.append([{"text": label, "callback_data": f"hist_{item['id']}"}])
    rows.append([{"text": "« Назад", "callback_data": "main_menu"}])
    return {"inline_keyboard": rows}

def kb_history_item(item_id: str):
    return {
        "inline_keyboard": [
            [
                {"text": "📤 Опубликовать",  "callback_data": f"hpub_{item_id}", "style": "success"},
                {"text": "✏️ Редактировать", "callback_data": f"hedit_{item_id}"},
            ],
            [{"text": "🗑 Удалить", "callback_data": f"hdel_{item_id}", "style": "danger"}],
            [{"text": "« История",  "callback_data": "history"}],
        ]
    }

# ─── PREMIUM EMOJI TAG ────────────────────────────────────────────────────────

def pe(emoji_id: str, fallback: str = "⭐") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# ─── HANDLERS ─────────────────────────────────────────────────────────────────

async def handle_start(chat_id: int, user_id: int):
    user_states[user_id] = "await_sub"
    text = (
        f"{pe(EMO_WELCOME, '👋')} <b>Добро пожаловать в бота!</b>\n\n"
        f"Подпишись на канал, чтобы пользоваться ботом!"
    )
    await send_message(chat_id, text, reply_markup=kb_subscribe())

async def handle_check_sub(chat_id: int, user_id: int, callback_id: str, message_id: int):
    await answer_callback(callback_id, "Проверяю подписку...")
    subscribed = await check_subscription(user_id)
    if not subscribed:
        await answer_callback(callback_id, "❌ Ты ещё не подписан(а)!", alert=True)
        return

    # Подписан — показываем благодарность
    await edit_message(
        chat_id, message_id,
        f"{pe(EMO_THANKS, '🙏')} <b>Спасибо за подписку на канал!</b>",
        reply_markup=None,
    )
    await asyncio.sleep(1)

    has_channel = user_states.get(f"{user_id}_channel", False)

    await send_message(
        chat_id,
        f"{pe(EMO_CHOOSE, '🎯')} <b>Выберите действие:</b>",
        reply_markup=kb_main_menu(has_channel),
    )
    user_states[user_id] = "idle"

async def handle_main_menu(chat_id: int, user_id: int, callback_id: str, message_id: int):
    await answer_callback(callback_id)
    has_channel = user_states.get(f"{user_id}_channel", False)
    await edit_message(
        chat_id, message_id,
        f"{pe(EMO_CHOOSE, '🎯')} <b>Выберите действие:</b>",
        reply_markup=kb_main_menu(has_channel),
    )
    user_states[user_id] = "idle"

async def handle_add_channel(chat_id: int, user_id: int, callback_id: str, message_id: int):
    await answer_callback(callback_id)
    await edit_message(
        chat_id, message_id,
        "➕ <b>Добавить бота в канал</b>\n\n"
        "1. Зайдите в настройки вашего канала\n"
        "2. Перейдите в <b>Администраторы</b>\n"
        "3. Нажмите <b>Добавить администратора</b>\n"
        "4. Найдите и добавьте этого бота\n\n"
        "После добавления — отправьте мне <b>@username</b> вашего канала:",
    )
    user_states[user_id] = "await_channel"

async def handle_support(chat_id: int, callback_id: str, message_id: int):
    await answer_callback(callback_id)
    await edit_message(
        chat_id, message_id,
        "🤝 <b>Поддержка</b>\n\n"
        "Если у тебя возникли проблемы или вопросы — напиши нам:\n"
        f"👉 {CHANNEL_URL}\n\n"
        "Мы постараемся ответить как можно скорее! 💪",
        reply_markup={
            "inline_keyboard": [
                [{"text": "📢 Написать в канал", "url": CHANNEL_URL}],
                [{"text": "« Назад", "callback_data": "main_menu"}],
            ]
        }
    )

async def handle_make_post(chat_id: int, user_id: int, callback_id: str, message_id: int):
    await answer_callback(callback_id)
    user_drafts[user_id] = {"type": None, "text": "", "buttons": [], "media_file_id": None}
    await edit_message(
        chat_id, message_id,
        f"{pe(EMO_WHAT_POST, '📝')} <b>Что будем выкладывать?</b>",
        reply_markup=kb_post_types(),
    )
    user_states[user_id] = "choose_post_type"

async def handle_post_type(chat_id: int, user_id: int, callback_id: str, message_id: int, ptype: str):
    await answer_callback(callback_id)
    user_drafts.setdefault(user_id, {})
    user_drafts[user_id]["type"] = ptype
    user_drafts[user_id]["buttons"] = []

    type_names = {
        "text": "💬 Сообщение",
        "contest": "🎉 Конкурс",
        "gif": "🎬 Гифка",
        "photo": "🖼 Фотка",
        "video": "🎥 Видео",
    }
    name = type_names.get(ptype, ptype)

    if ptype in ("gif", "photo", "video"):
        await edit_message(
            chat_id, message_id,
            f"📎 <b>{name}</b>\n\nОтправь мне файл ({ptype}) — я его приму!",
            reply_markup={"inline_keyboard": [[{"text": "« Назад", "callback_data": "choose_post_type"}]]}
        )
        user_states[user_id] = f"await_media_{ptype}"
    else:
        await edit_message(
            chat_id, message_id,
            f"✏️ <b>{name}</b>\n\nНапиши текст для поста (поддерживается HTML-разметка):",
            reply_markup={"inline_keyboard": [[{"text": "« Назад", "callback_data": "choose_post_type"}]]}
        )
        user_states[user_id] = "await_text"

async def handle_text_input(chat_id: int, user_id: int, text: str):
    state = user_states.get(user_id, "idle")

    if state == "await_channel":
        channel = text.strip()
        if not channel.startswith("@"):
            channel = "@" + channel
        r = await api_call("getChat", {"chat_id": channel})
        if r.get("ok"):
            user_states[f"{user_id}_channel"] = channel
            user_states[user_id] = "idle"
            has_channel = True
            await send_message(
                chat_id,
                f"✅ Канал <b>{channel}</b> успешно привязан!\n\n"
                f"{pe(EMO_CHOOSE, '🎯')} <b>Выберите действие:</b>",
                reply_markup=kb_main_menu(has_channel),
            )
        else:
            await send_message(
                chat_id,
                "❌ Не могу найти канал или бот не добавлен как администратор.\n"
                "Убедись, что бот добавлен в канал как <b>администратор</b>, и попробуй снова:",
            )
        return

    if state == "await_text":
        user_drafts[user_id]["text"] = text
        ptype = user_drafts[user_id].get("type", "text")
        is_contest = ptype == "contest"
        await send_message(
            chat_id,
            "🎛 <b>Кнопки для поста</b>\n\n" +
            ("Для конкурса автоматически добавится кнопка «Принять участие».\n"
             "Хочешь продолжить?" if is_contest else
             "Хочешь добавить кнопки к посту?\n"
             "Каждая кнопка может иметь цвет и ссылку."),
            reply_markup=kb_add_button_or_skip(is_contest),
        )
        user_states[user_id] = "await_buttons_decision"
        return

    if state == "await_button_text":
        user_drafts[user_id]["_btn_draft"] = {"text": text}
        await send_message(
            chat_id,
            f"🎨 <b>Выбери цвет кнопки</b> «{text}»:",
            reply_markup=kb_button_colors(),
        )
        user_states[user_id] = "await_button_color"
        return

    if state == "await_button_url":
        btn = user_drafts[user_id].get("_btn_draft", {})
        btn["url"] = text.strip()
        user_drafts[user_id]["buttons"].append(btn)
        user_drafts[user_id].pop("_btn_draft", None)

        buttons = user_drafts[user_id]["buttons"]
        await send_message(
            chat_id,
            f"✅ Кнопка добавлена! Всего кнопок: <b>{len(buttons)}</b>\n\n"
            "Добавить ещё одну кнопку или продолжить?",
            reply_markup=kb_add_button_or_skip(),
        )
        user_states[user_id] = "await_buttons_decision"
        return

async def handle_add_button(chat_id: int, user_id: int, callback_id: str):
    await answer_callback(callback_id)
    await send_message(
        chat_id,
        "✏️ <b>Напиши текст для кнопки:</b>",
    )
    user_states[user_id] = "await_button_text"

async def handle_button_color(chat_id: int, user_id: int, callback_id: str, style: str, message_id: int):
    await answer_callback(callback_id)
    if "_btn_draft" not in user_drafts.get(user_id, {}):
        user_drafts.setdefault(user_id, {})["_btn_draft"] = {}
    user_drafts[user_id]["_btn_draft"]["style"] = style
    await edit_message(
        chat_id, message_id,
        "🔗 <b>Отправь ссылку для кнопки</b> (например: https://t.me/yourbot):",
    )
    user_states[user_id] = "await_button_url"

async def handle_skip_buttons(chat_id: int, user_id: int, callback_id: str, message_id: int):
    await answer_callback(callback_id)
    draft = user_drafts.get(user_id, {})
    ptype = draft.get("type", "text")

    # Для конкурса добавляем дефолтную кнопку
    if ptype == "contest":
        contest_key = f"{user_id}_{uuid.uuid4().hex[:8]}"
        draft["buttons"] = [{
            "text": "🎉 Принять участие",
            "callback_data": f"contest_{contest_key}",
            "style": "success",
        }]

    await edit_message(
        chat_id, message_id,
        f"{pe(EMO_WHAT_POST, '📝')} <b>Опубликовать в канал?</b>\n\n"
        f"📄 Тип: <b>{ptype}</b>\n"
        f"📝 Текст: {draft.get('text', '')[:100]}\n"
        f"🔘 Кнопок: <b>{len(draft.get('buttons', []))}</b>",
        reply_markup=kb_confirm_publish(),
    )
    user_states[user_id] = "confirm_publish"

async def handle_publish(chat_id: int, user_id: int, callback_id: str, message_id: int, do_publish: bool):
    await answer_callback(callback_id)
    draft = user_drafts.get(user_id, {})
    channel = user_states.get(f"{user_id}_channel")

    item_id = uuid.uuid4().hex[:12]
    uid_str = str(user_id)
    if uid_str not in history:
        history[uid_str] = []

    item = {
        "id": item_id,
        "type": draft.get("type", "text"),
        "text": draft.get("text", ""),
        "buttons": draft.get("buttons", []),
        "media_file_id": draft.get("media_file_id"),
        "created_at": datetime.now().isoformat(),
        "channel_posted": False,
    }

    if do_publish and channel:
        post_buttons = build_post_keyboard(draft)
        result = await publish_to_channel(channel, draft, post_buttons)
        if result.get("ok"):
            item["channel_posted"] = True
            history[uid_str].append(item)
            save_history(history)
            has_channel = True
            await edit_message(
                chat_id, message_id,
                f"✅ <b>Пост успешно опубликован в {channel}!</b>\n\n"
                f"{pe(EMO_CHOOSE, '🎯')} <b>Выберите действие:</b>",
                reply_markup=kb_main_menu(has_channel),
            )
        else:
            await edit_message(
                chat_id, message_id,
                f"❌ Не удалось опубликовать: {result.get('description', 'неизвестная ошибка')}\n\n"
                "Проверь права бота в канале и попробуй снова.",
                reply_markup={"inline_keyboard": [[{"text": "« Главное меню", "callback_data": "main_menu"}]]}
            )
    else:
        history[uid_str].append(item)
        save_history(history)
        has_channel = bool(channel)
        await edit_message(
            chat_id, message_id,
            f"💾 <b>Пост сохранён в историю!</b>\n\n"
            f"{pe(EMO_CHOOSE, '🎯')} <b>Выберите действие:</b>",
            reply_markup=kb_main_menu(has_channel),
        )

    user_drafts.pop(user_id, None)
    user_states[user_id] = "idle"

def build_post_keyboard(draft: dict) -> Optional[dict]:
    buttons = draft.get("buttons", [])
    if not buttons:
        return None
    rows = []
    for i in range(0, len(buttons), 2):
        row = []
        for btn in buttons[i:i+2]:
            kb_btn = {"text": btn["text"]}
            if btn.get("url"):
                kb_btn["url"] = btn["url"]
            elif btn.get("callback_data"):
                kb_btn["callback_data"] = btn["callback_data"]
            if btn.get("style"):
                kb_btn["style"] = btn["style"]
            row.append(kb_btn)
        rows.append(row)
    return {"inline_keyboard": rows}

async def publish_to_channel(channel: str, draft: dict, keyboard) -> dict:
    ptype = draft.get("type", "text")
    text = draft.get("text", "")
    media = draft.get("media_file_id")
    payload_base = {
        "chat_id": channel,
        "parse_mode": "HTML",
    }
    if keyboard:
        payload_base["reply_markup"] = keyboard

    if ptype in ("text", "contest"):
        return await api_call("sendMessage", {**payload_base, "text": text})
    elif ptype == "photo":
        return await api_call("sendPhoto", {**payload_base, "photo": media, "caption": text})
    elif ptype == "gif":
        return await api_call("sendAnimation", {**payload_base, "animation": media, "caption": text})
    elif ptype == "video":
        return await api_call("sendVideo", {**payload_base, "video": media, "caption": text})
    return {"ok": False, "description": "Unknown type"}

async def handle_history(chat_id: int, user_id: int, callback_id: str, message_id: int):
    await answer_callback(callback_id)
    kb = kb_history_list(user_id)
    if not kb:
        await edit_message(
            chat_id, message_id,
            "📋 <b>История пуста</b>\n\nСоздай свой первый пост!",
            reply_markup={"inline_keyboard": [[{"text": "« Назад", "callback_data": "main_menu"}]]}
        )
        return
    await edit_message(
        chat_id, message_id,
        "📋 <b>История постов</b>\n\nВыбери шаблон:",
        reply_markup=kb,
    )

async def handle_history_item(chat_id: int, user_id: int, callback_id: str, message_id: int, item_id: str):
    await answer_callback(callback_id)
    uid_str = str(user_id)
    items = history.get(uid_str, [])
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        await answer_callback(callback_id, "Шаблон не найден!", alert=True)
        return
    status = "✅ Опубликован" if item.get("channel_posted") else "💾 Сохранён"
    await edit_message(
        chat_id, message_id,
        f"📄 <b>Шаблон [{item['type'].upper()}]</b>\n\n"
        f"📝 {item['text'][:200]}\n\n"
        f"🔘 Кнопок: {len(item.get('buttons', []))}\n"
        f"📅 {item['created_at'][:10]}\n"
        f"Статус: {status}",
        reply_markup=kb_history_item(item_id),
    )

async def handle_history_publish(chat_id: int, user_id: int, callback_id: str, message_id: int, item_id: str):
    await answer_callback(callback_id)
    channel = user_states.get(f"{user_id}_channel")
    if not channel:
        await answer_callback(callback_id, "❌ Сначала привяжи канал!", alert=True)
        return
    uid_str = str(user_id)
    items = history.get(uid_str, [])
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return
    keyboard = build_post_keyboard(item)
    result = await publish_to_channel(channel, item, keyboard)
    if result.get("ok"):
        item["channel_posted"] = True
        save_history(history)
        await edit_message(
            chat_id, message_id,
            f"✅ <b>Пост опубликован в {channel}!</b>",
            reply_markup={"inline_keyboard": [[{"text": "« История", "callback_data": "history"}]]}
        )
    else:
        await answer_callback(callback_id, f"Ошибка: {result.get('description')}", alert=True)

async def handle_history_edit(chat_id: int, user_id: int, callback_id: str, item_id: str):
    await answer_callback(callback_id)
    uid_str = str(user_id)
    items = history.get(uid_str, [])
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        return
    user_drafts[user_id] = {
        "type": item["type"],
        "text": item["text"],
        "buttons": list(item.get("buttons", [])),
        "media_file_id": item.get("media_file_id"),
        "_editing_id": item_id,
    }
    user_states[user_id] = "await_text"
    await send_message(
        chat_id,
        f"✏️ <b>Редактирование поста</b>\n\n"
        f"Текущий текст:\n{item['text']}\n\n"
        "Отправь новый текст поста:",
    )

async def handle_history_delete(chat_id: int, user_id: int, callback_id: str, message_id: int, item_id: str):
    await answer_callback(callback_id)
    uid_str = str(user_id)
    items = history.get(uid_str, [])
    history[uid_str] = [i for i in items if i["id"] != item_id]
    save_history(history)
    kb = kb_history_list(user_id)
    if not kb:
        await edit_message(
            chat_id, message_id,
            "📋 <b>История пуста</b>",
            reply_markup={"inline_keyboard": [[{"text": "« Главное меню", "callback_data": "main_menu"}]]}
        )
    else:
        await edit_message(
            chat_id, message_id,
            "🗑 Удалено! <b>История постов:</b>",
            reply_markup=kb,
        )

async def handle_media_received(chat_id: int, user_id: int, file_id: str):
    user_drafts[user_id]["media_file_id"] = file_id
    await send_message(
        chat_id,
        "✏️ Теперь напиши подпись / текст для поста:",
        reply_markup={"inline_keyboard": [[{"text": "« Назад", "callback_data": "choose_post_type"}]]}
    )
    user_states[user_id] = "await_text"

# ─── CONTEST CALLBACK ─────────────────────────────────────────────────────────

async def handle_contest_join(chat_id: int, user_id: int, callback_id: str, contest_key: str):
    contest_data_file = f"contest_{contest_key}.json"
    if os.path.exists(contest_data_file):
        with open(contest_data_file, "r") as f:
            participants = json.load(f)
    else:
        participants = []

    if user_id in participants:
        await answer_callback(callback_id, "Ты уже участвуешь в конкурсе! 🎉", alert=True)
        return

    participants.append(user_id)
    with open(contest_data_file, "w") as f:
        json.dump(participants, f)

    await answer_callback(
        callback_id,
        f"✅ Ты принят(а) в конкурс! Участников: {len(participants)}",
        alert=True
    )

# ─── MAIN UPDATE DISPATCHER ───────────────────────────────────────────────────

async def process_update(update: dict):
    try:
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            text = msg.get("text", "")

            if text == "/start":
                await handle_start(chat_id, user_id)
                return

            state = user_states.get(user_id, "idle")

            # Media handling
            if state.startswith("await_media_"):
                if "photo" in msg:
                    await handle_media_received(chat_id, user_id, msg["photo"][-1]["file_id"])
                elif "animation" in msg:
                    await handle_media_received(chat_id, user_id, msg["animation"]["file_id"])
                elif "video" in msg:
                    await handle_media_received(chat_id, user_id, msg["video"]["file_id"])
                return

            if text:
                await handle_text_input(chat_id, user_id, text)

        elif "callback_query" in update:
            cq = update["callback_query"]
            callback_id = cq["id"]
            user_id = cq["from"]["id"]
            chat_id = cq["message"]["chat"]["id"]
            message_id = cq["message"]["message_id"]
            data = cq.get("data", "")

            if data == "check_sub":
                await handle_check_sub(chat_id, user_id, callback_id, message_id)
            elif data == "main_menu":
                await handle_main_menu(chat_id, user_id, callback_id, message_id)
            elif data == "add_channel":
                await handle_add_channel(chat_id, user_id, callback_id, message_id)
            elif data == "support":
                await handle_support(chat_id, callback_id, message_id)
            elif data == "make_post":
                await handle_make_post(chat_id, user_id, callback_id, message_id)
            elif data == "choose_post_type":
                await handle_make_post(chat_id, user_id, callback_id, message_id)
            elif data.startswith("pt_"):
                ptype = data[3:]
                await handle_post_type(chat_id, user_id, callback_id, message_id, ptype)
            elif data == "add_button":
                await handle_add_button(chat_id, user_id, callback_id)
            elif data.startswith("btncolor_"):
                style = data[9:]
                if style == "default":
                    style = None
                await handle_button_color(chat_id, user_id, callback_id, style, message_id)
            elif data == "skip_buttons":
                await handle_skip_buttons(chat_id, user_id, callback_id, message_id)
            elif data == "publish_yes":
                await handle_publish(chat_id, user_id, callback_id, message_id, True)
            elif data == "publish_no":
                await handle_publish(chat_id, user_id, callback_id, message_id, False)
            elif data == "history":
                await handle_history(chat_id, user_id, callback_id, message_id)
            elif data.startswith("hist_"):
                item_id = data[5:]
                await handle_history_item(chat_id, user_id, callback_id, message_id, item_id)
            elif data.startswith("hpub_"):
                item_id = data[5:]
                await handle_history_publish(chat_id, user_id, callback_id, message_id, item_id)
            elif data.startswith("hedit_"):
                item_id = data[6:]
                await handle_history_edit(chat_id, user_id, callback_id, item_id)
            elif data.startswith("hdel_"):
                item_id = data[5:]
                await handle_history_delete(chat_id, user_id, callback_id, message_id, item_id)
            elif data.startswith("contest_"):
                contest_key = data[8:]
                await handle_contest_join(chat_id, user_id, callback_id, contest_key)
            else:
                await answer_callback(callback_id, "🤷 Неизвестная команда")
    except Exception as e:
        print(f"[ERROR] process_update: {e}")

# ─── POLLING LOOP ─────────────────────────────────────────────────────────────

async def polling():
    print("🚀 Bot started! Polling...")
    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                params["offset"] = offset
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=_ssl_ctx)) as s:
                async with s.get(
                    f"{API}/getUpdates",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=35)
                ) as r:
                    data = await r.json()
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    offset = update["update_id"] + 1
                    asyncio.create_task(process_update(update))
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[POLLING ERROR] {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(polling())
