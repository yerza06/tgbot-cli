# Spec Delta

## Purpose

Lets the user configure the Telegram bot token the CLI sends with, check that it works, and see where configuration lives, so that agents can send without any interactive login.

## ADDED Requirements

### Requirement: Token can be set interactively
The system SHALL provide `tgbot token set`. It prompts for the token without echoing it, validates the token against Telegram, and stores it in the user config file `<config_dir>/.env` with owner-only permissions (0600). The token MAY also be passed as an argument for non-interactive use.

#### Scenario: Valid token is saved
- **WHEN** the user runs `tgbot token set` and enters a token that Telegram accepts
- **THEN** the token is written to `<config_dir>/.env`, the file mode is 0600, and the bot's username is reported

#### Scenario: Invalid token is rejected
- **WHEN** the user enters a token that Telegram rejects as unauthorized
- **THEN** nothing is written, an error is reported, and the command exits with the Telegram error exit code

#### Scenario: Existing settings are preserved
- **WHEN** `<config_dir>/.env` already contains other `TGBOT_` keys and a new token is set
- **THEN** only the token key is updated and the other keys remain unchanged

### Requirement: Configuration sources and precedence
The system SHALL read settings from environment variables prefixed `TGBOT_` and from `<config_dir>/.env`, with environment variables taking precedence. `config_dir` SHALL default to `~/.config/tgbot` and SHALL be overridable with `TGBOT_CONFIG_DIR`. The tool SHALL work from any working directory.

#### Scenario: Environment overrides file
- **WHEN** `<config_dir>/.env` holds token A and the environment sets `TGBOT_BOT_TOKEN` to token B
- **THEN** commands use token B

#### Scenario: Custom config directory
- **WHEN** `TGBOT_CONFIG_DIR` points to another directory
- **THEN** the token file and the chat database are read from and written to that directory

### Requirement: Missing token is reported clearly
The system SHALL stop any command that needs Telegram before making a network call when no token is configured. It SHALL explain how to set a token and exit with the configuration exit code.

#### Scenario: Send without token
- **WHEN** no token is configured and the user runs `tgbot send "hi" 123`
- **THEN** no request is made, the error mentions `tgbot token set` and `TGBOT_BOT_TOKEN`, and the exit code is the configuration exit code

### Requirement: Bot identity can be inspected
The system SHALL provide `tgbot whoami`. It reports the configured bot's ID, username and display name, as returned by Telegram.

#### Scenario: whoami with valid token
- **WHEN** a valid token is configured and the user runs `tgbot whoami`
- **THEN** the bot's ID, `@username` and name are printed

### Requirement: Version and paths can be inspected
The system SHALL provide `tgbot version` and `tgbot --version`. They print the tool version. `tgbot version` SHALL also show the config directory, the database path and whether a token is configured, without revealing the token itself.

#### Scenario: version output hides the token
- **WHEN** a token is configured and the user runs `tgbot version`
- **THEN** the output shows the version, the config directory, the database path and "token: configured", and does not contain the token value
