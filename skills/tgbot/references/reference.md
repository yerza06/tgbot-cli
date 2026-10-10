# tgbot — full reference

Read this when `SKILL.md` is not enough.

## Global options

| Option | Description |
|--------|-------------|
| `--plain` | Plain text output, with no colors or boxes (also `TGBOT_PLAIN=1`, `NO_COLOR`, `color = false` in `config.toml`, or non-TTY stdout) |
| `--json` | JSON output; also accepted on every command |
| `--version`, `-V` | Print `tgbot X.Y.Z` |
| `--help` | Help for any command |
| `--install-completion`, `--show-completion` | Shell completion (zsh, bash, fish); see the README |

## Key, bots and identity

| Command | Description |
|---------|-------------|
| `tgbot key init [--force]` | Generate the token-encryption key and save it as `TGBOT_SECRET_KEY` in `<config_dir>/.env` (0600). Refuses (exit 3) if a key exists; `--force` replaces it and saved bots must be re-added. The key is never printed |
| `tgbot bot add NAME [TOKEN]` | Validate the token with `getMe`, then save it encrypted under NAME. Prompts with hidden input when TOKEN is omitted. Needs the key (exit 3 otherwise). Exit 1 if Telegram rejects the token; nothing is saved. The first bot becomes `default_bot` |
| `tgbot bot list` / `tgbot bot` | With `--json`, an array of `{name, bot_id, username, is_default, created_at}` (no tokens) |
| `tgbot bot default NAME` | Write `default_bot` to `config.toml` |
| `tgbot bot rename OLD NEW` | Fails (exit 3) if NEW exists; updates `default_bot` |
| `tgbot bot remove NAME` | Deletes the bot; if it was the default, the oldest remaining bot becomes default |
| `tgbot whoami [--bot NAME]` | The bot's alias, ID, @username and name |
| `tgbot version` | Version, config dir, config file, DB path, number of bots, default bot and chat (never tokens or the key) |

The sending bot is chosen in this order: `--bot` → `TGBOT_DEFAULT_BOT` → `default_bot` in
`config.toml`.

## Configuration

`<config_dir>/config.toml` (optional) holds preferences: `default_bot`, `default_chat`, `color`,
`timeout`, `api_url`. `<config_dir>/.env` holds the secret key. Precedence: flag → environment →
`.env` → `config.toml` → default. Invalid TOML or a wrong value type exits 3 and names the file.

| Variable | Default | Meaning |
|---|---|---|
| `TGBOT_SECRET_KEY` | — | Key that encrypts saved bot tokens |
| `TGBOT_DEFAULT_BOT` | — | Default bot alias |
| `TGBOT_DEFAULT_CHAT` | — | Target used when none is given |
| `TGBOT_CONFIG_DIR` | `~/.config/tgbot` | Location of `.env`, `config.toml` and `tgbot.db` |
| `TGBOT_PLAIN` | `false` | Plain output |
| `TGBOT_TIMEOUT` | `30` | HTTP timeout (seconds) |
| `TGBOT_API_URL` | `https://api.telegram.org` | Bot API base URL |

## Chat management

| Command | Description |
|---------|-------------|
| `chat add NAME ID` | ID is a number or `@username`. `@username` is resolved via `getChat` with the default bot when one is saved; `--no-resolve` stores it as is |
| `chat list` / `chat` | Sorted by name; with `--json`, an array of `{name, chat_id, title, created_at}` |
| `chat get-id NAME` | Bare ID on stdout |
| `chat replace-id NAME ID` | Change the ID |
| `chat rename OLD NEW` | Fails (exit 3) if NEW exists |
| `chat remove NAME` | Fails (exit 3) if missing |
| `chat default NAME` | Write `default_chat` to `config.toml`; fails (exit 3) if NAME is not saved |

Targets are resolved in this order: alias → integer chat ID → `@username`. Anything else exits 3
before any request is made. Without a target, `default_chat` is used; with no default either, the
command exits 2.

## Sending — options

| Command | Positional form | Caption | Several items |
|---------|-----------------|:-------:|---------------|
| `send` | `TEXT [TARGET]` (`-` = stdin) | — | Split at 4096 chars |
| `sendphoto` | `FILES… [TARGET] [CAPTION]` | ✓ | Album; batches of 10 |
| `sendvideo` | same | ✓ | Album; batches of 10 |
| `sendfile` | same | ✓ | Separate messages; album with `--group`/`-G` |
| `sendaudio`, `sendvoice`, `sendanimation` | same | ✓ | Separate messages, caption on the first |
| `sendvideonote`, `sendsticker` | `FILES… [TARGET]` | — | Separate messages |
| `sendcontact` | `PHONE FIRST [LAST] [TARGET]` | — | `--phone --first-name --last-name` |
| `sendlocation` | `LAT LON [TARGET]` | — | lat ∈ [-90, 90], lon ∈ [-180, 180] |
| `sendpoll` | `QUESTION OPT… [TARGET]` | — | 2–10 options; `--multiple`, `--anonymous/--no-anonymous` (default anonymous) |
| `senddice` | `[TARGET]` | — | `--emoji` one of 🎲 🎯 🏀 ⚽ 🎳 🎰 |

Common options: `--to`, `--bot`, `--silent`, `--json`, `--parse-mode html|markdown` (on text and
captions).

### Positional parsing rules

1. Leading tokens that are existing files or `http(s)://` URLs are media.
2. The next token is the target, unless `--to` is given.
3. The next token is the caption, unless `--caption` is given (and only for commands with
   captions).
4. Leftover tokens give exit 2. A path-like token that does not exist gives "File not found".
5. When `--to` is set (plus `--caption` for captioned commands), **all** positionals are media.
   This is the only way to send a `file_id`.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Exit 3, "Encryption key is not configured" | The user runs `tgbot key init` (or restores the old key) |
| Exit 3, "No bot configured" | The user runs `tgbot bot add NAME` |
| Exit 3, "Bot 'x' not found" | Check `tgbot bot list`; fix the default with `tgbot bot default` |
| Exit 3, "Cannot decrypt the token" | `TGBOT_SECRET_KEY` changed; restore it or re-add the bots |
| Exit 3, "Unknown chat 'x'" | `tgbot chat add x ID`, or pass a numeric ID |
| Exit 1, 403 "bot can't initiate conversation" | The recipient must open the bot and press Start |
| Exit 1, 403 "bot was blocked by the user" | The user blocked the bot; they must unblock it |
| Exit 1, 400 "chat not found" | Wrong ID, or the bot is not in that group or channel |
| Exit 1, 400 "can't parse entities" | Bad HTML/Markdown; drop `--parse-mode` |
| Exit 2, "File not found" | Check the path; positional parsing stops at missing files |
| Exit 4 | Network down or `TGBOT_TIMEOUT` too low for a large upload |
