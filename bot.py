import os
import random
import re
import asyncio

import discord
from discord.ext import commands
from discord import ui


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.environ["TOKEN"]

# ---------------- TICKETS ----------------

TICKET_PANEL_CHANNEL_ID = 1397525433624428554

SUPPORT_CATEGORY_ID = 1536759448226242661
BILLING_CATEGORY_ID = 1536759586168766504
APPEAL_CATEGORY_ID = 1536759712660455474

STAFF_ROLE_ID = 1393951328061095976

# ---------------- WELCOME ----------------

WELCOME_CHANNEL_ID = 1397563706510151871

# ---------------- GIVEAWAYS ----------------

# Role allowed to use !gway
GIVEAWAY_COMMAND_ROLE_ID = 1391071302890033355

# Staff role pinged when winners are announced
GIVEAWAY_STAFF_ROLE_ID = 1393951328061095976

# Category for automatic giveaway winner tickets
GIVEAWAY_TICKET_CATEGORY_ID = 1394270405707043059


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
# ACTIVE TICKETS
# ============================================================

# channel_id -> creator_id
active_tickets = {}


# ============================================================
# ACTIVE GIVEAWAYS
# ============================================================

# giveaway_message_id -> giveaway information
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

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketSelect()
        )


# ============================================================
# CREATE NORMAL TICKET
# ============================================================

async def create_ticket(
    interaction,
    ticket_type
):

    guild = interaction.guild
    user = interaction.user

    # --------------------------------------------------------
    # Check existing ticket
    # --------------------------------------------------------

    for channel_id, creator_id in active_tickets.items():

        if creator_id == user.id:

            existing_channel = guild.get_channel(
                channel_id
            )

            if existing_channel:

                await interaction.response.send_message(
                    f"You already have an open ticket: "
                    f"{existing_channel.mention}",
                    ephemeral=True
                )

                return

    # --------------------------------------------------------
    # Categories
    # --------------------------------------------------------

    categories = {

        "support": SUPPORT_CATEGORY_ID,

        "billing": BILLING_CATEGORY_ID,

        "appeal": APPEAL_CATEGORY_ID

    }

    category = guild.get_channel(
        categories[ticket_type]
    )

    # --------------------------------------------------------
    # Staff role
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Permissions
    # --------------------------------------------------------

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        user:
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

    # --------------------------------------------------------
    # Channel name
    # --------------------------------------------------------

    safe_name = "".join(
        character
        if character.isalnum() or character == "-"
        else "-"
        for character in user.name.lower()
    )

    channel_name = f"ticket-{safe_name}"

    # --------------------------------------------------------
    # Create channel
    # --------------------------------------------------------

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason=f"Ticket created by {user}"
    )

    active_tickets[
        ticket_channel.id
    ] = user.id

    # --------------------------------------------------------
    # Private confirmation
    # --------------------------------------------------------

    await interaction.response.send_message(
        f"✅ Your ticket has been created: "
        f"{ticket_channel.mention}",
        ephemeral=True
    )

    # --------------------------------------------------------
    # Opening message
    # --------------------------------------------------------

    message = await ticket_channel.send(
        f"Hello {user.mention}, a staff member will be with you shortly.\n"
        f"{staff_role.mention}"
    )

    # --------------------------------------------------------
    # Pin message
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Staff check
    # --------------------------------------------------------

    if (
        staff_role is None
        or staff_role not in ctx.author.roles
    ):

        await ctx.send(
            "❌ Only staff can close tickets.",
            delete_after=3
        )

        return

    # --------------------------------------------------------
    # Ticket check
    # --------------------------------------------------------

    if ctx.channel.id not in active_tickets:

        await ctx.send(
            "❌ This is not a ticket channel.",
            delete_after=3
        )

        return

    # --------------------------------------------------------
    # Remove from active tickets
    # --------------------------------------------------------

    active_tickets.pop(
        ctx.channel.id,
        None
    )

    # --------------------------------------------------------
    # Delete immediately
    # --------------------------------------------------------

    await ctx.channel.delete(
        reason=f"Ticket closed by {ctx.author}"
    )


# ============================================================
# GIVEAWAY DURATION PARSER
# ============================================================

