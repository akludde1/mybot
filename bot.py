import os
import discord
from discord.ext import commands
from discord import ui

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.environ["TOKEN"]

# Ticket panel channel
TICKET_PANEL_CHANNEL_ID = 1397525433624428554

# Ticket categories
SUPPORT_CATEGORY_ID = 1536759448226242661
BILLING_CATEGORY_ID = 1536759586168766504
APPEAL_CATEGORY_ID = 1536759712660455474

# Staff role
STAFF_ROLE_ID = 1536746004110516306

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

# Stores active tickets while the bot is running
active_tickets = {}


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

        self.add_item(
            TicketSelect()
        )


# ============================================================
# CREATE TICKET
# ============================================================

async def create_ticket(
    interaction,
    ticket_type
):

    guild = interaction.guild
    user = interaction.user

    # Check if the user already has an open ticket
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

    # Select category
    categories = {
        "support": SUPPORT_CATEGORY_ID,
        "billing": BILLING_CATEGORY_ID,
        "appeal": APPEAL_CATEGORY_ID
    }

    category = guild.get_channel(
        categories[ticket_type]
    )

    # Get staff role
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

    # ========================================================
    # CHANNEL PERMISSIONS
    # ========================================================

    overwrites = {

        # Nobody else can see the ticket
        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        # Ticket creator
        user:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),

        # Staff
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

    # ========================================================
    # CHANNEL NAME
    # ========================================================

    safe_name = "".join(
        character
        if character.isalnum() or character == "-"
        else "-"
        for character in user.name.lower()
    )

    channel_name = f"ticket-{safe_name}"

    # ========================================================
    # CREATE CHANNEL
    # ========================================================

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        reason=f"Ticket created by {user}"
    )

    active_tickets[ticket_channel.id] = user.id

    # Tell user privately that ticket was created
    await interaction.response.send_message(
        f"✅ Your ticket has been created: "
        f"{ticket_channel.mention}",
        ephemeral=True
    )

    # ========================================================
    # FIRST MESSAGE
    # ========================================================

    message = await ticket_channel.send(
        f"Hello {user.mention}, a staff member will be with you shortly.\n"
        f"{staff_role.mention}"
    )

    # Pin opening message
    await message.pin(
        reason="Ticket opening message"
    )


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

    # Only staff can close tickets
    if staff_role is None or staff_role not in ctx.author.roles:

        await ctx.send(
            "❌ Only staff can close tickets.",
            delete_after=3
        )

        return

    # Make sure this is a ticket
    if ctx.channel.id not in active_tickets:

        await ctx.send(
            "❌ This is not a ticket channel.",
            delete_after=3
        )

        return

    # Remove from active ticket list
    active_tickets.pop(
        ctx.channel.id,
        None
    )

    # Delete immediately
    await ctx.channel.delete(
        reason=f"Ticket closed by {ctx.author}"
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
async def say(ctx, *, message):

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    await ctx.send(message)


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
            value=member.joined_at.strftime("%Y-%m-%d"),
            inline=False
        )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await ctx.send(
        embed=embed
    )


@bot.command()
@commands.has_permissions(kick_members=True)
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
@commands.has_permissions(ban_members=True)
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
# MEMBER JOIN
# ============================================================

@bot.event
async def on_member_join(member):

    channel = member.guild.system_channel

    if channel:

        await channel.send(
            f"Welcome {member.mention}!"
        )


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print(f"Connected to {len(bot.guilds)} server(s)")
    print("Ticket system loaded.")

    # Make ticket dropdown survive bot restarts
    bot.add_view(
        TicketPanelView()
    )


# ============================================================
# RUN BOT
# ============================================================

bot.run(TOKEN)