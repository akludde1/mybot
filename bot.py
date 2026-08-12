import os
import re
import random
import asyncio
import sqlite3
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import ui

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.environ["TOKEN"]

# Tickets
TICKET_PANEL_CHANNEL_ID = 1397525433624428554
SUPPORT_CATEGORY_ID = 1536759448226242661
BILLING_CATEGORY_ID = 1536759586168766504
APPEAL_CATEGORY_ID = 1536759712660455474
STAFF_ROLE_ID = 1393951328061095976

# Giveaway
GIVEAWAY_COMMAND_ROLE_ID = 1391071302890033355
GIVEAWAY_STAFF_ROLE_ID = 1393951328061095976
GIVEAWAY_TICKET_CATEGORY_ID = 1394270405707043059

# Welcome
WELCOME_CHANNEL_ID = 1397563706510151871

# Counting
COUNTING_CHANNEL_ID = 1389308013608698058

# Logs / transcripts
TRANSCRIPT_CHANNEL_ID = 1537027862039625778
MESSAGE_LOG_CHANNEL_ID = 1537027660264243291

# Lockdown
LOCKDOWN_ROLE_ID = 1389245929164636190

# AFK
AFK_ROLE_ID = 1389503797100937337

# Invite permissions
INVITE_ALLOWED_ROLE_ID = 1391071302890033355

# Database
DB_FILE = "bot_data.sqlite3"

# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory active tickets/giveaways. Giveaway/ticket data is also
# persisted where appropriate so basic state survives restarts.
active_tickets = {}
active_giveaways = {}
lockdown_saved_permissions = {}
counting_number = 1
counting_last_user_id = None

# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS mute_offences (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    offences INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS afk (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT 'AFK',
    started_at INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
)
""")
db.commit()


def get_mute_offences(guild_id, user_id):
    row = db.execute(
        "SELECT offences FROM mute_offences WHERE guild_id=? AND user_id=?",
        (guild_id, user_id),
    ).fetchone()
    return row[0] if row else 0


def set_mute_offences(guild_id, user_id, offences):
    db.execute(
        """
        INSERT INTO mute_offences(guild_id,user_id,offences)
        VALUES(?,?,?)
        ON CONFLICT(guild_id,user_id)
        DO UPDATE SET offences=excluded.offences
        """,
        (guild_id, user_id, offences),
    )
    db.commit()


def set_afk(guild_id, user_id, reason):
    db.execute(
        """
        INSERT INTO afk(guild_id,user_id,reason,started_at)
        VALUES(?,?,?,?)
        ON CONFLICT(guild_id,user_id)
        DO UPDATE SET reason=excluded.reason, started_at=excluded.started_at
        """,
        (guild_id, user_id, reason, int(time.time())),
    )
    db.commit()


def get_afk(guild_id, user_id):
    return db.execute(
        "SELECT reason, started_at FROM afk WHERE guild_id=? AND user_id=?",
        (guild_id, user_id),
    ).fetchone()


def clear_afk(guild_id, user_id):
    db.execute(
        "DELETE FROM afk WHERE guild_id=? AND user_id=?",
        (guild_id, user_id),
    )
    db.commit()


# ============================================================
# HELPERS
# ============================================================

def has_role(member, role_id):
    return any(role.id == role_id for role in getattr(member, "roles", []))


def is_ticket_channel(channel):
    return channel.id in active_tickets


def parse_duration(text):
    text = text.lower().strip()
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|"
        r"h|hr|hrs|hour|hours|d|day|days)",
        text,
    )
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)

    if unit in {"s", "sec", "secs", "second", "seconds"}:
        seconds = amount
    elif unit in {"m", "min", "mins", "minute", "minutes"}:
        seconds = amount * 60
    elif unit in {"h", "hr", "hrs", "hour", "hours"}:
        seconds = amount * 3600
    else:
        seconds = amount * 86400

    return max(1, int(seconds))


def duration_text(seconds):
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def timestamp_now():
    return int(time.time())


def safe_channel_name(name, prefix="ticket"):
    clean = "".join(
        c if c.isalnum() or c == "-" else "-"
        for c in name.lower()
    ).strip("-")
    clean = clean[:70] or "user"
    return f"{prefix}-{clean}"


async def fetch_channel(channel_id):
    channel = bot.get_channel(channel_id)
    if channel:
        return channel
    try:
        return await bot.fetch_channel(channel_id)
    except discord.HTTPException:
        return None


# ============================================================
# TICKETS
# ============================================================

def ticket_embed():
    return discord.Embed(
        title="Tickets",
        description=(
            "Need help with anything?\n\n"
            "**Open a ticket**\n"
            "Use the boxes below to choose the category of your inquiry."
        ),
        color=discord.Color.blurple(),
    )


class TicketSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Support/Questions",
                description="Get help or ask a question.",
                emoji="🛠️",
                value="support",
            ),
            discord.SelectOption(
                label="Billing",
                description="Billing questions.",
                emoji="💳",
                value="billing",
            ),
            discord.SelectOption(
                label="Appeal",
                description="Submit an appeal.",
                emoji="⚖️",
                value="appeal",
            ),
        ]
        super().__init__(
            placeholder="Choose a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="multiplesmp_ticket_category",
        )

    async def callback(self, interaction):
        await create_ticket(interaction, self.values[0])


class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


async def create_ticket(interaction, ticket_type, forced_category=None, giveaway=None):
    guild = interaction.guild
    user = interaction.user

    if not guild:
        return

    for channel_id, creator_id in list(active_tickets.items()):
        if creator_id == user.id:
            existing = guild.get_channel(channel_id)
            if existing:
                await interaction.response.send_message(
                    f"You already have an open ticket: {existing.mention}",
                    ephemeral=True,
                )
                return
            active_tickets.pop(channel_id, None)

    category_ids = {
        "support": SUPPORT_CATEGORY_ID,
        "billing": BILLING_CATEGORY_ID,
        "appeal": APPEAL_CATEGORY_ID,
    }

    category = forced_category or guild.get_channel(category_ids.get(ticket_type))
    staff_role = guild.get_role(STAFF_ROLE_ID)

    if category is None:
        await interaction.response.send_message(
            "❌ Ticket category not found.", ephemeral=True
        )
        return

    if staff_role is None:
        await interaction.response.send_message(
            "❌ Staff role not found.", ephemeral=True
        )
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
        staff_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            manage_messages=True,
        ),
    }

    prefix = "giveaway" if giveaway else "ticket"
    channel_name = safe_channel_name(user.name, prefix)

    try:
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket created by {user}",
        )
    except discord.Forbidden:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ I don't have permission to create ticket channels.",
                ephemeral=True,
            )
        return

    active_tickets[ticket_channel.id] = user.id

    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"✅ Your ticket has been created: {ticket_channel.mention}",
            ephemeral=True,
        )

    if giveaway:
        opening = await ticket_channel.send(
            f"🎉 Congratulations {user.mention}!\n\n"
            f"You won the giveaway for:\n"
            f"**{giveaway['prize']}**\n\n"
            f"A staff member will assist you shortly.\n"
            f"{staff_role.mention}"
        )
    else:
        opening = await ticket_channel.send(
            f"Hello {user.mention}, a staff member will be with you shortly.\n"
            f"{staff_role.mention}"
        )

    try:
        await opening.pin(reason="Ticket opening message")
    except discord.HTTPException:
        pass


@bot.command(name="wedyeu9deufeuiofh39yourhfuohyigfgrg")
async def ticket_panel(ctx):
    channel = await fetch_channel(TICKET_PANEL_CHANNEL_ID)
    if channel is None:
        await ctx.send("❌ I couldn't find the ticket panel channel.", delete_after=5)
        return

    await channel.send(embed=ticket_embed(), view=TicketPanelView())
    await ctx.send("✅ Ticket panel posted.", delete_after=5)


async def build_transcript(channel, creator_id, opened_at, closed_by):
    lines = []
    async for message in channel.history(limit=None, oldest_first=True):
        content = message.content or "[no text content]"
        if message.attachments:
            content += " | Attachments: " + ", ".join(a.url for a in message.attachments)
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(f"[{timestamp}] {message.author} ({message.author.id}): {content}")

    text = "\n".join(lines) or "No messages."

    creator = channel.guild.get_member(creator_id)
    creator_name = str(creator) if creator else f"User ID {creator_id}"
    opened = datetime.fromtimestamp(opened_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    closed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    header = (
        f"Ticket: #{channel.name}\n"
        f"Creator: {creator_name} ({creator_id})\n"
        f"Opened: {opened}\n"
        f"Closed: {closed}\n"
        f"Closed by: {closed_by} ({closed_by.id})\n\n"
    )

    filename = f"{channel.name}-transcript.txt"
    return header + text, filename


@bot.command()
async def close(ctx):
    staff_role = ctx.guild.get_role(STAFF_ROLE_ID)
    if staff_role is None or staff_role not in ctx.author.roles:
        await ctx.send("❌ Only staff can close tickets.", delete_after=3)
        return

    if ctx.channel.id not in active_tickets:
        await ctx.send("❌ This is not a ticket channel.", delete_after=3)
        return

    creator_id = active_tickets.pop(ctx.channel.id)
    opened_at = int(getattr(ctx.channel, "created_at", datetime.now(timezone.utc)).timestamp())

    transcript_text, filename = await build_transcript(
        ctx.channel, creator_id, opened_at, ctx.author
    )

    transcript_channel = await fetch_channel(TRANSCRIPT_CHANNEL_ID)

    if transcript_channel:
        embed = discord.Embed(
            title="📄 Ticket Transcript",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Ticket", value=f"`{ctx.channel.name}`", inline=False)
        embed.add_field(name="Creator ID", value=str(creator_id), inline=True)
        embed.add_field(name="Closed By", value=ctx.author.mention, inline=True)
        embed.add_field(
            name="Messages",
            value=str(transcript_text.count("\n")),
            inline=True,
        )

        data = transcript_text.encode("utf-8")
        file = discord.File(__import__("io").BytesIO(data), filename=filename)

        try:
            await transcript_channel.send(embed=embed, file=file)
        except discord.HTTPException:
            pass

    await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")


# ============================================================
# GIVEAWAYS
# ============================================================

active_giveaways = {}


def create_giveaway_embed(g):
    return discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=(
            f"**Prize**\n{g['prize']}\n\n"
            f"**Ends**\n<t:{g['end_time']}:R>\n\n"
            f"**Winners**\n{g['winner_count']}\n\n"
            f"**Entries**\n{len(g['entries'])}\n\n"
            "Click the button below to enter!"
        ),
        color=discord.Color.gold(),
    )


class GiveawayView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GiveawayEnterButton())


class GiveawayEnterButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="Enter Giveaway",
            emoji="🎉",
            style=discord.ButtonStyle.success,
            custom_id="multiplesmp_giveaway_enter",
        )

    async def callback(self, interaction):
        giveaway = active_giveaways.get(interaction.message.id)
        if giveaway is None:
            await interaction.response.send_message(
                "❌ This giveaway has already ended.", ephemeral=True
            )
            return

        entries = giveaway["entries"]

        if interaction.user.id in entries:
            entries.remove(interaction.user.id)
            response = "❌ You have left the giveaway."
        else:
            entries.add(interaction.user.id)
            response = "🎉 You have entered the giveaway!"

        try:
            await interaction.message.edit(
                embed=create_giveaway_embed(giveaway),
                view=GiveawayView(),
            )
        except discord.HTTPException:
            pass

        await interaction.response.send_message(response, ephemeral=True)


class GiveawayFormView(ui.View):
    def __init__(self, channel):
        super().__init__(timeout=300)
        self.channel = channel
        self.add_item(GiveawayCreateButton())


class GiveawayCreateButton(ui.Button):
    def __init__(self):
        super().__init__(label="Create", style=discord.ButtonStyle.success)

    async def callback(self, interaction):
        await interaction.response.send_modal(GiveawayModal(self.view.channel))


class GiveawayModal(ui.Modal):
    def __init__(self, channel):
        super().__init__(title="Create Giveaway")
        self.channel = channel

        self.prize = ui.TextInput(
            label="Prize",
            placeholder="Example: $20 Steam Gift Card",
            required=True,
            max_length=200,
        )
        self.duration = ui.TextInput(
            label="Duration",
            placeholder="Examples: 30s, 10m, 2h, 3d",
            required=True,
            max_length=30,
        )
        self.winners = ui.TextInput(
            label="Winners",
            placeholder="Example: 1",
            required=True,
            max_length=3,
        )

        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.winners)

    async def on_submit(self, interaction):
        seconds = parse_duration(self.duration.value)
        if seconds is None:
            await interaction.response.send_message(
                "❌ Invalid duration. Examples: `30s`, `10m`, `2h`, `3d`.",
                ephemeral=True,
            )
            return

        try:
            winner_count = int(self.winners.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ Winners must be a number.", ephemeral=True
            )
            return

        if winner_count < 1:
            await interaction.response.send_message(
                "❌ You need at least 1 winner.", ephemeral=True
            )
            return

        giveaway = {
            "message_id": None,
            "channel_id": self.channel.id,
            "guild_id": self.channel.guild.id,
            "prize": self.prize.value,
            "duration": self.duration.value,
            "duration_seconds": seconds,
            "end_time": timestamp_now() + seconds,
            "winner_count": winner_count,
            "entries": set(),
            "creator_id": interaction.user.id,
        }

        message = await self.channel.send(
            embed=create_giveaway_embed(giveaway),
            view=GiveawayView(),
        )
        giveaway["message_id"] = message.id
        active_giveaways[message.id] = giveaway

        await interaction.response.send_message(
            "✅ Giveaway created successfully!", ephemeral=True
        )

        asyncio.create_task(finish_giveaway(message.id))


@bot.command(name="gway")
async def giveaway_command(ctx):
    role = ctx.guild.get_role(GIVEAWAY_COMMAND_ROLE_ID)
    if role is None or role not in ctx.author.roles:
        await ctx.send(
            "❌ You don't have permission to create giveaways.",
            delete_after=5,
        )
        return

    try:
        await ctx.author.send(
            "📋 **Giveaway Creator**\n\nClick **Create** below.",
            view=GiveawayFormView(ctx.channel),
        )
    except discord.Forbidden:
        await ctx.send(
            "❌ I couldn't DM you. Please enable DMs from server members.",
            delete_after=5,
        )
        return

    await ctx.send("✅ I've sent the giveaway form to your DMs.", delete_after=5)


async def announce_giveaway(giveaway, winner_ids, channel):
    winners = []
    for user_id in winner_ids:
        try:
            winners.append(await bot.fetch_user(user_id))
        except discord.HTTPException:
            pass

    if not winners:
        await channel.send("❌ The giveaway ended, but no valid winners could be found.")
        return

    winner_mentions = " ".join(u.mention for u in winners)
    staff_role = channel.guild.get_role(GIVEAWAY_STAFF_ROLE_ID)
    staff_mention = staff_role.mention if staff_role else ""

    await channel.send(
        f"🎉 **GIVEAWAY WINNERS!** 🎉\n\n"
        f"**Prize:** {giveaway['prize']}\n\n"
        f"Congratulations to:\n{winner_mentions}\n\n{staff_mention}"
    )

    category = channel.guild.get_channel(GIVEAWAY_TICKET_CATEGORY_ID)
    if category is None or staff_role is None:
        return

    for winner in winners:
        # Give each winner a ticket automatically.
        overwrites = {
            channel.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            winner: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            staff_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True,
            ),
        }

        ticket_channel = await channel.guild.create_text_channel(
            name=safe_channel_name(winner.name, "giveaway"),
            category=category,
            overwrites=overwrites,
            reason=f"Giveaway winner ticket for {winner}",
        )
        active_tickets[ticket_channel.id] = winner.id

        msg = await ticket_channel.send(
            f"🎉 Congratulations {winner.mention}!\n\n"
            f"You won the giveaway for **{giveaway['prize']}**.\n\n"
            f"A staff member will assist you shortly.\n{staff_role.mention}"
        )
        try:
            await msg.pin(reason="Giveaway winner ticket opening message")
        except discord.HTTPException:
            pass


async def finish_giveaway(giveaway_id):
    giveaway = active_giveaways.get(giveaway_id)
    if giveaway is None:
        return

    wait_time = max(0, giveaway["end_time"] - timestamp_now())
    await asyncio.sleep(wait_time)

    giveaway = active_giveaways.pop(giveaway_id, None)
    if giveaway is None:
        return

    channel = bot.get_channel(giveaway["channel_id"])
    if channel is None:
        return

    try:
        message = await channel.fetch_message(giveaway_id)
        await message.edit(view=None)
    except discord.HTTPException:
        pass

    entries = list(giveaway["entries"])
    if not entries:
        await channel.send(
            f"🎉 **Giveaway Ended!**\n\n"
            f"**Prize:** {giveaway['prize']}\n\n"
            "Nobody entered the giveaway."
        )
        return

    count = min(giveaway["winner_count"], len(entries))
    winner_ids = random.sample(entries, count)
    await announce_giveaway(giveaway, winner_ids, channel)


@bot.command(name="gwaytrack")
async def giveaway_track(ctx, giveaway_message_id: str = None):
    role = ctx.guild.get_role(GIVEAWAY_COMMAND_ROLE_ID)
    if role is None or role not in ctx.author.roles:
        await ctx.send("❌ You don't have permission to use this command.", delete_after=5)
        return

    if not giveaway_message_id:
        await ctx.send("❌ Usage: `!gwaytrack <giveaway message ID>`", delete_after=5)
        return

    try:
        giveaway_id = int(giveaway_message_id)
    except ValueError:
        await ctx.send("❌ That is not a valid message ID.", delete_after=5)
        return

    giveaway = active_giveaways.get(giveaway_id)
    if giveaway is None:
        await ctx.send(
            "❌ That giveaway is not active or doesn't exist.",
            delete_after=5,
        )
        return

    users = []
    for user_id in giveaway["entries"]:
        try:
            users.append(await bot.fetch_user(user_id))
        except discord.HTTPException:
            pass

    embed = discord.Embed(
        title="🎉 Giveaway Entrants",
        description=(
            f"**Prize:** {giveaway['prize']}\n"
            f"**Entries:** {len(giveaway['entries'])}\n"
            f"**Winners:** {giveaway['winner_count']}\n"
            f"**Ends:** <t:{giveaway['end_time']}:R>\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.gold(),
    )

    if not users:
        embed.description += "\nNo one has entered yet."
    else:
        for index, user in enumerate(users, 1):
            banner = "Yes" if user.banner else "No"
            embed.add_field(
                name=f"#{index}  {user}",
                value=(
                    f"**Username:** `{user}`\n"
                    f"**ID:** `{user.id}`\n"
                    f"**Banner:** {banner}\n"
                    f"[Avatar]({user.display_avatar.url})"
                ),
                inline=False,
            )

    await ctx.send(embed=embed)


@bot.command(name="gwayreroll")
async def giveaway_reroll(ctx, giveaway_message_id: str = None):
    role = ctx.guild.get_role(GIVEAWAY_COMMAND_ROLE_ID)
    if role is None or role not in ctx.author.roles:
        await ctx.send("❌ You don't have permission to use this command.", delete_after=5)
        return

    if not giveaway_message_id:
        await ctx.send("❌ Usage: `!gwayreroll <giveaway message ID>`", delete_after=5)
        return

    try:
        giveaway_id = int(giveaway_message_id)
    except ValueError:
        await ctx.send("❌ Invalid giveaway message ID.", delete_after=5)
        return

    giveaway = active_giveaways.get(giveaway_id)

    # If it is still active, reroll from current entries.
    if giveaway is not None:
        entries = list(giveaway["entries"])
        if not entries:
            await ctx.send("❌ Nobody has entered this giveaway.", delete_after=5)
            return
        winner_id = random.choice(entries)
        await announce_giveaway(giveaway, [winner_id], ctx.channel)
        return

    await ctx.send(
        "❌ That giveaway is no longer active. "
        "This bot only keeps reroll data while the giveaway is active.",
        delete_after=5,
    )


# ============================================================
# MODERATION
# ============================================================

@bot.command()
async def punish(ctx, member: discord.Member):
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ You need Ban Members permission.", delete_after=3)
        return

    try:
        await member.ban(reason=f"Punished by {ctx.author}")
        await ctx.send(f"# {member.mention} has been punished! ❌")
    except discord.HTTPException:
        await ctx.send("❌ I couldn't punish that user.", delete_after=3)


@bot.command()
async def unpunish(ctx, user_id: int):
    if not ctx.author.guild_permissions.ban_members:
        await ctx.send("❌ You need Ban Members permission.", delete_after=3)
        return

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"Unpunished by {ctx.author}")
        await ctx.send(f"# {user.mention} has been unpunished! ✅")
    except discord.NotFound:
        await ctx.send("# User is not banned or could not be found. ❌")
    except discord.Forbidden:
        await ctx.send("# I don't have permission to unban that user. ❌")


@bot.command()
async def mute(ctx, member: discord.Member):
    if not ctx.author.guild_permissions.moderate_members:
        await ctx.send("❌ You need Moderate Members permission.", delete_after=3)
        return

    if member == ctx.author:
        await ctx.send("❌ You cannot mute yourself.", delete_after=3)
        return

    offences = get_mute_offences(ctx.guild.id, member.id) + 1
    set_mute_offences(ctx.guild.id, member.id, offences)

    if offences == 1:
        seconds = 30 * 60
    elif offences == 2:
        seconds = 24 * 60 * 60
    else:
        seconds = 7 * 24 * 60 * 60

    until = discord.utils.utcnow() + __import__("datetime").timedelta(seconds=seconds)

    try:
        await member.timeout(until, reason=f"Mute offence #{offences} by {ctx.author}")
        await ctx.send(f"# {member.mention} has been muted 😂")
    except discord.HTTPException:
        await ctx.send("❌ I couldn't mute that user.", delete_after=3)


@bot.command()
async def unmute(ctx, member: discord.Member):
    if not ctx.author.guild_permissions.moderate_members:
        await ctx.send("❌ You need Moderate Members permission.", delete_after=3)
        return

    try:
        await member.timeout(None, reason=f"Unmuted by {ctx.author}")
        await ctx.send(f"# {member.mention} has been unmuted! 😂")
    except discord.HTTPException:
        await ctx.send("❌ I couldn't unmute that user.", delete_after=3)


@bot.command()
async def purge(ctx, number: int):
    if not ctx.author.guild_permissions.manage_messages:
        return

    if number < 1:
        return

    number = min(number, 100)

    try:
        await ctx.channel.purge(limit=number + 1)
    except discord.HTTPException:
        pass


# ============================================================
# INVITE BLOCKER
# ============================================================

INVITE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite|discordapp\.com/invite)/[A-Za-z0-9-]+",
    re.IGNORECASE,
)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # -------------------- Invite blocker --------------------
    if message.guild and INVITE_REGEX.search(message.content):
        allowed_role = has_role(message.author, INVITE_ALLOWED_ROLE_ID)
        ticket_allowed = is_ticket_channel(message.channel)

        # Role can post invites anywhere.
        # Everyone else can only post invites inside an active ticket.
        if not allowed_role and not ticket_allowed:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

            try:
                await message.author.timeout(
                    discord.utils.utcnow() + __import__("datetime").timedelta(minutes=5),
                    reason="Unauthorized Discord invite link",
                )
            except discord.HTTPException:
                pass

            return

    # -------------------- Counting --------------------
    if (
        message.guild
        and message.channel.id == COUNTING_CHANNEL_ID
    ):
        global counting_number, counting_last_user_id

        content = message.content.strip()

        if not content.isdigit():
            try:
                await message.delete()
            except discord.HTTPException:
                pass

            try:
                await message.author.timeout(
                    discord.utils.utcnow() + __import__("datetime").timedelta(minutes=5),
                    reason="Invalid counting message",
                )
            except discord.HTTPException:
                pass
            return

        number = int(content)

        if (
            number != counting_number
            or message.author.id == counting_last_user_id
        ):
            try:
                await message.delete()
            except discord.HTTPException:
                pass

            try:
                await message.author.timeout(
                    discord.utils.utcnow() + __import__("datetime").timedelta(minutes=5),
                    reason="Incorrect counting message or double count",
                )
            except discord.HTTPException:
                pass
            return

        try:
            await message.add_reaction("✅")
        except discord.HTTPException:
            pass

        counting_number += 1
        counting_last_user_id = message.author.id

        return

    # -------------------- AFK mentions --------------------
    if message.guild:
        mentioned_afk = []
        for member in message.mentions:
            afk_data = get_afk(message.guild.id, member.id)
            if afk_data:
                mentioned_afk.append((member, afk_data))

        for afk_member, afk_data in mentioned_afk:
            reason, started_at = afk_data
            timestamp = f"<t:{started_at}:F>"

            try:
                await message.channel.send(
                    f"hey, {afk_member.mention} is currently not available, "
                    f"I've sent him that you wanted something."
                )
            except discord.HTTPException:
                pass

            try:
                embed = discord.Embed(
                    title="📨 Someone tried to reach you while AFK",
                    description=(
                        f"**{message.author}** tried to reach you.\n\n"
                        f"**Server:** {message.guild.name}\n"
                        f"**Channel:** {message.channel.mention}\n"
                        f"**Time:** {timestamp}\n"
                        f"**Reason:** {reason}"
                    ),
                    color=discord.Color.blurple(),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.set_thumbnail(url=message.author.display_avatar.url)
                embed.set_footer(text="MultipleSMP AFK")
                await afk_member.send(
                    f"Hello {afk_member.mention}, "
                    f"{message.author.mention} tried to reach you while you were AFK.",
                    embed=embed,
                )
            except discord.HTTPException:
                pass

    # -------------------- Ping response --------------------
    if bot.user and bot.user in message.mentions:
        try:
            await message.channel.send(
                f"wsp {message.author.mention}? 👍"
            )
        except discord.HTTPException:
            pass

    # -------------------- Message logging --------------------
    if message.guild:
        log_channel = bot.get_channel(MESSAGE_LOG_CHANNEL_ID)
        if log_channel and log_channel.id != message.channel.id:
            try:
                # No mention parsing: plain text only.
                safe_content = message.content or "[attachment/embed/no text]"
                safe_content = discord.utils.escape_mentions(safe_content)

                embed = discord.Embed(
                    description=safe_content[:4000],
                    color=discord.Color.dark_grey(),
                    timestamp=message.created_at,
                )
                embed.set_author(
                    name=f"{message.author} • {message.channel.name}",
                    icon_url=message.author.display_avatar.url,
                )
                embed.set_footer(
                    text=f"{message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')} • Message ID {message.id}"
                )
                await log_channel.send(embed=embed)
            except discord.HTTPException:
                pass

    await bot.process_commands(message)


# ============================================================
# LOCKDOWN
# ============================================================

@bot.command()
async def lockdown(ctx):
    if not has_role(ctx.author, LOCKDOWN_ROLE_ID):
        await ctx.send("❌ You don't have permission to use lockdown.", delete_after=3)
        return

    if lockdown_saved_permissions:
        await ctx.send("❌ Lockdown is already active.", delete_after=3)
        return

    role = ctx.guild.default_role

    for channel in ctx.guild.channels:
        if not isinstance(
            channel,
            (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.ForumChannel),
        ):
            continue

        try:
            overwrite = channel.overwrites_for(role)
            lockdown_saved_permissions[channel.id] = (
                overwrite.send_messages,
                overwrite.send_messages_in_threads,
            )

            overwrite.send_messages = False
            overwrite.send_messages_in_threads = False
            await channel.set_permissions(
                role,
                overwrite=overwrite,
                reason=f"Server lockdown by {ctx.author}",
            )
        except (discord.Forbidden, discord.HTTPException):
            continue

    await ctx.send("🔒 Server lockdown enabled.", delete_after=3)


@bot.command()
async def unlockdown(ctx):
    if not has_role(ctx.author, LOCKDOWN_ROLE_ID):
        await ctx.send("❌ You don't have permission to unlock the server.", delete_after=3)
        return

    if not lockdown_saved_permissions:
        await ctx.send("❌ Lockdown is not active.", delete_after=3)
        return

    role = ctx.guild.default_role

    for channel_id, (send_messages, send_threads) in list(lockdown_saved_permissions.items()):
        channel = ctx.guild.get_channel(channel_id)
        if channel is None:
            continue

        try:
            overwrite = channel.overwrites_for(role)
            overwrite.send_messages = send_messages
            overwrite.send_messages_in_threads = send_threads
            await channel.set_permissions(
                role,
                overwrite=overwrite,
                reason=f"Server lockdown removed by {ctx.author}",
            )
        except (discord.Forbidden, discord.HTTPException):
            continue

    lockdown_saved_permissions.clear()
    await ctx.send("🔓 Server lockdown disabled.", delete_after=3)


# ============================================================
# COUNT RESET
# ============================================================

@bot.command()
async def countreset(ctx):
    if not has_role(ctx.author, STAFF_ROLE_ID):
        await ctx.send("❌ Only staff can reset the count.", delete_after=3)
        return

    global counting_number, counting_last_user_id
    counting_number = 1
    counting_last_user_id = None
    await ctx.send("✅ Counting has been reset to 1.", delete_after=3)


# ============================================================
# AFK
# ============================================================

@bot.command()
async def afk(ctx, *, reason="AFK"):
    if not has_role(ctx.author, AFK_ROLE_ID):
        await ctx.send("❌ You don't have permission to use AFK.", delete_after=3)
        return

    set_afk(ctx.guild.id, ctx.author.id, reason)

    try:
        await ctx.author.edit(nick=f"(AFK) {ctx.author.name}"[:32])
    except discord.HTTPException:
        pass

    await ctx.send(
        f"{ctx.author.mention} is now AFK. 💤",
        delete_after=5,
    )


# ============================================================
# BASIC COMMANDS
# ============================================================

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")


@bot.command()
async def info(ctx, member: discord.Member = None):
    member = member or ctx.author

    embed = discord.Embed(
        title=f"Info — {member}",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="ID", value=str(member.id), inline=False)

    if member.joined_at:
        embed.add_field(
            name="Joined",
            value=member.joined_at.strftime("%Y-%m-%d"),
            inline=False,
        )

    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command()
async def say(ctx, *, message_text):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    await ctx.send(message_text)


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 Kicked {member.mention}. Reason: {reason}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 Banned {member.mention}. Reason: {reason}")


# ============================================================
# WELCOME
# ============================================================

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        print(f"Welcome channel {WELCOME_CHANNEL_ID} not found.")
        return

    embed = discord.Embed(
        title="Welcome to MultipleSMP! 🎉",
        description=(
            f"Welcome {member.mention} to **MultipleSMP**!\n\n"
            "You are the **goaatt** for joining! tysm ❤️"
        ),
        color=discord.Color.blurple(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    try:
        user = await bot.fetch_user(member.id)
        if user.banner:
            embed.set_image(url=user.banner.url)
    except discord.HTTPException:
        pass

    embed.set_footer(text=f"Member #{member.guild.member_count}")

    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass


# ============================================================
# AFK AUTO-REMOVE WHEN USER SPEAKS
# ============================================================

async def remove_afk_if_needed(message):
    if not message.guild:
        return

    data = get_afk(message.guild.id, message.author.id)
    if not data:
        return

    clear_afk(message.guild.id, message.author.id)

    try:
        # Restore the nickname only if it still has our AFK prefix.
        if message.author.nick and message.author.nick.startswith("(AFK) "):
            await message.author.edit(nick=None)
    except discord.HTTPException:
        pass


# ============================================================
# COMMAND ERROR HANDLER
# ============================================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        return

    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ User not found.", delete_after=3)
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument.", delete_after=3)
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to do that.", delete_after=3)
        return

    if isinstance(error, commands.CommandInvokeError):
        print(f"Command error in {ctx.command}: {error.original}")
        return

    print(f"Unhandled command error: {error}")


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Connected to {len(bot.guilds)} server(s)")
    print("MultipleSMP systems loaded.")

    try:
        bot.add_view(TicketPanelView())
    except ValueError:
        pass

    try:
        bot.add_view(GiveawayView())
    except ValueError:
        pass


# ============================================================
# WRAP MESSAGE EVENT FOR AFK AUTO-REMOVE
# ============================================================

# We use a second listener via the bot's listener system so the
# main on_message above remains responsible for commands.
async def _afk_listener(message):
    if message.author.bot:
        return
    await remove_afk_if_needed(message)


bot.add_listener(_afk_listener, "on_message")


# ============================================================
# RUN
# ============================================================

bot.run(TOKEN)
