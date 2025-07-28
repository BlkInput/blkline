# cogs/utility.py

import os
import json
import time
import discord
from discord import app_commands
from discord.ext import commands

# ─── Configuration ────────────────────────────────────────────────
DEV_USER_IDS  = {448896936481652777, 777345438495277076}
SYNC_COOLDOWN = 60  # seconds between allowed syncs
_last_sync    = 0
VAULT_FILE    = "data/vault.json"

def _update_sync_time():
    global _last_sync
    _last_sync = time.time()

def _ensure_vault():
    os.makedirs(os.path.dirname(VAULT_FILE), exist_ok=True)
    if not os.path.exists(VAULT_FILE):
        with open(VAULT_FILE, "w") as f:
            json.dump({}, f)

def _load_vault():
    _ensure_vault()
    with open(VAULT_FILE, "r") as f:
        return json.load(f)

def _save_vault(data):
    _ensure_vault()
    with open(VAULT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_json(file, data):
    import os, json
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, "w") as f:
        json.dump(data, f, indent=4)


class UtilityCog(commands.Cog):
    """Hybrid `/sync` + `!sync`, simple key/value store and dispatch helper."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── Hybrid sync ────────────────────────────────────────────────
    @commands.hybrid_command(
        name="sync", description="Sync slash commands & update the command tree"
    )
    @commands.cooldown(1, SYNC_COOLDOWN, commands.BucketType.user)
    async def sync(self, ctx: commands.Context):
        now = time.time()
        user_id = ctx.author.id

        if user_id not in DEV_USER_IDS:
            return await ctx.reply("🚫 You lack permission to sync.", ephemeral=True)

        elapsed = now - _last_sync
        if elapsed < SYNC_COOLDOWN:
            wait = int(SYNC_COOLDOWN - elapsed)
            return await ctx.reply(f"⏳ Please wait {wait}s before re-syncing.", ephemeral=True)

        synced = await self.bot.tree.sync()
        _update_sync_time()
        await ctx.reply(f"✅ Synced {len(synced)} slash commands.", ephemeral=True)

    # ─── Key/value store ────────────────────────────────────────────
    @commands.command(name="store")
    async def store(self, ctx: commands.Context, key: str, *, value: str):
        """Store a value under a given key."""
        vault = _load_vault()
        vault[key] = value
        _save_vault(vault)
        await ctx.send(f"🔒 Stored key `{key}`.")

    @commands.command(name="get")
    async def get(self, ctx: commands.Context, key: str):
        """Retrieve the value for a given key."""
        vault = _load_vault()
        if key not in vault:
            return await ctx.send("❌ No such key.")
        await ctx.send(f"🔓 `{key}` = {vault[key]}")

    # ─── Dispatch helper ────────────────────────────────────────────
    @commands.command(name="dispatch")
    async def dispatch(self, ctx: commands.Context, channel_id: int, *, message: str):
        """Send <message> to channel with <channel_id>."""
        target = ctx.guild.get_channel(channel_id)
        if target is None or not isinstance(target, discord.TextChannel):
            return await ctx.send("❌ Invalid channel ID.")
        try:
            await target.send(message)
            await ctx.send("<:settings:1388586507664883772> Message dispatched.")
        except discord.Forbidden:
            await ctx.send("❌ I lack permission to send in that channel.")
        except Exception as e:
            await ctx.send(f"❌ Failed to dispatch: {e}")

    # ─── Usage hints on missing args ────────────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            name = ctx.command.name
            hints = {
                'store':    " Usage: `!store <key> <value>`",
                'get':      "<:settings:1388586507664883772> Usage: `!get <key>`",
                'dispatch': "<:settings:1388586507664883772> Usage: `!dispatch <channel_id> <message>`",
            }
            if name in hints:
                return await ctx.send(hints[name])
        # re-raise so other cogs can handle unexpected errors
        raise error

async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
