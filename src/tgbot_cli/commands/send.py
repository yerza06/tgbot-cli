"""Sending commands: text, media, contact, location, poll and dice.

Media commands accept two syntaxes:

* via flags:   ``tgbot sendphoto a.png b.png --to chat --caption "text"``
* positional:  ``tgbot sendphoto a.png b.png chat "text"``

Leading positional tokens that are existing files or URLs are content; the next token
is the target (unless ``--to`` is set), the one after it the caption (unless
``--caption`` is set). When the flags cover target and caption, every positional token
is content — that is how Telegram ``file_id`` values are sent.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

import typer

from .. import db, telegram
from ..config import get_settings
from ..console import out
from ..errors import UsageError
from ..media import (
    InputValue,
    Upload,
    check_caption,
    chunk_text,
    is_content_token,
    looks_like_path,
    resolve_input,
)
from ..resolver import resolve_target
from ..telegram import BotClient, FileTuple
from .options import (
    ALLOW_NEG,
    BotOpt,
    CaptionOpt,
    JsonOpt,
    ParseMode,
    ParseModeOpt,
    SilentOpt,
    ToOpt,
)

app = typer.Typer()

MEDIA_GROUP_MAX_ITEMS = 10
DICE_EMOJI = ("🎲", "🎯", "🏀", "⚽", "🎳", "🎰")
POLL_MIN_OPTIONS = 2
POLL_MAX_OPTIONS = 10


@dataclass(frozen=True)
class MediaKind:
    """How one kind of media maps onto the Bot API."""

    name: str  # used for limits and sendMediaGroup "type"
    method: str
    field: str
    has_caption: bool = True
    album: bool = False


PHOTO = MediaKind("photo", "sendPhoto", "photo", album=True)
VIDEO = MediaKind("video", "sendVideo", "video", album=True)
DOCUMENT = MediaKind("document", "sendDocument", "document", album=True)
AUDIO = MediaKind("audio", "sendAudio", "audio")
VOICE = MediaKind("voice", "sendVoice", "voice")
ANIMATION = MediaKind("animation", "sendAnimation", "animation")
VIDEO_NOTE = MediaKind("video note", "sendVideoNote", "video_note", has_caption=False)
STICKER = MediaKind("sticker", "sendSticker", "sticker", has_caption=False)


# --------------------------------------------------------------------------- #
# Positional argument parsing
# --------------------------------------------------------------------------- #
def _extra_args(rest: Sequence[str]) -> UsageError:
    return UsageError(f"Unexpected extra arguments: {' '.join(rest)}")


def _no_target() -> UsageError:
    return UsageError(
        "No target chat given.",
        hint=(
            "Pass it positionally or with --to (saved name, numeric ID or @channel), "
            "or set a default with `tgbot chat default NAME`."
        ),
    )


def split_media_args(
    items: Sequence[str],
    to: str | None,
    caption: str | None,
    *,
    has_caption: bool = True,
) -> tuple[list[str], str | None, str | None]:
    """Split positional arguments into (content, target, caption); target may be None."""
    items = list(items)
    flags_only = to is not None and (caption is not None or not has_caption)
    if flags_only:
        content, rest = items, []
    else:
        content = []
        for token in items:
            if not is_content_token(token):
                break
            content.append(token)
        rest = items[len(content) :]
        # A path-looking token where a target would go is a missing file, not a chat.
        if rest and looks_like_path(rest[0]) and (to is None or not content):
            raise UsageError(f"File not found: {rest[0]}")
        if to is None and rest:
            to = rest.pop(0)
        if has_caption and caption is None and rest:
            caption = rest.pop(0)

    if not content:
        raise UsageError("No media given: pass at least one file path, URL or file_id.")
    if rest:
        raise _extra_args(rest)
    return content, to, caption


def pick_target(rest: Sequence[str], to: str | None) -> str | None:
    """For commands with fixed positional fields: target from ``--to`` or the tail."""
    rest = list(rest)
    if to is None and rest:
        to = rest.pop(0)
    if rest:
        raise _extra_args(rest)
    return to


# --------------------------------------------------------------------------- #
# Shared send runner
# --------------------------------------------------------------------------- #
Sender = Callable[[BotClient, int | str], list[dict[str, Any]]]


def _dispatch(target: str | None, sender: Sender, bot: str | None = None) -> None:
    """Resolve bot and target, call ``sender`` and report the sent message IDs.

    Without a target the configured ``default_chat`` is used. Every configuration error
    (no target, no bot, unknown alias, missing key) is raised before any request.
    """
    settings = get_settings()
    target = target if target is not None else settings.default_chat
    if target is None:
        raise _no_target()
    client = telegram.build_client(settings, bot)
    with client:
        with db.open_db(settings.db_path) as conn:
            chat_id = resolve_target(conn, target)
        with out.status("Sending..."):
            messages = sender(client, chat_id)

    message_ids = [m["message_id"] for m in messages if "message_id" in m]
    count = len(message_ids)
    noun = "message" if count == 1 else "messages"
    label = target if str(chat_id) == target else f"{target} ({chat_id})"
    out.success(
        f"Sent {count} {noun} to {label}",
        data={"ok": True, "chat_id": chat_id, "message_ids": message_ids},
    )


def _common(silent: bool) -> dict[str, Any]:
    return {"disable_notification": True} if silent else {}


def _parse_mode(parse_mode: ParseMode | None) -> str | None:
    return parse_mode.api_value if parse_mode else None


# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #
def _read_message(message: str) -> str:
    if message == "-":
        text = sys.stdin.read()
        if not text.strip():
            raise UsageError("No message text on standard input.")
        return text.rstrip("\n")
    if not message.strip():
        raise UsageError("The message text is empty.")
    return message


@app.command(context_settings=ALLOW_NEG)
def send(
    message: Annotated[str, typer.Argument(help="Message text, or `-` to read stdin.")],
    rest: Annotated[list[str] | None, typer.Argument(help="Target chat.")] = None,
    to: ToOpt = None,
    bot: BotOpt = None,
    parse_mode: ParseModeOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send a text message. Long text is split into several messages."""
    out.use_json(json_output)
    target = pick_target(rest or [], to)
    parts = chunk_text(_read_message(message))

    def sender(client: BotClient, chat_id: int | str) -> list[dict[str, Any]]:
        return [
            client.call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": part,
                    "parse_mode": _parse_mode(parse_mode),
                    **_common(silent),
                },
            )
            for part in parts
        ]

    _dispatch(target, sender, bot)


