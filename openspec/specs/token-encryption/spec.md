# token-encryption Specification

## Purpose

Keeps saved bot tokens unreadable at rest: tokens are stored only in encrypted form, the encryption key comes from a single explicit setting the user creates once, and a missing or wrong key fails clearly instead of leaking or corrupting tokens.

## Requirements

### Requirement: Tokens are stored encrypted
The system SHALL store each saved bot token in the database only as authenticated symmetric ciphertext. The plaintext token SHALL NOT be written to the database, `config.toml`, `.env`, or any other file.

#### Scenario: Database contains no plaintext token
- **WHEN** the user adds a bot with token `123456:SECRET`
- **THEN** the database file does not contain the bytes `123456:SECRET`

#### Scenario: Same token encrypts differently
- **WHEN** the same token is saved under two aliases
- **THEN** the two stored ciphertexts differ

### Requirement: Encryption key source
The system SHALL read the encryption key only from the `TGBOT_SECRET_KEY` setting: the environment variable, or `<config_dir>/.env` when the variable is not set. The environment variable SHALL take precedence. The key SHALL NOT be read from `config.toml`, and the system SHALL NOT create a key implicitly.

#### Scenario: Key from environment
- **WHEN** `TGBOT_SECRET_KEY` is set in the environment and `.env` holds a different key
- **THEN** tokens are encrypted and decrypted with the environment key

#### Scenario: Key from .env
- **WHEN** the environment does not set `TGBOT_SECRET_KEY` and `<config_dir>/.env` contains it
- **THEN** tokens are encrypted and decrypted with the key from `.env`

#### Scenario: No implicit key creation
- **WHEN** no key is configured and the user runs `tgbot bot add news`
- **THEN** no key is generated, no file is written, nothing is saved, and the command exits with the configuration exit code

### Requirement: Key can be generated with a command
The system SHALL provide `tgbot key init`. It generates a new random key and writes `TGBOT_SECRET_KEY=<key>` to `<config_dir>/.env` with owner-only permissions (0600), preserving the other lines of that file. It SHALL report the file path and SHALL NOT print the key.

#### Scenario: First key is created
- **WHEN** no key is configured and the user runs `tgbot key init`
- **THEN** `<config_dir>/.env` contains `TGBOT_SECRET_KEY`, its mode is 0600, the output names the file, and the output does not contain the key

#### Scenario: Other .env lines are preserved
- **WHEN** `<config_dir>/.env` already contains other `TGBOT_` keys and the user runs `tgbot key init`
- **THEN** only `TGBOT_SECRET_KEY` is added and the other keys remain unchanged

### Requirement: Existing key is not overwritten by accident
When a key is already configured (in the environment or `.env`), `tgbot key init` SHALL refuse and exit with the configuration exit code. With `--force` it SHALL replace the key in `.env` and warn that bots saved with the old key must be added again.

#### Scenario: Key already exists
- **WHEN** `.env` already holds `TGBOT_SECRET_KEY` and the user runs `tgbot key init`
- **THEN** the file is unchanged, the error mentions `--force`, and the exit code is the configuration exit code

#### Scenario: Forced replacement
- **WHEN** `.env` holds a key, two bots are saved, and the user runs `tgbot key init --force`
- **THEN** `.env` holds a new key and the output warns that the two saved bots can no longer be decrypted and must be re-added

### Requirement: Missing key is reported clearly
When a token must be encrypted or decrypted and no key is configured, the system SHALL stop before any network call, explain that the key is missing, point to `tgbot key init` (and, if bots are already saved, to restoring the old key), and exit with the configuration exit code.

#### Scenario: Add bot without a key
- **WHEN** no key is configured and the user runs `tgbot bot add news 123456:ABC`
- **THEN** no request is made and the error mentions `tgbot key init`

#### Scenario: Key removed after bots were saved
- **WHEN** bots are saved, `TGBOT_SECRET_KEY` has been removed from `.env` and the environment, and the user runs `tgbot send "hi" me`
- **THEN** no request is made and the configuration error mentions the missing key

### Requirement: Wrong or invalid key is reported clearly
When the configured key is malformed, or cannot decrypt a stored token, the system SHALL stop before any network call, report the problem without printing the key or token, and exit with the configuration exit code.

#### Scenario: Key does not match stored tokens
- **WHEN** a bot was saved with key A and the user runs `tgbot send "hi" me` with `TGBOT_SECRET_KEY` set to a different valid key B
- **THEN** no request is made and a configuration error says the token cannot be decrypted with the current key

#### Scenario: Malformed key
- **WHEN** `TGBOT_SECRET_KEY` is set to a value that is not a valid key
- **THEN** the command exits with the configuration exit code and the output does not contain that value

### Requirement: Tokens never appear in output
Decrypted tokens SHALL NOT appear in any command output, error message or JSON, including Telegram error descriptions or network errors that echo the request URL.

#### Scenario: Telegram error does not leak the token
- **WHEN** a send fails with a network error whose message contains the request URL
- **THEN** the reported error shows the token masked and never in plaintext

#### Scenario: bot add output hides the token
- **WHEN** the user runs `tgbot bot add news 123456:SECRET --json`
- **THEN** neither stdout nor stderr contains `123456:SECRET`
