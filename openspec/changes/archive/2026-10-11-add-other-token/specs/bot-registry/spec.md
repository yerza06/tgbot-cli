# Spec Delta

## Purpose

Lets the user save several Telegram bots under short aliases, manage them like saved chats, and choose which bot each command sends as, so agents can write from different bots without handling raw tokens.

## ADDED Requirements

### Requirement: Bot can be added under an alias
The system SHALL provide `tgbot bot add NAME [TOKEN]`. When TOKEN is omitted it is prompted without echo. The token is validated with Telegram before saving; the bot's numeric ID and `@username` are stored with the alias. Adding a bot SHALL require a configured encryption key (see token-encryption).

#### Scenario: Valid token is saved under an alias
- **WHEN** the user runs `tgbot bot add news` and enters a token that Telegram accepts
- **THEN** a bot named `news` is saved with the bot's ID and username, and the output reports the alias and `@username`

#### Scenario: Token passed as argument
- **WHEN** the user runs `tgbot bot add news 123456:ABC` with a valid token
- **THEN** the bot is saved without any prompt

#### Scenario: Invalid token is rejected
- **WHEN** the user runs `tgbot bot add news` with a token Telegram rejects as unauthorized
- **THEN** nothing is saved, an error is reported, and the command exits with the Telegram error exit code

#### Scenario: Empty token is rejected
- **WHEN** the user enters an empty or whitespace-only token
- **THEN** nothing is saved, no request is made, and the command exits with the usage error exit code

#### Scenario: No encryption key configured
- **WHEN** no `TGBOT_SECRET_KEY` is configured and the user runs `tgbot bot add news 123456:ABC`
- **THEN** no request is made, nothing is saved, the error mentions `tgbot key init`, and the exit code is the configuration exit code

#### Scenario: Duplicate alias is rejected
- **WHEN** a bot named `news` already exists and the user runs `tgbot bot add news` again
- **THEN** no request is made, nothing is changed, and the command exits with the configuration exit code

### Requirement: First bot becomes the default
The default bot SHALL be stored as `default_bot` in `<config_dir>/config.toml`. When a bot is added and `default_bot` is not set, the system SHALL set it to the new bot's alias; adding further bots SHALL NOT change it.

#### Scenario: First bot is default
- **WHEN** no bots are saved, `config.toml` has no `default_bot`, and the user adds `news`
- **THEN** `config.toml` contains `default_bot = "news"` and `news` is the default bot

#### Scenario: Second bot does not take over
- **WHEN** `news` is the default and the user adds `alerts`
- **THEN** `news` remains the default

### Requirement: Default bot can be changed
The system SHALL provide `tgbot bot default NAME`, which checks that the bot exists and writes `default_bot = "NAME"` to `config.toml`, keeping the file's other keys and comments.

#### Scenario: Change default
- **WHEN** `news` is the default and the user runs `tgbot bot default alerts`
- **THEN** `config.toml` contains `default_bot = "alerts"`, its other keys and comments are unchanged, and `alerts` is the default

#### Scenario: Unknown bot as default
- **WHEN** the user runs `tgbot bot default missing` and no such bot exists
- **THEN** the default is unchanged and the command exits with the configuration exit code

### Requirement: Saved bots can be listed
The system SHALL provide `tgbot bot list`, and `tgbot bot` without a subcommand SHALL behave the same. The list SHALL show each alias, bot username, bot ID, which one is the default and when it was added. It SHALL NOT show tokens, in any output mode.

#### Scenario: List bots
- **WHEN** bots `news` (default) and `alerts` are saved and the user runs `tgbot bot list`
- **THEN** both aliases are shown with their usernames and IDs, `news` is marked as default, and no token value appears in the output

#### Scenario: List bots as JSON
- **WHEN** the user runs `tgbot bot list --json`
- **THEN** stdout is a JSON array with `name`, `bot_id`, `username`, `is_default` and `created_at` for each bot and no token field

#### Scenario: No bots saved
- **WHEN** no bots are saved and the user runs `tgbot bot`
- **THEN** a message explains how to add one with `tgbot bot add`

### Requirement: Bot can be renamed
The system SHALL provide `tgbot bot rename OLD NEW`. The token and bot identity SHALL be preserved; when the renamed bot is the `default_bot` in `config.toml`, the system SHALL update that value to the new alias.

#### Scenario: Rename bot
- **WHEN** `news` is the default and the user runs `tgbot bot rename news daily`
- **THEN** the bot is available as `daily` with the same token, `config.toml` contains `default_bot = "daily"`, and `news` no longer exists

