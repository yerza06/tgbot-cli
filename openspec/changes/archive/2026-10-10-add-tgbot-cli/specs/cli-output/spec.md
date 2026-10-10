# Spec Delta

## Purpose

Defines how the CLI reports results and errors, so that people get readable output and AI agents get stable, machine-parseable results and exit codes.

## ADDED Requirements

### Requirement: Rich output can be disabled
The system SHALL use styled Rich output (panels, tables, colors) by default. It SHALL switch to plain, unstyled text when any of these holds:
- `--plain` is given;
- `TGBOT_PLAIN` is true;
- `NO_COLOR` is set;
- stdout is not a terminal.

#### Scenario: Plain flag
- **WHEN** the user runs `tgbot --plain send "hi" me`
- **THEN** the success line contains no ANSI escape codes or box-drawing characters

#### Scenario: Piped output
- **WHEN** stdout is redirected to a file or a pipe
- **THEN** output is plain text

### Requirement: JSON output mode
The system SHALL support `--json`, both as a global option and on every send and chat command. In this mode a single JSON object is written: success to stdout, failure to stderr. Send success SHALL include `ok: true`, the resolved `chat_id`, and the list of `message_ids`. Failure SHALL include `ok: false`, `error` (a message) and `code` (the exit code).

#### Scenario: Successful send as JSON
- **WHEN** the user runs `tgbot send "hi" me --json` and Telegram returns message ID 42
- **THEN** stdout is `{"ok": true, "chat_id": 13342324, "message_ids": [42]}` and nothing else

#### Scenario: Failure as JSON
- **WHEN** a `--json` send fails because the alias is unknown
- **THEN** stderr holds a JSON object with `ok: false`, an `error` message and `code` 3, and stdout is empty

#### Scenario: Chat list as JSON
- **WHEN** the user runs `tgbot chat list --json`
- **THEN** stdout is a JSON array of objects with `name`, `chat_id`, `title` and `created_at`

### Requirement: Stable exit codes
The system SHALL exit with:
- `0` on success;
- `1` when Telegram rejects a request;
- `2` on usage errors (bad or missing arguments, invalid values, missing local files, limits exceeded);
- `3` on configuration errors (no token, unknown alias, alias already exists or not found);
- `4` on network errors (timeout, connection failure);
- `130` when interrupted.

#### Scenario: Network failure
- **WHEN** the Telegram API cannot be reached
- **THEN** the command reports a network error and exits with 4

#### Scenario: Telegram rejection
- **WHEN** Telegram returns `ok: false` with code 400
- **THEN** the command exits with 1

### Requirement: No raw tracebacks and no secret leakage
The system SHALL report unexpected failures as a short error message, not a Python traceback. No output, error or JSON object SHALL contain the bot token, including in the URLs of failed requests.

#### Scenario: Error message hides token
- **WHEN** a network error occurs while calling `https://api.telegram.org/bot<TOKEN>/sendMessage`
- **THEN** the reported error does not contain `<TOKEN>`

### Requirement: English user interface
The system SHALL present all help text, prompts, messages and errors in English.

#### Scenario: Help is English
- **WHEN** the user runs `tgbot --help`
- **THEN** the command descriptions are in English
