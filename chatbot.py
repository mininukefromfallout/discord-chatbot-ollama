import discord
from discord.ext import commands
from discord import app_commands
import json
import ollama
import os
import sys
import asyncio
import yaml
import pytz
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict, deque
from utils.parsepage import build_url_context, is_domain_allowed


class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'a', buffering=1)

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()


os.makedirs('logs', exist_ok=True)

date_str = datetime.now().strftime('%Y-%m-%d')
counter = 0
log_filename = f'logs/chatbot_log_{date_str}.log'

while os.path.exists(log_filename):
    counter += 1
    log_filename = f'logs/chatbot_log_{date_str}-{counter}.txt'

sys.stdout = Logger(log_filename)
sys.stderr = Logger(log_filename)


CONFIG_FILE = 'config.yml'

def load_config() -> dict:
    defaults = {
        'blacklisted_words': [],
        'allowed_url_domains': [],
        'blacklisted_roles': {},
        'restrict_servers': False,
        'allowed_server_users': [],
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(defaults, f, default_flow_style=False)
        return defaults
    with open(CONFIG_FILE, 'r') as f:
        data = yaml.safe_load(f) or {}
    for key, val in defaults.items():
        data.setdefault(key, val)
    return data

def save_config(data: dict):
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)


load_dotenv()

BOT_TOKEN            = os.getenv("BOT_TOKEN")
TIMEZONE             = pytz.timezone(os.getenv("TIMEZONE", "US/Eastern"))
OLLAMA_MODEL         = os.getenv("OLLAMA_MODEL", "phi")
OLLAMA_ERROR_MESSAGE = os.getenv("OLLAMA_ERROR_MESSAGE", "I couldn't process that.")
MESSAGE_MEMORY       = int(os.getenv("MESSAGE_MEMORY", "10"))
URL_FETCH_MAX_CHARS  = int(os.getenv("URL_FETCH_MAX_CHARS", "3000"))

_URL_MANAGER_IDS_RAW = os.getenv("URL_MANAGER_IDS", "")
URL_MANAGER_IDS: set[int] = {
    int(x.strip()) for x in _URL_MANAGER_IDS_RAW.split(",") if x.strip().isdigit()
}

SHOW_FULL_SYSTEM_PROMPT = os.getenv("SHOW_FULL_SYSTEM_PROMPT", "true").strip().lower() == "true"
USE_INSTRUCTIONS        = os.getenv("USE_INSTRUCTIONS", "true").strip().lower() == "true"

ACTIVE_FILE       = 'active_channels.json'
INSTRUCTIONS_FILE = 'instructions.txt'
LOG_FILE          = 'bot_actions.log'

cfg                       = load_config()
blacklisted_words: list   = cfg.get('blacklisted_words') or []
allowed_url_domains: list = cfg.get('allowed_url_domains') or []
blacklisted_roles: dict   = cfg.get('blacklisted_roles') or {}
restrict_servers: bool    = cfg.get('restrict_servers') or False
allowed_server_users: list = cfg.get('allowed_server_users') or []


intents = discord.Intents.default()
intents.message_content = True

bot  = commands.Bot(command_prefix="vErYcOmPlIcAtEdPrEfIx1257863", intents=intents)
tree = bot.tree


