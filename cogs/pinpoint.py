# PinPoint.py

import discord
from discord.ext import commands
from typing import Union
import json
import os
import csv
from datetime import datetime

PIN_DATA_FILE = "data/pins.json"
SUBMITTER_MAP = {
    "1": 448896936481652777,  # you
    "2": 1382042817467256983, # GhostFrame
    "3": 424532190290771998   # Ezra
}
DEV_IDS = [448896936481652777]  # you

def load_pins():
    if not os.path.exists(PIN_DATA_FILE):
        return {}
    with open(PIN_DATA_FILE, "r") as f:
        return json.load(f)

def save_pins(data):
    os.makedirs(os.path.dirname(PIN_DATA_FILE), exist_ok=True)
    with open(PIN_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class PinPoint(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mark")
    async def mark(self, ctx, x: int, y_or_desc: str, z: int, *, description: str = None):
        """Mark a location with optional Y coordinate. Usage: !mark x y z desc OR !mark x desc z"""

        required_role_id = 1388601551349612695
        dev_ids = [448896936481652777, 923014434228690966]
        if required_role_id not in [role.id for role in ctx.author.roles]:
            return  # silent fail, no message, no log
        try:
            y = int(y_or_desc)
            desc = description
        except ValueError:
            y = None
            desc = f"{y_or_desc} {description}" if description else y_or_desc

        pins = load_pins()
        pin_id = str(max([int(k) for k in pins.keys()] + [0]) + 1)
        timestamp = datetime.utcnow().isoformat()
        submitter_id = str(ctx.author.id)
        attributed_id = str(ctx.author.id)
    
        pins[pin_id] = {
            "x": x,
            "y": y,
            "z": z,
            "description": desc,
            "submitter_id": submitter_id,
            "attributed_user_id": attributed_id,
            "timestamp": timestamp
        }
    
        save_pins(pins)
        embed = discord.Embed(title=f"📍 {desc}", color=0x462f80)
        coord_field = f"x: {x}, z: {z}" if y is None else f"x: {x}, y: {y}, z: {z}"
        embed.add_field(name="🧭 Coordinates", value=coord_field, inline=False)
        embed.set_footer(text=f"Submitted by {ctx.author.display_name} • ID: {pin_id}")
        await ctx.send(embed=embed)


    @commands.command(name="pins")
    async def pins(self, ctx):
        pins = load_pins()
        if not pins:
            await ctx.send("📭 No pins found.")
            return
    
        embed = discord.Embed(title="📌 Recent Pins", color=0x462f80)
    
        recent = sorted(pins.items(), key=lambda item: int(item[0]))[-5:]
        for pid, p in recent:
            user_id = int(p["attributed_user_id"])
            user = self.bot.get_user(user_id)
            user_mention = user.mention if user else f"<@{user_id}>"
    
            # Build coordinate string
            coords = f"x: {p['x']}, z: {p['z']}"
            if p.get("y") is not None:
                coords = f"x: {p['x']}, y: {p['y']}, z: {p['z']}"
    
            embed.add_field(
                name=f"📍 {p['description']} (ID {pid})",
                value=f"{coords} — submitted by {user_mention}",
                inline=False
            )
    
        await ctx.send(embed=embed)


    @commands.command(name="markfor")
    @commands.has_permissions(administrator=True)
    async def mark_for(self, ctx, attributed: discord.Member, x: int, y_or_desc: str, z: int, *, description: str = None):
        """Add a pin for another user (admin/dev-only)."""
        try:
            y = int(y_or_desc)
            desc = description
        except ValueError:
            y = None
            desc = f"{y_or_desc} {description}" if description else y_or_desc
    
        pins = load_pins()
        pin_id = str(max([int(k) for k in pins.keys()] + [0]) + 1)
    
        pins[pin_id] = {
            "x": x,
            "y": y,
            "z": z,
            "description": desc,
            "submitter_id": str(ctx.author.id),
            "attributed_user_id": str(attributed.id),
            "timestamp": datetime.utcnow().isoformat()
        }
    
        save_pins(pins)
    
        embed = discord.Embed(title=f"📍 {desc}", color=0x462f80)
        coord_field = f"x: {x}, z: {z}" if y is None else f"x: {x}, y: {y}, z: {z}"
        attributed_display = attributed.display_name if hasattr(attributed, "display_name") else attributed
        
        embed.add_field(name="🧭 Coordinates", value=coord_field, inline=False)
        embed.set_footer(text=f"Marked by {ctx.author.display_name} for {attributed_display}")
        await ctx.send(embed=embed)


    
    @mark_for.error
    async def markfor_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("❗ Please mention a valid user for attribution.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("🚫 You need admin permissions to use this command.")
        else:
            await ctx.send("⚠️ An error occurred while processing the command.")


    @commands.command(name="pin")
    async def pin(self, ctx, pin_id: str):
        pins = load_pins()
        pin = pins.get(pin_id)
        if not pin:
            await ctx.send("❌ Pin not found.")
            return
    
        # Fallbacks if user not in cache
        submitter_id = int(pin["submitter_id"])
        attributed_id = int(pin["attributed_user_id"])
        submitter = self.bot.get_user(submitter_id)
        attributed = self.bot.get_user(attributed_id)
        submitter_display = submitter.mention if submitter else f"<@{submitter_id}>"
        attributed_display = attributed.mention if attributed else f"<@{attributed_id}>"
    
        coords = f"x: {pin['x']}, z: {pin['z']}"
        if pin.get("y") is not None:
            coords = f"x: {pin['x']}, y: {pin['y']}, z: {pin['z']}"
    
        embed = discord.Embed(title=f"📍 {pin['description']}", color=0x462f80)
        embed.add_field(name="🧭 Coordinates", value=coords, inline=False)
        embed.add_field(name="👤 Submitted by", value=submitter_display, inline=True)
        embed.add_field(name="🙋 Attributed to", value=attributed_display, inline=True)
        embed.set_footer(text=f"Pin ID: {pin_id} • {pin['timestamp']}")
        await ctx.send(embed=embed)


    @commands.command(name="filterpins")
    async def filterpins(self, ctx, *, query: str):
        pins = load_pins()
        results = []

        for pid, pin in pins.items():
            if (
                query in pin["description"]
                or query in pid
                or query in pin["submitter_id"]
                or query in pin["attributed_user_id"]
            ):
                results.append((pid, pin))

        if not results:
            await ctx.send("❌ No pins matched your filter.")
            return

        embed = discord.Embed(title="🔎 Filtered Pins", color=0x462f80)
        for pid, pin in results[:10]:
            user = self.bot.get_user(int(pin["attributed_user_id"])) or f"<@{pin['attributed_user_id']}>"
            embed.add_field(name=f"{pin['description']} (ID {pid})",
                            value=f"x: {pin['x']}, z: {pin['z']} — by {user}",
                            inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="editpin")
    async def editpin(self, ctx, pin_id: str, *, new_desc: str):
        pins = load_pins()
        pin = pins.get(pin_id)
        if not pin:
            await ctx.send("❌ Pin not found.")
            return
    
        user_id = str(ctx.author.id)
        is_owner = pin["submitter_id"] == user_id or user_id in map(str, DEV_IDS)
    
        if not is_owner:
            await ctx.send("🚫 You can't edit this pin.")
            return
    
        pin["description"] = new_desc
        save_pins(pins)
        await ctx.send(f"✏️ Pin `{pin_id}` updated.")

    @commands.command(name="deletepin")
    async def deletepin(self, ctx, pin_id: str):
        pins = load_pins()
        pin = pins.get(pin_id)
        if not pin:
            await ctx.send("❌ Pin not found.")
            return

        user_id = str(ctx.author.id)
        is_owner = pin["submitter_id"] == user_id or user_id in map(str, DEV_IDS)

        if not is_owner:
            await ctx.send("🚫 You can't delete this pin.")
            return

        del pins[pin_id]
        save_pins(pins)
        await ctx.send(f"🗑️ Pin `{pin_id}` deleted.")

    @commands.command(name="pinhelp", aliases=["pincmds", "pinmanual"])
    async def pinhelp(self, ctx):
        embed = discord.Embed(
            title="📍 PinPoint Commands",
            description="All available location tracking commands",
            color=0x462f80
        )
        embed.add_field(name="!mark x z description", value="Add a new pin at coordinates with a short description.", inline=False)
        embed.add_field(name="!pins", value="List the latest 5 pins added.", inline=False)
        embed.add_field(name="!pin ID", value="View detailed info on a specific pin.", inline=False)
        embed.add_field(name="!filterpins query", value="Search for pins by keyword, user ID, or description.", inline=False)
        embed.add_field(name="!editpin ID new description", value="Edit your own or dev-assigned pin's description.", inline=False)
        embed.add_field(name="!deletepin ID", value="Delete your own or dev-assigned pin.", inline=False)
        embed.add_field(name="!exportpins", value="Export all pins as `.json` and `.csv` files.", inline=False)
        embed.set_footer(text="PinPoint • Map tracking for explorers and troublemakers 🗺️")

        await ctx.send(embed=embed)

    @commands.command(name="exportpins")
    async def exportpins(self, ctx):
        pins = load_pins()
        if not pins:
            await ctx.send("📭 No pins to export.")
            return

        json_path = "/mnt/data/pin_export.json"
        csv_path = "/mnt/data/pin_export.csv"

        with open(json_path, "w") as f:
            json.dump(pins, f, indent=4)

        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ID", "X", "Z", "Description", "Submitter", "Attributed", "Timestamp"])
            for pid, pin in pins.items():
                writer.writerow([
                    pid,
                    pin["x"],
                    pin["z"],
                    pin["description"],
                    pin["submitter_id"],
                    pin["attributed_user_id"],
                    pin["timestamp"]
                ])

        await ctx.send("📦 Pins exported:", files=[
            discord.File(json_path),
            discord.File(csv_path)
        ])

async def setup(bot):
    await bot.add_cog(PinPoint(bot))
