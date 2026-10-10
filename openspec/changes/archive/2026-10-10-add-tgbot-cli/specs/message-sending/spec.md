# Spec Delta

## Purpose

Lets agents and people send notifications as a Telegram bot: text, media files, contacts, locations, polls and dice. Sending is strictly write-only, so the tool never reads anyone's messages.

## ADDED Requirements

### Requirement: Write-only Telegram access
The system SHALL call only these Bot API methods: `getMe`, `getChat` and the `send*` methods it exposes. It SHALL NOT call `getUpdates`, set webhooks, or otherwise read incoming messages. Any other method SHALL be refused locally.

#### Scenario: Reading is refused
- **WHEN** any code path attempts to call `getUpdates`
- **THEN** the call is refused before any network request is made

### Requirement: Send text
The system SHALL provide `tgbot send MESSAGE [TARGET]` and the flag form `tgbot send MESSAGE --to TARGET`. Text SHALL be sent as plain text unless `--parse-mode html` or `--parse-mode markdown` is given.

#### Scenario: Positional text
- **WHEN** the user runs `tgbot send "Build failed" me`
- **THEN** a text message "Build failed" is sent to the chat that `me` resolves to

#### Scenario: Plain text by default
- **WHEN** the message contains `*`, `_`, `.` and `-` and no parse mode is given
- **THEN** it is delivered literally, with no formatting errors

### Requirement: Text from stdin
The system SHALL read the message text from standard input when MESSAGE is `-`. It SHALL fail with a usage error when stdin is empty.

#### Scenario: Piped text
- **WHEN** the user runs `echo "deploy done" | tgbot send - me`
- **THEN** a message with text `deploy done` is sent

#### Scenario: Empty stdin
- **WHEN** MESSAGE is `-` and stdin is empty
- **THEN** nothing is sent and a usage error is reported

### Requirement: Long text is split
The system SHALL split text longer than Telegram's 4096-character limit into consecutive messages. It SHALL prefer to break at line boundaries and SHALL preserve the order of the parts.

#### Scenario: 9000-character message
- **WHEN** the text is 9000 characters long
- **THEN** three messages are sent in order, and their concatenation equals the original text apart from removed break newlines

### Requirement: Send media files
The system SHALL provide `sendphoto`, `sendfile` (document), `sendvideo`, `sendaudio`, `sendvoice`, `sendvideonote`, `sendanimation` and `sendsticker`. Each media item SHALL be accepted as a local file path, an `http(s)://` URL, or a Telegram `file_id`. Missing local files SHALL be reported before any network call.

#### Scenario: Photo with caption
- **WHEN** the user runs `tgbot sendphoto shot.png me "Screenshot"`
- **THEN** `shot.png` is uploaded as a photo with caption "Screenshot"

#### Scenario: Photo from URL
- **WHEN** the user runs `tgbot sendphoto https://example.com/a.png --to me`
- **THEN** the URL is passed to Telegram without a local upload

#### Scenario: Sticker by file_id
- **WHEN** the user runs `tgbot sendsticker CAACAgIAAxkB --to me`
- **THEN** the sticker is sent by its `file_id`

#### Scenario: Missing file
- **WHEN** the user runs `tgbot sendfile nope.pdf --to me`, `nope.pdf` does not exist and it is not a URL
- **THEN** nothing is sent and the error names `nope.pdf`

### Requirement: Positional argument syntax for media
In media commands the system SHALL treat leading tokens that are existing files or URLs as content. The next token is the target unless `--to` is given, and the one after that is the caption unless `--caption` is given. When `--to` and `--caption` are both given (or only `--to`, for commands without a caption such as `sendsticker` and `sendvideonote`), every positional token SHALL be content. Leftover tokens SHALL cause a usage error.

#### Scenario: Positional files, target and caption
- **WHEN** the user runs `tgbot sendfile a.pdf b.pdf team "Reports"`, where both files exist
- **THEN** both files are sent to `team`, and the caption "Reports" is on the first one

#### Scenario: Extra tokens
- **WHEN** the user runs `tgbot sendphoto a.png me "cap" extra`
- **THEN** nothing is sent and a usage error names `extra`

