# Spec Delta

## Purpose

Gives the user one readable configuration file in the config directory for non-secret preferences — default bot, default chat, colored output and connection settings — with a clear precedence against environment variables and command-line flags.

## ADDED Requirements

### Requirement: Configuration file location and format
The system SHALL read optional non-secret settings from `<config_dir>/config.toml` (default `~/.config/tgbot/config.toml`, moved with `TGBOT_CONFIG_DIR`). Supported keys SHALL be `default_bot`, `default_chat`, `color`, `api_url` and `timeout`. A missing file SHALL behave as an empty one; unknown keys SHALL be ignored.

#### Scenario: Settings read from the file
- **WHEN** `config.toml` contains `timeout = 5` and `api_url = "http://localhost:8081"`
- **THEN** requests go to `http://localhost:8081` with a 5-second timeout

#### Scenario: No configuration file
- **WHEN** `config.toml` does not exist
- **THEN** commands run with the built-in defaults and no file is created

#### Scenario: Custom config directory
- **WHEN** `TGBOT_CONFIG_DIR` points to another directory containing `config.toml`
- **THEN** settings are read from that directory's `config.toml`

### Requirement: Settings precedence
For every setting the system SHALL apply, from highest to lowest priority: the command-line flag, the `TGBOT_*` environment variable, `<config_dir>/.env`, `config.toml`, the built-in default. The environment variable for a file key SHALL be `TGBOT_` plus the upper-cased key (e.g. `TGBOT_DEFAULT_CHAT`).

#### Scenario: Environment overrides file
- **WHEN** `config.toml` has `default_chat = "me"` and `TGBOT_DEFAULT_CHAT=team` is set
- **THEN** a send without a target goes to `team`

#### Scenario: Flag overrides everything
- **WHEN** `config.toml` has `default_bot = "news"`, `TGBOT_DEFAULT_BOT=alerts` is set, and the user passes `--bot daily`
- **THEN** the bot `daily` is used

### Requirement: Invalid configuration file is reported clearly
When `config.toml` is not valid TOML or a supported key has a value of the wrong type, every command SHALL stop before any network call, report the file path and the problem, and exit with the configuration exit code.

#### Scenario: Broken TOML
- **WHEN** `config.toml` contains `default_bot = ` (no value) and the user runs `tgbot send "hi" me`
- **THEN** no request is made, the error names the `config.toml` path, and the exit code is the configuration exit code

#### Scenario: Wrong value type
- **WHEN** `config.toml` contains `timeout = "soon"`
- **THEN** the error names the `timeout` key and the exit code is the configuration exit code

### Requirement: Sending uses the default chat when no target is given
When a send command receives no target (no `--to` and no positional target), the system SHALL send to `default_chat`, which MAY be a saved alias, a numeric chat ID or a `@channel`. Positional parsing SHALL be unchanged: a token in the target position is always the target, so a caption given positionally still needs a target before it.

#### Scenario: Text without a target
- **WHEN** `config.toml` has `default_chat = "me"` and the user runs `tgbot send "hi"`
- **THEN** the message is sent to the chat saved as `me`

#### Scenario: Media without a target
- **WHEN** `default_chat = "me"` is configured and the user runs `tgbot sendphoto a.png --caption "cap"`
- **THEN** the photo is sent to `me` with caption `cap`

#### Scenario: Explicit target wins
- **WHEN** `default_chat = "me"` is configured and the user runs `tgbot send "hi" team`
- **THEN** the message is sent to `team`

#### Scenario: No target and no default chat
- **WHEN** no `default_chat` is configured and the user runs `tgbot send "hi"`
- **THEN** no request is made and a usage error says no target was given and mentions `tgbot chat default`

### Requirement: Default chat can be set from the CLI
The system SHALL provide `tgbot chat default NAME`, which checks that NAME is a saved alias and writes `default_chat = "NAME"` to `config.toml`, creating the file if needed and keeping its other keys and comments.

#### Scenario: Set default chat
- **WHEN** chat `me` is saved and the user runs `tgbot chat default me`
- **THEN** `config.toml` contains `default_chat = "me"` and its other keys and comments are unchanged

#### Scenario: Unknown chat as default
- **WHEN** no chat `ghost` is saved and the user runs `tgbot chat default ghost`
- **THEN** `config.toml` is unchanged and the exit code is the configuration exit code

### Requirement: Colored output can be disabled in the configuration
The system SHALL treat `color = false` in `config.toml` like `--plain`: output has no colors, styles or box drawing. Plain output SHALL be used when any of `--plain`, `TGBOT_PLAIN`, `NO_COLOR`, `color = false` or a non-TTY stdout applies. JSON output SHALL be unaffected.

#### Scenario: color = false in the file
- **WHEN** `config.toml` contains `color = false` and the user runs `tgbot chat list` in a terminal
- **THEN** the output contains no ANSI escape codes and no box-drawing characters

#### Scenario: Default keeps colors
- **WHEN** `config.toml` does not set `color`, no other plain setting applies, and stdout is a TTY
- **THEN** styled output is used
