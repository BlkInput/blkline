import os
import discord
import datetime
import time
import re
import asyncio
import random
import json
import requests
import logging
from discord.ui import Button, View
from discord.ext import commands, tasks
from mcstatus import JavaServer
from python_aternos import Client
from exaroton import Exaroton
from dotenv import load_dotenv
from discord.ext.commands import cooldown, BucketType, Context

# commit 27ce7b6

# Load .env variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

def is_trusted():
    async def predicate(ctx: Context):
        return any(role.id == 1366796508288127066 for role in ctx.author.roles)
    return commands.check(predicate)

TOKEN = os.getenv("DISCORD_TOKEN")
SERVER_ADDRESS = os.getenv("SERVER_ADDRESS")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ROLE_TO_TAG = os.getenv("ROLE_TO_TAG")
ATERNO_EMAIL = os.getenv("ATERNO_EMAIL")
ATERNO_PASSWORD = os.getenv("ATERNO_PASSWORD")
EXAROTON_EMAIL = os.getenv("EXAROTON_EMAIL")
EXAROTON_PASSWORD = os.getenv("EXAROTON_PASSWORD")
EXAROTON_TOKEN = os.getenv("EXAROTON_TOKEN")
EXAROTON_SERVER_ID = os.getenv("EXAROTON_SERVER_ID")
exaroton_client = Exaroton(EXAROTON_TOKEN)
ANNOUNCEMENT_CHANNEL_ID = 1383563592447557722
GUILD_ID = 1046624035464810496
STATUS_CHANNEL_ID = 1383563592447557722
DEV_LOG_CHANNEL_ID = 1369314903701065768
SUGGESTIONS_FILE = "suggestions.json"
MC_SERVER_PORT = int(os.getenv("MC_SERVER_PORT", 50430))
MC_SERVER_IP = os.getenv("MC_SERVER_IP")
DEV_USER_ID = [546650815297880066, 448896936481652777, 424532190290771998, 858462569043722271]
COOLDOWN_SECONDS = 600
cooldowns = {}  # Maps user_id to last suggestion timestamp

intents = discord.Intents.all()
intents.message_content = True
intents.presences = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
last_status = "offline"
boot_time = time.time()

@bot.event
async def on_ready():
    print(f'{bot.user} reporting for duty!')
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="✅ Beebo has reloaded!",
            description="We're Back <:pixelGUY:1368269152334123049>",
            color=0xb0c0ff
        )
        await channel.send(embed=embed)
    check_server_status.start()

@tasks.loop(hours=3)
async def check_server_status():
    global last_status
    channel = bot.get_channel(CHANNEL_ID)
    server = JavaServer.lookup(SERVER_ADDRESS)

    try:
        status = server.status()
        if last_status == "offline":
            embed = discord.Embed(title="**Minecraft Server is ONLINE!**", color=0xb0c0ff)
            embed.add_field(name="Java IP", value="termite.exaroton.me", inline=False)
            embed.add_field(name="Players", value=f"{status.players.online}/{status.players.max}", inline=False)

            if status.players.online > 0:
                players = ', '.join([player.name for player in status.players.sample]) if status.players.sample else "Unknown players"
                embed.add_field(name="Who's Online", value=players, inline=False)

            embed.set_footer(text="Summon the squad before Termite falls asleep.")
            await channel.send(content=ROLE_TO_TAG, embed=embed)
            last_status = "online"
        else:
            print("Server still online. No alert sent.")
    except:
        print("Server is offline or unreachable.")
        if last_status == "online":
            embed = discord.Embed(title="**Termite is OFFLINE or SLEEPING**", color=0xff5555)
            embed.set_footer(text="Someone needs to manually start it or join to wake it up.")
            await channel.send(content="<@&1368225900486721616>", embed=embed)
        last_status = "offline"

@commands.command(name="mcstatus", aliases=["mcserverstatus"])
async def mcserver_status(self, ctx):
    await ctx.trigger_typing()

    headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
    url = f"https://api.exaroton.com/v1/servers/{EXAROTON_SERVER_ID}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[Exaroton API Error] {e}")
        await ctx.send("❌ Failed to fetch server status from Exaroton.")
        return

    motd = data.get("motd", {}).get("clean", ["Unknown MOTD"])[0]
    status_text = data.get("statusText", "Offline")
    time_started = data.get("timeStarted")

    # Calculate uptime
    uptime_str = "Unavailable"
    if time_started:
        try:
            started_dt = datetime.fromisoformat(time_started.replace("Z", "+00:00"))
            now = datetime.utcnow()
            uptime = now - started_dt
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m"
        except Exception as e:
            print(f"[Uptime Parse Error] {e}")

    # Try JavaServer status check
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status(retries=1)
        online_players = [p.name for p in status.players.sample] if status.players.sample else []
        players_str = ", ".join(online_players) if online_players else "Nobody online"
        player_count_str = f"{status.players.online}/{status.players.max}"
    except Exception as e:
        print(f"[JavaServer Error] {e}")
        players_str = "Unavailable"
        player_count_str = "?"

    embed = discord.Embed(
        title="<:beebo:1383282292478312519> Termite Server Status",
        description=f"**MOTD:** {motd}",
        color=discord.Color.green() if status_text.lower() == "online" else discord.Color.red()
    )
    embed.add_field(name="Status", value=f"🟢 {status_text}", inline=True)
    embed.add_field(name="Uptime", value=uptime_str, inline=True)
    embed.add_field(name="Players Online", value=player_count_str, inline=False)
    embed.add_field(name="Who's Online", value=players_str, inline=False)

    await ctx.send(embed=embed)


    await ctx.send(embed=embed)
    print(json.dumps(data, indent=2))