### Requirement: Albums
The system SHALL send several photos or videos given to `sendphoto` or `sendvideo` as an album. It SHALL send several documents as an album only with `sendfile --group`. Albums SHALL be split into batches of at most 10 items, with the caption on the first item of the first batch.

#### Scenario: Twelve photos
- **WHEN** the user sends 12 existing photos with `sendphoto`
- **THEN** two albums are sent, of 10 and 2 items, and only the first item carries the caption

#### Scenario: Documents without --group
- **WHEN** the user runs `tgbot sendfile a.pdf b.pdf --to me` without `--group`
- **THEN** two separate document messages are sent

### Requirement: Telegram size and length limits
The system SHALL reject, before uploading:
- a local file larger than 50 MB;
- a local photo larger than 10 MB;
- a caption longer than 1024 characters.

Each rejection SHALL explain which limit was exceeded.

#### Scenario: Oversized upload
- **WHEN** a local file of 60 MB is passed to `sendfile`
- **THEN** nothing is sent and the error states the 50 MB limit

### Requirement: Send contact
The system SHALL provide `tgbot sendcontact PHONE FIRST_NAME [LAST_NAME] TARGET`. It SHALL also accept the flags `--phone`, `--first-name`, `--last-name` and `--to`. Phone and first name are required.

#### Scenario: Positional contact
- **WHEN** the user runs `tgbot sendcontact +77001234567 Ivan Petrov me`
- **THEN** a contact for Ivan Petrov with that phone number is sent to `me`

### Requirement: Send location
The system SHALL provide `tgbot sendlocation LATITUDE LONGITUDE TARGET`, with `--to` also accepted. Latitude SHALL be in [-90, 90] and longitude in [-180, 180]. Negative coordinates SHALL be accepted.

#### Scenario: Valid location
- **WHEN** the user runs `tgbot sendlocation 43.238 76.889 me`
- **THEN** a location pin is sent to `me`

#### Scenario: Out-of-range latitude
- **WHEN** latitude is 95
- **THEN** nothing is sent and a usage error is reported

### Requirement: Send poll
The system SHALL provide `tgbot sendpoll QUESTION OPTION OPTION... --to TARGET`, with between 2 and 10 options. It SHALL support `--multiple` (several answers allowed) and `--anonymous/--no-anonymous`, and polls SHALL be anonymous by default.

#### Scenario: Simple poll
- **WHEN** the user runs `tgbot sendpoll "Deploy now?" Yes No --to me`
- **THEN** an anonymous poll with options Yes and No is sent

#### Scenario: Too few options
- **WHEN** only one option is given
- **THEN** nothing is sent and a usage error is reported

### Requirement: Send dice
The system SHALL provide `tgbot senddice TARGET [--emoji E]`. E is one of the emoji Telegram supports for dice, and the default is the standard die.

#### Scenario: Default dice
- **WHEN** the user runs `tgbot senddice me`
- **THEN** a dice message with the standard die emoji is sent

### Requirement: Common send options
Every send command SHALL accept `--silent`, which delivers without a notification sound. Every command that carries text or a caption SHALL accept `--parse-mode html|markdown`.

#### Scenario: Silent message
- **WHEN** the user runs `tgbot send "nightly ok" me --silent`
- **THEN** the message is sent with notifications disabled

### Requirement: Helpful delivery errors
When Telegram refuses delivery, the system SHALL report Telegram's error description. When Telegram reports that the bot cannot initiate the conversation or was blocked (HTTP 403), the message SHALL explain that the recipient must open the bot and press Start. When Telegram rate-limits a request, the system SHALL retry it once after the advised delay.

#### Scenario: Recipient never started the bot
- **WHEN** Telegram answers 403 "bot can't initiate conversation with a user"
- **THEN** the error includes a hint to send `/start` to the bot, and the exit code is the Telegram error exit code

#### Scenario: Rate limited once
- **WHEN** Telegram answers 429 with `retry_after: 1` and then succeeds
- **THEN** the message is delivered and the command succeeds
