import discord
from discord.ext import commands, tasks
from mcstatus import JavaServer
from discord.ext.commands import cooldown, BucketType, Context
from .exaroton_scraper_playwright import get_live_status_playwright
import json
import time
import requests
import asyncio
from typing import Union
import os
import datetime
from playwright.async_api import async_playwright
from discord.ui import View, Button
from discord import ButtonStyle

DATA_FILE = "data/exaroton_data.json"
POOL_FILE = "data/exaroton_pool.json"
DONOR_FILE = "data/exaroton_donations.json"
donor_role_id = 1391053379106508831
DONOR_ROLE_THRESHOLD = 100.0
MOD_LOG_CHANNEL_ID = 1391076656835330111
EXAROTON_TRUSTED = [448896936481652777, 858462569043722271]
DEV_USER_ID = [448896936481652777, 424532190290771998]
EXAROTON_TOKEN = os.getenv("EXAROTON_TOKEN")
EXAROTON_SERVER_ID = os.getenv("EXAROTON_SERVER_ID")
SERVER_ADDRESS="obscura.exaroton.me"
CHECK_INTERVAL_HOURS = 3

def load_data(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_data(filename, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def save_json(file, data):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w") as f:
            json.dump(data, f, indent=4)


class ConfirmNukeView(View):
    def __init__(self, target_id, callback):
        super().__init__(timeout=30)
        self.target_id = target_id
        self.display_name = display_name
        self.callback = callback

    @discord.ui.button(label="Confirm Nuke", style=ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        await self.callback(interaction, self.target_id)
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("❌ Nuke cancelled.", ephemeral=True)
        self.stop()


class StatusButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(StatusButton(label="Show Status", custom_id="status_button"))
        self.add_item(StatusButton(label="Show Players", custom_id="players_button"))

class StatusButton(discord.ui.Button):
    def __init__(self, label, custom_id):
        super().__init__(label=label, style=discord.ButtonStyle.blurple, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        ctx = await interaction.client.get_context(interaction.message)
        if self.custom_id == "status_button":
            await interaction.response.defer()
            await ctx.invoke(ctx.bot.get_command("status"))
        elif self.custom_id == "players_button":
            await interaction.response.defer()
            await ctx.invoke(ctx.bot.get_command("players"))

class ServerControlView(discord.ui.View):
    def __init__(self, credit_code):
        super().__init__()
        self.add_item(discord.ui.Button(
            label="💸 Donate Credits",
            url=f"https://exaroton.com/pools/{credit_code}",
            style=discord.ButtonStyle.link
        ))
        self.add_item(discord.ui.Button(
            label="🛠️ Adjust RAM (Coming Soon)",
            style=discord.ButtonStyle.gray,
            disabled=True
        ))


DONORBOARD_COOLDOWN_SECONDS = 300  # 5 minutes
last_donorboard_time = 0
DEV_USER_IDS = [448896936481652777, 777345438495277076]

class DonateButton(discord.ui.View):
    def __init__(self, pool_code):
        super().__init__()
        if pool_code:
            self.add_item(discord.ui.Button(
                label="💸 Donate Credits",
                url=f"https://exaroton.com/pools/{pool_code}",
                style=discord.ButtonStyle.link
            ))


class ExarotonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.credit_balance = load_data(DATA_FILE).get("balance", 0.0)
        self.server_address = os.getenv("SERVER_ADDRESS")
        self.channel_id = int(os.getenv("CHANNEL_ID"))
        self.role_to_tag = os.getenv("ROLE_TO_TAG")
        self.last_status = "offline"
        self.check_server_status.start()

    def get_current_pool_code(self):
        """Always returns the latest pool code from disk."""
        return load_data(POOL_FILE).get("pool", "")

    @tasks.loop(hours=CHECK_INTERVAL_HOURS)
    async def check_server_status(self):
        channel = self.bot.get_channel(self.channel_id)
    
        headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
        url = f"https://api.exaroton.com/v1/servers/{EXAROTON_SERVER_ID}"
    
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print("[Exaroton API] Failed to fetch status.")
                return
    
            data = response.json()
            online = data.get("host", {}).get("online", False)
            status_code = data.get("status")
            players = data.get("players", {}).get("list", [])
            motd = data.get("motd", {}).get("clean", [""])[0]
    
            if status_code == 2 and self.last_status != "online":
                embed = discord.Embed(title="🟢 **Obscura Server is ONLINE!**", color=0x83fefd)
                embed.add_field(name="MOTD", value=motd or "Server Online", inline=False)
                embed.add_field(name="Java IP", value=self.server_address, inline=False)
                embed.add_field(name="Players", value=str(len(players)), inline=False)
    
                if players:
                    embed.add_field(name="Who's Online", value="\n".join(players), inline=False)
    
                embed.set_footer(text="Summon the squad.")
                await channel.send(content=self.role_to_tag, embed=embed)
                self.last_status = "online"
    
                # Check credits
                if self.credit_balance <= 200:
                    try:
                        warn_embed = discord.Embed(
                            title="<:warning:1388586513000042516> Low Server Credits!",
                            description=f"Current balance: **{self.credit_balance} credits**\nTop up soon to avoid downtime.",
                            color=0xffaa00
                        )
                        hours_left = round(self.credit_balance / 10, 1)
                        warn_embed.add_field(name="Burn Estimate", value=f"~{hours_left}h left @ 10GB RAM", inline=False)
                        warn_embed.set_footer(text="Use !topup to donate credits.")
                        view = ServerControlView(self.credit_pool_code)
                        await channel.send(embed=warn_embed, view=view)
                    except Exception as e:
                        print(f"[<:warning:1388586513000042516> Burn Warning Error] {e}")
    
            elif status_code != 2 and self.last_status != "offline":
                embed = discord.Embed(
                    title="🔴 **Minecraft Server is OFFLINE or SLEEPING**",
                    color=0xff5555
                )
                embed.set_footer(text="Someone needs to manually start it or join to wake it up.")
                await channel.send(content=self.role_to_tag, embed=embed)
                self.last_status = "offline"
    
        except Exception as e:
            print(f"[🔥 Server Status Error] {e}")

    async def fetch_server_status(self):
        server_address = self.server_address or SERVER_ADDRESS
        motd = "Unknown MOTD"
        players = []
        online = False
        status_text = "Offline"
        max_players = "?"
        source = "None"

        # ─── 1. Try mcstatus with timeout ───
        try:
            def run_mcstatus():
                return JavaServer.lookup(server_address).status()

            loop = asyncio.get_running_loop()
            status = await asyncio.wait_for(loop.run_in_executor(None, run_mcstatus), timeout=3)
            if status:
                motd = (
                    status.description.get("text", "Unknown MOTD")
                    if isinstance(status.description, dict)
                    else str(status.description)
                )
                players = [p.name for p in status.players.sample] if status.players.sample else []
                online = True
                status_text = "Online"
                max_players = status.players.max
                print("[mcstatus SUCCESS]")
                source = "mcstatus"
        except asyncio.TimeoutError:
            print("[mcstatus TIMEOUT]")
        except Exception as e:
            print(f"[mcstatus FAIL]: {e}")

        # ─── 2. Fallback: Exaroton API ───
        if not online and not players:
            try:
                headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
                url = f"https://api.exaroton.com/v1/servers/{EXAROTON_SERVER_ID}"
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    ex_online = data.get("host", {}).get("online", False)
                    ex_players = data.get("players", {}).get("list", [])
                    ex_motd = data.get("motd", {}).get("clean", [])
                    ex_max_players = data.get("players", {}).get("max", max_players)

                    if ex_online or ex_players:  # Only overwrite if it's giving us something
                        motd = ex_motd[0] if ex_motd else motd
                        online = ex_online
                        players = ex_players or players
                        status_text = "Online" if online else "Offline"
                        max_players = ex_max_players
                        print("[API fallback SUCCESS]")
                        source = "API"
                    else:
                        print("[API fallback gave no new info]")
            except Exception as e:
                print(f"[Exaroton API FAIL]: {e}")

        # ─── 3. Fallback: Scraper ───
        if not online and not players:
            try:
                scraped = await get_live_status_playwright()
                print("SCRAPER RESULT:", scraped)

                if "error" not in scraped:
                    scraped_status = scraped.get("status", "").lower()
                    scraped_players = scraped.get("players", [])
                    if "online" in scraped_status or scraped_players:
                        motd = scraped.get("motd", motd)
                        status_text = scraped.get("status", status_text)
                        players = scraped_players or players
                        online = "online" in scraped_status
                        print("[SCRAPER fallback SUCCESS]")
                        source = "Scraper"
                    else:
                        print("[SCRAPER gave no new info]")
            except Exception as e:
                print(f"[SCRAPER FAIL]: {e}")


        status_text = status_text or "Unknown"
        print(f"[Final Status Source]: {source} | Players: {players}")
        return motd.strip(), players, online, status_text, max_players, source


    @commands.command(name="refreshserverstatus", aliases=["refreshstatus", "rfs"])
    async def refresh_server_status(self, ctx):
        if ctx.author.id not in DEV_USER_ID:
            await ctx.send("🚫 You don't have permission to use this command.")
            return

        await ctx.typing()

        headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
        url = f"https://api.exaroton.com/v1/servers/{EXAROTON_SERVER_ID}"

        api_data = {}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                api_data = response.json()
                self.credit_balance = float(requests.get("https://api.exaroton.com/v1/credits", headers=headers).json().get("credits", 0.0))
        except Exception as e:
            print(f"[API Error] {e}")

        motd = api_data.get("motd", {}).get("clean", ["Unknown"])[0]
        players = api_data.get("players", {}).get("list", [])
        online = api_data.get("host", {}).get("online", False)
        status = "Online" if online else "Offline"

        # Fallback to scraper
        if not players or not online:
            scraped = await get_live_status_playwright()
            if "error" not in scraped:
                motd = scraped.get("motd", motd)
                status = scraped.get("status", status)
                players = scraped.get("players", players)
                online = "online" in status.lower()

        embed = discord.Embed(
            title="🔄 Refreshed Server Status",
            description=f"**MOTD:** `{motd}`",
            color=discord.Color.green() if online else discord.Color.red()
        )
        embed.add_field(name="Status", value=f"🟢 {status}" if online else f"🔴 {status}", inline=True)
        embed.add_field(name="Players Online", value=", ".join(players) if players else "Nobody online.", inline=False)
        embed.set_footer(text="Live refresh via API and scraper fallback")

        class RefreshControl(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(discord.ui.Button(label="Check !players", style=discord.ButtonStyle.blurple, custom_id="players_button"))
                self.add_item(discord.ui.Button(label="Check !status", style=discord.ButtonStyle.gray, custom_id="status_button"))

        await ctx.send(embed=embed, view=RefreshControl())

    @commands.command()
    @commands.is_owner()
    async def setcredits(self, ctx, amount: float, member: discord.Member = None):
        user = member or ctx.author
        user_id = str(user.id)

        # Update credit balance (you can customize whether this affects server logic or is just for stats)
        self.credit_balance = float(amount) if user == ctx.author else self.credit_balance

        # Update personal donation record
        donations = load_data("data/exaroton_donations.json")
        donations[user_id] = donations.get(user_id, 0) + amount
        save_data("data/exaroton_donations.json", donations)

        await ctx.send(f"<:checkbox:1388586497984430160> Set **{amount} credits** for {user.mention}.")

        # Optionally: show leaderboard position
        leaderboard = sorted(donations.items(), key=lambda x: x[1], reverse=True)
        position = [uid for uid, _ in leaderboard].index(user_id) + 1
        await ctx.send(f"🏆 {user.display_name} is now **#{position}** on the donor leaderboard!")

    @commands.command(name="statusapi")
    async def statusapi(self, ctx):
        headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
        url = f"https://api.exaroton.com/v1/servers/{EXAROTON_SERVER_ID}"

        # ─── Exaroton API Check ───
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                await ctx.send("❌ Failed to fetch server status from Exaroton.")
                return

            data = response.json()
        except Exception as e:
            await ctx.send(f"❌ API call failed: {e}")
            return

        # ─── Extract API Data ───
        motd = data.get("motd", {}).get("clean", ["Unknown MOTD"])[0]
        online = data.get("host", {}).get("online", False)
        players = data.get("players", {}).get("list", [])

        # ─── mcstatus Patch if API Sucks ───
        if not online:
            try:
                server = JavaServer.lookup(SERVER_ADDRESS)
                status = server.status()
                if status:
                    online = True
                    players = [p.name for p in status.players.sample] if status.players.sample else players
                    motd = (
                        status.description.get("text", motd)
                        if isinstance(status.description, dict)
                        else str(status.description)
                    )
                    print("[!statusapi patched via mcstatus]")
            except Exception as e:
                print(f"[!statusapi mcstatus FAIL]: {e}")

        # ─── Embed Response ───
        embed = discord.Embed(
            title="Obscura Server Status",
            description=f"**MOTD:** {motd}",
            color=discord.Color.green() if online else discord.Color.red()
        )
        embed.add_field(
            name="Status",
            value="🟢 Online" if online else "<:ban:1388586495643877406> Offline",
            inline=True
        )
        embed.add_field(
            name="Players Online",
            value="\n".join(players) if players else "Nobody online.",
            inline=False
        )

        # ─── Uptime Footer ───
        started = data.get("timeStarted")
        if started:
            try:
                dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                uptime = datetime.utcnow() - dt
                hours, rem = divmod(int(uptime.total_seconds()), 3600)
                minutes, _ = divmod(rem, 60)
                embed.set_footer(text=f"Uptime: {hours}h {minutes}m • Pulled via API + mcstatus")
            except Exception as e:
                print(f"[Uptime parse FAIL]: {e}")
                embed.set_footer(text="Pulled via API + mcstatus")
        else:
            embed.set_footer(text="Pulled via API + mcstatus")

        await ctx.send(embed=embed)


    @commands.command(name="status", aliases=["serverstatus", "termstatus"])
    async def status(self, ctx):
        if await self.handle_cooldown(ctx):
            return

        await ctx.typing()
        motd, players, online, status_text, max_players, source = await self.fetch_server_status()

        embed = discord.Embed(
            title="Obscura Server Status",
            description=f"**MOTD:** `{motd}`",
            color=discord.Color.green() if online else discord.Color.red()
        )
        embed.add_field(name="Status", value=f"🟢 {status_text}" if online else f"🔴 {status_text}", inline=True)
        embed.add_field(name="Players", value=", ".join(players) if players else "Nobody online.", inline=False)
        embed.set_footer(text=f"Pulled via {source} {'(fallback)' if source != 'mcstatus' else '(primary)'}")

        await ctx.send(embed=embed)


    @commands.command(name="dboard", aliases=["donors"])
    async def donorboard(self, ctx, top: int = 5):
        global last_donorboard_time
        now = time.time()
        is_dev = ctx.author.id in DEV_USER_IDS

        if not is_dev and now - last_donorboard_time < DONORBOARD_COOLDOWN_SECONDS:
            remaining = int(DONORBOARD_COOLDOWN_SECONDS - (now - last_donorboard_time))
            embed = discord.Embed(
                title="⏳ Slow down there!",
                description=f"`!donorboard` is on cooldown for **{remaining}** more seconds.",
                color=0xffaa00
            )
            embed.set_footer(text="Try again later.")
            await ctx.send(embed=embed)
            return

        last_donorboard_time = now

        donations = load_data("data/exaroton_donations.json")
        if not donations:
            await ctx.send("📭 No donation data yet!")
            return

        leaderboard = sorted(donations.items(), key=lambda x: x[1], reverse=True)
        embed = discord.Embed(
            title="🏆 Top Server Donors",
            description="Most generous credit contributors ❤️",
            color=0x83fefd
        )

        for i, (user_id, total) in enumerate(leaderboard[:top], start=1):
            user = self.bot.get_user(int(user_id)) or f"<@{user_id}>"
            name = user.display_name if hasattr(user, 'display_name') else str(user)
            embed.add_field(
                name=f"{i}. {name}",
                value=f"💰 {total:.2f} credits",
                inline=False
            )

        if is_dev:
            embed.set_footer(text="Dev bypass (GUY)")

        view = DonateButton(self.get_current_pool_code())
        await ctx.send(embed=embed, view=view)

    @commands.command(name="credits", aliases=["excredits", "bal"])
    async def credits(self, ctx):
        headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
        response = requests.get("https://api.exaroton.com/v1/credits", headers=headers)

        if response.status_code != 200:
            await ctx.send("❌ Failed to fetch credit balance.")
            return

        credits = response.json().get("credits", 0.0)
        embed = discord.Embed(
            title="💳 Server Credit Balance",
            description=f"You currently have **{credits:.2f}** Obscura credits remaining.",
            color=0x3d5e8e
        )
        embed.set_footer(text="Keep it running <:beebo:1383282292478312519>")
        await ctx.send(embed=embed)


    @commands.command(name="add", aliases=["grant"])
    @commands.is_owner()
    async def adddonation(self, ctx, user: Union[discord.Member, discord.User, str], amount: float):
        try:
            # Resolve user
            if isinstance(user, (discord.Member, discord.User)):
                target = user
            else:
                user_id = int(user)
                target = ctx.guild.get_member(user_id) or await self.bot.fetch_user(user_id)

            donor_data = load_data(DONOR_FILE)
            user_id_str = str(target.id)
            donor_data[user_id_str] = donor_data.get(user_id_str, 0) + amount
            save_data(DONOR_FILE, donor_data)

            await ctx.send(
                f"<:Premium:1388586503092961482> Added **{amount:.2f}** credits to **{target.display_name}**'s donation total."
            )

        except Exception as e:
            await ctx.send(f"<:warning:1388586513000042516> Couldn't add donation: {e}")

    @adddonation.error
    async def adddonation_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("<:warning:1388586513000042516> You must name a user that exists and specify an amount, like `!grant @user 100`.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("<:warning:1388586513000042516> Invalid input. Make sure you're naming a valid user and the amount is a number.")

    @commands.command()
    async def burn(self, ctx, hours: float = 1, ram: int = 10):
        rate_per_gb_hour = 1.0  # Exaroton's current rate
        session_burn = round(rate_per_gb_hour * ram * hours, 2)
        daily_burn = round(rate_per_gb_hour * ram * 24, 2)
        weekly_burn = round(daily_burn * 7, 2)

        # Estimate runtime left based on current credit balance
        if ram > 0:
            response = requests.get("https://api.exaroton.com/v1/credits", headers={"Authorization": f"Bearer {EXAROTON_TOKEN}"})
            balance = response.json().get("credits", 0.0)
            hours_left = balance / (rate_per_gb_hour * ram)
            days_left = hours_left / 24
            lifespan = f"Estimated uptime left: **{hours_left:.1f}h** (~{days_left:.1f} days)"
        else:
            lifespan = "<:warning:1388586513000042516> Invalid RAM config for burn estimate."

        embed = discord.Embed(
            title="🔥 Obscura Burn Estimate",
            description=f"Using **{ram}GB RAM**...",
            color=0x83fefd
        )
        embed.add_field(name=f"Per {hours}h session", value=f"💸 **{session_burn} credits**", inline=False)
        embed.add_field(name="Per 24h/day (1 day)", value=f"🕒 **{daily_burn} credits**", inline=False)
        embed.add_field(name="Per 7d/week", value=f"📅 **{weekly_burn} credits**", inline=False)
        embed.add_field(name="Lifespan at current balance", value=lifespan, inline=False)
        embed.set_footer(text="For current server usage, try !burnrate")

        await ctx.send(embed=embed)

    @commands.command(name="burnrate", aliases=["burnstats", "projected"])
    async def burnrate(self, ctx):
        headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
        response = requests.get(f"https://api.exaroton.com/v1/servers/{EXAROTON_SERVER_ID}", headers=headers)

        if response.status_code != 200:
            await ctx.send("<:warning:1388586513000042516> Couldn't fetch server details.")
            return

        server = response.json()
        if server.get("creditsPerHour") is None:
            await ctx.send("<:warning:1388586513000042516> Server burn rate data is unavailable.")
            return

        rate = server["creditsPerHour"]
        balance = server.get("credits", 0.0)
        projected_hours = balance / rate if rate > 0 else 0

        embed = discord.Embed(
            title="🔥 Burn Rate & Projections",
            color=0xdb4437,
            description=(
                f"• Burn Rate: **{rate:.2f}** credits/hour\n"
                f"• Balance: **{balance:.2f}** credits\n"
                f"• Estimated Time Left: **{projected_hours:.2f} hours**"
            )
        )
        embed.set_footer(text="Based on current usage pattern")
        await ctx.send(embed=embed)

    @commands.command(name="setdonation", aliases=["setdono", "forceadd"])
    @commands.is_owner()
    async def set_donation(self, ctx, user: Union[discord.Member, discord.User, str], amount: float):
        try:
            if isinstance(user, (discord.Member, discord.User)):
                target = user
            else:
                user_id = int(user)
                target = ctx.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
    
            donor_data = load_data(DONOR_FILE)
            donor_data[str(target.id)] = amount
            save_data(DONOR_FILE, donor_data)

            # Safe rank calculation
            sorted_donors = sorted(donor_data.items(), key=lambda x: x[1], reverse=True)
            rank = next((i + 1 for i, (uid, amt) in enumerate(sorted_donors) if uid == str(target.id)), None)

            await ctx.send(f"✏️ Set **{target.display_name}**'s donation total to **{amount:.2f} credits**.")

            if rank:
                await ctx.send(f"👑 {target.display_name} is now ranked **#{rank}** on the donor leaderboard!")
        except Exception as e:
            await ctx.send(f"<:warning:1388586513000042516> Error setting donation: {e}")

            if ctx.guild:
                donor_role = interaction.guild.get_role(donor_role_id)
                if donor_role and isinstance(target, discord.Member):
                    if amount >= DONOR_ROLE_THRESHOLD and donor_role not in target.roles:
                        await target.add_roles(donor_role, reason="Donation threshold reached.")
                        await ctx.send(f"✨ {target.display_name} has been awarded the **{DONOR_ROLE_NAME}** role!")
                    elif amount < DONOR_ROLE_THRESHOLD and donor_role in target.roles:
                        await target.remove_roles(donor_role, reason="Donation dropped below threshold.")
                        await ctx.send(f"❌ {target.display_name} no longer qualifies for **{DONOR_ROLE_NAME}** role.")

    @commands.command(name="resetdono", aliases=["cleardono", "nukedono"])
    @commands.is_owner()
    async def reset_donation_soft(self, ctx, user: Union[discord.Member, discord.User, str]):
        try:
            if isinstance(user, (discord.Member, discord.User)):
                target = user
            else:
                user_id = int(user)
                target = ctx.guild.get_member(user_id) or await self.bot.fetch_user(user_id)

            async def confirmed(interaction, user_id, display_name):
                donor_data = load_data(DONOR_FILE)
                user_key = str(user_id)

                if user_key in donor_data:
                    # 🔥 Remove donor record
                    del donor_data[user_key]
                    save_data(DONOR_FILE, donor_data)

                    # 📎 Log the nuke
                    timestamp = datetime.utcnow().isoformat()
                    with open("data/donation_nukes.log", "a", encoding="utf-8") as f:
                        f.write(f"{timestamp} - Nuked: {display_name} (ID: {user_id}) by {interaction.user.id}\n")

                    # 🗼 Remove donor role if exists
                    donor_role = interaction.guild.get_role(DONOR_ROLE_ID)
                    member = interaction.guild.get_member(user_id)
                    if donor_role and member and donor_role in member.roles:
                        await member.remove_roles(donor_role, reason="Donation nuked.")
                        await interaction.followup.send(f"❌ {member.display_name}'s **Donor** role has been removed.")

                    await interaction.response.send_message(f"💥 Nuked **{display_name}** from donor records.")

                    # 📊 Track mod nuke count
                    nuke_stats = load_data("data/nuke_counts.json")
                    mod_id = str(interaction.user.id)
                    monthly_key = datetime.utcnow().strftime("%Y-%m")
                    if mod_id not in nuke_stats:
                        nuke_stats[mod_id] = {}
                    if monthly_key not in nuke_stats[mod_id]:
                        nuke_stats[mod_id][monthly_key] = 0
                    nuke_stats[mod_id][monthly_key] += 1
                    save_data("data/nuke_counts.json", nuke_stats)

                else:
                    await interaction.response.send_message("❌ That user has no recorded donations.")

            view = ConfirmNukeView(target.id, target.display_name, confirmed)
            await ctx.send(
                f"<:warning:1388586513000042516> Are you absolutely sure you want to **nuke** {target.mention} from the donor records?",
                view=view
            )
        except Exception as e:
            await ctx.send(f"<:warning:1388586513000042516> Error during nuke attempt: {e}")


    @commands.command(name="nukeboard")
    async def nukeboard(self, ctx, month: str = None):
        try:
            nuke_stats = load_data("data/nuke_counts.json")
            month_key = month or datetime.utcnow().strftime("%Y-%m")
            leaderboard = []

            for mod_id, months in nuke_stats.items():
                count = months.get(month_key, 0)
                if count > 0:
                    leaderboard.append((mod_id, count))

            if not leaderboard:
                await ctx.send(f"💪 No nukes recorded for {month_key}.")
                return

            leaderboard.sort(key=lambda x: x[1], reverse=True)
            embed = discord.Embed(
                title=f"💥 Top Nukers - {month_key}",
                color=discord.Color.red()
            )

            for i, (mod_id, count) in enumerate(leaderboard[:5], start=1):
                user = self.bot.get_user(int(mod_id)) or f"<@{mod_id}>"
                name = user.display_name if hasattr(user, 'display_name') else str(user)
                embed.add_field(name=f"{i}. {name}", value=f"{count} nukes", inline=False)

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"<:warning:1388586513000042516> Failed to show nukeboard: {e}")


    @commands.command(name="resetdono", aliases=["cleardono", "nukedono"])
    @commands.is_owner()
    async def reset_donation_soft(self, ctx, user: Union[discord.Member, discord.User, str]):
        try:
            if isinstance(user, (discord.Member, discord.User)):
                target = user
            else:
                user_id = int(user)
                target = ctx.guild.get_member(user_id) or await self.bot.fetch_user(user_id)

            async def confirmed(interaction, user_id, display_name):
                donor_data = load_data(DONOR_FILE)
                user_key = str(user_id)

                if user_key in donor_data:
                    # 🔥 Remove donor record
                    previous_amount = donor_data[user_key]
                    del donor_data[user_key]
                    save_data(DONOR_FILE, donor_data)

                    # 📅 Backup to graveyard
                    graveyard = load_data("data/donation_graveyard.json")
                    graveyard[user_key] = previous_amount
                    save_data("data/donation_graveyard.json", graveyard)

                    # 📉 Increment nuke count
                    nuke_tracker = load_data("data/nuke_counts.json")
                    mod_id = str(interaction.user.id)
                    nuke_tracker[mod_id] = nuke_tracker.get(mod_id, 0) + 1
                    save_data("data/nuke_counts.json", nuke_tracker)

                    # 📎 Log the nuke
                    with open("data/donation_nukes.log", "a", encoding="utf-8") as f:
                        f.write(f"{datetime.utcnow().isoformat()} - Nuked: {display_name} (ID: {user_id}) by {interaction.user}\n")

                    # 🗼 Remove donor role if exists
                    DONOR_ROLE_NAME = "💎 Donor"
                    donor_role = interaction.guild.get_role(DONOR_ROLE_ID)
                    member = interaction.guild.get_member(user_id)
                    if donor_role and member and donor_role in member.roles:
                        await member.remove_roles(donor_role, reason="Donation nuked.")
                        await interaction.followup.send(f"❌ {member.display_name}'s **{DONOR_ROLE_NAME}** role has been removed.")

                    await interaction.response.send_message(f"💥 Nuked **{display_name}** from donor records.")
                else:
                    await interaction.response.send_message("❌ That user has no recorded donations.")

            view = ConfirmNukeView(target.id, target.display_name, confirmed)
            await ctx.send(
                f"<:warning:1388586513000042516> Are you absolutely sure you want to **nuke** {target.mention} from the donor records?",
                view=view
            )
        except Exception as e:
            await ctx.send(f"<:warning:1388586513000042516> Error during nuke attempt: {e}")


    @commands.command(name="nd")
    @commands.is_owner()
    async def nukedono_button(self, ctx, user: Union[discord.Member, discord.User, str]):
        if isinstance(user, (discord.Member, discord.User)):
            target = user
        else:
            user_id = int(user)
            target = ctx.guild.get_member(user_id) or await self.bot.fetch_user(user_id)

        async def confirmed(interaction, user_id):
            donor_data = load_data(DONOR_FILE)
            user_key = str(user_id)
            if user_key in donor_data:
                del donor_data[user_key]
                save_data(DONOR_FILE, donor_data)
                await interaction.response.send_message(f"💥 Nuked **{target.display_name}** from donor records.")
            else:
                await interaction.response.send_message("❌ That user has no recorded donations.")

        view = ConfirmNukeView(target.id, confirmed)
        await ctx.send(
            f"<:warning:1388586513000042516> Are you *sure* you want to nuke **{target.display_name}** from donor records?",
            view=view
        )


    @commands.command(name="forgive", aliases=["undonuke", "resurrect"])
    @commands.is_owner()
    async def forgive(self, ctx, user: Union[discord.Member, discord.User, str]):
        try:
            if isinstance(user, (discord.Member, discord.User)):
                target = user
            else:
                user_id = int(user)
                target = ctx.guild.get_member(user_id) or await self.bot.fetch_user(user_id)

            user_id_str = str(target.id)
            graveyard = load_data("data/donation_graveyard.json")
            if user_id_str not in graveyard:
                await ctx.send("👻 No previous donation data found for this user.")
                return

            # 💾 Restore donation
            donor_data = load_data(DONOR_FILE)
            restored_amount = graveyard[user_id_str]
            donor_data[user_id_str] = restored_amount
            save_data(DONOR_FILE, donor_data)
            del graveyard[user_id_str]
            save_data("data/donation_graveyard.json", graveyard)

            # 🔄 Decrement mod nuke count
            nuke_tracker = load_data("data/nuke_counts.json")
            mod_id = str(ctx.author.id)
            if mod_id in nuke_tracker:
                nuke_tracker[mod_id] = max(0, nuke_tracker[mod_id] - 1)
                save_data("data/nuke_counts.json", nuke_tracker)

            # 🎖️ Restore donor role if present in guild
            donor_role = ctx.guild.get_role(DONOR_ROLE_ID)
            if donor_role and isinstance(target, discord.Member):
                await target.add_roles(donor_role, reason="Donation forgiven.")

            # 📜 Log the forgiveness
            with open("data/donation_forgiveness.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()} - Forgiven: {target.display_name} (ID: {target.id}) by {ctx.author}\n")

            modlog = self.bot.get_channel(MOD_LOG_CHANNEL_ID)
            if modlog:
                embed = discord.Embed(
                    title="🕊️ Donation Forgiven",
                    color=discord.Color.green()
                )
                embed.add_field(name="User", value=target.mention, inline=False)
                embed.add_field(name="Restored Amount", value=f"{restored_amount:.2f} credits", inline=True)
                embed.add_field(name="Forgiven By", value=ctx.author.mention, inline=False)
                embed.timestamp = datetime.utcnow()
                await modlog.send(embed=embed)

            await ctx.send(f"🕊️ Forgave **{target.display_name}** and restored their donation of **{restored_amount:.2f} credits**.")

        except Exception as e:
            await ctx.send(f"<:warning:1388586513000042516> Could not forgive: {e}")

    @commands.command(name="redemptionboard", aliases=["redemption", "forgiven", "redboard"])
    async def redemption_board(self, ctx, top: int = 5):
        log_file = "data/donation_forgiveness.log"
        if not os.path.exists(log_file):
            await ctx.send("📭 No redemption data yet!")
            return

        from collections import Counter
        user_counter = Counter()
        forgiver_counter = Counter()
        last_forgiver = {}

        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if "Forgave:" in line:
                    try:
                        parts = line.strip().split(" - ")
                        forgave_part = parts[1].split("Forgave: ")[1]
                        user_info, _, forgiver = forgave_part.partition(" by ")
                        display_name, user_id_part = user_info.strip().rsplit(" ", 1)
                        user_id = user_id_part.strip("()ID:")
                        user_counter[user_id] += 1
                        forgiver_counter[forgiver.strip()] += 1
                        last_forgiver[user_id] = forgiver.strip()
                    except Exception:
                        continue

        if not user_counter:
            await ctx.send("📭 No one has been forgiven yet.")
            return

        embed = discord.Embed(
            title="🕊️ Redemption Leaderboards",
            description="The most forgiven, and the most forgiving.",
            color=0x77dd77
        )

        embed.add_field(
            name="👑 Most Forgiven Users",
            value="\n".join([
                f"**{i+1}.** <@{uid}> — {count}x (by {last_forgiver.get(uid, 'Unknown')})"
                for i, (uid, count) in enumerate(user_counter.most_common(top))
            ]) or "None yet.",
            inline=False
        )

        embed.add_field(
            name="🧙 Top Forgivers",
            value="\n".join([
                f"**{i+1}.** {mod} — {count}x"
                for i, (mod, count) in enumerate(forgiver_counter.most_common(top))
            ]) or "None yet.",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(name="donocmds", aliases=["donorcommands", "donohelp"])
    async def list_dono_commands(self, ctx, *, flag: str = None):
        """Displays all donor-related commands. Use --dev to see internal tools."""
        is_dev = ctx.author.id in DEV_USER_IDS and flag == "--dev"

        public_cmds = [
            "`!dboard` — View the top donors leaderboard",
            "`!credits` — Check remaining server credits",
            "`!burn` — Estimate credit burn time for server usage",
            "`!burnrate` — Show real-time burn rate and credit lifespan",
            "`!forgive @user` — Resurrect a nuked donation (if any exists)",
            "`!nukeboard` — Leaderboard of who nuked the most donors",
            "`!nukeboard --month` — Top nukers this month",
            "`!nukeboard --user <mod>` — Show how many nukes a specific mod has triggered"
        ]

        dev_cmds = [
            "`!setdono @user <amount>` — Forcefully set a user's donation total",
            "`!add @user <amount>` — Add credits to a user's donation total",
            "`!resetdono @user` — Begin soft nuke (confirmation required)",
            "`!cleardono @user --confirm` — Instantly remove and log donation (no mercy)",
            "`!forgive @user` — Restore donation from graveyard, reinstate donor role",
            "`!nukeboard --user <mod>` — Shows how many nukes a mod has issued"
        ]

        embed = discord.Embed(
            title="<:Premium:1388586503092961482> Donor Command Index",
            description="Here are the available commands for donation tracking and server credit tools:",
            color=0x83fefd
        )

        for cmd in public_cmds:
            embed.add_field(name="⠀", value=cmd, inline=False)

        if is_dev:
            embed.add_field(name="🔧 Internal Developer Tools", value="These are only visible to verified devs:", inline=False)
            for cmd in dev_cmds:
                embed.add_field(name="⠀", value=cmd, inline=False)

        await ctx.send(embed=embed)


    @commands.command()
    @commands.is_owner()
    async def setpool(self, ctx, pool_code: str):
        pool_code_clean = pool_code.strip("#")
        save_json(POOL_FILE, {"pool": pool_code_clean})  # ✅ Persist to disk
        await ctx.send(f"<:checkbox:1388586497984430160> Credit pool code set to `{pool_code_clean}`.")

    @commands.command()
    async def debugpool(self, ctx):
        pool_data = load_json(POOL_FILE)
        await ctx.send(f"Debug pool file contents: `{pool_data}`")

    @commands.command()
    async def topup(self, ctx):
        user_id = ctx.author.id
        code = self.get_current_pool_code()

        if not code:
            await ctx.send("❌ No credit pool link set.")
            return

        embed = discord.Embed(
            title="💸 Top Up Server Credits",
            description="Use the button below to donate credits directly to the Obscura server!",
            color=0x3d5e8e
        )
        embed.set_footer(text="Credits help us stay online and expand RAM!")

        view = ServerControlView(code)  # This already exists in your cog
        await ctx.send(embed=embed, view=view)

        
    @commands.command(name="up", aliases=["termup"])
    @commands.cooldown(2, 300, BucketType.guild)
    async def server_uptime(self, ctx):
        if ctx.author.id not in DEV_USER_ID:
            await ctx.send("🚫 You don't have permission to use this command.")
            return

        await ctx.typing()

        headers = {"Authorization": f"Bearer {EXAROTON_TOKEN}"}
        url = f"https://api.exaroton.com/v1/servers/{EXAROTON_SERVER_ID}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception(f"API status {response.status_code}")
            data = response.json()
        except Exception as e:
            print(f"[Uptime Fetch Error]: {e}")
            await ctx.send("❌ Could not retrieve server uptime.")
            return

        time_started = data.get("timeStarted")
        if not time_started:
            await ctx.send("<:warning:1388586513000042516> Server is not online or uptime not available.")
            return

        try:
            started_dt = datetime.fromisoformat(time_started.replace("Z", "+00:00"))
            now = datetime.utcnow()
            uptime = now - started_dt
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
        except Exception as e:
            print(f"[Uptime Parsing Error]: {e}")
            await ctx.send("<:warning:1388586513000042516> Something went wrong calculating uptime.")
            return

        await ctx.send(f"🕓 **Obscura** has been online for **{hours}h {minutes}m**.")


    async def handle_cooldown(self, ctx):
        bucket = commands.CooldownMapping.from_cooldown(1, 60, commands.BucketType.user).get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            await ctx.send(f"🕒 Slow down! Try again in `{int(retry_after)}s`.")
            return True
        return False

    @commands.command(name="players", aliases=["who"])
    async def server_players(self, ctx):
        if await self.handle_cooldown(ctx):
            return

        await ctx.typing()
        motd, players, online, status_text, max_players, source = await self.fetch_server_status()

        embed = discord.Embed(
            title="Online Players",
            description="Nobody online." if not players else ", ".join(players),
            color=discord.Color.green() if online else discord.Color.red()
        )
        embed.add_field(name="MOTD", value=f"`{motd}`", inline=False)
        embed.set_footer(text=f"Pulled via {source} {'(fallback)' if source != 'mcstatus' else '(primary)'}")
        await ctx.send(embed=embed)


    @commands.command()
    async def donate(self, ctx):
        """Show donation embed if user has the proper role."""
        if donor_role_id not in [role.id for role in ctx.author.roles]:
            await ctx.send("🚫 You don't have permission to access the donation panel.")
            return

        code = self.get_current_pool_code()
        if not code:
            await ctx.send("❌ No credit pool link set.")
            return

        embed = discord.Embed(
            title="💸 Donate Server Credits",
            description="Thank you for supporting the server! Use the button below to add credits directly.",
            color=0x83fefd
        )
        embed.set_footer(text="Credits go into uptime & more RAM for all of us 😌")
        view = ServerControlView(code)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="help_exaroton", aliases=["exahelp"])
    async def help_exaroton(self, ctx):
        if ctx.author.id not in EXAROTON_TRUSTED:
            await ctx.send("🚫 You’re not allowed to view this command list.")
            return

        embed = discord.Embed(
            title="Obscura MC Commands",
            description="Commands for managing and supporting the Obscura server.",
            color=0x83fefd
        )

        embed.add_field(
            name="💰 Credit Management",
            value="`!credits` — View credit balance\n"
                "`!setcredits <amount>` — Set balance (owner only)",
            inline=False
        )

        embed.add_field(
            name="🔥 Burn Estimate",
            value="`!burn <hours> <ram>` — Estimate burn cost for server usage (e.g. `!burn 3 10`)",
            inline=False
        )

        embed.add_field(
            name="💸 Credit Pool",
            value="`!setpool <code>` — Save donation pool code (owner only)\n"
                "`!topup` — Send button to donate credits",
            inline=False
        )

        embed.add_field(
            name="<:noentry:1388586500756865126> Status Pings",
            value="Server alerts for online/offline run every 3 hours.\nNo command needed.",
            inline=False
        )

        embed.set_footer(text="Only trusted users can see this.")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ExarotonCog(bot))
    bot.add_view(StatusButtonView())
