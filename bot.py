import os
import random
import re
import asyncio
import time
import datetime

import discord
from discord.ext import commands
from discord import ui


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.environ["TOKEN"]


# ============================================================
# TICKET CONFIG
# ============================================================

TICKET_PANEL_CHANNEL_ID = 1397525433624428554

SUPPORT_CATEGORY_ID = 1536759448226242661
BILLING_CATEGORY_ID = 1536759586168766504
APPEAL_CATEGORY_ID = 1536759712660455474

STAFF_ROLE_ID = 1393951328061095976


# ============================================================
# WELCOME CONFIG
# ============================================================

WELCOME_CHANNEL_ID = 1397563706510151871


# ============================================================
# GIVEAWAY CONFIG
# ============================================================

GIVEAWAY_COMMAND_ROLE_ID = 1391071302890033355
GIVEAWAY_STAFF_ROLE_ID = 1393951328061095976
GIVEAWAY_TICKET_CATEGORY_ID = 1394270405707043059


# ============================================================
# COUNTING CONFIG
# ============================================================

COUNTING_CHANNEL_ID = 1389308013608698058

counting_number = 1
last_counter_id = None


# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ============================================================
# ACTIVE DATA
# ============================================================

active_tickets = {}
active_giveaways = {}


# ============================================================
# TICKET EMBED
# ============================================================

def ticket_embed():
    embed = discord.Embed(
        title="Tickets",
        description=(
            "Need help with anything?\n\n"
            "**Open a ticket**\n"
            "Use the boxes below to choose the category "
            "of your inquiry."
        ),
        color=discord.Color.blurple()
    )

    return embed


# ============================================================
# TICKET DROPDOWN
# ============================================================

class TicketSelect(ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Support/Questions",
                description="Get help or ask a question.",
                emoji="🛠️",
                value="support"
            ),
            discord.SelectOption(
                label="Billing",
                description="Billing questions.",
                emoji="💳",
                value="billing"
            ),
            discord.SelectOption(
                label="Appeal",
                description="Submit an appeal.",
                emoji="⚖️",
                value="appeal"
            )
        ]

        super().__init__(
            placeholder="Choose a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="multiplesmp_ticket_category"
        )

    async def callback(self, interaction):
        await create_ticket(
            interaction,
            self.values[0]
        )


class TicketPanelView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ============================================================
# CREATE NORMAL TICKET
# ============================================================

async def create_ticket(interaction, ticket_type):

    guild = interaction.guild
    user = interaction.user

    for channel_id, creator_id in list(active_tickets.items()):

        if creator_id == user.id:

            existing_channel = guild.get_channel(channel_id)

            if existing_channel:

                await interaction.response.send_message(
                    f"You already have an open ticket: "
                    f"{existing_channel.mention}",
                    ephemeral=True
                )

                return

            active_tickets.pop(channel_id, None)

    categories = {
        "support": SUPPORT_CATEGORY_ID,
        "billing": BILLING_CATEGORY_ID,
        "appeal": APPEAL_CATEGORY_ID
    }

    category = guild.get_channel(
        categories[ticket_type]
    )

    staff_role = guild.get_role(
        STAFF_ROLE_ID
    )

    if category is None:
        await interaction.response.send_message(
            "❌ Ticket category not found.",
            ephemeral=True
        )
        return

    if staff_role is None:
        await interaction.response.send_message(
            "❌ Staff role not found.",
            ephemeral=True
        )
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True
        ),

        staff_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            manage_messages=True
        )
    }

    safe_name = "".join(
        character
        if character.isalnum() or character == "-"
        else "-"
        for character in user.name.lower()
    )

    channel_name = f"ticket-{safe_name}"

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason=f"Ticket created by {user}"
    )

    active_tickets[ticket_channel.id] = user.id

    await interaction.response.send_message(
        f"✅ Your ticket has been created: "
        f"{ticket_channel.mention}",
        ephemeral=True
    )

    message = await ticket_channel.send(
        f"Hello {user.mention}, a staff member will be with you shortly.\n"
        f"{staff_role.mention}"
    )

    try:
        await message.pin(
            reason="Ticket opening message"
        )
    except discord.HTTPException:
        pass


# ============================================================
# SECRET TICKET PANEL COMMAND
# ============================================================

