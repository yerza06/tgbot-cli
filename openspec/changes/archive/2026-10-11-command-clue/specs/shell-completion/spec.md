# Spec Delta

## Purpose

Gives `tgbot` shell tab-completion, as `git` has: subcommands, options, saved chat aliases and saved bot aliases are suggested on <Tab>, so users do not have to remember names or run `tgbot chat list` first.

## ADDED Requirements

### Requirement: Commands are completed
Pressing <Tab> after `tgbot` or after a command group (`chat`, `bot`, `key`) SHALL suggest matching subcommands, with their short help as the description where the shell supports it.

#### Scenario: Top-level command prefix
- **WHEN** completion is requested for `tgbot cha`
- **THEN** `chat` is suggested with its help text

#### Scenario: Subcommands of a group
- **WHEN** completion is requested for `tgbot chat ` (empty current word)
- **THEN** the suggestions include `add`, `list`, `get-id`, `default`, `replace-id`, `rename` and `remove`

### Requirement: Options are completed after `-`
When the current word starts with `-`, completion SHALL suggest the options of the current command that match it, with their help text as the description. This SHALL take precedence over chat alias and file completion, including where a target or a media file is expected.

#### Scenario: Global options
- **WHEN** completion is requested for `tgbot -`
- **THEN** `--plain`, `--json`, `--version` and `--help` are suggested with descriptions

#### Scenario: Options where a target is expected
- **WHEN** chat `me` is saved and completion is requested for `tgbot send "hi" -`
- **THEN** `--to`, `--bot`, `--parse-mode`, `--silent` and `--json` are suggested, and `me` is not

#### Scenario: Options after a media file
- **WHEN** completion is requested for `tgbot sendphoto shot.png -`
- **THEN** options including `--caption` and `--to` are suggested instead of file paths or aliases

### Requirement: Option values with fixed choices are completed
For options that accept a fixed set of values, completion SHALL suggest those values and SHALL NOT fall back to file paths.

#### Scenario: Parse mode
- **WHEN** completion is requested for `tgbot send "hi" me --parse-mode `
- **THEN** `html` and `markdown` are suggested

#### Scenario: Dice emoji
- **WHEN** completion is requested for `tgbot senddice --emoji `
- **THEN** the six supported dice emoji are suggested and no file paths are offered

### Requirement: Saved chat aliases are completed for targets
Wherever a chat target is expected, completion SHALL suggest saved chat aliases that start with the current word. The description of each suggestion SHALL show the chat ID and the chat title when one is saved. This applies to the `--to` option, the positional target of `send` and `senddice`, and the alias NAME of `chat get-id`, `chat default`, `chat replace-id`, `chat rename` (old name) and `chat remove`.

#### Scenario: Positional target of send
- **WHEN** chats `me` and `team` are saved and completion is requested for `tgbot send "hi" `
- **THEN** `me` and `team` are suggested

#### Scenario: Prefix filters aliases
- **WHEN** chats `me` and `team` are saved and completion is requested for `tgbot send "hi" --to t`
- **THEN** only `team` is suggested

#### Scenario: Chat management argument
- **WHEN** chat `team` is saved and completion is requested for `tgbot chat remove `
- **THEN** `team` is suggested

#### Scenario: New alias names are not completed
- **WHEN** completion is requested for the NAME of `tgbot chat add ` or the new name of `tgbot chat rename team `
- **THEN** no saved aliases are suggested

### Requirement: Saved bot aliases are completed
Completion SHALL suggest saved bot aliases that start with the current word for the `--bot` option of every command that has it and for the alias NAME of `bot default`, `bot rename` (old name) and `bot remove`. The description SHALL show the bot's `@username` when known.

#### Scenario: --bot option
- **WHEN** bots `main` and `alerts` are saved and completion is requested for `tgbot send "hi" me --bot `
- **THEN** `main` and `alerts` are suggested

#### Scenario: Bot management argument
- **WHEN** bot `alerts` is saved and completion is requested for `tgbot bot default a`
- **THEN** `alerts` is suggested

### Requirement: Media commands keep file completion
For media sending commands (`sendphoto`, `sendfile`, `sendvideo`, `sendaudio`, `sendvoice`, `sendanimation`, `sendvideonote`, `sendsticker`), the positional arguments SHALL complete as file paths. Saved chat aliases SHALL be suggested only after at least one media argument has been given and only when at least one alias starts with the current word. Otherwise the shell's normal file path completion is used.

#### Scenario: First argument is a file
- **WHEN** chat `me` is saved and completion is requested for `tgbot sendphoto `
- **THEN** file paths are completed and no chat aliases are suggested

#### Scenario: Target after a file
- **WHEN** chat `me` is saved and completion is requested for `tgbot sendphoto shot.png m`
- **THEN** `me` is suggested

#### Scenario: Second file after a file
- **WHEN** no saved alias starts with `./` and completion is requested for `tgbot sendphoto shot.png ./`
- **THEN** file paths are completed

### Requirement: Completion is read-only and silent
Computing completions SHALL NOT create or modify any file or directory (including the config directory, `tgbot.db` and `config.toml`). It SHALL NOT make network requests, SHALL NOT need the encryption key and SHALL NOT decrypt tokens. It SHALL NOT print errors. When the database is missing or unreadable, or the configuration is invalid, alias completion SHALL produce no suggestions.

#### Scenario: Fresh install without config directory
- **WHEN** the config directory does not exist and completion is requested for `tgbot send "hi" `
- **THEN** no aliases are suggested, nothing is printed to stderr, and the config directory still does not exist

#### Scenario: Broken config file
- **WHEN** `config.toml` is not valid TOML and completion is requested for `tgbot send "hi" --to `
- **THEN** no aliases are suggested and no error is printed

#### Scenario: No secret key
- **WHEN** `TGBOT_SECRET_KEY` is not configured and bots are saved
- **THEN** completion for `--bot ` still suggests the saved bot aliases

### Requirement: Completion can be installed for the user's shell
The CLI SHALL keep the `--install-completion [SHELL]` and `--show-completion [SHELL]` options, supporting at least zsh, bash and fish. The README SHALL document installation for zsh, including a setup that works with oh-my-zsh.

#### Scenario: Show zsh script
- **WHEN** the user runs `tgbot --show-completion zsh`
- **THEN** a zsh completion script for `tgbot` is printed to stdout and the exit code is 0
