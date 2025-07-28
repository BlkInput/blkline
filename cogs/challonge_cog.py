import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
import aiohttp, os, json
from cogs.utils import UtilsCog
import challonge


MAP_FILE = "data/tourney_map.json"
SCORE_FILE = "data/tourney_scores.json"
ELO_FILE = "data/elo_scores.json"
MATCH_HISTORY_FILE = "data/match_history.json"
ARCHIVE_FILE = "data/archived_slugs.json"
ALERT_CACHE = "data/alerted_matches.json"
OPTOUT_FILE = "data/match_ping_optouts.json"
LOG_CHANNEL_ID = 1390938867128860692
PLAYER_MAP_FILE = "data/player_map.json"

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_player_map():
    if not os.path.exists(PLAYER_MAP_FILE):
        return {}
    with open(PLAYER_MAP_FILE, "r") as f:
        return json.load(f)

def save_player_map(data):
    os.makedirs(os.path.dirname(PLAYER_MAP_FILE), exist_ok=True)
    with open(PLAYER_MAP_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_participants(self, slug):
    url = f"https://api.challonge.com/v1/tournaments/{slug}/participants.json"
    params = {"api_key": CHALLONGE_API_KEY}
    res = requests.get(url, params=params)
    res.raise_for_status()
    return res.json()

class ChallongeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("CHALLONGE_API_KEY")
        self.username = os.getenv("CHALLONGE_USERNAME")
        self.base_url = "https://api.challonge.com/v1"
        self.active_tournament_slug = None
        self.participant_map = {}
        self.match_alerts.start()

    def cog_unload(self):
        self.match_alerts.cancel()

    def auth(self):
        return aiohttp.BasicAuth(self.username, self.api_key)

    async def request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}/{endpoint}.json"
        async with aiohttp.ClientSession(auth=self.auth()) as session:
            async with session.request(method, url, **kwargs) as resp:
                try:
                    return await resp.json(), resp.status
                except:
                    return {"error": "Invalid response"}, resp.status

    @commands.command(aliases=["mh"])
    async def match_history(self, ctx, slug: str, member: discord.Member = None):
        uid = str((member or ctx.author).id)
        history = load_json(MATCH_HISTORY_FILE).get(slug, {}).get(uid, [])

        if not history:
            await ctx.send("No match history found.")
            return

        embed = discord.Embed(
            title=f"📜 Match History for {(member or ctx.author).display_name} in {slug}",
            color=0x00bfff
        )

        for i, entry in enumerate(history[-10:], start=1):
            opponent_id = int(entry["opponent"])
            opponent = ctx.guild.get_member(opponent_id)
            opponent_display = opponent.mention if opponent else f"<@{entry['opponent']}>"

            result = entry["result"]
            match_id = entry["match_id"]
            emoji = "🥇" if result == "Win" else "❌"

            embed.add_field(
                name=f"{i}.",
                value=f"{emoji} vs {opponent_display}\nResult: **{result}** | Match ID: `{match_id}`",
                inline=False
            )

        await ctx.send(embed=embed)


    @commands.command()
    async def elo(self, ctx, member: discord.Member = None):
        uid = str((member or ctx.author).id)
        scores = load_json(ELO_FILE)
        elo = scores.get(uid, 1000)
        await ctx.send(f"📈 ELO for {member.display_name if member else ctx.author.display_name}: **{elo}** <:settings:1388586507664883772>")

    def update_elo(self, winner_id, loser_id, k=32):
        scores = load_json(ELO_FILE)
        winner = scores.get(winner_id, 1000)
        loser = scores.get(loser_id, 1000)
        expected_win = 1 / (1 + 10 ** ((loser - winner) / 400))
        expected_lose = 1 - expected_win
        scores[winner_id] = round(winner + k * (1 - expected_win))
        scores[loser_id] = round(loser + k * (0 - expected_lose))
        save_json(ELO_FILE, scores)

    def log_match(self, slug, winner_id, loser_id, match_id):
        history = load_json(MATCH_HISTORY_FILE)
        history.setdefault(slug, {}).setdefault(winner_id, []).append({
            "match_id": match_id,
            "opponent": loser_id,
            "result": "Win"
        })
        history.setdefault(slug, {}).setdefault(loser_id, []).append({
            "match_id": match_id,
            "opponent": winner_id,
            "result": "Loss"
        })
        save_json(MATCH_HISTORY_FILE, history)

    @commands.command()
    async def standings(self, ctx):
        scores = load_json(ELO_FILE)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
        embed = discord.Embed(title="📊 Global ELO Standings", color=0xffcc00)
        for rank, (uid, elo) in enumerate(sorted_scores[:20], start=1):
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f"<@{uid}>"
            embed.add_field(name=f"{rank}. {name}", value=f"ELO: **{elo}**", inline=False)
    
        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def set_elo(self, ctx, member: discord.Member, new_score: int):
        scores = load_json(ELO_FILE)
        scores[str(member.id)] = new_score
        save_json(ELO_FILE, scores)
        await ctx.send(f"📌 Set ELO of {member.display_name} to **{new_score}**.")
        

    @commands.command(aliases=["unslug", "forgetslug", "purge_slug"])
    @commands.is_owner()
    async def remove_slug(self, ctx, slug: str):
        """Safely archive and purge a tournament slug (with confirmation)."""
        tourney_map = load_json(MAP_FILE)
        match_history = load_json(MATCH_HISTORY_FILE)
        elo_scores = load_json(ELO_FILE)
        archive = load_json(ARCHIVE_FILE)
    
        if slug not in tourney_map:
            await ctx.send(f"❌ `{slug}` isn’t currently tracked.")
            return
    
        # Button confirmation UI
        class ConfirmView(View):
            def __init__(self):
                super().__init__(timeout=15)
                self.confirmed = False
    
            @discord.ui.button(label="Yes, purge it", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: Button):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("Not your nuke to launch. 🧨", ephemeral=True)
                    return
                self.confirmed = True
                await interaction.response.edit_message(content="⏳ Purging in progress...", view=None)
                self.stop()
    
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                await interaction.response.edit_message(content="❌ Purge cancelled. Slug is safe.", view=None)
                self.stop()
    
        view = ConfirmView()
        await ctx.send(
            f"⚠️ Are you **sure** you want to purge `{slug}`?\nThis will:\n"
            "- Remove it from tracking\n"
            "- Archive it safely\n"
            "- Wipe related match history\n"
            "- Clean ELO entries for involved users\n\nChoose wisely.",
            view=view
        )
    
        await view.wait()
    
        if not view.confirmed:
            return  # User canceled or timed out
    
        # Archive the slug and its player map
        archive[slug] = tourney_map[slug]
        save_json(ARCHIVE_FILE, archive)
    
        # Delete from MAP_FILE
        del tourney_map[slug]
        save_json(MAP_FILE, tourney_map)
    
        # Delete match history
        if slug in match_history:
            del match_history[slug]
            save_json(MATCH_HISTORY_FILE, match_history)
    
        # Clean up ELO scores
        for uid in archive[slug].keys():
            elo_scores.pop(uid, None)
        save_json(ELO_FILE, elo_scores)
    
        await ctx.send(f"✅ `{slug}` has been **purged and archived**. No longer tracked. 🪦")

    @commands.command(aliases=["sm"])
    async def sync_matches(self, ctx, slug: str):
        await self.alert_matches(ctx.guild, slug)
        await ctx.send(f"✅ Match alerts manually synced for `{slug}`.")

    @commands.command(name="set_active_slug", aliases=["sas", "s_active"])
    @commands.is_owner()
    async def set_active_slug(self, ctx, slug: str):
        """Force-set the active tournament slug (DEV ONLY)"""
        self.active_tournament_slug = slug
        await ctx.send(f"<:checkbox:1388586497984430160> Active slug manually set to `{slug}`.")

    @commands.command()
    async def register(self, ctx, slug: str):
        """Link your Discord account to a Challonge participant in the tournament."""
        uid = str(ctx.author.id)
        tourney_map = load_json(MAP_FILE)

        # Get all participants
        data, status = await self.request("GET", f"tournaments/{slug}/participants")
        if status != 200:
            await ctx.send(f"❌ Failed to fetch participants: {data.get('errors') or data}")
            return

        # Try to match by Discord name or nickname
        display_name = ctx.author.display_name.lower()
        matches = []
        for p in data:
            name = p["participant"]["name"].lower()
            if display_name in name or name in display_name:
                matches.append(p["participant"])

        if not matches:
            await ctx.send("❌ No likely participant matches found for your name. Ask an admin to add you manually. <:settings:1388586507664883772>")
            return
        if len(matches) > 1:
            names = ", ".join(p["name"] for p in matches)
            await ctx.send(f"⚠️ Multiple potential matches found: {names}. Be more specific or ask an admin. <:settings:1388586507664883772>")
            return

        participant_id = str(matches[0]["id"])
        tourney_map.setdefault(slug, {})[uid] = participant_id
        print("Updated tourney_map:", tourney_map)
        print("Saving to:", MAP_FILE)

        save_json(MAP_FILE, tourney_map)

        await ctx.send(f"✅ You’ve been registered to `{slug}` as `{matches[0]['name']}` (ID: {participant_id})! <:Premium:1388586503092961482>")


    @commands.command(aliases=["slugs", "tlist"])
    async def list_slugs(self, ctx):
        file_path = "data/tracked_slugs.json"
        if not os.path.exists(file_path):
            await ctx.send("🗂️ No tournaments found.")
            return
    
        with open(file_path, "r") as f:
            data = json.load(f)
    
        tournaments = data.get("tournaments", [])
        if not tournaments:
            await ctx.send("🗂️ No tournaments found.")
            return
    
        embed = discord.Embed(title="📋 Tracked Tournament Slugs", color=0x5865f2)
        for slug in tournaments:
            embed.add_field(name=slug, value="👥 Not yet mapped to players", inline=False)
    
        await ctx.send(embed=embed)

    @commands.command(name="track_slug")
    @commands.has_permissions(administrator=True)
    async def track_slug(self, ctx, slug: str):
        """Track a new Challonge tournament slug and set it as active."""
        file_path = "data/tracked_slugs.json"
    
        # Load existing tracked slugs
        if not os.path.exists(file_path):
            data = {"tournaments": []}
        else:
            with open(file_path, "r") as f:
                data = json.load(f)
    
        slug = slug.lower()
    
        # Add slug if not already tracked
        if slug in data["tournaments"]:
            await ctx.send(f"⚠️ Slug `{slug}` is already being tracked.")
        else:
            data["tournaments"].append(slug)
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            await ctx.send(f"<:checkbox:1388586497984430160> Now tracking tournament slug: `{slug}`.")
    
        # ✅ Set as active for bot session
        self.active_tournament_slug = slug
        print(f"[Challonge] Active tournament set to: {slug}")

    @tasks.loop(minutes=10)
    async def match_alerts(self):
        for guild in self.bot.guilds:
            for slug in load_json(MAP_FILE):
                await self.alert_matches(guild, slug)


    async def alert_matches(self, guild, slug):
        tourney_map = load_json(MAP_FILE)
        alert_cache = load_json(ALERT_CACHE)
        optouts = load_json(OPTOUT_FILE)
        if slug not in tourney_map:
            return

        tdata, status = await self.request("GET", f"tournaments/{slug}")
        if status != 200 or tdata["tournament"]["state"] != "underway":
            return

        matches_data, status = await self.request("GET", f"tournaments/{slug}/matches")
        if status != 200:
            return

        if slug not in alert_cache:
            alert_cache[slug] = []
        user_map = {v: k for k, v in tourney_map[slug].items()}

        for match in matches_data:
            match = match["match"]
            mid = str(match["id"])
            if match["state"] != "open" or mid in alert_cache[slug]:
                continue
            p1, p2 = user_map.get(str(match["player1_id"])), user_map.get(str(match["player2_id"]))
            mentions = [f"<@{uid}>" for uid in (p1, p2) if uid and uid not in optouts.get(slug, [])]
            if not mentions:
                continue
            embed = discord.Embed(title=f"🎮 Match Ready in {slug}", description=f"Match ID: `{mid}` is now open!", color=0x3498db)
            if p1: embed.add_field(name="Player 1", value=f"<@{p1}>", inline=True)
            if p2: embed.add_field(name="Player 2", value=f"<@{p2}>", inline=True)

            class OptOutView(View):
                def __init__(self, uid):
                    super().__init__(timeout=None)
                    self.uid = uid
                @discord.ui.button(label="<:settings:1388586507664883772> Opt Out of Pings", style=discord.ButtonStyle.danger)
                async def optout(self, interaction: discord.Interaction, button: Button):
                    if str(interaction.user.id) != self.uid:
                        await interaction.response.send_message("Not your button.", ephemeral=True)
                        return
                    optouts.setdefault(slug, []).append(self.uid)
                    save_json(OPTOUT_FILE, optouts)
                    await interaction.response.send_message("You have opted out of match pings. <:settings:1388586507664883772>", ephemeral=True)

            channel = guild.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(" ".join(mentions), embed=embed, view=OptOutView(p1 or p2))
            alert_cache[slug].append(mid)
        save_json(ALERT_CACHE, alert_cache)

    @commands.command(name="addplayer", aliases=["join", "signup"])
    async def addplayer(self, ctx, *, player_name: str = None):
        """Add a player to the tournament using a mapped or given name."""
        if not self.active_tournament_slug:
            await ctx.send("🚫 No active tournament set. Use `!seed_tourney <slug>` first.")
            return
    
        player_map = load_player_map()
    
        if not player_name:
            # Try mapping from Discord display name
            key = ctx.author.display_name.strip()
            player_name = player_map.get(key, key)  # fallback to display name if unmapped
    
        try:
            participant = challonge.participants.create(
                self.active_tournament_slug,
                name=player_name
            )
            await ctx.send(f"✅ Added `{player_name}` to the tournament.")
        except challonge.api.ChallongeException as e:
            await ctx.send(f"❌ Could not add player: {e}")

    @commands.command(name="mapname", aliases=["setname"])
    async def mapname(self, ctx, *, desired_name: str):
        """Map your Discord display name to a tournament name."""
        name = ctx.author.display_name.strip()
        player_map = load_player_map()
        player_map[name] = desired_name
        save_player_map(player_map)
        await ctx.send(f"🔗 Mapped `{name}` → `{desired_name}` for auto-registration.")

    @commands.command(name="namemap")
    async def view_name_map(self, ctx):
        """View all current name mappings."""
        player_map = load_player_map()
        if not player_map:
            await ctx.send("📭 No name mappings have been set yet.")
            return
    
        embed = discord.Embed(title="📇 Player Name Mappings", color=0x00bfa5)
        for discord_name, mapped_name in player_map.items():
            embed.add_field(name=discord_name, value=f"→ `{mapped_name}`", inline=False)
        await ctx.send(embed=embed)

    @commands.command(aliases=["mlist"])
    async def match_list(self, ctx, slug: str):
        """List all current matches for a given tournament slug."""
        data, status = await self.request("GET", f"tournaments/{slug}/matches")
        if status != 200:
            await ctx.send(f"❌ Failed to fetch matches: {data.get('errors') or data}")
            return

        if not data:
            await ctx.send("No matches found for this tournament.")
            return

        embed = discord.Embed(title=f"📋 Match List: {slug}", color=0x2ecc71)

        for match in data[:10]:  # Show only first 10 to prevent spam
            m = match["match"]
            embed.add_field(
                name=f"Match ID: {m['id']}",
                value=f"Player1 ID: `{m['player1_id']}` vs Player2 ID: `{m['player2_id']}`\nState: **{m['state']}**",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(aliases=["dumppl"])
    @commands.is_owner()
    async def dump_participants(self, ctx, slug: str):
        """Dump participant names and their Challonge IDs from a tournament."""
        participants = await self.fetch_participants(slug)
        if not participants:
            await ctx.send(f"❌ Couldn't fetch participants for `{slug}`.")
            return

        msg = "\n".join([f"{name} → `{pid}`" for name, pid in participants.items()])
        if len(msg) > 1900:
            await ctx.send("Too many participants. Sending as a file.", file=discord.File(io.StringIO(msg), filename=f"{slug}_participants.txt"))
        else:
            await ctx.send(f"📋 Participants in `{slug}`:\n```{msg}```")

    @commands.command()
    @commands.is_owner()
    async def bind(self, ctx, slug: str, participant_id: str):
        tourney_map = load_json(MAP_FILE)
        tourney_map.setdefault(slug, {})[str(ctx.author.id)] = participant_id
        save_json(MAP_FILE, tourney_map)
        await ctx.send(f"✅ Bound <@{ctx.author.id}> to participant ID `{participant_id}` in `{slug}`.")

    @commands.command()
    @commands.is_owner()
    async def drop(self, ctx, slug: str, member: discord.Member):
        tourney_map = load_json(MAP_FILE)
        uid = str(member.id)
        if slug in tourney_map and uid in tourney_map[slug]:
            del tourney_map[slug][uid]
            save_json(MAP_FILE, tourney_map)
            await ctx.send(f"✅ Removed {member.display_name} from `{slug}`.")
        else:
            await ctx.send("❌ User not found in tournament map.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def seed(self, ctx, slug: str):
        data, status = await self.request("POST", f"tournaments/{slug}/process_check_ins")
        if status == 200:
            await ctx.send(f"✅ Check-ins processed for `{slug}`.")
        else:
            await ctx.send(f"❌ Failed to process check-ins: {data.get('errors') or data}")

    @commands.command()
    async def report(self, ctx, slug: str, match_id: int, score: str):
        import re
        PENDING_FILE = "data/pending_reports.json"

        tourney_map = load_json(MAP_FILE)
        user_id = str(ctx.author.id)
        if slug not in tourney_map or user_id not in tourney_map[slug]:
            await ctx.send("❌ You are not registered in this tournament.")
            return

        if not re.match(r"^\d+-\d+(,\d+-\d+)*$", score.strip()):
            await ctx.send("❌ Invalid score format. Use `X-Y` or `X-Y,X-Y,...` (e.g., `3-1` or `11-7,8-11,11-9`).")
            return

        participant_id = tourney_map[slug][user_id]

        data, status = await self.request("GET", f"tournaments/{slug}/matches/{match_id}")
        if status != 200:
            await ctx.send(f"❌ Match not found: {data.get('errors') or data}")
            return

        match = data["match"]
        p1, p2 = str(match["player1_id"]), str(match["player2_id"])
        if participant_id not in [p1, p2]:
            await ctx.send("❌ You are not in this match.")
            return

        winner_id = participant_id
        loser_id = p2 if participant_id == p1 else p1

        # Save to pending reports
        pending = load_json(PENDING_FILE)
        pending.setdefault(slug, {})[str(match_id)] = {
            "score": score,
            "winner_id": winner_id,
            "loser_id": loser_id,
            "reporter": user_id
        }
        save_json(PENDING_FILE, pending)

        await ctx.send(f"📝 Match report submitted for review. Awaiting dev confirmation. <:settings:1388586507664883772>")

    @commands.command(aliases=["cr"])
    @commands.is_owner()
    async def confirm_report(self, ctx, slug: str, match_id: int):
        reports = load_json("data/pending_reports.json")
        slug_reports = reports.get(slug, {})
        str_match_id = str(match_id)

        if str_match_id not in slug_reports:
            await ctx.send(f"❌ No pending report found for match `{match_id}` in `{slug}`.")
            return

        report = slug_reports[str_match_id]
        payload = {
            "match": {
                "scores_csv": report["score"],
                "winner_id": int(report["winner_id"])
            }
        }

        _, status = await self.request("PUT", f"tournaments/{slug}/matches/{match_id}", json=payload)
        if status == 200:
            self.log_match(slug, report["winner_id"], report["loser_id"], str(match_id))
            self.update_elo(report["winner_id"], report["loser_id"])
            await ctx.send(f"✅ Match `{match_id}` confirmed and recorded! <:Premium:1388586503092961482>")
            del slug_reports[str_match_id]
            if not slug_reports:
                reports.pop(slug)
            else:
                reports[slug] = slug_reports
            save_json("data/pending_reports.json", reports)
        else:
            await ctx.send("❌ Failed to finalize match via Challonge API.")

    @commands.command(aliases=["dr"])
    @commands.is_owner()
    async def deny_report(self, ctx, slug: str, match_id: int):
        reports = load_json("data/pending_reports.json")
        slug_reports = reports.get(slug, {})
        str_match_id = str(match_id)

        if str_match_id not in slug_reports:
            await ctx.send(f"⚠️ No pending report for match `{match_id}` in `{slug}`.")
            return

        reporter_id = slug_reports[str_match_id]["reporter"]
        del slug_reports[str_match_id]
        if not slug_reports:
            reports.pop(slug)
        else:
            reports[slug] = slug_reports

        save_json("data/pending_reports.json", reports)

        await ctx.send(f"<:noentry:1388586500756865126> <@{reporter_id}>, your match report for `{slug}` match `{match_id}` was **denied** by the tournament overlords. Try again or appeal with better vibes. <:settings:1388586507664883772>")


    @commands.command(aliases=["confres"])
    @commands.is_owner()
    async def confirm_result(self, ctx, slug: str, match_id: int, score: str, loser: discord.Member):
        """Dev-only: Immediately confirm and push a match result."""
        tourney_map = load_json(MAP_FILE)
        ELO_FILE = "data/elo_scores.json"

        winner_id = str(ctx.author.id)
        loser_id = str(loser.id)

        if slug not in tourney_map or winner_id not in tourney_map[slug] or loser_id not in tourney_map[slug]:
            await ctx.send("❌ One or both users not registered in this tournament.")
            return

        participant_winner = tourney_map[slug][winner_id]
        participant_loser = tourney_map[slug][loser_id]

        payload = {
            "match": {
                "scores_csv": score,
                "winner_id": int(participant_winner)
            }
        }

        data, status = await self.request("PUT", f"tournaments/{slug}/matches/{match_id}", json=payload)

        if status == 200:
            self.log_match(slug, winner_id, loser_id, str(match_id))
            self.update_elo(winner_id, loser_id)

            embed = discord.Embed(
                title="✅ Match Result Confirmed",
                description=f"**{ctx.author.display_name}** defeated **{loser.display_name}**\nMatch ID: `{match_id}`\nScore: `{score}`",
                color=0x2ecc71
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Failed to confirm result: {data.get('errors') or data}")

    @commands.command(name="whoami")
    async def whoami(self, ctx, slug: str):
        """Find your participant ID for a tournament."""
        user_name = ctx.author.display_name.lower()
        try:
            participants = self.get_participants(slug)
        except Exception as e:
            return await ctx.send(f"❌ Failed to fetch participants: `{e}`")
    
        # Try to match by display name or username
        matches = []
        for p in participants:
            name = p["participant"]["name"].lower()
            if user_name in name or ctx.author.name.lower() in name:
                matches.append((p["participant"]["id"], p["participant"]["name"]))
    
        if not matches:
            return await ctx.send(f"🔍 No participant matches found for `{ctx.author.display_name}` in `{slug}`.")
    
        msg = f"👤 Matches for **{ctx.author.display_name}** in `{slug}`:\n"
        for pid, pname in matches:
            msg += f"• `{pname}` — ID: `{pid}`\n"
        msg += "\nUse `!bind <slug> <participant_id>` to link yourself."
    
        await ctx.send(msg)

    @commands.command(aliases=["ct", "ctour", "newtour"])
    @commands.is_owner()
    async def create_tourney(self, ctx, slug: str, t_type: str = "single", *, tail: str = ""):
        """Create a new tournament. Optional: preload members from a role.
        Usage: !ct slug-name round My Tourney Name @RoleToAdd
        """
        role = None
        name = tail

        # If last token is a role mention, parse it out
        if ctx.message.role_mentions:
            role = ctx.message.role_mentions[-1]
            name = tail.replace(role.mention, "").strip()

        name = name or slug.replace("-", " ").title()
        t_type_map = {
            "single": "single elimination",
            "double": "double elimination",
            "round": "round robin"
        }
        selected_type = t_type_map.get(t_type.lower())

        if not selected_type:
            await ctx.send("❌ Invalid tournament type. Use: `single`, `double`, or `round`.")
            return

        payload = {
            "tournament": {
                "name": name,
                "url": slug,
                "tournament_type": selected_type,
                "open_signup": False,
                "private": True
            }
        }

        data, status = await self.request("POST", "tournaments", json=payload)

        if status != 200:
            errors = data.get("errors") or data
            await ctx.send(f"<:noentry:1388586500756865126> Couldn’t create tournament: `{errors}` <:settings:1388586507664883772>")
            return

        # Auto-create entry in MAP_FILE
        tourney_map = load_json(MAP_FILE)
        tourney_map.setdefault(slug, {})
        created_participants = []

        # Preload from role
        if role:
            for member in role.members:
                pname = member.display_name
                p_payload = {
                    "participant": {
                        "name": pname
                    }
                }
                pdata, pstatus = await self.request("POST", f"tournaments/{slug}/participants", json=p_payload)
                if pstatus == 200:
                    pid = pdata["participant"]["id"]
                    tourney_map[slug][str(member.id)] = str(pid)
                    created_participants.append(pname)
            save_json(MAP_FILE, tourney_map)

        embed = discord.Embed(
            title="<:Premium:1388586503092961482> Tournament Created!",
            description=f"[{name}](https://challonge.com/{slug}) is live and ready.",
            color=0x00ff99
        )
        embed.add_field(name="Slug", value=f"`{slug}`", inline=True)
        embed.add_field(name="Type", value=f"`{selected_type}`", inline=True)

        if created_participants:
            embed.add_field(
                name=f"👥 Preloaded {len(created_participants)} Participant(s)",
                value=", ".join(created_participants[:10]) + ("..." if len(created_participants) > 10 else ""),
                inline=False
            )

        embed.set_footer(text=f"Created by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)



    @commands.command(aliases=["fp"])
    @commands.is_owner()
    async def find_pid_by_name(self, ctx, slug: str, *, name_query: str):
        """Search for participant IDs by name in a given tournament."""
        data, status = await self.request("GET", f"tournaments/{slug}/participants")
        if status != 200:
            await ctx.send(f"<:settings:1388586507664883772> Couldn't fetch participants for `{slug}`: {data.get('errors') or data}")
            return

        matches = [
            (p["participant"]["name"], p["participant"]["id"])
            for p in data
            if name_query.lower() in p["participant"]["name"].lower()
        ]

        if not matches:
            await ctx.send(f"No matches found for `{name_query}` in `{slug}`.")
            return

        result_lines = [f"• `{name}` → `{pid}`" for name, pid in matches[:10]]
        msg = "\n".join(result_lines)
        await ctx.send(f"**Matches found in `{slug}`:**\n{msg}")

    @commands.command(aliases=["bracket", "view_bracket"])
    async def bracket_link(self, ctx, slug: str):
        await ctx.send(f"🔗 View the bracket: https://challonge.com/{slug}")

    @commands.command(aliases=["tinfo", "view_slug"])
    async def tourney_info(self, ctx, slug: str):
        data, status = await self.request("GET", f"tournaments/{slug}")
        if status != 200:
            await ctx.send(f"<:noentry:1388586500756865126> Failed to fetch tournament: `{data.get('errors') or data}`")
            return

        t = data["tournament"]
        embed = discord.Embed(
            title=f"<:ghostframe:1382050156131651635> {t['name']}",
            description=f"[View on Challonge](https://challonge.com/{slug})",
            color=0x7289da
        )
        embed.add_field(name="Type", value=t['tournament_type'].title(), inline=True)
        embed.add_field(name="State", value=t['state'].capitalize(), inline=True)
        embed.add_field(name="Participants", value=str(t['participants_count']), inline=True)
        embed.set_footer(text=f"Created by {t['creator_name']}" if t.get("creator_name") else "Challonge")

        await ctx.send(embed=embed)


    @commands.command(aliases=["pb", "purge"])
    @commands.is_owner()
    async def purgebot(self, ctx, limit: int = 50, *, keyword: str = None):
        """
        Delete BlkLine's messages and your own command triggers (within limit).
        Optional: filter by keyword.
        Usage: !purgebot 50
               !purgebot 100 matches ready
        """
        def check(m):
            # Bot message OR your own command message
            is_blk_or_trigger = (
                m.author == ctx.bot.user or
                (m.author == ctx.author and m.content.startswith(ctx.prefix))
            )
            
            # Optional keyword filter (in content or embed text)
            if keyword:
                in_content = keyword.lower() in m.content.lower()
                in_embed = any(
                    keyword.lower() in (e.description or "").lower()
                    or any(keyword.lower() in (f.value or "") for f in e.fields)
                    for e in m.embeds
                ) if m.embeds else False
                return is_blk_or_trigger and (in_content or in_embed)
    
            return is_blk_or_trigger
    
        deleted = await ctx.channel.purge(limit=limit, check=check)
        await ctx.send(f"🧽 Deleted {len(deleted)} bot/trigger messages.", delete_after=3)

    
    @commands.command(aliases=["tourneyhelp", "tourhelp", "thelp"])
    async def help_tourney(self, ctx):
        embed = discord.Embed(
            title="Tournament Commands Help",
            description="All commands related to managing and playing in Challonge tournaments.",
            color=0x5865f2
        )

        embed.add_field(
            name="🎮 Player Commands",
            value=(
                "`!register <slug>` – Join a tournament\n"
                "`!report <slug> <match_id> <score>` – Report a match win\n"
                "`!elo [@user]` – View ELO rating\n"
                "`!match_history <slug> [@user]` – Match history\n"
                "`!leaderboard <slug>` – Show wins leaderboard\n"
                "`!status <slug>` – Tournament status\n"
                "`!tinfo <slug>` – View tournament overview\n"
                "`!bracket <slug>` – Get bracket link\n"
                "`!tourneys` – Your created tournaments\n"
                "`!slugs` – List tracked tournament slugs"
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ Organizer Commands",
            value=(
                "`!ct <slug> [type] [name] [@role]` – Create a tournament\n"
                "`!seed <slug>` – Reseed / process check-ins\n"
                "`!sync_matches <slug>` – Manually trigger match alerts"
            ),
            inline=False
        )

        embed.add_field(
            name="<:settings:1388586507664883772> Dev-Only Commands",
            value=(
                "`!bind <slug> <participant_id>`\n"
                "`!drop <slug> <@user>` – Remove player from tourney\n"
                "`!dump_participants <slug>`\n"
                "`!confirm_report <slug> <match_id>`\n"
                "`!deny_report <slug> <match_id>`"
            ),
            inline=False
        )

        embed.set_footer(text="Use the <slug> from Challonge URL (e.g. 'mycooltourney')")
        await ctx.send(embed=embed)


    async def fetch_participants(self, slug):
        """Fetch participants from Challonge and return name → ID mapping."""
        data, status = await self.request("GET", f"tournaments/{slug}/participants")
        if status != 200:
            return None
        return {
            p["participant"]["name"]: str(p["participant"]["id"])
            for p in data
        }
async def setup(bot):
    await bot.add_cog(ChallongeCog(bot))