@bot.command(
    name="wedyeu9deufeuiofh39yourhfuohyigfgrg"
)
async def ticket_panel(ctx):

    channel = bot.get_channel(
        TICKET_PANEL_CHANNEL_ID
    )

    if channel is None:
        await ctx.send(
            "❌ I couldn't find the ticket panel channel.",
            delete_after=5
        )
        return

    await channel.send(
        embed=ticket_embed(),
        view=TicketPanelView()
    )

    await ctx.send(
        "✅ Ticket panel posted.",
        delete_after=5
    )


# ============================================================
# CLOSE TICKET
# ============================================================

@bot.command()
async def close(ctx):

    staff_role = ctx.guild.get_role(
        STAFF_ROLE_ID
    )

    if (
        staff_role is None
        or staff_role not in ctx.author.roles
    ):
        await ctx.send(
            "❌ Only staff can close tickets.",
            delete_after=3
        )
        return

    if ctx.channel.id not in active_tickets:
        await ctx.send(
            "❌ This is not a ticket channel.",
            delete_after=3
        )
        return

    active_tickets.pop(
        ctx.channel.id,
        None
    )

    await ctx.channel.delete(
        reason=f"Ticket closed by {ctx.author}"
    )


# ============================================================
# GIVEAWAY DURATION PARSER
# ============================================================

def parse_duration(duration_text):

    duration_text = duration_text.lower().strip()

    pattern = (
        r"^\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(s|sec|secs|second|seconds|"
        r"m|min|mins|minute|minutes|"
        r"h|hr|hrs|hour|hours|"
        r"d|day|days)"
        r"\s*$"
    )

    match = re.match(
        pattern,
        duration_text
    )

    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2)

    if unit in [
        "s", "sec", "secs",
        "second", "seconds"
    ]:
        seconds = amount

    elif unit in [
        "m", "min", "mins",
        "minute", "minutes"
    ]:
        seconds = amount * 60

    elif unit in [
        "h", "hr", "hrs",
        "hour", "hours"
    ]:
        seconds = amount * 60 * 60

    elif unit in [
        "d", "day", "days"
    ]:
        seconds = amount * 60 * 60 * 24

    else:
        return None

    return int(seconds)


# ============================================================
# GIVEAWAY EMBED
# ============================================================

def create_giveaway_embed(giveaway):

    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=(
            f"**Prize**\n"
            f"{giveaway['prize']}\n\n"

            f"**Ends**\n"
            f"<t:{giveaway['end_time']}:R>\n\n"

            f"**Winners**\n"
            f"{giveaway['winner_count']}\n\n"

            f"**Entries**\n"
            f"{len(giveaway['entries'])}\n\n"

            "Click the button below to enter!"
        ),
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="MultipleSMP Giveaway"
    )

    return embed


# ============================================================
# GIVEAWAY CREATOR VIEW
# ============================================================

class GiveawayFormView(ui.View):

    def __init__(self, channel):
        super().__init__(timeout=300)
        self.channel = channel

        self.add_item(
            GiveawayCreateButton()
        )


class GiveawayCreateButton(ui.Button):

    def __init__(self):
        super().__init__(
            label="Create",
            style=discord.ButtonStyle.success
        )

    async def callback(self, interaction):

        await interaction.response.send_modal(
            GiveawayModal(
                self.view.channel
            )
        )


# ============================================================
# GIVEAWAY MODAL
# ============================================================

class GiveawayModal(ui.Modal):

    def __init__(self, channel):

        super().__init__(
            title="Create Giveaway"
        )

        self.channel = channel

        self.prize = ui.TextInput(
            label="Prize",
            placeholder="Example: $20 Steam Gift Card",
            required=True,
            max_length=200
        )

        self.duration = ui.TextInput(
            label="Duration",
            placeholder="Examples: 30s, 10m, 2h, 3d",
            required=True,
            max_length=30
        )

        self.winners = ui.TextInput(
            label="Winners",
            placeholder="Example: 1",
            required=True,
            max_length=3
        )

        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.winners)

    async def on_submit(self, interaction):

        duration_seconds = parse_duration(
            self.duration.value
        )

        if duration_seconds is None:
            await interaction.response.send_message(
                "❌ Invalid duration.\n\n"
                "Examples: `30s`, `10m`, `2h`, `3d`, "
                "`30 mins`, `2 hours`",
                ephemeral=True
            )
            return

        if duration_seconds <= 0:
            await interaction.response.send_message(
                "❌ Duration must be greater than 0.",
                ephemeral=True
            )
            return

        try:
            winner_count = int(
                self.winners.value
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Number of winners must be a number.",
                ephemeral=True
            )
            return

        if winner_count < 1:
            await interaction.response.send_message(
                "❌ You need at least 1 winner.",
                ephemeral=True
            )
            return

        end_time = int(time.time()) + duration_seconds

        giveaway = {
            "message_id": None,
            "channel_id": self.channel.id,
            "prize": self.prize.value,
            "duration": self.duration.value,
            "duration_seconds": duration_seconds,
            "end_time": end_time,
            "winner_count": winner_count,
            "entries": set(),
            "creator_id": interaction.user.id
        }

        giveaway_message = await self.channel.send(
            embed=create_giveaway_embed(
                giveaway
            ),
            view=GiveawayView()
        )

        giveaway["message_id"] = giveaway_message.id

        active_giveaways[
            giveaway_message.id
        ] = giveaway

        await interaction.response.send_message(
            "✅ Giveaway created successfully!",
            ephemeral=True
        )

        asyncio.create_task(
            finish_giveaway(
                giveaway_message.id
            )
        )