def load_active_channels():
    try:
        with open(ACTIVE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_active_channels(channels):
    with open(ACTIVE_FILE, 'w') as f:
        json.dump(channels, f)

def load_instructions():
    try:
        with open(INSTRUCTIONS_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "You are a default chatbot who will provide ethical and constructive communication."

def log_action(user, action, channel, other=None):
    timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d %I:%M:%S %p %Z")
    guild = channel.guild
    entry = (
        f"[{timestamp}] {user.name} ({user.id}) used {action} in "
        f"#{channel.name} ({channel.id}) on {guild.name} ({guild.id})"
    )
    if other:
        entry += f" [{other}]"
    entry += "\n"
    with open(LOG_FILE, 'a') as f:
        f.write(entry)


active_channels     = load_active_channels()
ollama_instructions = load_instructions()

channel_memory: dict[int, deque] = defaultdict(lambda: deque(maxlen=MESSAGE_MEMORY * 2))


def is_owner_or_trusted(user_id: int) -> bool:
    return user_id == bot.owner_id

def is_admin(interaction: discord.Interaction) -> bool:
    return (
        interaction.user.guild_permissions.administrator
        or is_owner_or_trusted(interaction.user.id)
    )

def can_manage_urls(interaction: discord.Interaction) -> bool:
    uid = interaction.user.id
    return is_owner_or_trusted(uid) or uid in URL_MANAGER_IDS

def user_has_blacklisted_role(member: discord.Member, guild_id: int) -> bool:
    bl = blacklisted_roles.get(str(guild_id), [])
    return any(str(role.id) in bl for role in member.roles)


async def query_ollama(channel_id: int, user_message: str, url_context: str | None = None) -> str:
    try:
        messages = []

        if USE_INSTRUCTIONS and ollama_instructions:
            messages.append({"role": "system", "content": ollama_instructions})

        if url_context:
            messages.append({"role": "system", "content": url_context})

        if MESSAGE_MEMORY > 0:
            messages.extend(list(channel_memory[channel_id]))

        messages.append({"role": "user", "content": user_message})

        response = await asyncio.to_thread(
            ollama.chat,
            model=OLLAMA_MODEL,
            messages=messages
        )

        reply = response["message"]["content"]

        if MESSAGE_MEMORY > 0:
            channel_memory[channel_id].append({"role": "user",      "content": user_message})
            channel_memory[channel_id].append({"role": "assistant", "content": reply})

        return reply

    except Exception as e:
        print(f"Ollama error: {e}")
        return OLLAMA_ERROR_MESSAGE


@bot.event
async def on_ready():
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} commands!")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    bot.owner_id = (await bot.application_info()).owner.id
    print(f"Logged in as {bot.user} | Owner ID: {bot.owner_id}")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(name=f"Current model: {OLLAMA_MODEL}")
    )

@bot.event
async def on_guild_join(guild):
    if not restrict_servers:
        return
    for user_id in allowed_server_users:
        if guild.get_member(int(user_id)) is not None:
            return
    await guild.leave()

@bot.event
async def on_message(message):
    if message.author.bot or message.webhook_id:
        return

    if isinstance(message.author, discord.Member):
        if user_has_blacklisted_role(message.author, message.guild.id):
            return

    if bot.user in message.mentions or message.channel.id in active_channels:
        async with message.channel.typing():
            url_context = await build_url_context(message.content, allowed_url_domains, URL_FETCH_MAX_CHARS)
            reply = await query_ollama(message.channel.id, message.content, url_context)
            response_tries = 0
            await asyncio.sleep(10)

            while any(word.lower() in reply.lower() for word in blacklisted_words):
                bad_word = next(w for w in blacklisted_words if w.lower() in reply.lower())
                print(f'Blacklisted word detected: "{bad_word}" — retrying...')
                reply = await query_ollama(message.channel.id, message.content, url_context)
                await asyncio.sleep(10)
                response_tries += 1
                if response_tries >= 5:
                    reply = "Failed to generate a response without blacklisted words."
                    break

        async def send_response(text=None, file=None):
            try:
                await (message.reply(file=file) if file else message.reply(text))
            except (discord.NotFound, discord.HTTPException):
                await (message.channel.send(file=file) if file else message.channel.send(text))

        if len(reply) > 2000:
            filename = f"{message.id}-extended.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(reply)
            await send_response(file=discord.File(filename))
            os.remove(filename)
        else:
            await send_response(reply)

    await bot.process_commands(message)


