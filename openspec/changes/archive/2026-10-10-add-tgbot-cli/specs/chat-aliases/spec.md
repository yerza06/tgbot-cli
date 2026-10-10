# Spec Delta

## Purpose

Lets users and agents refer to Telegram chats by memorable names (like `git remote`) instead of numeric IDs. Aliases are stored in a local SQLite database.

## ADDED Requirements

### Requirement: Add an alias
The system SHALL provide `tgbot chat add NAME CHAT_ID`. It stores the mapping in the local database. Alias names SHALL be unique. Negative IDs (for example `-1001234567890`) SHALL be accepted as positional arguments.

#### Scenario: Add a user alias
- **WHEN** the user runs `tgbot chat add me 13342324`
- **THEN** alias `me` maps to `13342324` and a confirmation is shown

#### Scenario: Add a negative group ID
- **WHEN** the user runs `tgbot chat add team -1001234567890`
- **THEN** alias `team` maps to `-1001234567890` and the value is not parsed as an option

#### Scenario: Duplicate name
- **WHEN** alias `me` exists and the user runs `tgbot chat add me 999`
- **THEN** the existing mapping is unchanged, an error says the alias already exists, and the exit code is non-zero

### Requirement: Resolve public channel usernames on add
The system SHALL resolve a `CHAT_ID` given as `@username` through Telegram, when a token is configured, and store the numeric ID and chat title. With `--no-resolve`, or when resolution fails, it SHALL store the value as given and report why.

#### Scenario: Resolve a public channel
- **WHEN** the user runs `tgbot chat add news @mychannel` and Telegram knows the channel
- **THEN** the alias stores the channel's numeric ID and title

#### Scenario: Resolution not possible
- **WHEN** the user runs `tgbot chat add news @mychannel` and no token is configured
- **THEN** the alias stores `@mychannel` as given and a notice explains that it was not resolved

### Requirement: List aliases
The system SHALL provide `tgbot chat list`. Running `tgbot chat` with no subcommand SHALL do the same. The list shows each alias with its chat ID, title and creation time, sorted by name. An empty database SHALL produce a friendly message, not an error.

#### Scenario: List existing aliases
- **WHEN** aliases `me` and `team` exist and the user runs `tgbot chat`
- **THEN** both are listed in name order with their IDs

#### Scenario: Empty list
- **WHEN** no aliases exist and the user runs `tgbot chat list`
- **THEN** a message says there are no saved chats and the exit code is 0

### Requirement: Look up, change, rename and remove aliases
The system SHALL provide these commands:
- `tgbot chat get-id NAME` prints only the ID;
- `tgbot chat replace-id NAME NEW_ID`;
- `tgbot chat rename OLD NEW`;
- `tgbot chat remove NAME`.

Each SHALL fail with a non-zero exit code when the alias does not exist. `rename` SHALL also fail when NEW already exists.

#### Scenario: get-id prints bare value
- **WHEN** alias `me` maps to `13342324` and the user runs `tgbot chat get-id me`
- **THEN** stdout is exactly `13342324` followed by a newline

#### Scenario: Rename onto existing name
- **WHEN** aliases `a` and `b` exist and the user runs `tgbot chat rename a b`
- **THEN** nothing changes and an error says `b` already exists

#### Scenario: Remove missing alias
- **WHEN** alias `ghost` does not exist and the user runs `tgbot chat remove ghost`
- **THEN** an error says the alias was not found and the exit code is non-zero

### Requirement: Target resolution
The system SHALL resolve a send target in this order:
1. a saved alias name gives its stored ID;
2. otherwise an integer value is used as a numeric chat ID;
3. otherwise a `@username` value is passed to Telegram as is.

Any other value SHALL be rejected as an unknown alias before any network call.

#### Scenario: Alias wins
- **WHEN** alias `me` maps to `13342324` and a command targets `me`
- **THEN** the message is sent to chat `13342324`

#### Scenario: Unknown alias
- **WHEN** no alias `boss` exists and a command targets `boss`
- **THEN** no request is made, the error suggests `tgbot chat add`, and the exit code is the configuration exit code