# ============================================================
# GIVEAWAY ENTER VIEW
# ============================================================

class GiveawayView(ui.View):

    def __init__(self):
        super().__init__(
            timeout=None
        )

        self.add_item(
            GiveawayEnterButton()
        )


class GiveawayEnterButton(ui.Button):

    def __init__(self):
        super().__init__(
            label="Enter Giveaway",
            emoji="🎉",
            style=discord.ButtonStyle.success,
            custom_id="multiplesmp_giveaway_enter"
        )

    async def callback(self, interaction):

        giveaway = active_giveaways.get(
            interaction.message.id
        )

        if giveaway is None:
            await interaction.response.send_message(
                "❌ This giveaway has already ended.",
                ephemeral=True
            )
            return

        entries = giveaway["entries"]

        if interaction.user.id in entries:

            entries.remove(
                interaction.user.id
            )

            response = "❌ You have left the giveaway."

        else:

            entries.add(
                interaction.user.id
            )

            response = "🎉 You have entered the giveaway!"

        try:
            await interaction.message.edit(
                embed=create_giveaway_embed(
                    giveaway
                ),
                view=GiveawayView()
            )
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            response,
            ephemeral=True
        )


# ============================================================
# GIVEAWAY TRACK
# ============================================================

@bot.command(
    name="gwaytrack"
)
async def giveaway_track(
    ctx,
    giveaway_message_id: str = None
):

    giveaway_role = ctx.guild.get_role(
        GIVEAWAY_COMMAND_ROLE_ID
    )

    if giveaway_role is None:
        await ctx.send(
            "❌ Giveaway command role was not found.",
            delete_after=5
        )
        return

    if giveaway_role not in ctx.author.roles:
        await ctx.send(
            "❌ You don't have permission to use this command.",
            delete_after=5
        )
        return

    if giveaway_message_id is None:
        await ctx.send(
            "❌ Usage: `!gwaytrack <giveaway message ID>`",
            delete_after=5
        )
        return

    try:
        giveaway_id = int(
            giveaway_message_id
        )
    except ValueError:
        await ctx.send(
            "❌ That is not a valid message ID.",
            delete_after=5
        )
        return

    giveaway = active_giveaways.get(
        giveaway_id
    )

    if giveaway is None:
        await ctx.send(
            "❌ That giveaway is not active or doesn't exist.",
            delete_after=5
        )
        return

    entrant_ids = list(
        giveaway["entries"]
    )

    if not entrant_ids:

        embed = discord.Embed(
            title="🎉 Giveaway Entrants",
            description=(
                f"**Prize:** {giveaway['prize']}\n\n"
                "**Entries:** 0\n\n"
                "Nobody has entered the giveaway yet."
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text=f"Giveaway ID: {giveaway_id}"
        )

        await ctx.send(
            embed=embed
        )

        return

    users = []

    for user_id in entrant_ids:

        try:
            user = await bot.fetch_user(
                user_id
            )
            users.append(user)

        except discord.HTTPException:
            continue

    pages = []

    users_per_page = 5

    for page_start in range(
        0,
        len(users),
        users_per_page
    ):

        page_users = users[
            page_start:
            page_start + users_per_page
        ]

        embed = discord.Embed(
            title="🎉 Giveaway Entrants",
            description=(
                f"**Prize:** {giveaway['prize']}\n"
                f"**Total Entries:** "
                f"{len(entrant_ids)}\n"
                f"**Winners:** "
                f"{giveaway['winner_count']}\n"
                f"**Ends:** "
                f"<t:{giveaway['end_time']}:R>\n\n"
                "━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.gold()
        )

        for index, user in enumerate(
            page_users,
            start=page_start + 1
        ):

            banner_text = "No banner"

            try:

                full_user = await bot.fetch_user(
                    user.id
                )

                if full_user.banner:
                    banner_text = "Has banner"

            except discord.HTTPException:
                pass

            embed.add_field(
                name=f"#{index}  {user.name}",
                value=(
                    f"**Username:** `{user}`\n"
                    f"**ID:** `{user.id}`\n"
                    f"**Banner:** {banner_text}\n"
                    f"[Avatar]({user.display_avatar.url})"
                ),
                inline=False
            )

        if page_users:
            embed.set_thumbnail(
                url=page_users[0].display_avatar.url
            )

        total_pages = (
            (len(users) - 1) // users_per_page
        ) + 1

        embed.set_footer(
            text=(
                f"Page "
                f"{(page_start // users_per_page) + 1}"
                f"/{total_pages}"
                f" • Giveaway ID: {giveaway_id}"
            )
        )

        pages.append(embed)

    if len(pages) == 1:
        await ctx.send(
            embed=pages[0]
        )
        return

    await ctx.send(
        embed=pages[0],
        view=GiveawayTrackView(
            pages,
            ctx.author.id
        )
    )


# ============================================================
# GIVEAWAY TRACK PAGINATION
# ============================================================

class GiveawayTrackView(ui.View):

    def __init__(
        self,
        pages,
        author_id
    ):

        super().__init__(
            timeout=180
        )

        self.pages = pages
        self.author_id = author_id
        self.current_page = 0

        self.previous_button.disabled = True

        if len(pages) <= 1:
            self.next_button.disabled = True

    @ui.button(
        label="Previous",
        emoji="⬅️",
        style=discord.ButtonStyle.secondary
    )
    async def previous_button(
        self,
        interaction,
        button
    ):

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the person who used `!gwaytrack` "
                "can control these buttons.",
                ephemeral=True
            )
            return

        if self.current_page > 0:
            self.current_page -= 1

        self.previous_button.disabled = (
            self.current_page == 0
        )

        self.next_button.disabled = (
            self.current_page == len(self.pages) - 1
        )

        await interaction.response.edit_message(
            embed=self.pages[
                self.current_page
            ],
            view=self
        )

    @ui.button(
        label="Next",
        emoji="➡️",
        style=discord.ButtonStyle.secondary
    )
    async def next_button(
        self,
        interaction,
        button
    ):

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the person who used `!gwaytrack` "
                "can control these buttons.",
                ephemeral=True
            )
            return

        if self.current_page < len(self.pages) - 1:
            self.current_page += 1

        self.previous_button.disabled = (
            self.current_page == 0
        )

        self.next_button.disabled = (
            self.current_page == len(self.pages) - 1
        )

        await interaction.response.edit_message(
            embed=self.pages[
                self.current_page
            ],
            view=self
        )