#### Scenario: Rename onto an existing alias
- **WHEN** both `news` and `alerts` exist and the user runs `tgbot bot rename news alerts`
- **THEN** nothing is changed and the command exits with the configuration exit code

### Requirement: Bot can be removed
The system SHALL provide `tgbot bot remove NAME`, which deletes the bot and its stored token. When the removed bot was the `default_bot`, the system SHALL set `default_bot` to the remaining bot with the earliest creation time, or remove the key when no bots remain.

#### Scenario: Remove non-default bot
- **WHEN** the user runs `tgbot bot remove alerts`
- **THEN** `alerts` is no longer listed and the default is unchanged

#### Scenario: Remove the default bot
- **WHEN** `news` is the default, `alerts` is the only other bot, and the user runs `tgbot bot remove news`
- **THEN** `news` is removed and `config.toml` contains `default_bot = "alerts"`

#### Scenario: Remove the last bot
- **WHEN** `news` is the only bot and the user runs `tgbot bot remove news`
- **THEN** `config.toml` no longer contains `default_bot`

#### Scenario: Remove unknown bot
- **WHEN** the user runs `tgbot bot remove missing`
- **THEN** the command exits with the configuration exit code

### Requirement: Commands choose the sending bot
Every command that talks to Telegram SHALL accept `--bot NAME`. The bot SHALL be chosen in this order: `--bot`, then `TGBOT_DEFAULT_BOT` (environment or `.env`), then `default_bot` from `config.toml`.

#### Scenario: Explicit bot flag
- **WHEN** `news` is the default and the user runs `tgbot send "hi" me --bot alerts`
- **THEN** the message is sent with the token of `alerts`

#### Scenario: Environment selects bot
- **WHEN** `config.toml` has `default_bot = "news"`, `TGBOT_DEFAULT_BOT=alerts` is set, and the user runs `tgbot send "hi" me` without `--bot`
- **THEN** the message is sent with the token of `alerts`

#### Scenario: Default bot is used
- **WHEN** neither `--bot` nor `TGBOT_DEFAULT_BOT` is given and `config.toml` has `default_bot = "news"`
- **THEN** the message is sent with the token of `news`

#### Scenario: Unknown bot alias
- **WHEN** the user runs `tgbot send "hi" me --bot missing`
- **THEN** no request is made, the error names the alias and points to `tgbot bot list`, and the exit code is the configuration exit code

#### Scenario: Configured default bot does not exist
- **WHEN** `config.toml` has `default_bot = "gone"`, no bot `gone` is saved, and the user runs `tgbot send "hi" me`
- **THEN** no request is made, the error names `gone` and points to `tgbot bot default`, and the exit code is the configuration exit code

### Requirement: Missing bot is reported clearly
When no bot is saved, any command that needs Telegram SHALL stop before making a network call, explain that a bot must be added with `tgbot bot add`, and exit with the configuration exit code.

#### Scenario: Send without any bot
- **WHEN** no bots are saved and the user runs `tgbot send "hi" 123`
- **THEN** no request is made, the error mentions `tgbot bot add`, and the exit code is the configuration exit code

### Requirement: Bot identity can be inspected
The system SHALL provide `tgbot whoami [--bot NAME]`. It reports the selected bot's alias, ID, username and display name as returned by Telegram.

#### Scenario: whoami for a chosen bot
- **WHEN** the user runs `tgbot whoami --bot alerts`
- **THEN** the alias `alerts` and that bot's ID, `@username` and name are printed

### Requirement: Version shows bot configuration without tokens
`tgbot version` SHALL show the tool version, the config directory, the `config.toml` path, the database path, the number of saved bots and the default bot's alias. It SHALL NOT reveal any token or the encryption key.

#### Scenario: version with saved bots
- **WHEN** two bots are saved with `news` as default and the user runs `tgbot version`
- **THEN** the output shows "2" saved bots and default `news`, and contains no token value and no key

### Requirement: Legacy single-token configuration is not used
The system SHALL NOT read a bot token from `TGBOT_BOT_TOKEN` or from `<config_dir>/.env`, and SHALL NOT provide `tgbot token set`. Bots SHALL come only from the saved bot registry.

#### Scenario: Legacy token variable is ignored
- **WHEN** `TGBOT_BOT_TOKEN` is set, no bots are saved, and the user runs `tgbot send "hi" 123`
- **THEN** no request is made and the "no bot" configuration error is reported

#### Scenario: Old command is gone
- **WHEN** the user runs `tgbot token set`
- **THEN** the command is rejected as unknown with the usage error exit code