@bot.command()
async def listcommands(ctx):
    cmds = [cmd.name for cmd in bot.commands]
    await ctx.send(f"Loaded commands: {', '.join(cmds)}")

@bot.command(aliases=["set", "setty"])
async def setserver(ctx, new_address: str):
    author_id = ctx.author.id
    if author_id not in [546650815297880066, 448896936481652777]:
        await ctx.send("🚫 You don't have permission to update the server address.")
        return

    if author_id == 448896936481652777:
        _apply_server_address(new_address)
        await ctx.send(f"✅ Server address updated to `{new_address}`.")
        return

    class ConfirmView(View):
        def __init__(self):
            super().__init__(timeout=60)
            self.result = None

        @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
        async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id == 448896936481652777:
                _apply_server_address(new_address)
                await interaction.response.edit_message(content=f"✅ Approved by <@{interaction.user.id}>. Server address updated to `{new_address}`.", view=None)
                self.result = True
                self.stop()
            else:
                await interaction.response.send_message("🚫 Only the owner can approve this action.", ephemeral=True)

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(content="❌ Server address update cancelled.", view=None)
            self.result = False
            self.stop()

    view = ConfirmView()
    await ctx.send(f"⚠️ <@448896936481652777>, <@{author_id}> wants to set the server address to `{new_address}`.", view=view)

def _apply_server_address(new_address):
    with open(".env", "r") as f:
        lines = f.readlines()
    with open(".env", "w") as f:
        for line in lines:
            if line.startswith("SERVER_ADDRESS="):
                f.write(f"SERVER_ADDRESS={new_address}\n")
            else:
                f.write(line)
    load_dotenv(override=True)

@bot.command(name="𝑩𝒆𝒆𝒃𝒐", aliases=["beebo", "ping"])
async def beebo_ping(ctx):
    start = time.perf_counter()
    msg = await ctx.send("🏓 Pinging Beebo...")
    end = time.perf_counter()
    latency_ms = (end - start) * 1000
    embed = discord.Embed(description="<:pixel_cake_blk:1368286757094949056> Did someone call for Beebo?", color=0xffefb0)
    embed.set_footer(text=f"Latency: {latency_ms:.2f} ms ({latency_ms/1000:.2f} sec)")
    await msg.edit(content=None, embed=embed)

