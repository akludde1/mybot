```python
import os
import discord
from discord.ext import commands
from discord import ui

TOKEN = os.environ["TOKEN"]

# ============================================================
# CHANNEL / ROLE IDS
# ============================================================

# Staff applications
APPLICATION_POST_CHANNEL_ID = 1536742885200756856
APPLICATION_REVIEW_CHANNEL_ID = 1536744148042911974

# Tickets
TICKET_PANEL_CHANNEL_ID = 1536754341535424633

SUPPORT_CATEGORY_ID = 1536753783021904053
BILLING_CATEGORY_ID = 1536754163289956412
APPEAL_CATEGORY_ID = 1536754243610873976

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

# ============================================================
# APPLICATION SYSTEM
# ============================================================

QUESTIONS = [
    "What's your age?",
    "What's your Discord username?",
    "What's your country & timezone?",
    "How many hours per week can you dedicate to MultipleSMP?",
    "Do you have any prior staff experience? If yes, describe it.",
    "Why do you want to become a Helper on MultipleSMP?",
    "How would you handle a situation where two players are arguing?",
    "Have you ever been punished on MultipleSMP or any other server? Explain.",
    "What makes you stand out from other applicants?",
    "Is there anything else you'd like us to know about you?"
]

active_applications = {}


def application_embed():
    embed = discord.Embed(
        title="Staff Application",
        description=(
            "**Apply For Staff @ MultipleSMP.net**\n\n"
            "Want to join the team and help the community?\n\n"
            "Click the button below to **Apply For Helper**.\n\n"
            "The application will open as forms. "
            "We will respond via DMs with your results."
        ),
        color=discord.Color.green()
    )

    return embed


class ApplyView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Apply",
        style=discord.ButtonStyle.success,
        custom_id="multiplesmp_staff_apply"
    )
    async def apply_button(self, interaction, button):

        if interaction.user.id in active_applications:
            await interaction.response.send_message(
                "You already have an active application.",
                ephemeral=True
            )
            return

        active_applications[interaction.user.id] = {
            "user": interaction.user,
            "answers": [],
            "current_question": 0
        }

        await interaction.response.send_message(
            "Your application is starting.",
            ephemeral=True
        )

        await send_question(
            interaction,
            interaction.user.id
        )


async def send_question(interaction, user_id):

    application = active_applications.get(user_id)

    if not application:
        return

    number = application["current_question"]

    if number >= len(QUESTIONS):
        return

    await interaction.followup.send(
        f"**Question {number + 1} of {len(QUESTIONS)}**\n\n"
        f"{QUESTIONS[number]}",
        view=QuestionView(user_id, number),
        ephemeral=True
    )


class QuestionView(ui.View):

    def __init__(self, user_id, question_number):
        super().__init__(timeout=None)

        self.user_id = user_id
        self.question_number = question_number

    @ui.button(
        label="Answer Question",
        style=discord.ButtonStyle.primary
    )
    async def answer_button(self, interaction, button):

        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your application.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            QuestionModal(
                self.user_id,
                self.question_number
            )
        )


class QuestionModal(ui.Modal):

    def __init__(self, user_id, question_number):

        self.user_id = user_id
        self.question_number = question_number

        super().__init__(
            title=f"Question {question_number + 1}"
        )

        self.answer = ui.TextInput(
            label=QUESTIONS[question_number][:45],
            placeholder="Type your answer here...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(self.answer)

    async def on_submit(self, interaction):

        application = active_applications.get(self.user_id)

        if not application:
            await interaction.response.send_message(
                "Your application is no longer active.",
                ephemeral=True
            )
            return

        application["answers"].append(self.answer.value)

        next_question = self.question_number + 1

        if next_question < len(QUESTIONS):

            application["current_question"] = next_question

            await interaction.response.send_message(
                f"Answer saved. Next question: "
                f"**{next_question + 1} of {len(QUESTIONS)}**",
                ephemeral=True
            )

            await send_question(
                interaction,
                self.user_id
            )

        else:

            await interaction.response.send_message(
                "Your application has been submitted!",
                ephemeral=True
            )

            await submit_application(
                self.user_id
            )


async def submit_application(user_id):

    application = active_applications.get(user_id)

    if not application:
        return

    user = application["user"]

    channel = bot.get_channel(
        APPLICATION_REVIEW_CHANNEL_ID
    )

    if not channel:
        print("Application review channel not found.")
        return

    embed = discord.Embed(
        title="New Staff Application",
        description=f"Application from {user.mention}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Applicant",
        value=f"{user.mention}\n`{user}`\nID: `{user.id}`",
        inline=False
    )

    for i, answer in enumerate(application["answers"]):

        embed.add_field(
            name=f"Question {i + 1}",
            value=f"**{QUESTIONS[i]}**\n{answer}",
            inline=False
        )

    embed.set_thumbnail(
        url=user.display_avatar.url
    )

    await channel.send(
        embed=embed,
        view=StaffReviewView(user.id)
    )

    active_applications.pop(user_id, None)


class StaffReviewView(ui.View):

    def __init__(self, applicant_id):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    async def is_staff(self, interaction):

        role = interaction.guild.get_role(
            STAFF_ROLE_ID
        )

        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You don't have permission to review applications.",
                ephemeral=True
            )
            return False

        return True

    @ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        custom_id="staff_accept"
    )
    async def accept(self, interaction, button):

        if not await self.is_staff(interaction):
            return

        user = await bot.fetch_user(
            self.applicant_id
        )

        try:
            await user.send(
                "🎉 **Staff Application Accepted!**\n\n"
                "Congratulations! Your application for "
                "**Helper** at **MultipleSMP.net** has been accepted."
            )
            result = "Applicant notified by DM."

        except discord.Forbidden:
            result = "Could not DM the applicant."

        await interaction.response.send_message(
            result,
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(
            view=self
        )

    @ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id="staff_deny"
    )
    async def deny(self, interaction, button):

        if not await self.is_staff(interaction):
            return

        user = await bot.fetch_user(
            self.applicant_id
        )

        try:
            await user.send(
                "❌ **Staff Application Denied**\n\n"
                "Thank you for applying for Helper at "
                "**MultipleSMP.net**.\n\n"
                "Unfortunately, your application was not accepted."
            )
            result = "Applicant notified by DM."

        except discord.Forbidden:
            result = "Could not DM the applicant."

        await interaction.response.send_message(
            result,
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(
            view=self
        )

    @ui.button(
        label="Deny with reason",
        style=discord.ButtonStyle.danger,
        custom_id="staff_deny_reason"
    )
    async def deny_reason(self, interaction, button):

        if not await self.is_staff(interaction):
            return

        await interaction.response.send_modal(
            DenyReasonModal(
                self.applicant_id,
                self
            )
        )


class DenyReasonModal(ui.Modal):

    def __init__(self, applicant_id, review_view):

        self.applicant_id = applicant_id
        self.review_view = review_view

        super().__init__(
            title="Deny Application"
        )

        self.reason = ui.TextInput(
            label="Reason",
            placeholder="Why was this application denied?",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1500
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction):

        user = await bot.fetch_user(
            self.applicant_id
        )

        try:
            await user.send(
                "❌ **Staff Application Denied**\n\n"
                f"**Reason:**\n{self.reason.value}"
            )
            result = "Applicant notified by DM."

        except discord.Forbidden:
            result = "Could not DM the applicant."

        await interaction.response.send_message(
            result,
            ephemeral=True
        )

        for child in self.review_view.children:
            child.disabled = True

        await interaction.message.edit(
            view=self.review_view
        )


# ============================================================
# SECRET APPLICATION COMMAND
# ============================================================

@bot.command(
    name="ajudfheuhfjrjfjwi2w3j3wpijd3eijfoj30pi4ripj"
)
async def staff_application(ctx):

    channel = bot.get_channel(
        APPLICATION_POST_CHANNEL_ID
    )

    if not channel:
        await ctx.send(
            "Application channel not found.",
            delete_after=5
        )
        return

    await channel.send(
        embed=application_embed(),
        view=ApplyView()
    )

    await ctx.send(
        "Staff application panel posted.",
        delete_after=5
    )


# ============================================================
# TICKET SYSTEM
# ============================================================

active_tickets = {}


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
            options=options,
            custom_id="ticket_category"
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


async def create_ticket(
    interaction,
    ticket_type
):

    guild = interaction.guild
    user = interaction.user

    # Prevent multiple tickets
    for channel_id, creator_id in active_tickets.items():

        if creator_id == user.id:

            existing = guild.get_channel(
                channel_id
            )

            if existing:

                await interaction.response.send_message(
                    f"You already have a ticket: {existing.mention}",
                    ephemeral=True
                )

                return

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

    if not category or not staff_role:

        await interaction.response.send_message(
            "Ticket setup is incorrect. Contact an administrator.",
            ephemeral=True
        )

        return

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        user:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),

        staff_role:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )
    }

    safe_name = "".join(
        c if c.isalnum() or c == "-"
        else "-"
        for c in user.name.lower()
    )

    channel = await guild.create_text_channel(
        name=f"ticket-{safe_name}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket created by {user}"
    )

    active_tickets[channel.id] = user.id

    await interaction.response.send_message(
        f"Your ticket has been created: {channel.mention}",
        ephemeral=True
    )

    message = await channel.send(
        f"Hello {user.mention}, a staff member will be with you shortly.\n"
        f"{staff_role.mention}"
    )

    await message.pin()


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

    if not channel:

        await ctx.send(
            "Ticket panel channel not found.",
            delete_after=5
        )

        return

    await channel.send(
        embed=ticket_embed(),
        view=TicketPanelView()
    )

    await ctx.send(
        "Ticket panel posted.",
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

    if not staff_role or staff_role not in ctx.author.roles:

        await ctx.send(
            "Only staff can close tickets.",
            delete_after=3
        )

        return

    if ctx.channel.id not in active_tickets:

        await ctx.send(
            "This is not a ticket channel.",
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
async def info(ctx, member: discord.Member = None):

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

    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):

    await member.kick(reason=reason)

    await ctx.send(
        f"Kicked {member.mention}. Reason: {reason}"
    )


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):

    await member.ban(reason=reason)

    await ctx.send(
        f"Banned {member.mention}. Reason: {reason}"
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
# READY
# ============================================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print(f"Connected to {len(bot.guilds)} server(s)")
    print("Staff applications loaded.")
    print("Ticket system loaded.")

    bot.add_view(ApplyView())
    bot.add_view(TicketPanelView())


# ============================================================
# RUN
# ============================================================

bot.run(TOKEN)