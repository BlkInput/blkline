# cogs/reason.py

import re
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Load environment variables from .env
load_dotenv()
BOT_NAME       = os.getenv('BOT_NAME', 'Reason')
TARGET_CHANNEL = os.getenv('LOGIC_CHANNEL', 'logic-lab')

class ArgumentDebugger:
    # Expanded factual indicators
    IS_PATTERNS = [
        r"\bis\b", r"\bare\b", r"\bwas\b", r"\bwere\b",
        r"\bhas\b", r"\bhave\b", r"\bhad\b",
        r"\btripled\b", r"\bincreased\b", r"\blink(s)?\b", r"\bremains\b"
    ]
    # Standard normative cues
    OUGHT_PATTERNS = [
        r"\bshould\b", r"\boug?ht to\b", r"\bmust\b", r"\bneed to\b"
    ]
    # Expanded bridge indicators
    BRIDGE_PATTERNS = [
        r"\b(because|since|as|considering that|given that|in light of|seeing that)\b"
    ]

    def __init__(self, text: str):
        # Split on end-of-sentence punctuation plus space
        self.sentences = re.split(r'(?<=[.!?]) +', text)

    def find_is_statements(self) -> list:
        return [
            s.strip() for s in self.sentences
            if any(re.search(p, s, re.I) for p in self.IS_PATTERNS)
        ]

    def find_ought_statements(self) -> list:
        return [
            s.strip() for s in self.sentences
            if any(re.search(p, s, re.I) for p in self.OUGHT_PATTERNS)
        ]

    def has_explicit_bridge(self, sentence: str) -> bool:
        return any(re.search(p, sentence, re.I) for p in self.BRIDGE_PATTERNS)

    def detect_gaps(self) -> list:
        gaps = []
        for ought in self.find_ought_statements():
            if not self.has_explicit_bridge(ought):
                suggestion = f"Consider adding a premise like 'Because <value>, {ought}'"
                gaps.append((ought, suggestion))
        return gaps

    def generate_report_embed(self, author: discord.Member) -> discord.Embed:
        facts = self.find_is_statements()
        norms = self.find_ought_statements()
        gaps = self.detect_gaps()

        embed = discord.Embed(
            title=f"{BOT_NAME} Logic Audit",
            color=0x1F8B4C
        )
        embed.set_author(
            name=author.display_name,
            icon_url=author.avatar.url if author.avatar else None
        )

        embed.add_field(
            name="🕵️‍♂️ Facts",
            value="\n".join(facts) or "*No factual statements detected.*",
            inline=False
        )
        embed.add_field(
            name="🤔 Normative Claims",
            value="\n".join(norms) or "*No normative statements detected.*",
            inline=False
        )

        if gaps:
            gap_lines = [f"• \"{o}\" → {s}" for o, s in gaps]
            embed.add_field(
                name="🚧 Gaps & Suggestions",
                value="\n".join(gap_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="✅ No Hidden Premises",
                value="All normative statements have explicit bridges—no gaps detected!",
                inline=False
            )

        return embed


class ArgumentDebuggerCog(commands.Cog):
    """Cog for auditing is→ought gaps in arguments."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='debugarg', aliases=['argdebug', 'logiccheck'], help='Analyze text for is→ought argument gaps')
    async def debugarg(self, ctx: commands.Context, *, text: str):
        dbg = ArgumentDebugger(text)
        embed = dbg.generate_report_embed(ctx.author)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ensure other commands still process
        await self.bot.process_commands(message)
        if message.author.bot:
            return

        if message.channel.name == TARGET_CHANNEL and len(message.content) > 50:
            dbg = ArgumentDebugger(message.content)
            embed = dbg.generate_report_embed(message.author)
            await message.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ArgumentDebuggerCog(bot))