# ============================================================
# FINISH GIVEAWAY
# ============================================================

async def finish_giveaway(giveaway_id):

    giveaway = active_giveaways.get(
        giveaway_id
    )

    if giveaway is None:
        return

    wait_time = max(
        0,
        giveaway["end_time"] - int(time.time())
    )

    await asyncio.sleep(
        wait_time
    )

    giveaway = active_giveaways.pop(
        giveaway_id,
        None
    )

    if giveaway is None:
        return

    channel = bot.get_channel(
        giveaway["channel_id"]
    )

    if channel is None:
        return

    try:

        giveaway_message = await channel.fetch_message(
            giveaway["message_id"]
        )

        await giveaway_message.edit(
            view=None
        )

    except discord.HTTPException:
        pass

    entries = list(
        giveaway["entries"]
    )

    if not entries:

        await channel.send(
            "🎉 **Giveaway Ended!**\n\n"
            f"**Prize:** {giveaway['prize']}\n\n"
            "Unfortunately, nobody entered the giveaway."
        )

        return

    winner_count = min(
        giveaway["winner_count"],
        len(entries)
    )

    winner_ids = random.sample(
        entries,
        winner_count
    )

    winners = []

    for user_id in winner_ids:

        try:

            user = await bot.fetch_user(
                user_id
            )

            winners.append(user)

        except discord.HTTPException:
            continue

    if not winners:

        await channel.send(
            "❌ The giveaway ended, but I couldn't "
            "find the winners."
        )

        return

    winner_mentions = " ".join(
        user.mention
        for user in winners
    )

    staff_role = channel.guild.get_role(
        GIVEAWAY_STAFF_ROLE_ID
    )

    if staff_role:
        staff_mention = staff_role.mention
    else:
        staff_mention = ""

    await channel.send(
        f"🎉 **GIVEAWAY WINNERS!** 🎉\n\n"
        f"**Prize:** {giveaway['prize']}\n\n"
        f"Congratulations to:\n"
        f"{winner_mentions}\n\n"
        f"{staff_mention}"
    )

    category = channel.guild.get_channel(
        GIVEAWAY_TICKET_CATEGORY_ID
    )

    if category is None:
        await channel.send(
            "⚠️ I couldn't create the winner tickets "
            "because the giveaway ticket category "
            "was not found."
        )
        return

    if staff_role is None:
        await channel.send(
            "⚠️ I couldn't create the winner tickets "
            "because the staff role was not found."
        )
        return

    for winner in winners:

        overwrites = {

            channel.guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            winner:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                ),

            staff_role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True
                )
        }

        safe_name = "".join(
            character
            if character.isalnum() or character == "-"
            else "-"
            for character in winner.name.lower()
        )

        ticket_channel = await channel.guild.create_text_channel(
            name=f"giveaway-{safe_name}",
            category=category,
            overwrites=overwrites,
            reason=f"Giveaway winner ticket for {winner}"
        )

        active_tickets[
            ticket_channel.id
        ] = winner.id

        ticket_message = await ticket_channel.send(
            f"🎉 Congratulations {winner.mention}!\n\n"
            f"You won the giveaway for:\n"
            f"**{giveaway['prize']}**\n\n"
            f"A staff member will assist you shortly.\n"
            f"{staff_role.mention}"
        )

        try:
            await ticket_message.pin(
                reason="Giveaway winner ticket opening message"
            )
        except discord.HTTPException:
            pass


