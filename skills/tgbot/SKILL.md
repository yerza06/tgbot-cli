---
name: tgbot
description: >-
  Send Telegram notifications AS A BOT (Bot API) via the write-only `tgbot` CLI: text, photos,
  files, videos, audio, voice, stickers, contacts, locations, polls and dice, from one or several
  saved bots. Manages saved chat aliases like `git remote`. Use whenever the user wants to be notified, or wants someone else
  notified, on Telegram about an event: "notify me on Telegram when the build finishes", "send
  this file to Telegram", "ping the team chat", "post to my channel". Also covers Russian
  phrasing ("уведоми в телеграм", "отправь в телеграм", "скинь файл в телеграм"). tgbot cannot
  read messages, so it is not for checking replies.
license: MIT
compatibility: Requires Python 3.13+, uv, and a bot added once by a human (`tgbot key init`, `tgbot bot add`).
metadata:
  author: yerza06
  version: "0.1.0"
---

# tgbot — send Telegram notifications as a bot

`tgbot` sends messages and media to Telegram **from a bot** through the Bot API. It is
**write-only**: it never reads messages, so you cannot use it to wait for or check replies.
Chats and bots are saved under short names in a local SQLite database, like `git remote`; bot
tokens are stored encrypted.

## 1. Check the tool and the bot

```bash
command -v tgbot && tgbot whoami --json
```

- `tgbot` missing: install it from a clone with `uv tool install .`. Always install globally;
  never use `uv run tgbot` outside the repo.
- Exit code `3` with a missing key: **ask the user** to run `tgbot key init` (in Claude Code:
  `! tgbot key init`). Exit code `3` with "No bot configured": ask them to run
  `tgbot bot add NAME` (`! tgbot bot add main`). The token comes from @BotFather and is a secret:
  never ask for it in chat, never print it or `TGBOT_SECRET_KEY`, and never run `tgbot key init
  --force` yourself (it makes every saved bot unusable).

### Several bots

`tgbot bot list --json` shows the saved bots (`name`, `username`, `is_default`; never tokens).
Without `--bot` the default bot sends. Use `--bot NAME` on any send command or `whoami` when the
user asks for a specific bot.

## 2. Pick a target

| Form | Example | Notes |
|------|---------|-------|
| Saved alias | `--to me` | Checked first. List them with `tgbot chat list --json` |
| Numeric ID | `--to -1001234567890` | Groups and channels are negative; type the `-` as is |
| Public channel | `--to @mychannel` | The bot must be a channel admin |

There is **no built-in "me"**. It is just a common alias name. If `tgbot chat list` shows no
suitable alias, ask the user for the chat ID and save it with `tgbot chat add NAME ID`.

The user may have set a default chat (`tgbot chat default NAME`), which is used when no target is
given. **Still pass `--to` explicitly** unless the user asked you to use the default chat, so a
message never goes to the wrong place.

**The recipient must have pressed Start in the bot** (or the bot must be in the group). A 403
error means they have not; tell the user, and do not retry.

## 3. Send — always use flags and `--json`

Positional syntax exists, but flags are unambiguous. Check that files exist first.

```bash
tgbot send "Build finished ✅" --to me --json
long_output_command 2>&1 | tail -50 | tgbot send - --to me --json   # text from stdin
tgbot sendphoto ./out/chart.png --to me --caption "Latest chart" --json
tgbot sendfile ./report.pdf --to team --caption "Q4 report" --json
tgbot sendfile a.log b.log --to me --group --json                   # one album
tgbot sendlocation 43.238 76.889 --to me --json
tgbot sendpoll "Deploy now?" Yes No --to team --json
tgbot send "Deploy started" --to team --bot ops --json              # as a specific bot
```

| Command | Sends |
|---------|-------|
| `send TEXT\|-` | Text. Plain by default (no formatting errors); `--parse-mode html\|markdown`. Text over 4096 chars is split automatically |
| `sendphoto` / `sendvideo` | Photo(s) / video(s); several form an album |
| `sendfile` | Documents (`--group` for an album) |
| `sendaudio`, `sendvoice`, `sendanimation`, `sendvideonote`, `sendsticker` | The matching media type |
| `sendcontact` | `--phone`, `--first-name`, `--last-name` |
| `sendlocation` | `LAT LON` |
| `sendpoll` | `QUESTION OPT OPT…` with `--multiple` and `--no-anonymous` |
| `senddice` | `--emoji 🎲🎯🏀⚽🎳🎰` |

Media can be a local path, an `https://` URL, or a Telegram `file_id`. Common flags are
`--silent` (no notification sound) and `--caption`. Limits: 50 MB per file, 10 MB per photo,
1024-character captions.

## 4. Read the result: exit code first

With `--json`, success prints `{"ok": true, "chat_id": …, "message_ids": […]}` on stdout.
Failures print `{"ok": false, "error": "…", "code": N, "hint": "…"}` on **stderr**.

| Exit | Meaning | What to do |
|------|---------|------------|
| `0` | Sent | — |
| `1` | Telegram refused | Read `error`; 403 means the recipient must press Start |
| `2` | Bad usage, missing file, limit exceeded | Fix the command |
| `3` | No key or bot, unknown bot or chat alias, duplicate alias, broken config file | Ask the user, or `tgbot chat add` |
| `4` | Network failure | Retry later |

## Chat aliases

```bash
tgbot chat add me 13342324
tgbot chat add news @mychannel     # resolved to the numeric ID via getChat
tgbot chat list --json
tgbot chat get-id me               # bare ID on stdout
tgbot chat rename OLD NEW / replace-id NAME ID / remove NAME
```

Do not delete or edit `~/.config/tgbot/`: `.env` holds the encryption key, `tgbot.db` the
chats and encrypted bots, `config.toml` the user's defaults.

More: [`references/reference.md`](references/reference.md).
