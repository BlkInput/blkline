import discord
from discord.ext import commands, tasks
import json
import time
import os
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


LINK_FILE = "data/mc_links.json"
TIME_FILE = "data/mc_time.json"
POOL_FILE = "data/exaroton_pool.json"
PLAYTIME_FILE = "data/playtime_rewards.json"
REWARD_HISTORY_FILE = "data/reward_history.json"
DEV_USER_ID = [448896936481652777, 777345438495277076]
COOLDOWN_SECONDS = 60
cooldowns = {}
MC_LOG_CHANNEL_ID = 1390936792567382089

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def get_rendered_page(url):
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(5)
        return driver.page_source
    finally:
        driver.quit()

class RewardsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_playtime.start()
        pool_data = load_json(POOL_FILE)
        self.credit_pool_code = load_json(POOL_FILE).get("pool")
        print(f"[INIT] Loaded pool code: {self.credit_pool_code}")
        print("[REWARDS] RewardsCog loaded.")

    def cog_unload(self):
        self.check_playtime.cancel()


    # -- Simulated Playtime Tracker --
    @tasks.loop(minutes=5)
    async def check_playtime(self):
        online_players = ["BlkLine", "GhostFrame", "Toast"]  # Replace with real data pull when Exaroton key is in
        now = datetime.utcnow()

        data = load_json(PLAYTIME_FILE)
        for player in online_players:
            if player not in data:
                data[player] = {
                    "total_minutes": 0,
                    "last_seen": now.isoformat()
                }
            else:
                last_seen = datetime.fromisoformat(data[player]["last_seen"])
                elapsed = int((now - last_seen).total_seconds() / 60)
                data[player]["total_minutes"] += elapsed
                data[player]["last_seen"] = now.isoformat()

        save_json(PLAYTIME_FILE, data)

    @commands.command(name="forcecheck")
    async def forcecheck(self, ctx):
        if ctx.author.id not in DEV_USER_ID:
            return await ctx.send("🚫 Only devs can run dry checks.")
        await self.check_playtime()
        await ctx.send("✅ Playtime updated manually.")

    @commands.command(name="forcecheckdry", aliases=["drycheck", "dryrun", "fdd"])
    async def forcecheckdry(self, ctx):
        """Dry run playtime update — shows projected gains and new totals, sorted by time added."""
        if ctx.author.id not in DEV_USER_ID:
            return await ctx.send("🚫 Only devs can run dry checks.")
    
        online_players = get_online_players()
        if not online_players:
            return await ctx.send("<:beebo:1383282292478312519> No players online to check.")
    
        now = datetime.utcnow()
        data = load_json(PLAYTIME_FILE)
        results = []
    
        for player in online_players:
            if player not in data:
                results.append({
                    "name": player,
                    "gain": 0,
                    "new_total": 0,
                    "note": "🆕 Would be added fresh."
                })
            else:
                last_seen = datetime.fromisoformat(data[player]["last_seen"])
                elapsed = int((now - last_seen).total_seconds() / 60)
                if elapsed > 0:
                    new_total = data[player]["total_minutes"] + elapsed
                    results.append({
                        "name": player,
                        "gain": elapsed,
                        "new_total": new_total,
                        "note": f"⏱️ +**{elapsed} min** ({elapsed//60}h {elapsed%60}m), total: **{new_total//60}h {new_total%60}m**"
                    })
                else:
                    results.append({
                        "name": player,
                        "gain": 0,
                        "new_total": data[player]["total_minutes"],
                        "note": "🕒 Already up to date."
                    })
    
        results.sort(key=lambda x: x["gain"], reverse=True)
        results = results[:10]  # Limit to top 10 for Discord embed safety
    
        embed = discord.Embed(
            title="<:beebo_:1383281762385531081> Dry Run — Playtime Update Preview",
            color=discord.Color.purple()
        )
    
        for r in results:
            embed.add_field(
                name=f"🧍 {r['name']}",
                value=r["note"],
                inline=False
            )
    
        embed.set_footer(text="This is a preview. No data was saved.")
        await ctx.send(embed=embed)
    @commands.command(name="playtime", aliases=["mctime", "timeplayed"])
    async def playtime(self, ctx, player_name: str = None):
        data = load_json(PLAYTIME_FILE)
        player_name = player_name or ctx.author.display_name
        stats = data.get(player_name)

        if not stats:
            await ctx.send(f"⏳ No playtime tracked yet for `{player_name}`.")
            return

        total = stats["total_minutes"]
        hours = total // 60
        minutes = total % 60
        await ctx.send(f"🕹️ `{player_name}` has played for **{hours}h {minutes}m**.")

    @commands.command(name="topplaytime", aliases=["leaderboard", "tophours"])
    async def topplaytime(self, ctx):
        data = load_json(PLAYTIME_FILE)
        if not data:
            await ctx.send("🏜️ No playtime data available yet.")
            return

        top = sorted(data.items(), key=lambda x: x[1]["total_minutes"], reverse=True)[:5]
        embed = discord.Embed(title="🏆 Top Playtime", color=0x462f80)
        for i, (name, stats) in enumerate(top, start=1):
            total = stats["total_minutes"]
            hours = total // 60
            minutes = total % 60
            embed.add_field(name=f"#{i}: {name}", value=f"{hours}h {minutes}m", inline=False)

        await ctx.send(embed=embed)


    @commands.command(name="unlinkmc")
    async def unlinkmc(self, ctx):
        links = load_json(LINK_FILE)
        user_id = str(ctx.author.id)
        if user_id in links:
            del links[user_id]
            save_json(LINK_FILE, links)
            await ctx.send("❎ Your Minecraft link has been removed.")
        else:
            await ctx.send("<:warning:1388586513000042516> You don't have a Minecraft account linked.")

    @commands.command(name="rewardhistory")
    async def rewardhistory(self, ctx):
        history = load_json(REWARD_HISTORY_FILE)
        user_id = str(ctx.author.id)
        entries = history.get(user_id, [])
        if not entries:
            await ctx.send("📭 No reward history found.")
            return

        embed = discord.Embed(title="🎁 Reward History", color=0x462f80)
        for entry in entries[-5:]:
            embed.add_field(name=entry["reward"], value=f"<t:{entry['timestamp']}:R>", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="checkuuid")
    async def checkuuid(self, ctx, mc_username: str):
        url = f"https://api.mojang.com/users/profiles/minecraft/{mc_username}"
        response = requests.get(url)
        if response.status_code != 200:
            await ctx.send(f"❌ No player found with name `{mc_username}`.")
            return

        data = response.json()
        formatted_uuid = f"{data['id'][:8]}-{data['id'][8:12]}-{data['id'][12:16]}-{data['id'][16:20]}-{data['id'][20:]}"
        await ctx.send(f"🆔 UUID for `{mc_username}` is `{formatted_uuid}`.")

    @commands.command(name="pooladd")
    @commands.has_permissions(administrator=True)
    async def pooladd(self, ctx, amount: float):
        print(f"[POOLADD] Triggered by {ctx.author} from instance id: {id(self)}")
        pool = load_json(POOL_FILE)
        pool["credits"] = pool.get("credits", 0.0) + amount
        save_json(POOL_FILE, pool)
        await ctx.send(f"💸 Added **{amount:.2f}** credits. New pool balance: **{pool['credits']:.2f}**")

    @commands.command(name="linkmc", aliases=["uuidlink", "setuuid"])
    async def linkmc(self, ctx, mc_username: str):
        user_id = ctx.author.id
        now = time.time()
    
        # Cooldown check for non-devs
        if user_id not in DEV_USER_ID:
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
            cooldowns[user_id] = now  # update
    
        # Mojang UUID request
        url = f"https://api.mojang.com/users/profiles/minecraft/{mc_username}"
        response = requests.get(url)
    
        if response.status_code != 200:
            await ctx.send(f"❌ Could not find Minecraft user `{mc_username}`.")
            return
    
        data = response.json()
        uuid = data["id"]
        formatted_uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
    
        links = load_json(LINK_FILE)
    
        # Check if MC username already linked or flagged
        for linked_id, entry in links.items():
            if entry.get("username", "").lower() == mc_username.lower():
                await ctx.send("❌ That Minecraft username is already claimed or under review by another Discord account.")
    
                # Optional logging
                log_channel = self.bot.get_channel(MC_LOG_CHANNEL_ID)
                if log_channel:
                    embed = discord.Embed(title="<:warning:1388586513000042516> Link Attempt Blocked", color=discord.Color.red())
                    embed.add_field(name="Attempted Username", value=mc_username)
                    embed.add_field(name="By", value=f"{ctx.author} ({ctx.author.id})", inline=False)
                    embed.timestamp = datetime.utcnow()
                    await log_channel.send(embed=embed)
                return
    
        # Flag as unverified until manually approved
        links[str(user_id)] = {
            "username": mc_username,
            "uuid": uuid,
            "verified": False,
            "link_channel": ctx.channel.id
        }
        save_json(LINK_FILE, links)
    
        await ctx.send(f"📝 Your account has been linked to **{mc_username}** and is pending verification.")
    
        # Log to dev channel
        log_channel = self.bot.get_channel(MC_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="📝 New Link Request (Pending)",
                color=discord.Color.blurple()
            )
            embed.add_field(name="User", value=f"{ctx.author} ({ctx.author.mention})", inline=False)
            embed.add_field(name="MC Username", value=mc_username, inline=True)
            embed.add_field(name="UUID", value=f"`{formatted_uuid}`", inline=False)
            embed.add_field(name="Status", value="Pending verification", inline=True)
            embed.set_footer(text=f"Submitted in #{ctx.channel}", icon_url=ctx.author.display_avatar.url)
            embed.timestamp = datetime.utcnow()
            await log_channel.send(embed=embed)

    @commands.command(name="verify", aliases=["appuser", "mcverify", "mcv"])
    async def verify_user(self, ctx, member: discord.Member):
        """Dev-only: Verify a pending Minecraft link request."""
        if ctx.author.id not in DEV_USER_ID:
            await ctx.send("🚫 You don’t have permission to do this.")
            return
    
        links = load_json(LINK_FILE)
        user_id = str(member.id)
    
        if user_id not in links:
            await ctx.send("❌ That user has no linked Minecraft account.")
            return
    
        if links[user_id].get("verified", False):
            await ctx.send("<:checkbox:1388586497984430160> This user is already verified.")
            return
    
        links[user_id]["verified"] = True
        save_json(LINK_FILE, links)
        # Ping the user in the channel where they linked (if possible)
        channel_id = links[user_id].get("link_channel")
        link_channel = self.bot.get_channel(channel_id) if channel_id else None

        if link_channel:
            await link_channel.send(
                f"<:checkbox:1388586497984430160> {member.mention}, your Minecraft account has been verified! You’re all set to play. 🎮🧱"
            )
        else:
            await ctx.send(f"<:checkbox:1388586497984430160> {member.mention} has been verified, but I couldn't find the original link channel to ping them.")

        # 🧼 Clean up the link_channel from their record — no longer needed
        links[user_id].pop("link_channel", None)
        save_json(LINK_FILE, links)
    
        await ctx.send(f"<:checkbox:1388586497984430160> Verified **{member.display_name}**'s Minecraft link.")
    
        log_channel = self.bot.get_channel(MC_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🔓 MC Link Verified",
                color=discord.Color.green()
            )
            embed.add_field(name="Verified By", value=ctx.author.mention, inline=False)
            embed.add_field(name="User", value=member.mention, inline=False)
            embed.add_field(name="Minecraft Username", value=links[user_id].get("username", "N/A"), inline=True)
            embed.add_field(name="UUID", value=links[user_id].get("uuid", "N/A"), inline=False)
            embed.set_footer(text="Manual verification complete")
            embed.timestamp = datetime.utcnow()
            await log_channel.send(embed=embed)

    @commands.command(name="unvuser", aliases=["rejuser", "revoke"])
    async def unverify_user(self, ctx, member: discord.Member):
        """Dev-only: Fully remove a user's MC link and verification."""
        if ctx.author.id not in DEV_USER_ID:
            await ctx.send("🚫 You don’t have permission to do this.")
            return
    
        links = load_json(LINK_FILE)
        user_id = str(member.id)
    
        if user_id not in links:
            await ctx.send("❌ That user has no linked Minecraft account.")
            return
    
        removed_entry = links.pop(user_id)
        save_json(LINK_FILE, links)
    
        await ctx.send(f"🗑️ Removed Minecraft link for **{member.display_name}**.")
    
        log_channel = self.bot.get_channel(MC_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🗑️ MC Link Deleted",
                color=discord.Color.red()
            )
            embed.add_field(name="Deleted By", value=ctx.author.mention, inline=False)
            embed.add_field(name="User", value=member.mention, inline=False)
            embed.add_field(name="MC Username", value=removed_entry.get("username", "N/A"), inline=True)
            embed.add_field(name="UUID", value=removed_entry.get("uuid", "N/A"), inline=False)
            embed.set_footer(text="Link forcibly removed")
            embed.timestamp = datetime.utcnow()
            await log_channel.send(embed=embed)

    @commands.command(name="forceunlink", aliases=["unlinkid", "unlinkuser"])
    async def force_unlink(self, ctx, mc_username: str):
        """Dev-only: Unlink a Minecraft username from any Discord account."""
        if ctx.author.id not in DEV_USER_ID:
            await ctx.send("🚫 You don’t have permission to do this.")
            return
    
        links = load_json(LINK_FILE)
        target_id = None
        for uid, entry in links.items():
            if entry.get("username", "").lower() == mc_username.lower():
                target_id = uid
                break
    
        if not target_id:
            await ctx.send(f"❌ No Discord account is linked to `{mc_username}`.")
            return
    
        removed = links.pop(target_id)
        save_json(LINK_FILE, links)
    
        await ctx.send(f"💥 Force-unlinked `{mc_username}` from <@{target_id}>.")
    
        log_channel = self.bot.get_channel(MC_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="💥 Minecraft Username Force-Unlinked",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(name="Minecraft Username", value=mc_username, inline=True)
            embed.add_field(name="UUID", value=removed.get("uuid", "N/A"), inline=False)
            embed.add_field(name="Former Discord ID", value=f"<@{target_id}>", inline=False)
            embed.set_footer(text="Forced unlink")
            embed.timestamp = datetime.utcnow()
            await log_channel.send(embed=embed)


    @commands.command(name="devlinkmc")
    async def devlinkmc(self, ctx, member: discord.Member, mc_username: str):
        if ctx.author.id not in DEV_USER_ID:
            await ctx.send("🚫 You don’t have permission to use this.")
            return

        url = f"https://api.mojang.com/users/profiles/minecraft/{mc_username}"
        response = requests.get(url)
        if response.status_code != 200:
            await ctx.send(f"❌ Minecraft user `{mc_username}` not found.")
            return

        raw = response.json()["id"]
        formatted_uuid = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
        links = load_json(LINK_FILE)
        links[str(member.id)] = {
            "username": mc_username,
            "uuid": raw
        }
        save_json(LINK_FILE, links)

        await ctx.send(f"🔧 Linked **{member.display_name}** to **{mc_username}**.")
        log_channel = self.bot.get_channel(MC_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="🔐 Dev Linked MC", color=discord.Color.gold())
            embed.add_field(name="Dev", value=ctx.author.mention, inline=False)
            embed.add_field(name="Target User", value=member.mention, inline=False)
            embed.add_field(name="MC Username", value=mc_username, inline=False)
            embed.add_field(name="UUID", value=formatted_uuid, inline=False)
            embed.set_footer(text="Manual link action")
            await log_channel.send(embed=embed)

    # -- Pool Credits Check --
    @commands.command(name="credpool", aliases=["creditpool", "donorpool"])
    async def show_cached_credits(self, ctx):
        pool_code = getattr(self, "credit_pool_code", None) or load_json(POOL_FILE).get("pool")
        if not pool_code:
            await ctx.send("<:warning:1388586513000042516> No pool code has been set. Use `!setpool <code>`.")
            return

        try:
            url = f"https://exaroton.com/pools/{pool_code}"
            headers = {"User-Agent": "Mozilla/5.0"}
            html = requests.get(url, headers=headers).text
            soup = BeautifulSoup(html, "html.parser")
            credit_element = soup.find("div", class_="credits")

            if not credit_element:
                raise ValueError("Could not find credit balance on the page.")

            credits = float(credit_element.text.strip().replace("credits", "").strip())

            if credits is None:
                raise ValueError("Missing 'credits' key")

            await ctx.send(f"💰 Current server credit pool balance: **{credits:.2f}** credits.")
        except Exception as e:
            await ctx.send(f"<:warning:1388586513000042516> Failed to fetch pool info: {e}")

    @commands.command(name="poolcached", aliases=["pooloffline", "poolbackup"])
    async def cached_pool(self, ctx):
        """Show the last saved pool balance from local JSON."""
        pool_data = load_json(POOL_FILE)
        credits = pool_data.get("credits", None)
        if credits is None:
            await ctx.send("📂 No cached credit balance found.")
        else:
            await ctx.send(f"📦 Cached pool balance: **{credits:.2f}** credits.")

    @commands.command(name="poolcheck")
    async def poolcheck(self, ctx):
        """Compare memory vs file pool code, and check live vs cached balance."""
        embed = discord.Embed(title="<:report:1388586505693302968> Pool Check Diagnostic", color=0x00bfa5)

        # Step 1: Check memory
        memory_code = getattr(self, "credit_pool_code", None)
        embed.add_field(name="Memory Pool Code", value=f"`{memory_code}`" if memory_code else "❌ None", inline=True)

        # Step 2: Check file
        try:
            file_data = load_json(POOL_FILE)
            file_code = file_data.get("pool")
            cached_credits = file_data.get("credits")
            embed.add_field(name="File Pool Code", value=f"`{file_code}`" if file_code else "❌ None", inline=True)
        except Exception as e:
            embed.add_field(name="File Read Error", value=f"❌ `{e}`", inline=False)
            return await ctx.send(embed=embed)

        # Step 3: Choose a pool code
        pool_code = memory_code or file_code
        if not pool_code:
            embed.color = 0xff0000
            embed.description = "🚫 No pool code set in memory or file.\nUse `!setpool <code>` to initialize."
            return await ctx.send(embed=embed)

        # Step 4: Fetch and parse Exaroton pool page
        try:
            html = get_rendered_page(f"https://exaroton.com/pools/{pool_code}")


            # DEBUG: Save the full page to inspect
            with open("exaroton_pool_debug.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("[DEBUG] HTML Selenium saved")

            soup = BeautifulSoup(html, "html.parser")
            credit_element = soup.find("div", class_="credits")

            if not credit_element:
                raise ValueError("Could not find credit balance on the page.")

            live_credits = float(credit_element.text.strip().replace("credits", "").strip())
            embed.add_field(name="Live Balance", value=f"💳 **{live_credits:.2f}** credits", inline=True)

            if cached_credits is not None:
                diff = round(live_credits - cached_credits, 2)
                status = "📈 Increased" if diff > 0 else "📉 Decreased" if diff < 0 else "⏸ No Change"
                embed.add_field(name="Cached Balance", value=f"🗃️ {cached_credits:.2f} credits", inline=True)
                embed.add_field(name="Δ Change", value=f"`{diff:+.2f}` ({status})", inline=False)
            else:
                embed.set_footer(text="No cached balance to compare.")

            # 🔄 Update local file
            file_data["credits"] = live_credits
            save_json(POOL_FILE, file_data)

        except Exception as e:
            embed.add_field(name="Live Fetch Error", value=f"❌ `{e}`", inline=False)
            embed.color = 0xff9900

        finally:
            driver.quit()

        await ctx.send(embed=embed)



async def setup(bot):
    await bot.add_cog(RewardsCog(bot))