# ============================================================
# GIVEAWAY COMMAND
# ============================================================

@bot.command(
    name="gway"
)
async def giveaway_command(ctx):

    role = ctx.guild.get_role(
        GIVEAWAY_COMMAND_ROLE_ID
    )

    if role is None:
        await ctx.send(
            "❌ Giveaway command role was not found.",
            delete_after=5
        )
        return

    if role not in ctx.author.roles:
        await ctx.send(
            "❌ You don't have permission to create giveaways.",
            delete_after=5
        )
        return

    try:

        await ctx.author.send(
            "📋 **Giveaway Creator**\n\n"
            "Click **Create** below to set up your giveaway.",
            view=GiveawayFormView(
                ctx.channel
            )
        )

    except discord.Forbidden:

        await ctx.send(
            "❌ I couldn't DM you. "
            "Please enable DMs from server members.",
            delete_after=5
        )

        return

    await ctx.send(
        "✅ I've sent the giveaway form to your DMs.",
        delete_after=5
    )


# ============================================================
# PING
# ============================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        f"🏓 Pong! `{round(bot.latency * 1000)}ms`"
    )


# ============================================================
# PUNISH
# ============================================================

@bot.command()
@commands.has_permissions(ban_members=True)
async def punish(
    ctx,
    member: discord.Member
):

    await member.ban(
        reason=f"Banned by {ctx.author}"
    )

    await ctx.send(
        f"# {member.mention} has been punished! ❌"
    )


# ============================================================
# UNPUNISH
# ============================================================

@bot.command()
@commands.has_permissions(ban_members=True)
async def unpunish(
    ctx,
    user_id: int
):

    try:

        user = await bot.fetch_user(
            user_id
        )

        await ctx.guild.unban(
            user,
            reason=f"Unpunished by {ctx.author}"
        )

        await ctx.send(
            f"# {user.mention} has been unpunished! ✅"
        )

    except discord.NotFound:

        await ctx.send(
            "# User is not banned or could not be found. ❌"
        )

    except discord.Forbidden:

        await ctx.send(
            "# I don't have permission to unban that user. ❌"
        )


# ============================================================
# INFO
# ============================================================

