import discord
from discord.ext import commands
from cogs.utils import UtilsCog
import requests
import os
import time

EXAROTON_TOKEN = os.getenv("EXAROTON_TOKEN")
EXAROTON_SERVER_ID = os.getenv("EXAROTON_SERVER_ID")
GRAND_USER_ID = [448896936481652777]
cooldowns = {}
COOLDOWN_SECONDS = 30

HEADERS = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
EXAROTON_BASE = "https://api.exaroton.com/v1/servers"

def get_server_data():
    url = f"{EXAROTON_BASE}/{EXAROTON_SERVER_ID}"
    response = requests.get(url, headers=HEADERS)
    return response.json() if response.status_code == 200 else None

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def dev_check(self, user_id):
        return user_id in GRAND_USER_ID

    def is_on_cooldown(self, user_id):
        now = time.time()
        last = cooldowns.get(user_id, 0)
        return now - last < COOLDOWN_SECONDS

    def update_cooldown(self, user_id):
        cooldowns[user_id] = time.time()

    async def handle_cooldown(self, ctx):
        user_id = ctx.author.id
        if self.dev_check(user_id):
            return False
        if user_id not in cooldowns:
            self.update_cooldown(user_id)
            return False
        elif self.is_on_cooldown(user_id):
            await ctx.send("You're on cooldown. Try again soon.")
            return True
        else:
            self.update_cooldown(user_id)
            return False

    @commands.command(name="serveruptime", aliases=["serverun"])
    async def server_uptime(self, ctx):
        if await self.handle_cooldown(ctx):
            return

        data = get_server_data()
        if not data or "host" not in data:
            await ctx.send("❌ Could not fetch uptime information.")
            return

        uptime = data["host"].get("uptime", 0)
        minutes = uptime // 60
        hours = minutes // 60
        await ctx.send(f"Server has been online for **{hours}h {minutes % 60}m**.")

    @commands.command(name="projectedburn", aliases=["burnproject", "burner"])
    async def projected_burn(self, ctx):
        if await self.handle_cooldown(ctx):
            return

        data = get_server_data()
        if not data:
            await ctx.send("🔥 Couldn't fetch burn rate info.")
            return

        credit_balance = float(data.get("credits", 0))
        burn_rate = float(data.get("settings", {}).get("creditPerHour", 0))
        if burn_rate == 0:
            await ctx.send("🔥 Burn rate is not currently available.")
            return

        hours_left = credit_balance / burn_rate
        await ctx.send(f"🔥 With **{credit_balance:.2f}** credits and a burn rate of **{burn_rate:.2f}/hr**, the server can run for approximately **{hours_left:.1f} hours**.")


    @commands.command(name="sessionlength", aliases=["session"])
    async def session_length(self, ctx):
        if await self.handle_cooldown(ctx):
            return

        data = get_server_data()
        if not data or "host" not in data:
            await ctx.send("❌ Could not fetch session data.")
            return

        uptime = data["host"].get("uptime", 0)
        minutes = uptime // 60
        await ctx.send(f"⏱️ Current session length is **{minutes} minutes**.")

    @commands.command(name="restartserver")
    async def restart_server(self, ctx):
        if ctx.author.id not in GRAND_USER_ID:
            await ctx.send("<:noentry:1388586500756865126> You don't have permission to restart the server.")
            return

        url = f"{EXAROTON_BASE}/{EXAROTON_SERVER_ID}/restart"
        response = requests.post(url, headers=HEADERS)
        if response.status_code == 204:
            await ctx.send("🔄 Restarting the server...")
        else:
            await ctx.send("<:ban:1388586495643877406> Failed to restart the server.")

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