@bot.command(aliases=["upt", "alive"])
async def uptime(ctx):
    uptime_seconds = int(time.time() - boot_time)
    minutes, seconds = divmod(uptime_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    embed = discord.Embed(
        title="🕒 Beebo Uptime",
        description=f"I've been alive for {hours}h {minutes}m {seconds}s",
        color=0xb0c0ff
    )
    await ctx.send(embed=embed)

@bot.command(aliases=["emojiid", "stickerid", "getid", "se"])
async def idcheck_command(ctx):
    message = ctx.message

    # Regex for custom emoji: <a:name:id> (animated) or <:name:id>
    custom_emoji_pattern = r'<a?:([a-zA-Z0-9_]+):(\d+)>'
    matches = re.findall(custom_emoji_pattern, message.content)

    embed = discord.Embed(title="🆔 ID Check", color=0xb0c0ff)

    if matches:
        for name, emoji_id in matches:
            embed.add_field(name=f"Emoji: {name}", value=f"ID: `{emoji_id}`", inline=False)
    else:
        embed.add_field(name="Emoji", value="No custom emojis found.", inline=False)

    if message.stickers:
        for sticker in message.stickers:
            embed.add_field(name=f"Sticker: {sticker.name}", value=f"ID: `{sticker.id}`", inline=False)
    else:
        embed.add_field(name="Sticker", value="No stickers found.", inline=False)

    # Delete original message after 10 seconds
    await ctx.send(embed=embed, delete_after=10)
    await ctx.message.delete(delay=10)

@bot.command(aliases=["ver", "commit"])
async def version(ctx):
    import subprocess
    try:
        commit = subprocess.check_output(["git", "log", "-1", "--pretty=format:%h - %s"]).decode().strip()
        embed = discord.Embed(
            title="📦 Beebo Version",
            description=f"`{commit}`",
            color=0xb0c0ff
        )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Could not retrieve version: {e}")       

@bot.command(aliases=["awake", "wakeserver"])
async def startserver(ctx):
    if 1366796508288127066 not in [role.id for role in ctx.author.roles]:
        await ctx.send("🚫 You don't have permission to use this command.")
        return

    try:
        atclient = Client()
        atclient.login(EXAROTON_EMAIL, EXAROTON_PASSWORD)
        servers = exaroton_client.get_servers()

        if not servers:
            await ctx.send("No Exaroton servers found for this account.")
            return

        myserver = servers[0]
        myserver.start()

        embed = discord.Embed(title="Server Startup Initiated!", color=0xffd79f)
        embed.add_field(name="Launching", value="Beebo has triggered Termite startup.", inline=False)
        embed.set_footer(text="Give it a minute. Queue times vary.")
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Failed to start server: `{str(e)}`")

@bot.command(aliases=["offping", "cacaw"])
@cooldown(1, 300, BucketType.channel)  # once every 5 minutes per channel
async def pingoffline(ctx):
    server = JavaServer.lookup(SERVER_ADDRESS)
    try:
        status = server.status()
        await ctx.send("Termite is currently online — no need to ping the squad.")
    except:
        embed = discord.Embed(title="**Heads Up! The Server Seems to Be Offline or Sleeping**", color=0xffd79f)
        embed.set_footer(text="Someone needs to hop in or start it manually.")
        await ctx.send(content="<@&1368225900486721616>", embed=embed)

@bot.command(aliases=["commitgit", "gitcommit", "gc"])
async def commitcode(ctx, *, msg: str = None):
    if ctx.author.id not in DEV_USER_ID:
        await ctx.send("🚫 You don't have permission to commit code.")
        return

    if not msg:
        await ctx.send("❗ You need to include a commit message.\nUsage: `!commitcode <your message>`")
        return

    import subprocess

    try:
        # Stage all changes
        subprocess.run(["git", "add", "."], check=True)

        # Commit with message
        subprocess.run(["git", "commit", "-m", msg], check=True)

        embed = discord.Embed(
            title="✅ Git Commit Successful",
            description=f"Committed with message:\n```{msg}```",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    except subprocess.CalledProcessError as e:
        await ctx.send(f"❌ Commit failed:\n```{e}```")

@bot.command(aliases=["syncpush", "deploy"])
async def pushcode(ctx, *, commit_msg="Updated from Beebo"):
    if ctx.author.id not in DEV_USER_ID:
        await ctx.send("🚫 You don't have permission to push code.")
        return

    import subprocess
    try:
        # Add all modified/unknown files
        subprocess.run(["git", "add", "-A"], check=True)

        # Commit changes
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)

        # Push to origin/main
        subprocess.run(["git", "push", "origin", "main"], check=True)

        embed = discord.Embed(
            title="✅ Code Pushed Successfully",
            description=f"Commit message: `{commit_msg}`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    except subprocess.CalledProcessError as e:
        embed = discord.Embed(
            title="❌ Git Operation Failed",
            description=f"```{e}```",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        embed = discord.Embed(
            title="❌ Unexpected Error",
            description=f"```{str(e)}```",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@pingoffline.error
async def pingoffline_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        retry_after = int(error.retry_after)
        minutes, seconds = divmod(retry_after, 60)
        time_left = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
        await ctx.send(f"\u23F3 That command is on cooldown. Try again in `{time_left}`.")

@bot.command()
async def cakecheck(ctx):
    cake_id = 546650815297880066
    cake_user = ctx.guild.get_member(cake_id)

    if not cake_user:
        description = "Can't find Cake...probably lost in notifications again."
    else:
        status = str(cake_user.status)
        if status == "online":
            description = "🟢 Cake is online...maybe watching, maybe ignoring."
        elif status == "idle":
            description = "🌙 Cake is idle. She's drifting through frosting fog."
        elif status == "dnd":
            description = "⛔ Do not disturb: probably battling her DM pile."
        else:
            description = "⚫ Cake is offline...or is she?"

    unread_messages = f"{random.randint(3000, 9000):,}"
    embed = discord.Embed(
        title="<:pixel_cake:1368264542064345108> Cake Status Scan",
        description=description,
        color=0xffaad4
    )
    embed.set_thumbnail(url="attachment://pixel_cake.png")
    embed.set_footer(text="Unread messages: 8,042. DMs: yes, but no.")
    file = discord.File("/root/beebo/assets/pixel_cake.png", filename="pixel_cake.png")
    await ctx.send(file=file, embed=embed)

def get_presence_description(member, lines):
    if not member:
        return lines["not_found"]
    status = str(member.status)
    return lines.get(status, lines["default"])

@bot.command(aliases=["vivera", "vscan"])
async def viveracheck(ctx):
    member = ctx.guild.get_member(533680872747171841)
    desc = get_presence_description(member, {
        "online": "🟢 Vivera is vibing online. Possibly watching everything in silence.",
        "idle": "🌙 Vivera is idle... probably lost in deep lore.",
        "dnd": "⛔ Do not disturb. Vivera's in another dimension.",
        "offline": "⚫ Vivera is offline... or just too cool to be seen.",
        "not_found": "Couldn't locate Vivera. Too ethereal.",
        "default": "Vivera exists in a state beyond presence."
    })
    embed = discord.Embed(title="✨ Vivera Status", description=desc, color=0xd8b3ff)
    await ctx.send(embed=embed)

@bot.command(aliases=["jenna", "jscan", "statsqueen"])
async def jennacheck(ctx):
    member = ctx.guild.get_member(715950635282858094)
    desc = get_presence_description(member, {
        "online": "🟢 Jenna is online and probably checking five dashboards.",
        "idle": "🌙 Jenna is idle. Give her a stat to monitor.",
        "dnd": "⛔ Jenna is deep in analytics mode.",
        "offline": "⚫ Jenna is offline. Stats are on their own now.",
        "not_found": "Can't find Jenna. Maybe she's optimizing the guild.",
        "default": "Jenna is in stealth analyst mode."
    })
    embed = discord.Embed(title="📊 Jenna Scan", description=desc, color=0xffeaa7)
    await ctx.send(embed=embed)

@bot.command(aliases=["toast", "toastlord"])
async def toastcheck(ctx):
    member = ctx.guild.get_member(858462569043722271)
    desc = get_presence_description(member, {
        "online": "🟢 Toast is here — and Minecraft trembles.",
        "idle": "🌙 Toast is idle. Possibly brewing potions.",
        "dnd": "⛔ Toast is busy defending the realm.",
        "offline": "⚫ Toast is offline. The chunk has unloaded.",
        "not_found": "Toast is nowhere to be found. Server lag?",
        "default": "Toast is in ghost mode."
    })
    embed = discord.Embed(title="🔥 Toast Tracker", description=desc, color=0xffc300)
    await ctx.send(embed=embed)

@bot.command(aliases=["asiasen", "asiapower"])
async def asiasencheck(ctx):
    member = ctx.guild.get_member(568577192682848267)
    desc = get_presence_description(member, {
        "online": "🟢 Asiasen is online. Eyes sharp, moves sharper.",
        "idle": "🌙 Asiasen is idle. Awaiting the next call.",
        "dnd": "⛔ Do not disturb. Probably doing boss things.",
        "offline": "⚫ Asiasen is offline. Power-saving mode engaged.",
        "not_found": "Asiasen is missing from the grid.",
        "default": "Asiasen is operating from the shadows."
    })
    embed = discord.Embed(title="💼 Asiasen Ops Check", description=desc, color=0x7ed6df)
    await ctx.send(embed=embed)

@bot.command(aliases=["gooby", "sus", "loud"])
async def goobycheck(ctx):
    member = ctx.guild.get_member(883446198579634177)
    desc = get_presence_description(member, {
        "online": "🟢 Gooby is online. Probably yelling SUS at someone.",
        "idle": "🌙 Gooby is idle. The calm before the scream.",
        "dnd": "⛔ Do not disturb. Emergency meeting in progress.",
        "offline": "⚫ Gooby is offline. Mic cooldown active.",
        "not_found": "Gooby couldn't be found. Sabotage?",
        "default": "Gooby is venting through the shadows."
    })
    embed = discord.Embed(title="🔊 Gooby Voice Check", description=desc, color=0xf8a5c2)
    await ctx.send(embed=embed)

@bot.command(aliases=["meow", "simpstar", "brainfan"])
async def meowstarcheck(ctx):
    member = ctx.guild.get_member(1148630927686254602)
    desc = get_presence_description(member, {
        "online": "🟢 Meowstar is online — probably admiring your Among Us genius.",
        "idle": "🌙 Meowstar is idle. Thinking about how big-brained you are.",
        "dnd": "⛔ Do not disturb. Braincell charging in progress.",
        "offline": "⚫ Meowstar is offline... maybe writing a fanfic about your galaxy brain.",
        "not_found": "Meowstar not detected. Has he stopped praising you?",
        "default": "Meowstar is AFK but spiritually simping."
    })
    embed = discord.Embed(title="🌟 Meowstar Worship Log", description=desc, color=0xa29bfe)
    await ctx.send(embed=embed)


@bot.command(aliases=["talk", "broadcast", "bcast"])
async def say(ctx, channel_input=None, *, message: str = None):
    if 1366796508288127066 not in [role.id for role in ctx.author.roles]:
        await ctx.send("🚫 You don't have permission to use this command.")
        return

    # Handle empty call
    if not channel_input and not message:
        await ctx.send("❗ You must provide a message.")
        return

    # Try to resolve channel from input
    target_channel = None
    if channel_input:
        channel_id = None
        if channel_input.startswith("<#") and channel_input.endswith(">"):
            channel_id = int(channel_input[2:-1])
        elif channel_input.isdigit():
            channel_id = int(channel_input)
        else:
            # Try name match
            matched = [c for c in ctx.guild.text_channels if c.name.lower() == channel_input.lower()]
            if matched:
                target_channel = matched[0]

        if channel_id:
            target_channel = bot.get_channel(channel_id)

        # If we *couldn't* resolve the channel, treat it as message text
        if not target_channel:
            message = f"{channel_input} {message or ''}".strip()
            target_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    else:
        target_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)

    # Final check
    if not message:
        await ctx.send("❗ You must provide a message to send.")
        return

    try:
        embed = discord.Embed(description=message, color=0xb0c0ff)
        await target_channel.send(content=ROLE_TO_TAG, embed=embed)
        await ctx.send(f"✅ Message sent to {target_channel.mention}")
    except discord.Forbidden:
        await ctx.send("🚫 Bot lacks permission to send messages in that channel.")
    except Exception as e:
        await ctx.send("💥 Failed to send the message.")
        logging.exception(f"Error sending message to {target_channel.id}: {e}")

@bot.command(aliases=["sp", "chat"])
async def speak(ctx, channel_input=None, *, message: str = None):
    if 1366796508288127066 not in [role.id for role in ctx.author.roles]:
        await ctx.send("🚫 You don't have permission to use this command.")
        return

    # Handle empty call
    if not channel_input and not message:
        await ctx.send("❗ You must provide a message.")
        return

    # Try to resolve channel from input
    target_channel = None
    if channel_input:
        channel_id = None
        if channel_input.startswith("<#") and channel_input.endswith(">"):
            channel_id = int(channel_input[2:-1])
        elif channel_input.isdigit():
            channel_id = int(channel_input)
        else:
            # Try name match
            matched = [c for c in ctx.guild.text_channels if c.name.lower() == channel_input.lower()]
            if matched:
                target_channel = matched[0]

        if channel_id:
            target_channel = bot.get_channel(channel_id)

        # If we *couldn't* resolve the channel, treat it as message text
        if not target_channel:
            message = f"{channel_input} {message or ''}".strip()
            target_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    else:
        target_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)

    # Final check
    if not message:
        await ctx.send("❗ You must provide a message to send.")
        return

    try:
        embed = discord.Embed(description=message, color=0xb0c0ff)
        await target_channel.send(content="", embed=embed)
        await ctx.send(f"✅ Message sent to {target_channel.mention}")
    except discord.Forbidden:
        await ctx.send("🚫 Bot lacks permission to send messages in that channel.")
    except Exception as e:
        await ctx.send("💥 Failed to send the message.")
        logging.exception(f"Error sending message to {target_channel.id}: {e}")



@bot.command(aliases=["rle"])
async def reloadenv(ctx):
    if ctx.author.id not in [546650815297880066, 448896936481652777]:
        await ctx.send("🚫 You don't have permission to reload the environment.")
        return

    load_dotenv(override=True)
    embed = discord.Embed(
        title="Environment Reloaded ✅",
        description="Configuration has been reloaded from .env. Beebo's got the latest settings <:pixel_cake:1368264542064345108>.",
        color=0xb0c0ff
    )
    await ctx.send(embed=embed)

@bot.command(aliases=["check", "perms"])
@is_trusted()
async def checkperms(ctx, channel_input: str = None):
    if not channel_input:
        await ctx.send("ℹ️ Please provide a channel name, mention, ID, or `all`.")
        return

    if channel_input.lower() == "all":
        report = []
        for channel in ctx.guild.text_channels:
            perms = channel.permissions_for(ctx.guild.me)
            missing = []
            if not perms.view_channel:
                missing.append("View")
            if not perms.send_messages:
                missing.append("Send")
            if not perms.embed_links:
                missing.append("Embed")

            if missing:
                report.append(f"❌ `{channel.name}`: Missing {', '.join(missing)}")
            else:
                report.append(f"✅ `{channel.name}`: All good")

        pages = [report[i:i + 20] for i in range(0, len(report), 20)]
        for page in pages:
            await ctx.send("\n".join(page))
        return

    # Else: normal single-channel check
    channel = None
    if channel_input.startswith("<#") and channel_input.endswith(">"):
        channel_id = int(channel_input[2:-1])
        channel = bot.get_channel(channel_id)
    elif channel_input.isdigit():
        channel = bot.get_channel(int(channel_input))
    else:
        matches = [c for c in ctx.guild.text_channels if c.name == channel_input]
        if matches:
            channel = matches[0]

    if not channel:
        await ctx.send("❌ Channel not found.")
        return

    perms = channel.permissions_for(ctx.guild.me)
    missing = []
    if not perms.view_channel:
        missing.append("View Channel")
    if not perms.send_messages:
        missing.append("Send Messages")
    if not perms.embed_links:
        missing.append("Embed Links")

    if not missing:
        await ctx.send(f"✅ I have all necessary permissions in {channel.mention}.")
    else:
        await ctx.send(
            f"⚠️ Missing permissions in {channel.mention}: {', '.join(missing)}"
        )

@bot.command()
async def reload(ctx):
    if ctx.author.id != 448896936481652777:
        await ctx.send("🚫 You don't have permission to perform a full reload.")
        return

    import asyncio
    async def delayed_restart():
        await asyncio.sleep(2)
        import subprocess
        try:
            subprocess.run(["/root/beebo/reload_beebo.sh"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Reload failed: {e}")

    embed = discord.Embed(
        title="Restarting Beebo 🔁",
        description="Pulling latest code and restarting. Back in a sec...<:pixelGUY:1368269152334123049>",
        color=0xb0c0ff
    )
    await ctx.send(embed=embed)
    bot.loop.create_task(delayed_restart())

@bot.command()
async def gitstatus(ctx):
    if ctx.author.id not in [546650815297880066, 448896936481652777]:
        await ctx.send("🚫 You don't have permission to use this command.")
        return    
    import subprocess
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            await ctx.send(f"❌ Git error:\n```{result.stderr}```")
            return

        output = result.stdout.strip()
        if not output:
            await ctx.send("✅ Working tree is clean.")
        else:
            await ctx.send(f"⚠️ Uncommitted changes:\n```diff\n{output}```")
    except Exception as e:
        await ctx.send(f"❌ Couldn't check Git status: {e}")

@bot.command(aliases=["debug", "commands"])
async def debugstatus(ctx):
    if ctx.author.id not in [546650815297880066, 448896936481652777]:
        await ctx.send("🚫 You don't have permission to use this command.")
        return

    embed = discord.Embed(title="🛠️ Beebo Debug Command List", color=0x462f80)
    
    for cmd in bot.commands:
        aliases = ', '.join(cmd.aliases) if cmd.aliases else "None"
        embed.add_field(
            name=f"!{cmd.name}",
            value=f"Aliases: `{aliases}`",
            inline=False
        )

    embed.set_footer(text="These are all currently loaded commands. Dev eyes only.")
    await ctx.send(embed=embed)

@bot.command(aliases=["bhelp", "beebohelp"])
async def help(ctx):
    embed = discord.Embed(title="Beebo Command List", color=0xb0c0ff)
    embed.add_field(name="!status", value="Check if the Minecraft server is online and who's on.", inline=False)
    embed.add_field(name="!pingoffline / !offping", value="If the server is offline, alert the squad to start it.", inline=False)
    embed.add_field(name="!startserver / !awake", value="Attempts to start the server using Exaroton (restricted to ☁️ �𝓿𝓲𝓼𝓬𝓵𝓸𝓾𝓭 role).", inline=False)
    embed.add_field(name="!say / !talk / !bcast", value="Send a custom message with an embed and ping MCSquad (restricted).", inline=False)
    embed.add_field(name="!suggest", value="Submit changes you'd like to see in 𝑩𝒆𝒆𝒃𝒐.", inline=False)
    embed.add_field(name="!cakecheck, !viveracheck, !jennacheck, etc.", value="Check specific users' status in a fun way.", inline=False)
    embed.add_field(name="!reloadenv / !rle", value="Reloads the environment settings <:pixel_cake:1368264542064345108>. Restricted.", inline=False)
    embed.add_field(name="!reload", value="Pulls latest code and restarts Beebo <:pixelGUY:1368269152334123049>. Restricted.", inline=False)
    embed.add_field(name="!uptime / !upt", value="Shows how long Beebo has been running.", inline=False)
    embed.add_field(name="!version / !ver", value="Shows the latest commit hash from Git.", inline=False)
    embed.add_field(name="!setserver <address>", value="Request/update the Minecraft server address. Protected.", inline=False)
    embed.add_field(name="!help", value="You're looking at it.", inline=False)
    embed.set_footer(text="Bot made for keeping the realm alive and the squad notified.")
    await ctx.send(embed=embed)

@tasks.loop(time=datetime.time(hour=3, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))))  # 3AM EST
async def daily_server_status():
    channel = bot.get_channel(STATUS_CHANNEL_ID)
    try:
        server = JavaServer.lookup(f"{MC_SERVER_IP}:{MC_SERVER_PORT}")
        status = server.status()
        await channel.send(f"🟢 Minecraft server is online with {status.players.online} player(s).")
    except Exception as e:
        await channel.send(f"🔴 Minecraft server is offline or unreachable.\nError: `{e}`")

@bot.command()
async def githelp(ctx):
    if ctx.author.id not in [546650815297880066, 448896936481652777]:
        await ctx.send("🚫 You don't have permission to use this command.")
        return
    
    embed = discord.Embed(title="💡 Git Cheat Sheet", color=0x462f80)
    embed.add_field(name="🔄 Sync Latest Code", value="`git pull origin main`", inline=False)
    embed.add_field(name="📤 Add & Push Changes", value="`git add .`\n`git commit -m \"msg\"`\n`git push origin main`", inline=False)
    embed.add_field(name="🔍 Status & History", value="`git status`\n`git log --oneline`", inline=False)
    embed.add_field(name="🧹 Undo Changes", value="`git checkout -- your_file.py`", inline=False)
    embed.add_field(name="⚔️ Merge Conflict Fix", value="1. Manually edit\n2. `git add .`\n3. `git commit -m \"resolve conflict\"`", inline=False)
    embed.set_footer(text="Use with great power. Git good.")
    await ctx.send(embed=embed)

# --- Suggestion Collection ---
def load_suggestions():
    if not os.path.exists(SUGGESTIONS_FILE):
        return []
    with open(SUGGESTIONS_FILE, "r") as f:
        return json.load(f)

def save_suggestions(suggestions):
    with open(SUGGESTIONS_FILE, "w") as f:
        json.dump(suggestions, f, indent=2)

@bot.command()
async def suggest(ctx, action=None, *, arg=None):
    """Submit or manage suggestions for the bot"""
    suggestions = load_suggestions()
    now = time.time()  # Capture time once

    # Cooldown check first
    user_id = ctx.author.id
    if user_id not in DEV_USER_ID:  # Only enforce cooldown for non-developers
        last_time = cooldowns.get(user_id, 0)
        if now - last_time < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - (now - last_time))
            embed = discord.Embed(
                title="⏳ Slow down!",
                description=f"You're on cooldown. Try again in **{remaining}** seconds.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Only devs can bypass this.")
            await ctx.send(embed=embed)
            return
        cooldowns[user_id] = now  # Update cooldown

    if action is None:
        await ctx.send("Usage: !suggest <message> | !suggest view [keyword/user] | !suggest delete <index>")
        return

    # Rest of your command logic here...
    # Make sure ALL code under this point is properly indented with 4 spaces

    action = action.lower()

    # Add suggestion
    if action not in ["view", "delete"]:
        message = f"{action} {arg}" if arg else action
        suggestion = {
            "user": str(ctx.author),
            "user_id": user_id,
            "message": message,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        suggestions.append(suggestion)
        save_suggestions(suggestions)

        # Log to dev channel
        log_channel = bot.get_channel(DEV_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="💡 New Suggestion Submitted",
                color=discord.Color.blurple()
            )
            embed.add_field(name="User", value=f"{ctx.author} ({ctx.author.mention})", inline=False)
            embed.add_field(name="User ID", value=f"{ctx.author.id}", inline=False)
            embed.add_field(name="Channel", value=f"{ctx.channel.mention}", inline=False)
            embed.add_field(name="Suggestion", value=message, inline=False)
            embed.add_field(name="Submitted At", value=f"<t:{int(now)}:F>", inline=False)
            embed.set_footer(text="Beebo Suggestion System", icon_url=ctx.author.display_avatar.url)
            await log_channel.send(embed=embed)


        confirmation = discord.Embed(
            title="✅ Suggestion Received",
            description="Thanks for your input! Your suggestion has been logged.",
            color=discord.Color.green()
        )
        await ctx.send(embed=confirmation)

        return

    # View suggestions
    if action == "view":
        filtered = suggestions
        if arg:
            arg = arg.lower()
            filtered = [s for s in suggestions 
                       if arg in s["message"].lower() or 
                       arg in s["user"].lower()]

        if not filtered:
            await ctx.send("No suggestions found.")
            return

        # Pagination code here
        pages = []
        for i in range(0, len(filtered), 5):
            embed = discord.Embed(
                title=f"Suggestions (Page {i//5 + 1}/{len(filtered)//5 + 1})",
                color=0xb0c0ff
            )
            for j, s in enumerate(filtered[i:i+5], start=i+1):
                embed.add_field(
                    name=f"#{j} - {s['user']}",
                    value=s['message'],
                    inline=False
                )
            pages.append(embed)

        # Send first page
        msg = await ctx.send(embed=pages[0])
        
        # Add reactions if multiple pages
        if len(pages) > 1:
            await msg.add_reaction("⬅️")
            await msg.add_reaction("➡️")

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"]

            page = 0
            while True:
                try:
                    reaction, _ = await bot.wait_for("reaction_add", timeout=60.0, check=check)
                    
                    if str(reaction.emoji) == "➡️" and page < len(pages)-1:
                        page += 1
                    elif str(reaction.emoji) == "⬅️" and page > 0:
                        page -= 1
                        
                    await msg.edit(embed=pages[page])
                    await msg.remove_reaction(reaction, ctx.author)
                    
                except asyncio.TimeoutError:
                    await msg.clear_reactions()
                    break
        return

    # DELETE
    if action.lower() == "delete":
        if ctx.author.id not in DEV_USER_ID:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only devs can delete suggestions.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

# Delete suggestion
    if action == "delete":
        if ctx.author.id not in DEV_USER_ID:
            await ctx.send("🚫 Only devs can delete suggestions.")
            return

        if not arg or not arg.isdigit():
            await ctx.send("Usage: `!suggest delete <index>`")
            return

        index = int(arg) - 1
        if 0 <= index < len(suggestions):
            deleted = suggestions.pop(index)
            save_suggestions(suggestions)
            await ctx.send(f"🗑️ Deleted suggestion #{index + 1} by {deleted['user']}.")
        else:
            await ctx.send("Invalid suggestion index.")

versionfix_cooldown = 0  # Shared cooldown for version fix
EXAROTON_TOKEN = os.getenv("EXAROTON_TOKEN")
exaroton = Exaroton(EXAROTON_TOKEN)
challenge_file = "data/challenges.json"
if not os.path.exists("data"):
    os.makedirs("data")
if not os.path.exists(challenge_file):
    with open(challenge_file, "w") as f:
        json.dump({}, f)

@bot.command()
@commands.is_owner()
async def reloadcog(ctx, name: str):
    try:
        await bot.reload_extension(f"cogs.{name}")
        await ctx.send(f"✅ Reloaded cog: `{name}`")
    except Exception as e:
        await ctx.send(f"❌ Failed to reload: `{e}`")

@bot.command()
async def explayers(ctx):
    try:
        server = exaroton.get_servers()[0]
        status = server.status()
        players = status.players
        if players:
            await ctx.send(f"🟢 Players online: {', '.join(players)}")
        else:
            await ctx.send("⚫ No players online.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
async def exlog(ctx):
    try:
        server = exaroton.get_servers()[0]
        log = server.get_log()
        with open("latest.log", "w") as f:
            f.write(log)
        await ctx.send(file=File("latest.log"))
    except Exception as e:
        await ctx.send(f"❌ Failed to fetch logs: {e}")

@bot.group(invoke_without_command=True)
async def challenge(ctx):
    await ctx.send("Use `!challenge start <name>`, `!challenge submit <proof>`, or `!challenge leaderboard`.")

@challenge.command(name="start")
async def start_challenge(ctx, *, name: str):
    with open(challenge_file, "r") as f:
        data = json.load(f)
    data[name] = []
    with open(challenge_file, "w") as f:
        json.dump(data, f, indent=2)
    await ctx.send(f"✅ Challenge **{name}** started!")

@challenge.command(name="submit")
async def submit_challenge(ctx, *, proof: str):
    with open(challenge_file, "r") as f:
        data = json.load(f)
    if not data:
        await ctx.send("⚠️ No active challenges.")
        return
    latest = list(data.keys())[-1]
    data[latest].append({
        "user": str(ctx.author),
        "proof": proof,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })
    with open(challenge_file, "w") as f:
        json.dump(data, f, indent=2)
    await ctx.send(f"✅ Submission added to **{latest}**!")

@challenge.command(name="leaderboard")
async def challenge_leaderboard(ctx):
    with open(challenge_file, "r") as f:
        data = json.load(f)
    if not data:
        await ctx.send("⚠️ No challenges found.")
        return
    latest = list(data.keys())[-1]
    entries = data[latest]
    leaderboard = {}
    for entry in entries:
        user = entry["user"]
        leaderboard[user] = leaderboard.get(user, 0) + 1
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    desc = "\n".join([f"**{i+1}. {u}** — {c} entries" for i, (u, c) in enumerate(sorted_lb)])
    embed = discord.Embed(title=f"🏆 {latest} Leaderboard", description=desc or "No entries yet.", color=0xffc300)
    await ctx.send(embed=embed)

@bot.command(aliases=["mcerror"])
async def versionfix(ctx):
    global versionfix_cooldown
    now = time.time()
    if now - versionfix_cooldown < 1800:
        remaining = int(1800 - (now - versionfix_cooldown))
        minutes, seconds = divmod(remaining, 60)
        await ctx.send(f"⏳ That info was recently posted. Try again in `{minutes}m {seconds}s`.")
        return

    versionfix_cooldown = now
    await send_versionfix_embed(ctx.channel)

async def send_versionfix_embed(channel):
    embed = discord.Embed(
        title="⚠️ Minecraft Version Mismatch?",
        description=(
            "Seeing `Incompatible client version` or `Server mainly supports 1.20.1`?\n\n"
            "**That means your game is too updated for the server.**\n"
            "**We run Minecraft 1.20.X.** Not the latest.\n\n"
            "**How to fix it:**\n"
            "1. Open the Minecraft Launcher\n"
            "2. Go to `Installations`\n"
            "3. Create or select version `1.21.X`\n"
            "4. Launch it and join!\n\n"
            "_Need help?_ Use `!status` or ping a staff member."
        ),
        color=0xffc300
    )
    embed.set_footer(text="Sticky version info provided by 𝑩𝒆𝒆𝒃𝒐.")
    await channel.send(embed=embed)

@tasks.loop(hours=6)
async def refresh_sticky_message():
    channel = bot.get_channel(STICKY_CHANNEL_ID)
    if not channel:
        return

    # Load previous message ID
    last_id = None
    if os.path.exists(STICKY_MESSAGE_ID_FILE):
        with open(STICKY_MESSAGE_ID_FILE) as f:
            data = json.load(f)
            last_id = data.get("message_id")

    # Delete old message
    if last_id:
        try:
            old_msg = await channel.fetch_message(last_id)
            await old_msg.delete()
        except discord.NotFound:
            pass

    # Send new sticky embed
    embed = discord.Embed(
        title="🌍 How to Join the Minecraft Server",
        description="Instructions for JAVA users.",
        color=0x57C7FF
    )
    embed.add_field(name="**🖥️ PC (Java Edition)**", value="`IP:` **termite.exaroton.me**\n`Port:` **14663**", inline=False)
    embed.set_footer(text="Posted by 𝑩𝒆𝒆𝒃𝒐 • Updated regularly")

    new_msg = await channel.send(embed=embed)
    await new_msg.pin()

@bot.event
async def on_message(message):
    print(f"Received message: {message.content}")
    if message.author.bot:
        return

    global versionfix_cooldown
    keywords = ["too updated", "incompatible version", "server version", "can't join server"]
    if any(kw in message.content.lower() for kw in keywords):
        now = time.time()
        if now - versionfix_cooldown >= 1800:
            versionfix_cooldown = now
            await send_versionfix_embed(message.channel)

    await bot.process_commands(message)

@bot.command()
@commands.is_owner()  # Only you can run this
async def testsuggest(ctx, attempts: int = 5):
    """Test the spam protection in !suggest. Usage: !testsuggest [attempts]"""
    cooldowns.clear()  # Reset cooldown tracker
    test_msg = "Stress-testing suggestion system"
    
    for i in range(attempts):
        # Simulate a !suggest command
        fake_ctx = ctx
        fake_ctx.message.content = f"!suggest {test_msg}"
        await bot.process_commands(fake_ctx.message)
        await ctx.send(f"Attempt {i+1}/{attempts} - Sent: `!suggest`")
        await asyncio.sleep(0.5)  # Avoid rate limits
    
    await ctx.send(f"**Test complete.** Check cooldowns: `{cooldowns.get(ctx.author.id, 'None')}`")

# --- Developer Command Logging ---
@bot.listen('on_command')
async def log_dev_commands(ctx):
    if ctx.guild and ctx.guild.id == GUILD_ID:
        log_channel = bot.get_channel(DEV_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"🛠️ Command `{ctx.command}` used by **{ctx.author}** in #{ctx.channel}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

# Main async startup
async def main():
    await bot.load_extension("cogs.challonge_cog")
    await bot.load_extension("cogs.exaroton")
    await bot.load_extension("cogs.pinpoint")
    await bot.load_extension("cogs.rewards")
    await bot.load_extension("cogs.utils")
    await bot.load_extension("cogs.helpcog")
    await bot.load_extension("cogs.admin")
    await bot.start(TOKEN)

asyncio.run(main())
