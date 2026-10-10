# tgbot

A **write-only** CLI for sending Telegram messages **as a bot** (Bot API). Built for AI agents
such as Claude Code, Codex CLI and Hermes-Agent, so they can notify you, or anyone else, about an
event.

`tgbot` only sends. It never calls `getUpdates` or webhooks and never reads anyone's messages:
the HTTP client refuses every Bot API method except `getMe`, `getChat` and `send*`.

Chat IDs and bots can be saved under short names in a local SQLite database, much like
`git remote`. Several bots are supported; their tokens are stored **encrypted**.

Sibling project: [tguser-cli](https://github.com/yerza06/tguser-cli) does the same as a *user*
account over MTProto.

## Stack

Python 3.13 · [uv](https://docs.astral.sh/uv/) · [Typer](https://typer.tiangolo.com/) +
[Rich](https://rich.readthedocs.io/) · Pydantic-Settings · [httpx](https://www.python-httpx.org/) ·
SQLite (stdlib `sqlite3`) · [cryptography](https://cryptography.io/) (Fernet) ·
[tomlkit](https://tomlkit.readthedocs.io/).

## Installation

From a clone:

```bash
git clone https://github.com/yerza06/tgbot-cli.git
cd tgbot-cli
uv tool install .
```

This puts `tgbot` in `~/.local/bin/`, and it then works **from any directory**, which matters
because an agent's working directory is not known in advance.

```bash
uv tool install . --force    # reinstall after changing the code
uv tool install -e .         # editable install
uv tool uninstall tgbot-cli  # remove
```

For development, `uv sync` then `uv run tgbot …` from the project root.

## Setup

1. Create the encryption key for bot tokens. It is written as `TGBOT_SECRET_KEY` to
   `~/.config/tgbot/.env` (mode 0600); the key itself is never printed:

   ```bash
   tgbot key init
   ```

2. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`), copy its token and save it
   under a name. The token is checked with Telegram first, then stored encrypted. The first bot
   you add becomes the default one:

   ```bash
   tgbot bot add main       # prompts for the token (input hidden)
   tgbot whoami             # shows the default bot's ID and @username
   ```

3. **Open your bot in Telegram and press Start.** A bot cannot start a conversation: every
   person it should message must send `/start` to it once. For groups and channels, add the bot
   as a member (as an admin, for channels).
4. Find your numeric chat ID, e.g. with [@userinfobot](https://t.me/userinfobot), and save it:

   ```bash
   tgbot chat add me 13342324
   tgbot chat default me    # optional: send here when no target is given
   ```

> **Back up `TGBOT_SECRET_KEY`.** Without it the saved tokens cannot be decrypted, and every bot
> has to be added again. `tgbot key init --force` replaces the key with the same effect. For
> stronger isolation keep the key in your environment or a secrets manager instead of `.env`.

### Bots

```bash
tgbot bot add alerts 123456:ABC...      # token as an argument (non-interactive)
tgbot bot list                          # aliases, @usernames, IDs, default (or just `tgbot bot`)
tgbot bot default alerts                # change the default bot
tgbot bot rename alerts ops             # rename
tgbot bot remove ops                    # delete the bot and its token
tgbot send "hi" me --bot ops            # send as a specific bot
tgbot whoami --bot ops
```

The bot is chosen in this order: `--bot`, then `TGBOT_DEFAULT_BOT`, then `default_bot` from
`config.toml`.

### Configuration file

Preferences live in `~/.config/tgbot/config.toml` (optional; `bot default` and `chat default`
write it for you, keeping your comments):

```toml
default_bot = "main"      # bot used without --bot
default_chat = "me"       # target used when none is given (alias, numeric ID or @channel)
color = false             # plain output: no colors or boxes
timeout = 30              # HTTP timeout, seconds
api_url = "https://api.telegram.org"   # e.g. a local Bot API server
```

Every key can be overridden with an environment variable (`TGBOT_` + the upper-cased key) or in
`~/.config/tgbot/.env`. Precedence: command-line flag → environment → `.env` → `config.toml` →
built-in default. `.env` is meant for the secret key; see `.env.example`.

| Variable | Default | Meaning |
|---|---|---|
| `TGBOT_SECRET_KEY` | — | Key that encrypts saved bot tokens (`tgbot key init`) |
| `TGBOT_DEFAULT_BOT` | — | Default bot alias |
| `TGBOT_DEFAULT_CHAT` | — | Default target |
| `TGBOT_CONFIG_DIR` | `~/.config/tgbot` | Where `.env`, `config.toml` and `tgbot.db` live |
| `TGBOT_PLAIN` | `false` | Disable Rich styling |
| `TGBOT_TIMEOUT` | `30` | HTTP timeout in seconds |
| `TGBOT_API_URL` | `https://api.telegram.org` | Bot API server (e.g. a local Bot API server) |

> Do not delete `~/.config/tgbot/tgbot.db`: it holds your saved chats and (encrypted) bots.

### Upgrading from a single-token version

`TGBOT_BOT_TOKEN` and the old `token set` command are gone. Run `tgbot key init` and
`tgbot bot add main` once, then delete the `TGBOT_BOT_TOKEN=` line from `~/.config/tgbot/.env`:
it is ignored but still holds the token in plain text.

## Shell completion

Like `git`, `tgbot` completes on <kbd>Tab</kbd>: commands, options after `-` (with their
descriptions), `--parse-mode` and `--emoji` values, and your **saved chats and bots**. Chats are
suggested for `--to`, the target of `send`/`senddice`/media commands and `tgbot chat
remove|rename|get-id|default|replace-id`. Bots are suggested for `--bot` and `tgbot bot
remove|rename|default`. Completion only reads `tgbot.db`: it needs no key and never prints
errors.

**zsh with oh-my-zsh.** Save the script once into a directory on `fpath`:

```bash
mkdir -p ~/.oh-my-zsh/custom/completions
{ tgbot --show-completion zsh; echo '_tgbot_completion "$@"'; } \
  > ~/.oh-my-zsh/custom/completions/_tgbot
```

The extra last line makes the very first <kbd>Tab</kbd> complete too: without it, zsh only
loads the script on the first press and completes from the second one.

Then add this line to `~/.zshrc` **before** `source $ZSH/oh-my-zsh.sh`, and restart the shell
with `rm -f ~/.zcompdump*; exec zsh`:

```zsh
fpath+=~/.oh-my-zsh/custom/completions
```

**Plain zsh, bash, fish.** `tgbot --install-completion zsh` (or `bash`, `fish`) writes the
script and the shell setup for you; open a new shell afterwards.

Avoid `eval "$(tgbot --show-completion zsh)"` in `~/.zshrc`: it starts Python on every new
shell. Re-run the command above after upgrading `tgbot` only if the script itself changes;
the suggestions are computed live.

In media commands the first arguments are files, so <kbd>Tab</kbd> completes paths. After a
file, saved chats are offered when one matches what you typed; start the word with `./` to
complete another file instead (`tgbot sendphoto a.png ./<Tab>`).

## Chat aliases

```bash
tgbot chat add me 13342324              # save an alias
tgbot chat add team -1001234567890      # groups and channels have negative IDs
tgbot chat add news @mychannel          # public channel: resolved to its ID via getChat
tgbot chat list                         # table of saved chats (or just `tgbot chat`)
tgbot chat get-id team                  # print the bare ID
tgbot chat replace-id team -100999      # point the alias elsewhere
tgbot chat rename team devs             # rename
tgbot chat remove devs                  # delete
tgbot chat default me                   # default target (written to config.toml)
```

A target can be a **saved alias**, a **numeric chat ID** or a **`@channel` username**. Aliases are
checked first. Without a target, the configured `default_chat` is used.

## Sending

Every command accepts two syntaxes: flags (`--to`, `--caption`) or positional arguments, and
`--bot NAME` to send as a saved bot other than the default.

```bash
# Text (plain by default; long text is split into several messages)
tgbot send "Build failed" me
tgbot send "Build failed" --to me --silent
some_command 2>&1 | tgbot send - me                 # read the text from stdin
tgbot send "<b>Done</b>" me --parse-mode html       # or --parse-mode markdown (MarkdownV2)

# Photos (several -> album, batches of 10), from a file or a URL
tgbot sendphoto shot.png me "Screenshot"
tgbot sendphoto a.png b.png --to me --caption "Screens"
tgbot sendphoto https://example.com/chart.png --to me

# Documents (several -> separate messages, or one album with --group)
tgbot sendfile report.pdf --to me --caption "Report"
tgbot sendfile part1.pdf part2.pdf --to me --group

# Video / audio / voice / animation / video note / sticker
tgbot sendvideo clip.mp4 me "Clip"
tgbot sendaudio track.mp3 --to me
tgbot sendvoice voice.ogg --to me
tgbot sendanimation fun.gif --to me
tgbot sendvideonote note.mp4 --to me
tgbot sendsticker sticker.webp --to me
tgbot sendsticker CAACAgIAAxkBAAE... --to me        # by file_id: use the flag form

# Contact, location, poll, dice
tgbot sendcontact +77001234567 Ivan Petrov me
tgbot sendlocation 43.238 76.889 me
tgbot sendpoll "Deploy now?" Yes No --to me --no-anonymous
tgbot senddice me --emoji 🎯
```

How positional arguments are read: leading tokens that are existing files or URLs are the media.
The next token is the target, and the one after it is the caption. Leftover tokens are an error,
so a typo never sends to the wrong chat. A Telegram `file_id` is only recognised when you pass
`--to` (plus `--caption` for commands that have one). With a `default_chat` you may omit the
target, but a positional token after the media is still read as the target, so give the caption
with `--caption`: `tgbot sendphoto shot.png --caption "Screenshot"`.

Limits are checked before uploading: files up to 50 MB, photos up to 10 MB, captions up to
1024 characters.

## Output for agents

| Mode | How |
|---|---|
| Rich (panels, colors) | default in a terminal |
| Plain text | `tgbot --plain …`, `TGBOT_PLAIN=1`, `NO_COLOR=1`, `color = false` in `config.toml`, or stdout not a TTY |
| JSON | `--json` (global or on any command) |

```console
$ tgbot send "hi" me --json
{"ok": true, "chat_id": 13342324, "message_ids": [42]}

$ tgbot send "hi" boss --json        # error JSON goes to stderr
{"ok": false, "error": "Unknown chat 'boss'.", "code": 3, "hint": "..."}
```

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | Telegram rejected the request (e.g. 403: the recipient has not pressed Start) |
| `2` | Usage error: bad arguments, missing file, limit exceeded |
| `3` | Configuration error: no bot or key, unknown bot or chat alias, alias exists, bad config file |
| `4` | Network error: Telegram unreachable or timed out |
| `130` | Interrupted |

Bot tokens and the encryption key never appear in any output.

## Agent Skill

[`skills/tgbot/`](skills/tgbot/SKILL.md) is an [Agent Skill](https://agentskills.io/specification)
that teaches agents how to use `tgbot`. Copy or symlink it into your agent's skills directory
(e.g. `~/.claude/skills/tgbot`).

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

```
src/tgbot_cli/
├── cli.py         # root Typer app, exit-code mapping
├── config.py      # pydantic-settings (TGBOT_*, .env, config.toml)
├── crypto.py      # Fernet encryption of saved bot tokens
├── console.py     # output facade: rich | plain | json
├── errors.py      # error hierarchy -> exit codes
├── telegram.py    # write-only Bot API client (allowlist)
├── db.py          # sqlite3 chat aliases and saved bots
├── resolver.py    # alias -> chat_id
├── media.py       # file/URL/file_id inputs, limits, text chunking
└── commands/      # bot, key, chat, send, info
```