@bot.command()
async def info(
    ctx,
    member: discord.Member = None
):

    member = member or ctx.author

    embed = discord.Embed(
        title=f"Info — {member}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="ID",
        value=str(member.id),
        inline=False
    )

    if member.joined_at:

        embed.add_field(
            name="Joined",
            value=member.joined_at.strftime(
                "%Y-%m-%d"
            ),
            inline=False
        )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# KICK
# ============================================================

@bot.command()
@commands.has_permissions(
    kick_members=True
)
async def kick(
    ctx,
    member: discord.Member,
    *,
    reason="No reason"
):

    await member.kick(
        reason=reason
    )

    await ctx.send(
        f"👢 Kicked {member.mention}. "
        f"Reason: {reason}"
    )


# ============================================================
# BAN
# ============================================================

@bot.command()
@commands.has_permissions(
    ban_members=True
)
async def ban(
    ctx,
    member: discord.Member,
    *,
    reason="No reason"
):

    await member.ban(
        reason=reason
    )

    await ctx.send(
        f"🔨 Banned {member.mention}. "
        f"Reason: {reason}"
    )


# ============================================================
# WELCOME
# ============================================================

@bot.event
async def on_member_join(member):

    channel = bot.get_channel(
        WELCOME_CHANNEL_ID
    )

    if channel is None:

        print(
            f"Welcome channel "
            f"{WELCOME_CHANNEL_ID} not found."
        )

        return

    embed = discord.Embed(
        title="Welcome to MultipleSMP! 🎉",
        description=(
            f"Welcome {member.mention} to **MultipleSMP**!\n\n"
            "You are the **goaatt** for joining! tysm ❤️"
        ),
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    try:

        user = await bot.fetch_user(
            member.id
        )

        if user.banner:

            embed.set_image(
                url=user.banner.url
            )

    except discord.HTTPException:
        pass

    embed.set_footer(
        text=f"Member #{member.guild.member_count}"
    )

    await channel.send(
        embed=embed
    )


# ============================================================
# COUNTING SYSTEM
# ============================================================

@bot.event
async def on_message(message):

    global counting_number
    global last_counter_id

    # Ignore bots
    if message.author.bot:
        return

    # ========================================================
    # COUNTING CHANNEL
    # ========================================================

    if message.channel.id == COUNTING_CHANNEL_ID:

        # ----------------------------------------------------
        # Must be a number
        # ----------------------------------------------------

        try:

            number = int(
                message.content.strip()
            )

        except ValueError:

            try:
                await message.delete()
            except discord.HTTPException:
                pass

            try:

                await message.author.timeout(
                    datetime.timedelta(minutes=5),
                    reason="Invalid counting message"
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

            return

        # ----------------------------------------------------
        # Can't count twice in a row
        # ----------------------------------------------------

        if message.author.id == last_counter_id:

            try:
                await message.delete()
            except discord.HTTPException:
                pass

            try:

                await message.author.timeout(
                    datetime.timedelta(minutes=5),
                    reason="Counting twice in a row"
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

            return

        # ----------------------------------------------------
        # Wrong number
        # ----------------------------------------------------

        if number != counting_number:

            try:
                await message.delete()
            except discord.HTTPException:
                pass

            try:

                await message.author.timeout(
                    datetime.timedelta(minutes=5),
                    reason="Wrong counting number"
                )

            except (
                discord.Forbidden,
                discord.HTTPException
            ):
                pass

            return

        # ----------------------------------------------------
        # Correct number
        # ----------------------------------------------------

        try:

            await message.add_reaction(
                "✅"
            )

        except discord.HTTPException:
            pass

        last_counter_id = message.author.id

        counting_number += 1

        return

    # ========================================================
    # ALL OTHER MESSAGES / COMMANDS
    # ========================================================

    await bot.process_commands(message)


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user}"
    )

    print(
        f"Connected to {len(bot.guilds)} server(s)"
    )

    print(
        "Ticket system loaded."
    )

    print(
        "Welcome system loaded."
    )

    print(
        "Giveaway system loaded."
    )

    print(
        "Counting system loaded."
    )

    try:

        bot.add_view(
            TicketPanelView()
        )

    except ValueError:
        pass

    try:

        bot.add_view(
            GiveawayView()
        )

    except ValueError:
        pass


# ============================================================
# RUN BOT
# ============================================================

bot.run(TOKEN)