# --------------------------------------------------------------------------- #
# Media
# --------------------------------------------------------------------------- #
class _Files:
    """Opens local uploads lazily and closes them when the send finishes."""

    def __init__(self, stack: contextlib.ExitStack) -> None:
        self._stack = stack

    def tuple_for(self, upload: Upload) -> FileTuple:
        handle = self._stack.enter_context(upload.path.open("rb"))
        return (upload.filename, handle, upload.mime_type)


def _send_single(
    client: BotClient,
    chat_id: int | str,
    kind: MediaKind,
    item: InputValue,
    caption: str | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    params: dict[str, Any] = {"chat_id": chat_id, **extra}
    if kind.has_caption:
        params["caption"] = caption
    else:
        params.pop("parse_mode", None)
    with contextlib.ExitStack() as stack:
        files: dict[str, FileTuple] | None = None
        if isinstance(item, Upload):
            files = {kind.field: _Files(stack).tuple_for(item)}
        else:
            params[kind.field] = item
        return client.call(kind.method, params, files)


def _send_album(
    client: BotClient,
    chat_id: int | str,
    kind: MediaKind,
    items: Sequence[InputValue],
    caption: str | None,
    extra: dict[str, Any],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for start in range(0, len(items), MEDIA_GROUP_MAX_ITEMS):
        batch = items[start : start + MEDIA_GROUP_MAX_ITEMS]
        batch_caption = caption if start == 0 else None
        if len(batch) == 1:  # Telegram rejects one-item media groups.
            messages.append(_send_single(client, chat_id, kind, batch[0], batch_caption, extra))
            continue

        with contextlib.ExitStack() as stack:
            opener = _Files(stack)
            media: list[dict[str, Any]] = []
            files: dict[str, FileTuple] = {}
            for index, item in enumerate(batch):
                entry: dict[str, Any] = {"type": kind.name}
                if isinstance(item, Upload):
                    attach = f"file{index}"
                    files[attach] = opener.tuple_for(item)
                    entry["media"] = f"attach://{attach}"
                else:
                    entry["media"] = item
                if index == 0 and batch_caption:
                    entry["caption"] = batch_caption
                    if extra.get("parse_mode"):
                        entry["parse_mode"] = extra["parse_mode"]
                media.append(entry)

            params: dict[str, Any] = {"chat_id": chat_id, "media": media}
            if extra.get("disable_notification"):
                params["disable_notification"] = True
            messages.extend(client.call("sendMediaGroup", params, files or None))
    return messages


def _send_media(
    kind: MediaKind,
    items: list[str],
    to: str | None,
    caption: str | None,
    *,
    silent: bool,
    parse_mode: ParseMode | None = None,
    album: bool = False,
    bot: str | None = None,
) -> None:
    content, target, cap = split_media_args(items, to, caption, has_caption=kind.has_caption)
    check_caption(cap)
    inputs = [resolve_input(value, kind=kind.name) for value in content]
    extra = {**_common(silent), "parse_mode": _parse_mode(parse_mode)}

    def sender(client: BotClient, chat_id: int | str) -> list[dict[str, Any]]:
        if album and len(inputs) > 1:
            return _send_album(client, chat_id, kind, inputs, cap, extra)
        return [
            _send_single(client, chat_id, kind, item, cap if index == 0 else None, extra)
            for index, item in enumerate(inputs)
        ]

    _dispatch(target, sender, bot)


ItemsArg = Annotated[
    list[str],
    typer.Argument(help="File path(s), URL(s) or file_id(s), then [TARGET] [CAPTION]."),
]
SingleItemsArg = Annotated[
    list[str],
    typer.Argument(help="File path(s), URL(s) or file_id(s), then [TARGET]."),
]


@app.command(context_settings=ALLOW_NEG)
def sendphoto(
    items: ItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    caption: CaptionOpt = None,
    parse_mode: ParseModeOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send photo(s); several photos are sent as an album."""
    out.use_json(json_output)
    _send_media(
        PHOTO, items, to, caption, silent=silent, parse_mode=parse_mode, album=True, bot=bot
    )


@app.command(context_settings=ALLOW_NEG)
def sendfile(
    items: ItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    caption: CaptionOpt = None,
    group: Annotated[
        bool, typer.Option("--group", "-G", help="Send several documents as one album.")
    ] = False,
    parse_mode: ParseModeOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send file(s) as documents."""
    out.use_json(json_output)
    _send_media(
        DOCUMENT, items, to, caption, silent=silent, parse_mode=parse_mode, album=group, bot=bot
    )


@app.command(context_settings=ALLOW_NEG)
def sendvideo(
    items: ItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    caption: CaptionOpt = None,
    parse_mode: ParseModeOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send video(s); several videos are sent as an album."""
    out.use_json(json_output)
    _send_media(
        VIDEO, items, to, caption, silent=silent, parse_mode=parse_mode, album=True, bot=bot
    )


@app.command(context_settings=ALLOW_NEG)
def sendaudio(
    items: ItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    caption: CaptionOpt = None,
    parse_mode: ParseModeOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send audio / music file(s)."""
    out.use_json(json_output)
    _send_media(AUDIO, items, to, caption, silent=silent, parse_mode=parse_mode, bot=bot)


@app.command(context_settings=ALLOW_NEG)
def sendvoice(
    items: ItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    caption: CaptionOpt = None,
    parse_mode: ParseModeOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send voice message(s) (.ogg with OPUS)."""
    out.use_json(json_output)
    _send_media(VOICE, items, to, caption, silent=silent, parse_mode=parse_mode, bot=bot)


@app.command(context_settings=ALLOW_NEG)
def sendanimation(
    items: ItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    caption: CaptionOpt = None,
    parse_mode: ParseModeOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send animation(s) (GIF or soundless MP4)."""
    out.use_json(json_output)
    _send_media(ANIMATION, items, to, caption, silent=silent, parse_mode=parse_mode, bot=bot)


@app.command(context_settings=ALLOW_NEG)
def sendvideonote(
    items: SingleItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send video note(s) (round video messages)."""
    out.use_json(json_output)
    _send_media(VIDEO_NOTE, items, to, None, silent=silent, bot=bot)


@app.command(context_settings=ALLOW_NEG)
def sendsticker(
    items: SingleItemsArg,
    to: ToOpt = None,
    bot: BotOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send sticker(s): .webp/.tgs/.webm file, URL or file_id (use --to for file_id)."""
    out.use_json(json_output)
    _send_media(STICKER, items, to, None, silent=silent, bot=bot)


# --------------------------------------------------------------------------- #
# Contact / location / poll / dice
# --------------------------------------------------------------------------- #
@app.command(context_settings=ALLOW_NEG)
def sendcontact(
    args: Annotated[
        list[str] | None,
        typer.Argument(help="PHONE FIRST_NAME [LAST_NAME] TARGET"),
    ] = None,
    phone: Annotated[str | None, typer.Option("--phone", help="Phone number.")] = None,
    first_name: Annotated[str | None, typer.Option("--first-name", help="First name.")] = None,
    last_name: Annotated[str | None, typer.Option("--last-name", help="Last name.")] = None,
    to: ToOpt = None,
    bot: BotOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send a contact card."""
    out.use_json(json_output)
    rest = list(args or [])
    if phone is None and rest:
        phone = rest.pop(0)
    if first_name is None and rest:
        first_name = rest.pop(0)
    # Two tokens left: [last_name, target]; one token: the target (or last name with --to).
    if last_name is None and (len(rest) >= 2 or (to is not None and len(rest) == 1)):
        last_name = rest.pop(0)
    if not phone or not first_name:
        raise UsageError("A contact needs a phone number and a first name.")
    target = pick_target(rest, to)

    def sender(client: BotClient, chat_id: int | str) -> list[dict[str, Any]]:
        return [
            client.call(
                "sendContact",
                {
                    "chat_id": chat_id,
                    "phone_number": phone,
                    "first_name": first_name,
                    "last_name": last_name,
                    **_common(silent),
                },
            )
        ]

    _dispatch(target, sender, bot)


def _coordinate(value: str, name: str, bound: float) -> float:
    try:
        number = float(value)
    except ValueError:
        raise UsageError(f"{name} must be a number, got '{value}'.") from None
    if not -bound <= number <= bound:
        raise UsageError(f"{name} must be between {-bound:g} and {bound:g}, got {number:g}.")
    return number


@app.command(context_settings=ALLOW_NEG)
def sendlocation(
    args: Annotated[list[str], typer.Argument(help="LATITUDE LONGITUDE [TARGET]")],
    to: ToOpt = None,
    bot: BotOpt = None,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send a location pin."""
    out.use_json(json_output)
    if len(args) < 2:
        raise UsageError("A location needs LATITUDE and LONGITUDE.")
    latitude = _coordinate(args[0], "Latitude", 90)
    longitude = _coordinate(args[1], "Longitude", 180)
    target = pick_target(args[2:], to)

    def sender(client: BotClient, chat_id: int | str) -> list[dict[str, Any]]:
        return [
            client.call(
                "sendLocation",
                {
                    "chat_id": chat_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    **_common(silent),
                },
            )
        ]

    _dispatch(target, sender, bot)


@app.command(context_settings=ALLOW_NEG)
def sendpoll(
    question: Annotated[str, typer.Argument(help="Poll question.")],
    options: Annotated[
        list[str], typer.Argument(help="2-10 answer options (last one is the target without --to).")
    ],
    to: ToOpt = None,
    bot: BotOpt = None,
    multiple: Annotated[bool, typer.Option("--multiple", help="Allow several answers.")] = False,
    anonymous: Annotated[
        bool, typer.Option("--anonymous/--no-anonymous", help="Anonymous poll (default).")
    ] = True,
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send a poll."""
    out.use_json(json_output)
    answers = list(options)
    if to is None:
        if not answers:
            raise _no_target()
        to = answers.pop()
    if not POLL_MIN_OPTIONS <= len(answers) <= POLL_MAX_OPTIONS:
        raise UsageError(
            f"A poll needs {POLL_MIN_OPTIONS}-{POLL_MAX_OPTIONS} options, got {len(answers)}."
        )

    def sender(client: BotClient, chat_id: int | str) -> list[dict[str, Any]]:
        return [
            client.call(
                "sendPoll",
                {
                    "chat_id": chat_id,
                    "question": question,
                    "options": [{"text": answer} for answer in answers],
                    "is_anonymous": anonymous,
                    "allows_multiple_answers": multiple,
                    **_common(silent),
                },
            )
        ]

    _dispatch(to, sender, bot)


@app.command(context_settings=ALLOW_NEG)
def senddice(
    rest: Annotated[list[str] | None, typer.Argument(help="Target chat.")] = None,
    to: ToOpt = None,
    bot: BotOpt = None,
    emoji: Annotated[
        str, typer.Option("--emoji", help=f"One of: {' '.join(DICE_EMOJI)}")
    ] = DICE_EMOJI[0],
    silent: SilentOpt = False,
    json_output: JsonOpt = False,
) -> None:
    """Send an animated dice."""
    out.use_json(json_output)
    if emoji not in DICE_EMOJI:
        raise UsageError(f"Unsupported dice emoji '{emoji}'. Use one of: {' '.join(DICE_EMOJI)}")
    target = pick_target(rest or [], to)

    def sender(client: BotClient, chat_id: int | str) -> list[dict[str, Any]]:
        return [client.call("sendDice", {"chat_id": chat_id, "emoji": emoji, **_common(silent)})]

    _dispatch(target, sender, bot)
