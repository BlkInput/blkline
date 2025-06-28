
import discord
from discord.ext import commands
import math

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="how", aliases=["helpme", "commandhelp"])
    async def how(self, ctx):
        # Custom help menu grouped by cogs with pagination
        cog_map = {
            "📍 PinPoint": {
                "!mark <x> <y> <z> <desc>": "Save a location pin with description.",
                "!markfor <@user> <x> <y> <z> <desc>": "Admin-only: Save a pin for someone else.",
            },
            "🎁 Rewards": {
                "!linkmc <username>": "Link your Discord with your Minecraft account.",
                "!unlinkmc": "Remove your Minecraft link.",
                "!linkstatus": "Check your current Minecraft link.",
                "!checkuuid <username>": "Fetch UUID of a Minecraft user.",
                "!rewardhistory": "View your last 5 rewards.",
                "!pool": "Check the server credit pool.",
                "!pooladd <amount>": "Admin: Add to server credit pool.",
                "!devlinkmc <@user> <username>": "Dev-only: Force link a user.",
            },
            "🖥️ Exaroton": {
                "!serverstatus": "Check server status (live uptime, queue, etc).",
                "!burnstats": "View credit burn rate and project time remaining.",
                "!credits": "Current Exaroton credit balance.",
                "!players": "See who's currently online.",
                "!sessionlength": "Current session duration (uptime).",
                "!restartserver": "Dev-only: Restart the server.",
            }
        }

        pages = []
        cog_list = list(cog_map.items())

        for i, (cog, commands_dict) in enumerate(cog_list, start=1):
            embed = discord.Embed(title="Command Reference", description=cog, color=0x5865F2)
            for cmd, desc in commands_dict.items():
                embed.add_field(name=cmd, value=desc, inline=False)
            embed.set_footer(text=f"Use !how to view pinpoint, exa and reward commands • Page {i}/{len(cog_list)}")
            pages.append(embed)

        message = await ctx.send(embed=pages[0])
        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"] and reaction.message.id == message.id

        i = 0
        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                await message.remove_reaction(reaction, user)

                if str(reaction.emoji) == "▶️" and i < len(pages) - 1:
                    i += 1
                    await message.edit(embed=pages[i])
                elif str(reaction.emoji) == "◀️" and i > 0:
                    i -= 1
                    await message.edit(embed=pages[i])
            except Exception:
                break

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
