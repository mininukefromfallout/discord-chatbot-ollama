# Discord Chatbot using [Ollama](https://ollama.com) API

A Discord bot that integrates with the [Ollama](https://ollama.com) API to generate responses using a local LLM. The bot can be activated to respond to all messages in a specific channel or when mentioned. It supports conversation memory, word filtering, role blacklisting, URL content fetching, and custom model instructions. Responses longer than 2000 characters are sent as a `.md` file attachment.

> ⚠️ **Windows users:** The bot may have issues logging commands or reading `instructions.txt`. It is recommended to use [Windows Subsystem for Linux (WSL)](https://learn.microsoft.com/en-us/windows/wsl/) to run the bot on Windows.

## Quick Links

- [Installation](#installation)
- [Setting up .env](#setting-up-the-env-file)
- [Setting up config.yml](#setting-up-configyml)
- [Setting up Ollama](#setting-up-the-ollama-model)
- [Using the default Modelfile](#using-the-default-modelfile)
- [Using a custom model](#using-a-custom-model)
- [Bot commands](#bot-commands)
- [Getting your bot token](#getting-the-bot-token)
- [Inviting the bot](#invite-bot-to-server)

## On Linux or MacOS?

Try using the setup script `setup.sh`. Run it with 
```bash
./setup.sh
``` 
This script will setup basically everything you need to run the bot.

## Requirements

This project requires the following Python dependencies:

- `discord.py`: For building the bot.
- `ollama`: Ollama Python client for generating responses.
- `aiohttp`: For fetching URL content.
- `python-dotenv`: To manage environment variables.
- `pytz`: For time logging in the command log.
- `pyyaml`: For parsing `config.yml`.
- `beautifulsoup4`: For parsing HTML when fetching URLs.
- `lxml`: HTML parser backend for BeautifulSoup.

You can install all dependencies via `requirements.txt`:

```bash
pip3 install -r requirements.txt
```

You also need git to clone the repository.

## Installation

```bash
# 1. Clone the repository to your local machine:
git clone https://github.com/mininukefromfallout/discord-chatbot-ollama.git
cd discord-chatbot-ollama

# 2. Create a virtual environment (recommended but not required):
python3 -m venv venv

# 3. Activate the virtual environment:
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate  # On Windows

# 4. Install the required dependencies:
pip3 install -r requirements.txt
```

## Setting Up the .env File

Create a `.env` file in the root of your project directory. A base `.env` is included in the repo.

```env
BOT_TOKEN=YOUR_TOKEN_HERE
TIMEZONE=America/New_York
OLLAMA_MODEL=phi3:mini
OLLAMA_ERROR_MESSAGE=I couldn't process that.

MESSAGE_MEMORY=10
URL_FETCH_MAX_CHARS=3000

URL_MANAGER_IDS=

SHOW_FULL_SYSTEM_PROMPT=true
```

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Your Discord bot token from the [Developer Portal](https://discord.com/developers/applications) |
| `TIMEZONE` | Timezone for command logging. See `timezones.txt` for valid values |
| `OLLAMA_MODEL` | The Ollama model to use (e.g. `phi3:mini`, `llama3`) |
| `OLLAMA_ERROR_MESSAGE` | Message shown when Ollama fails to respond |
| `MESSAGE_MEMORY` | Number of message pairs to remember per channel (`0` = disabled) |
| `URL_FETCH_MAX_CHARS` | Max characters of fetched URL page content passed to the model |
| `URL_MANAGER_IDS` | Comma-separated Discord user IDs who can manage allowed URL domains |
| `SHOW_FULL_SYSTEM_PROMPT` | `true` shows the full system prompt in `/model_info`, `false` shows a short preview |
| `USE_INSTRUCTIONS` | `true` sends `instructions.txt` as the system prompt. Set to `false` when using a custom model with a system prompt already baked into its Modelfile |

## Setting Up config.yml

`config.yml` is auto-created on first run with empty defaults. A base `config.yml` is included in the repo.

```yaml
blacklisted_words:
  # - example

allowed_url_domains:
  # - example.com

blacklisted_roles:
  # "YOUR_GUILD_ID":
  #   - "ROLE_ID"

restrict_servers: false
allowed_server_users:
  # - 123456789012345678
```

| Key | Description |
|---|---|
| `blacklisted_words` | Words the bot will never include in a response. If detected the bot retries up to 5 times |
| `allowed_url_domains` | Domains the bot is allowed to fetch and read content from. Subdomains are included automatically |
| `blacklisted_roles` | Per-guild role IDs whose members are silently ignored by the bot |
| `restrict_servers` | If `true`, the bot will leave any server that doesn't contain at least one user from `allowed_server_users` |
| `allowed_server_users` | List of Discord user IDs used for server restriction. If `restrict_servers` is `true` and none of these users are in a server the bot joins, it will leave |

## Setting Up the Ollama Model

### macOS/Linux

1. **Install Ollama**:

   * Download and install Ollama from [ollama.com](https://ollama.com).
   * After installation, open a terminal and run:

     ```bash
     ollama run phi3:mini
     ```

2. **Test the API**:

   * Open your browser and visit `http://localhost:11434/api/generate` to ensure the API is running.

3. **Stop Ollama**:

   ```bash
   ollama stop phi3:mini
   ```

### Windows

1. **Install Ollama**:

   * Download and install Ollama from [ollama.com](https://ollama.com).
   * Run Ollama with the following command:

     ```bash
     ollama run phi3:mini
     ```

2. **Test the API**:

   * Open your browser and visit `http://localhost:11434/api/generate` to ensure the API is running.

3. **Stop Ollama**:

   ```bash
   ollama stop phi3:mini
   ```

## Running the Bot

```bash
# 1. Ensure the virtual environment is activated:
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate  # On Windows

# 2. Run Ollama:
ollama run phi3:mini

# 3. Run the bot:
python3 chatbot.py
```

The bot will log into Discord using the token provided in the `.env` file. You should see a message in your terminal indicating that the bot has successfully logged in.

## Bot Commands

### Channel Control

| Command | Permission | Description |
|---|---|---|
| `/activate [time]` | Admin / Owner | Activate the bot in the current channel. Optional `time` in seconds auto-deactivates it after that duration |
| `/deactivate` | Admin / Owner | Deactivate the bot in the current channel |
| `/clear_memory` | Admin / Owner | Clear the conversation memory for the current channel |

### Instructions

| Command | Permission | Description |
|---|---|---|
| `/reload_instructions` | Owner only | Reload `instructions.txt` without restarting the bot |

### Role Blacklist

| Command | Permission | Description |
|---|---|---|
| `/blacklist_role <role>` | Admin / Owner | Prevent all members with this role from interacting with the bot |
| `/unblacklist_role <role>` | Admin / Owner | Remove a role from the blacklist |
| `/list_blacklisted_roles` | Anyone | List all blacklisted roles in this server |

### URL Management

| Command | Permission | Description |
|---|---|---|
| `/add_allowed_url <domain>` | Owner / `URL_MANAGER_IDS` | Add a domain the bot is allowed to fetch content from |
| `/remove_allowed_url <domain>` | Owner / `URL_MANAGER_IDS` | Remove a domain from the allowed list |
| `/list_allowed_urls` | Anyone | Show all currently allowed URL domains |

### Model

| Command | Permission | Description |
|---|---|---|
| `/model_info` | Anyone | Show the current model, base model, system prompt, memory setting, and allowed URL domains |

## How URL Fetching Works

When any user sends a message containing a URL from a domain on the `allowed_url_domains` list, the bot will:

1. Automatically detect the URL in the message
2. Fetch the page content
3. Strip HTML tags and collapse whitespace using BeautifulSoup
4. Inject the content as context into the Ollama prompt, capped at `URL_FETCH_MAX_CHARS` characters
5. Generate a response informed by the page content

If the URL's domain is not on the allowed list it is ignored and the bot responds to the message text only. URL domain management is restricted to the bot owner and any user IDs set in `URL_MANAGER_IDS` in `.env`.

## Using the Default Modelfile

A `Modelfile` is included in the repo as a starting point. It is based on `phi3:mini` and includes a basic Discord assistant system prompt:

```
FROM phi3:mini

PARAMETER temperature 1.2

SYSTEM """
You are a helpful assistant in a Discord server.
"""
```

- **`FROM`** — the base model to build on. You can swap this for any model you have pulled with `ollama pull`.
- **`PARAMETER temperature`** — controls how creative/random the responses are. `1.2` is slightly above default. Lower values (e.g. `0.7`) make responses more focused and deterministic, higher values make them more varied.
- **`SYSTEM`** — the system prompt baked into the model. Edit this to change how the bot behaves.

To build and use it:

```bash
ollama create discord-bot -f Modelfile
```

Then set your `.env` to use it and disable `instructions.txt` since the system prompt is already in the Modelfile:

```env
OLLAMA_MODEL=discord-bot
USE_INSTRUCTIONS=false
```

To rebuild after editing the Modelfile just run the `ollama create` command again.

## Using a Custom Model

If you want to use your own Modelfile from scratch the process is the same — create a `Modelfile`, build it with `ollama create`, point `OLLAMA_MODEL` at it, and set `USE_INSTRUCTIONS=false` so `instructions.txt` is not sent as a conflicting second system prompt.

```
FROM llama3

PARAMETER temperature 0.8

SYSTEM """
Your custom instructions here.
"""
```

```bash
ollama create my-custom-model -f Modelfile
```

```env
OLLAMA_MODEL=my-custom-model
USE_INSTRUCTIONS=false
```

You can verify the system prompt and base model are detected correctly using `/model_info` in Discord. Set `SHOW_FULL_SYSTEM_PROMPT=true` in `.env` to see the full system prompt in the output.

## How Conversation Memory Works

The bot keeps a per-channel rolling history of the last `MESSAGE_MEMORY` user/assistant message pairs. This history is injected into every Ollama request so the model has context from earlier in the conversation. Set `MESSAGE_MEMORY=0` in `.env` to disable it. Use `/clear_memory` to wipe a channel's history at any time.

## How Server Restriction Works

If `restrict_servers` is set to `true` in `config.yml`, the bot will check every server it joins for the presence of at least one user ID from `allowed_server_users`. If none of those users are in the server, the bot leaves automatically. Set `restrict_servers` to `false` to let the bot join any server freely.

## Installing Python on Linux, macOS, and Windows

### Linux

```bash
sudo apt update
sudo apt install python3 python3-pip
```

### macOS

```bash
brew install python3
python3 --version
```

### Windows

1. Download Python from [python.org](https://www.python.org/downloads/).
2. Run the installer and ensure **Add Python to PATH** is checked.
3. Verify: `python3 --version`

## Getting the Bot Token

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application.
3. Under the **Bot** tab, click **Reset Token** and copy it.
4. Scroll down and enable **Message Content Intent** and **Server Members Intent**.
5. Paste the token into `.env` as `BOT_TOKEN`.

## Invite Bot to Server

1. Go to the **OAuth2** tab in the Developer Portal.
2. Under **OAuth2 URL Generator**, select `bot` as the scope.
3. Enable the following permissions:
   - Read Message History
   - Send Messages
   - View Channels
   - Attach Files
4. Also enable **Message Content Intent** under Privileged Gateway Intents.
5. Copy and open the generated URL to invite the bot.

If you have any problems please create an issue and I'll get to it as soon as I can.