@tree.command(name="activate", description="Activate the bot in this channel.")
async def activate(interaction: discord.Interaction, time: int = None):
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    if interaction.channel.id not in active_channels:
        active_channels.append(interaction.channel.id)
        save_active_channels(active_channels)
        other = f"for {time} seconds" if time else None
        await interaction.response.send_message(
            "Activated: I will now respond to all messages in this channel." +
            (f" (auto-deactivates in {time}s)" if time else "")
        )
        log_action(interaction.user, "/activate", interaction.channel, other)
        if time:
            await asyncio.sleep(time)
            if interaction.channel.id in active_channels:
                active_channels.remove(interaction.channel.id)
                save_active_channels(active_channels)
                await interaction.channel.send("Deactivated: I will now only respond when pinged.")
                log_action(bot.user, "AUTOMATIC: /deactivate", interaction.channel)
    else:
        await interaction.response.send_message("I'm already active in this channel.")

@tree.command(name="deactivate", description="Deactivate the bot in this channel.")
async def deactivate(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    if interaction.channel.id in active_channels:
        active_channels.remove(interaction.channel.id)
        save_active_channels(active_channels)
        await interaction.response.send_message("Deactivated: I will now only respond when pinged.")
        log_action(interaction.user, "/deactivate", interaction.channel)
    else:
        await interaction.response.send_message("I'm not active in this channel.")

@tree.command(name="reload_instructions", description="Reload the assistant's behavior from instructions.txt.")
async def reload_instructions(interaction: discord.Interaction):
    if not is_owner_or_trusted(interaction.user.id):
        await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=True)
        return
    global ollama_instructions
    ollama_instructions = load_instructions()
    await interaction.response.send_message("Instructions reloaded.")
    log_action(interaction.user, "/reload_instructions", interaction.channel)