def parse_duration(duration_text):

    duration_text = (
        duration_text
        .lower()
        .strip()
    )

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

    amount = float(
        match.group(1)
    )

    unit = match.group(2)

    # Seconds
    if unit in [
        "s",
        "sec",
        "secs",
        "second",
        "seconds"
    ]:

        seconds = amount

    # Minutes
    elif unit in [
        "m",
        "min",
        "mins",
        "minute",
        "minutes"
    ]:

        seconds = amount * 60

    # Hours
    elif unit in [
        "h",
        "hr",
        "hrs",
        "hour",
        "hours"
    ]:

        seconds = amount * 60 * 60

    # Days
    elif unit in [
        "d",
        "day",
        "days"
    ]:

        seconds = amount * 60 * 60 * 24

    else:

        return None

    return int(seconds)


# ============================================================
# GIVEAWAY FORM VIEW
# ============================================================

class GiveawayFormView(ui.View):

    def __init__(self, channel):

        super().__init__(
            timeout=300
        )

        self.channel = channel

    @ui.button(
        label="Create Giveaway",
        style=discord.ButtonStyle.success
    )
    async def create(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            GiveawayModal(
                self.channel
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
            label="Number of Winners",
            placeholder="Example: 1",
            required=True,
            max_length=3
        )

        self.add_item(
            self.prize
        )

        self.add_item(
            self.duration
        )

        self.add_item(
            self.winners
        )

    async def on_submit(
        self,
        interaction
    ):

        # ----------------------------------------------------
        # Parse duration
        # ----------------------------------------------------

        duration_seconds = parse_duration(
            self.duration.value
        )

        if duration_seconds is None:

            await interaction.response.send_message(
                "❌ Invalid duration.\n\n"
                "Examples:\n"
                "`30s`\n"
                "`10m`\n"
                "`2h`\n"
                "`3d`\n"
                "`30 mins`\n"
                "`2 hours`",
                ephemeral=True
            )

            return

        # ----------------------------------------------------
        # Parse winners
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Create giveaway message
        # ----------------------------------------------------

        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=(
                f"**Prize**\n"
                f"{self.prize.value}\n\n"

                f"**Duration**\n"
                f"{self.duration.value}\n\n"

                f"**Winners**\n"
                f"{winner_count}\n\n"

                "Click the button below to enter!"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="MultipleSMP Giveaway"
        )

        giveaway_message = await self.channel.send(
            embed=embed,
            view=GiveawayView()
        )

        # ----------------------------------------------------
        # Store giveaway
        # ----------------------------------------------------

        giveaway_id = giveaway_message.id

        active_giveaways[
            giveaway_id
        ] = {

            "message_id":
                giveaway_id,

            "channel_id":
                self.channel.id,

            "prize":
                self.prize.value,

            "duration":
                self.duration.value,

            "duration_seconds":
                duration_seconds,

            "winner_count":
                winner_count,

            "entries":
                set(),

            "creator_id":
                interaction.user.id

        }

        # ----------------------------------------------------
        # Confirm privately
        # ----------------------------------------------------

        await interaction.response.send_message(
            "✅ Giveaway created successfully!",
            ephemeral=True
        )

        # ----------------------------------------------------
        # Start timer
        # ----------------------------------------------------

        asyncio.create_task(
            finish_giveaway(
                giveaway_id
            )
        )


# ============================================================
# GIVEAWAY ENTRY VIEW
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

    async def callback(
        self,
        interaction
    ):

        giveaway = active_giveaways.get(
            interaction.message.id
        )

        if giveaway is None:

            await interaction.response.send_message(
                "❌ This giveaway has already ended.",
                ephemeral=True
            )

            return

        entries = giveaway[
            "entries"
        ]

        # ----------------------------------------------------
        # Leave giveaway if already entered
        # ----------------------------------------------------

        if interaction.user.id in entries:

            entries.remove(
                interaction.user.id
            )

            await interaction.response.send_message(
                "❌ You have left the giveaway.",
                ephemeral=True
            )

            return

        # ----------------------------------------------------
        # Enter giveaway
        # ----------------------------------------------------

        entries.add(
            interaction.user.id
        )

        await interaction.response.send_message(
            "🎉 You have entered the giveaway!",
            ephemeral=True
        )


# ============================================================
# FINISH GIVEAWAY
# ============================================================

async def finish_giveaway(
    giveaway_id
):

    giveaway = active_giveaways.get(
        giveaway_id
    )

    if giveaway is None:

        return

    # --------------------------------------------------------
    # Wait for giveaway duration
    # --------------------------------------------------------

    await asyncio.sleep(
        giveaway["duration_seconds"]
    )

    # --------------------------------------------------------
    # Remove active giveaway
    # --------------------------------------------------------

    giveaway = active_giveaways.pop(
        giveaway_id,
        None
    )

    if giveaway is None:

        return

    # --------------------------------------------------------
    # Get channel
    # --------------------------------------------------------

    channel = bot.get_channel(
        giveaway["channel_id"]
    )

    if channel is None:

        return

    # --------------------------------------------------------
    # Disable giveaway button
    # --------------------------------------------------------

    try:

        giveaway_message = await channel.fetch_message(
            giveaway["message_id"]
        )

        await giveaway_message.edit(
            view=None
        )

    except discord.HTTPException:

        pass

    # --------------------------------------------------------
    # Get entries
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Pick winners
    # --------------------------------------------------------

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

            winners.append(
                user
            )

        except discord.HTTPException:

            pass

    if not winners:

        await channel.send(
            "❌ The giveaway ended, but I couldn't find "
            "the winners."
        )

        return

    # --------------------------------------------------------
    # Winner mentions
    # --------------------------------------------------------

    winner_mentions = " ".join(
        user.mention
        for user in winners
    )

    # --------------------------------------------------------
    # Staff role
    # --------------------------------------------------------

    staff_role = channel.guild.get_role(
        GIVEAWAY_STAFF_ROLE_ID
    )

    if staff_role:

        staff_mention = staff_role.mention

    else:

        staff_mention = ""

    # --------------------------------------------------------
    # Winner announcement
    # --------------------------------------------------------

    await channel.send(
        f"🎉 **GIVEAWAY WINNERS!** 🎉\n\n"
        f"**Prize:** {giveaway['prize']}\n\n"
        f"Congratulations to:\n"
        f"{winner_mentions}\n\n"
        f"{staff_mention}"
    )

    # --------------------------------------------------------
    # Winner ticket category
    # --------------------------------------------------------

    category = channel.guild.get_channel(
        GIVEAWAY_TICKET_CATEGORY_ID
    )

    if category is None:

        await channel.send(
            "⚠️ I couldn't create the winner tickets because "
            "the giveaway ticket category was not found."
        )

        return

    # --------------------------------------------------------
    # Staff role check
    # --------------------------------------------------------

    if staff_role is None:

        await channel.send(
            "⚠️ I couldn't create the winner tickets because "
            "the staff role was not found."
        )

        return

    # --------------------------------------------------------
    # Create ticket for every winner
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Role doesn't exist
    # --------------------------------------------------------

    if role is None:

        await ctx.send(
            "❌ Giveaway command role was not found.",
            delete_after=5
        )

        return

    # --------------------------------------------------------
    # Permission check
    # --------------------------------------------------------

    if role not in ctx.author.roles:

        await ctx.send(
            "❌ You don't have permission to create giveaways.",
            delete_after=5
        )

        return

    # --------------------------------------------------------
    # Open form privately in DM
    # --------------------------------------------------------

    try:

        await ctx.author.send(
            "📋 **Giveaway Creator**\n\n"
            "Click the button below to create your giveaway.",
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
# BASIC COMMANDS
# ============================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        f"🏓 Pong! `{round(bot.latency * 1000)}ms`"
    )


@bot.command()
async def say(
    ctx,
    *,
    message
):

    try:

        await ctx.message.delete()

    except discord.Forbidden:

        pass

    await ctx.send(
        message
    )


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
# WELCOME MESSAGE
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

    # --------------------------------------------------------
    # Welcome embed
    # --------------------------------------------------------

    embed = discord.Embed(
        title="Welcome to MultipleSMP! 🎉",
        description=(
            f"Welcome {member.mention} to **MultipleSMP**!\n\n"
            "You are the **goaatt** for joining! tysm ❤️"
        ),
        color=discord.Color.blurple()
    )

    # --------------------------------------------------------
    # Profile picture
    # --------------------------------------------------------

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    # --------------------------------------------------------
    # Discord banner
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Footer
    # --------------------------------------------------------

    embed.set_footer(
        text=f"Member #{member.guild.member_count}"
    )

    await channel.send(
        embed=embed
    )


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

    # --------------------------------------------------------
    # Persistent ticket button
    # --------------------------------------------------------

    try:

        bot.add_view(
            TicketPanelView()
        )

    except ValueError:

        pass

    # --------------------------------------------------------
    # Persistent giveaway button
    # --------------------------------------------------------

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