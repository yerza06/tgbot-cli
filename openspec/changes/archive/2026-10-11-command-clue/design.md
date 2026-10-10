# Design

## Context

- `cli.py` already builds the Typer app with `add_completion=True`. `tgbot --show-completion zsh` prints a script that calls `tgbot` with `_TGBOT_COMPLETE=complete_zsh` and `_TYPER_COMPLETE_ARGS="<words>"`. This works with the `run()` wrapper (`prog_name="tgbot"`, `standalone_mode=False`): I checked that `tgbot cha` completes to `chat`.
- Typer's zsh formatter (`typer._completion_classes.ZshComplete.complete`) emits `_arguments '*: :(("value":"help" …))'` when a completer returns items. When it returns none, it emits `_files`. A single completion cannot mix aliases and file paths.
- Click runs completion with `resilient_parsing`, so the root callback (`out.configure`, `get_settings`) does not run. Completers are called with the partly parsed `ctx` and the `incomplete` word.
- `db.open_db()` runs `mkdir` and `executescript(SCHEMA)`, so it creates and writes files. The completion path cannot use it.
- `get_settings()` raises `ConfigError` on a broken `config.toml` or invalid env values.
- The user's shell is zsh with oh-my-zsh, which runs `compinit` from `oh-my-zsh.sh`. One completion call takes about 0.6 s, mostly Python start-up. Importing `tgbot_cli.cli` takes about 0.13 s of that.

## Goals / Non-Goals

**Goals:**
- Dynamic completers for chat and bot aliases, attached to the existing option and argument declarations.
- A completion path that never writes anything, raises errors or touches the network or key.
- Documented, tested installation for zsh.

**Non-Goals:**
- A hand-written `_tgbot` zsh completion function. We keep Typer's generated script.
- Completing values that are not stored locally: `@channel` usernames, numeric chat IDs, `file_id`s, or targets of `sendcontact`/`sendlocation`/`sendpoll` given positionally (`--to` still completes there).
- Startup-time optimisation (lazy imports). It could follow later if 0.6 s per <Tab> feels slow.
- Editing the user's `~/.zshrc` from code paths other than Typer's explicit `--install-completion`.

## Decisions

1. **New module `tgbot_cli/completion.py`.** It holds `complete_chat(ctx, incomplete)`, `complete_bot(ctx, incomplete)` and `complete_target_after_media(ctx, incomplete)`, which return `list[tuple[str, str]]` (value, help). Typer turns these into `CompletionItem`s with descriptions. Keeping them in one module keeps the commands thin and gives tests a single place to call.
   - *Alternative:* inline lambdas in each command. Rejected because the code would be duplicated and harder to test.

2. **Read-only DB access.** Add `db.open_db_readonly(path)`, or a private helper in `completion.py`, that returns no rows when the file does not exist. Otherwise it connects with `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` and queries `chats` / `bots` (name, chat_id, title / name, username) directly. It does not run the schema script. All exceptions (`sqlite3.Error`, `ConfigError`, `OSError`, …) are caught and turned into `[]`.
   - *Alternative:* reuse `open_db()`. Rejected because it creates the config dir and the DB, which violates the read-only requirement.

3. **Locating the DB.** Call `get_settings().db_path` inside the same `try` block. This respects `TGBOT_CONFIG_DIR` like every other command, and a broken config produces no suggestions. `secret_key` is never read.

4. **Attaching completers.**
   - `options.py`: `ToOpt` gets `autocompletion=complete_chat` and `BotOpt` gets `autocompletion=complete_bot`. Every command using them picks this up.
   - `chat.py`: a separate `ExistingNameArg` (with `complete_chat`) is used by `get-id`, `default`, `replace-id`, `remove` and `rename`'s `old_name`. `NameArg` for `add` and `rename`'s `new_name` stays without completion, because those are new names.
   - `bot.py`: the same pattern for `default`, `remove` and `rename`'s `old_name`.
   - `send.py`: `send`'s and `senddice`'s `rest` get `complete_chat`. The media `content` arguments of the eight media commands get `complete_target_after_media`.

5. **Media heuristic.** `complete_target_after_media` reads the arguments already parsed for this parameter from `ctx.params` (or `ctx.args`). With zero, it returns `[]`, so zsh does file completion. Otherwise it returns the aliases matching `incomplete`. If none match, the result is `[]` again, so zsh falls back to `_files`. This works around the "aliases or `_files`, not both" limit without a custom zsh script.
   - *Alternative:* always return aliases plus files listed in Python. Rejected because it duplicates zsh's path completion and loses `~`, globbing and directory navigation.

6. **Descriptions.** Chats use `"<chat_id> · <title>"` (or just the chat ID). Bots use `"@username"` (or the bot ID). Typer escapes and truncates the text for zsh.

7. **Installation docs.** Add a README section, "Shell completion":
   - zsh (generic): `tgbot --install-completion zsh`, then `exec zsh`.
   - zsh + oh-my-zsh: `mkdir -p ~/.oh-my-zsh/custom/completions && tgbot --show-completion zsh > ~/.oh-my-zsh/custom/completions/_tgbot`. Append a line `_tgbot_completion "$@"` to that file: Typer's script only registers itself when zsh autoloads it, so without this line the first <Tab> completes nothing. Add `fpath+=~/.oh-my-zsh/custom/completions` before `source $ZSH/oh-my-zsh.sh`, then run `rm -f ~/.zcompdump*; exec zsh`. This avoids a second `compinit` call and avoids running Python at every shell start, which `eval "$(tgbot --show-completion zsh)"` would do.
   - bash/fish: `tgbot --install-completion bash|fish`.
   - The README must pass `tests/test_docs.py`. It only extracts non-option words, so `tgbot --install-completion zsh` maps to the path `("zsh",)`, which is not a real command. The section therefore shows these commands as `console` blocks or `tgbot --show-completion …` forms. Alternatively, it adjusts `_command_paths` to skip invocations that start with an option. Decide while implementing, and keep the docs test green.

8. **Options after `-` and fixed option values.** Click resolves a word starting with `-` to option completion before it calls any parameter completer. Our completers therefore do not handle `-` themselves, and tests pin this behaviour. `--parse-mode` already completes from its `ParseMode` enum. `--emoji` is a plain `str`, so it gets `complete_dice_emoji`, which returns `DICE_EMOJI`. Otherwise zsh falls back to `_files`.
   - *Alternative:* turn `--emoji` into an Enum. Rejected because it would change the help text and error messages for no benefit.

## Risks / Trade-offs

- [About 0.6 s Python start-up per <Tab>] → Acceptable for now and listed as a non-goal. Completion does not import more than the normal CLI.
- [Typer's private `_completion_classes` behaviour (`_files` fallback) may change in a Typer upgrade] → Tests exercise the real `_TGBOT_COMPLETE=complete_zsh` path end-to-end, so an upgrade that breaks it fails CI.
- [Media heuristic: a second file whose name starts like an alias (e.g. `me.png` vs alias `me`) gets alias suggestions first] → The user can type `./` to force path completion. Document this in the README.
- [`ctx.params` contents during resilient parsing differ between Click versions] → Cover with a test, and fall back to "no aliases" when the parsed list is unavailable.
- [A Typer/Click upgrade changes how `-` is resolved] → Tests in task 2.4 fail.
- [Typer's `--install-completion zsh` appends `compinit` to `~/.zshrc`, which runs it twice with oh-my-zsh] → Harmless but slower. The README recommends the oh-my-zsh variant.