@tree.command(name="clear_memory", description="Clear the conversation memory for this channel.")
async def clear_memory(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    channel_memory[interaction.channel.id].clear()
    await interaction.response.send_message("Conversation memory cleared for this channel.")
    log_action(interaction.user, "/clear_memory", interaction.channel)


@tree.command(name="blacklist_role", description="Blacklist a role from using the bot.")
@app_commands.describe(role="The role to blacklist")
async def blacklist_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    gid = str(interaction.guild.id)
    blacklisted_roles.setdefault(gid, [])
    if str(role.id) not in blacklisted_roles[gid]:
        blacklisted_roles[gid].append(str(role.id))
        cfg['blacklisted_roles'] = blacklisted_roles
        save_config(cfg)
        await interaction.response.send_message(f"Role **{role.name}** has been blacklisted.")
        log_action(interaction.user, "/blacklist_role", interaction.channel, f"{role.name} ({role.id})")
    else:
        await interaction.response.send_message(f"Role **{role.name}** is already blacklisted.")

@tree.command(name="unblacklist_role", description="Remove a role from the blacklist.")
@app_commands.describe(role="The role to remove")
async def unblacklist_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    gid = str(interaction.guild.id)
    if str(role.id) in blacklisted_roles.get(gid, []):
        blacklisted_roles[gid].remove(str(role.id))
        cfg['blacklisted_roles'] = blacklisted_roles
        save_config(cfg)
        await interaction.response.send_message(f"Role **{role.name}** removed from the blacklist.")
        log_action(interaction.user, "/unblacklist_role", interaction.channel, f"{role.name} ({role.id})")
    else:
        await interaction.response.send_message(f"Role **{role.name}** is not blacklisted.")

@tree.command(name="list_blacklisted_roles", description="List all blacklisted roles in this server.")
async def list_blacklisted_roles(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    ids = blacklisted_roles.get(gid, [])
    if not ids:
        await interaction.response.send_message("No roles are blacklisted in this server.")
        return
    lines = []
    for rid in ids:
        role = interaction.guild.get_role(int(rid))
        lines.append(f"• {role.name if role else 'Unknown Role'} (`{rid}`)")
    await interaction.response.send_message("**Blacklisted roles:**\n" + "\n".join(lines))


@tree.command(name="add_allowed_url", description="Allow the bot to fetch content from a domain.")
@app_commands.describe(domain="Domain to allow, e.g. example.com")
async def add_allowed_url(interaction: discord.Interaction, domain: str):
    if not can_manage_urls(interaction):
        await interaction.response.send_message("You don't have permission to manage allowed URLs.", ephemeral=True)
        return
    domain = domain.lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
    if domain in allowed_url_domains:
        await interaction.response.send_message(f"`{domain}` is already in the allowed list.")
        return
    allowed_url_domains.append(domain)
    cfg['allowed_url_domains'] = allowed_url_domains
    save_config(cfg)
    await interaction.response.send_message(f"✅ `{domain}` added to allowed URL domains.")
    log_action(interaction.user, "/add_allowed_url", interaction.channel, f"domain: {domain}")

@tree.command(name="remove_allowed_url", description="Remove a domain from the allowed URL list.")
@app_commands.describe(domain="Domain to remove, e.g. example.com")
async def remove_allowed_url(interaction: discord.Interaction, domain: str):
    if not can_manage_urls(interaction):
        await interaction.response.send_message("You don't have permission to manage allowed URLs.", ephemeral=True)
        return
    domain = domain.lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
    if domain not in allowed_url_domains:
        await interaction.response.send_message(f"`{domain}` is not in the allowed list.")
        return
    allowed_url_domains.remove(domain)
    cfg['allowed_url_domains'] = allowed_url_domains
    save_config(cfg)
    await interaction.response.send_message(f"🗑️ `{domain}` removed from allowed URL domains.")
    log_action(interaction.user, "/remove_allowed_url", interaction.channel, f"domain: {domain}")

@tree.command(name="list_allowed_urls", description="List all domains the bot is allowed to fetch.")
async def list_allowed_urls(interaction: discord.Interaction):
    if not allowed_url_domains:
        await interaction.response.send_message("No URL domains are currently allowed.")
        return
    await interaction.response.send_message(
        "**Allowed URL domains:**\n" + "\n".join(f"• `{d}`" for d in allowed_url_domains)
    )


@tree.command(name="model_info", description="Show info about the current Ollama model.")
async def model_info(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        info = await asyncio.to_thread(ollama.show, OLLAMA_MODEL)

        modelfile  = info.get("modelfile", "")

        base_model    = None
        system_prompt = None
        for line in modelfile.splitlines():
            stripped = line.strip()
            if not base_model and stripped.upper().startswith("FROM"):
                raw_from = stripped[4:].strip()
                if raw_from.startswith("/") or "sha256" in raw_from:
                    base_model = OLLAMA_MODEL
                else:
                    base_model = raw_from
            if not system_prompt and stripped.upper().startswith("SYSTEM"):
                system_prompt = stripped[6:].strip().strip('"').strip('"""')

        embed = discord.Embed(title=f"Model Info: {OLLAMA_MODEL}", color=discord.Color.blurple())
        embed.add_field(name="Base Model", value=base_model or "N/A", inline=True)
        embed.add_field(
            name="Message Memory",
            value=f"{MESSAGE_MEMORY} pairs" if MESSAGE_MEMORY > 0 else "Disabled",
            inline=True
        )
        embed.add_field(
            name="Allowed URL Domains",
            value=", ".join(f"`{d}`" for d in allowed_url_domains) if allowed_url_domains else "None",
            inline=False
        )

        if SHOW_FULL_SYSTEM_PROMPT:
            prompt_text = system_prompt or ollama_instructions or "None"
            label = "System Prompt"
        else:
            raw = system_prompt or ollama_instructions or ""
            prompt_text = (raw[:80] + "...") if len(raw) > 80 else (raw or "None")
            label = "System Prompt (preview)"

        if len(prompt_text) > 1024:
            prompt_text = prompt_text[:1021] + "..."
        embed.add_field(name=label, value=prompt_text, inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Failed to fetch model info: `{e}`")


bot.run(BOT_TOKEN)