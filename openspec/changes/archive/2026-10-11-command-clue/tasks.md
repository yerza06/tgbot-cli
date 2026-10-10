# Tasks

## 1. Completion helpers

- [x] 1.1 Create `src/tgbot_cli/completion.py` (design D1–D3, D6). Add `complete_chat(incomplete)` and `complete_bot(incomplete)`, which return `(value, help)` pairs filtered by prefix. Locate the DB with `get_settings().db_path`, then return `[]` when the file is missing. Otherwise open it read-only (`file:…?mode=ro`, `uri=True`), and turn every exception into `[]`. Chats use the help `"<chat_id> · <title>"` (or just the chat ID). Bots use `@username` (or the ID). Verify with new `tests/test_completion.py` that calls the functions directly:
  - saved chats and bots are returned with descriptions, and a prefix filters them;
  - a missing config dir returns `[]`, and the dir is still absent afterwards;
  - broken `config.toml` returns `[]`;
  - without `TGBOT_SECRET_KEY`, saved bots are still returned;
  - the DB file's mtime and size do not change.

  Run `uv run ruff check . && uv run ruff format --check .`.
- [x] 1.2 Add `complete_target_after_media(ctx, incomplete)` (design D5). It returns `[]` when no media argument has been parsed yet. Otherwise it returns the matching chat aliases, or `[]` when none match. Verify with pytest in `tests/test_completion.py` through the real completion path. Add a helper that runs `run([])` with `_TGBOT_COMPLETE=complete_zsh` and `_TYPER_COMPLETE_ARGS` set, and captures stdout and `SystemExit`. Check these cases:
  - `tgbot sendphoto ` gives `_files`;
  - `tgbot sendphoto shot.png m` offers `me`;
  - `tgbot sendphoto shot.png ./` gives `_files`.

  Run ruff.

## 2. Wire completers into commands

- [x] 2.1 In `commands/options.py`, add `autocompletion=complete_chat` to `ToOpt` and `autocompletion=complete_bot` to `BotOpt`. Verify with the end-to-end helper in `tests/test_completion.py`:
  - `tgbot send "hi" --to t` offers only `team`;
  - `tgbot send "hi" me --bot ` offers `main` and `alerts`;
  - `tgbot whoami --bot ` offers bots.

  Run ruff.
- [x] 2.2 In `commands/send.py`, attach `complete_chat` to the `rest` argument of `send` and `senddice`. Attach `complete_target_after_media` to the media `content` arguments of all eight media commands. Verify with pytest:
  - `tgbot send "hi" ` offers `me` and `team`;
  - `tgbot senddice ` offers aliases;
  - parametrize over the eight media commands, checking that the first argument gives `_files` and that a matching alias after a file is offered.

  Make sure the existing `tests/test_send_*.py` still pass. Run ruff.
- [x] 2.3 In `commands/chat.py`, add `ExistingNameArg` with `complete_chat`. Use it in `get-id`, `default`, `replace-id`, `remove` and `rename`'s `old_name`. `add` and `rename`'s new name keep `NameArg` without completion. Do the same in `commands/bot.py` for `default`, `remove` and `rename`'s old name, using `complete_bot`. Verify with pytest:
  - `tgbot chat remove ` offers saved chats;
  - `tgbot bot default a` offers `alerts`;
  - `tgbot chat add ` and `tgbot chat rename team ` do not offer aliases.

  Make sure `tests/test_chat.py` and `tests/test_bot.py` still pass. Run ruff.
- [x] 2.4 Add regression tests for the static completion and the install options. Check that `tgbot cha` offers `chat` with its help, and that `tgbot chat ` offers all chat subcommands. Check that `tgbot --show-completion zsh` exits 0 and prints a script containing `compdef` and `_TGBOT_COMPLETE`. Check options after `-`: `tgbot -` offers global options with descriptions, `tgbot send "hi" -` offers `--to`/`--bot`/`--silent` and no aliases, `tgbot sendphoto shot.png -` offers `--caption`, and `tgbot chat add -` offers `--no-resolve`. Check that `--parse-mode ` offers `html` and `markdown`. Verify with `uv run pytest tests/test_completion.py`.
- [x] 2.5 Add `complete_dice_emoji` and attach it to `senddice --emoji` (design D8). Verify with pytest that `tgbot senddice --emoji ` offers all six `DICE_EMOJI` values and not `_files`. Run ruff.

## 3. Documentation

- [x] 3.1 Add a "Shell completion" section to `README.md` (design D7). Cover:
  - generic zsh: `--install-completion zsh` and `exec zsh`;
  - zsh with oh-my-zsh: generate `_tgbot` into `~/.oh-my-zsh/custom/completions`, add `fpath+=…` before `source $ZSH/oh-my-zsh.sh`, then clear `.zcompdump` and restart;
  - bash and fish;
  - what gets completed;
  - the `./` tip for media commands.

  Keep `tests/test_docs.py` green: either write the commands so the parser does not treat `zsh` as a command, or teach `_command_paths` to skip invocations that start with an option, and cover that with a test. Add a short line about completion to `skills/tgbot/references/reference.md` only if it lists global options. Verify that `uv run pytest tests/test_docs.py` passes. Run ruff.

## 4. Integration check

- [x] 4.1 Run the full suite and lint: `uv run ruff check . && uv run ruff format --check . && uv run pytest`. All must pass.
- [x] 4.2 Reinstall the tool (`uv tool install . --force`) and install completion in the real zsh (oh-my-zsh variant from the README). Then check these by hand in a new shell:
  - `tgbot <Tab>` lists commands with descriptions;
  - `tgbot send "hi" <Tab>` lists saved chats;
  - `tgbot send "hi" me --bot <Tab>` lists saved bots;
  - `tgbot sendphoto <Tab>` completes files.
