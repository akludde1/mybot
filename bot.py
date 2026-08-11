import os
import discord
from discord.ext import commands
from discord import ui

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.environ["TOKEN"]

APPLICATION_POST_CHANNEL_ID = 1536742885200756856
APPLICATION_REVIEW_CHANNEL_ID = 1536744148042911974

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
# STAFF APPLICATION QUESTIONS
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

# Active applications
active_applications = {}

# ============================================================
# STAFF APPLICATION EMBED
# ============================================================

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

    embed.set_footer(
        text="MultipleSMP Staff Applications"
    )

    return embed


# ============================================================
# APPLY BUTTON
# ============================================================

class ApplyView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Apply",
        style=discord.ButtonStyle.success,
        custom_id="multiplesmp_staff_apply"
    )
    async def apply_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        user_id = interaction.user.id

        if user_id in active_applications:
            await interaction.response.send_message(
                "❌ You already have an active application.",
                ephemeral=True
            )
            return

        active_applications[user_id] = {
            "user": interaction.user,
            "answers": [],
            "current_question": 0
        }

        await interaction.response.send_message(
            "✅ Your application is starting.",
            ephemeral=True
        )

        await send_question_prompt(
            interaction,
            user_id
        )


# ============================================================
# QUESTION PROMPT
# ============================================================

async def send_question_prompt(
    interaction: discord.Interaction,
    user_id: int
):

    application = active_applications.get(user_id)

    if application is None:
        return

    question_number = application["current_question"]

    if question_number >= len(QUESTIONS):
        return

    view = QuestionView(
        user_id=user_id,
        question_number=question_number
    )

    await interaction.followup.send(
        f"**Question {question_number + 1} of {len(QUESTIONS)}**\n\n"
        f"{QUESTIONS[question_number]}\n\n"
        f"Click **Answer Question** below.",
        view=view,
        ephemeral=True
    )


# ============================================================
# QUESTION BUTTON
# ============================================================

class QuestionView(ui.View):

    def __init__(
        self,
        user_id: int,
        question_number: int
    ):
        super().__init__(timeout=None)

        self.user_id = user_id
        self.question_number = question_number

    @ui.button(
        label="Answer Question",
        style=discord.ButtonStyle.primary
    )
    async def answer_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This isn't your application.",
                ephemeral=True
            )
            return

        modal = QuestionModal(
            user_id=self.user_id,
            question_number=self.question_number
        )

        await interaction.response.send_modal(modal)


# ============================================================
# QUESTION MODAL
# ============================================================

class QuestionModal(ui.Modal):

    def __init__(
        self,
        user_id: int,
        question_number: int
    ):

        self.user_id = user_id
        self.question_number = question_number

        super().__init__(
            title=f"Question {question_number + 1} of {len(QUESTIONS)}"
        )

        self.answer = ui.TextInput(
            label=QUESTIONS[question_number][:45],
            placeholder="Type your answer here...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(self.answer)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        application = active_applications.get(self.user_id)

        if application is None:
            await interaction.response.send_message(
                "❌ Your application is no longer active.",
                ephemeral=True
            )
            return

        # Save answer
        application["answers"].append(
            self.answer.value
        )

        next_question = self.question_number + 1

        # More questions
        if next_question < len(QUESTIONS):

            application["current_question"] = next_question

            await interaction.response.send_message(
                f"✅ Answer saved.\n\n"
                f"Next: **Question {next_question + 1} "
                f"of {len(QUESTIONS)}**",
                ephemeral=True
            )

            await send_question_prompt(
                interaction,
                self.user_id
            )

        # Application finished
        else:

            await interaction.response.send_message(
                "✅ **Application complete!**\n\n"
                "Your application has been sent to the staff team.",
                ephemeral=True
            )

            await submit_application(
                interaction,
                self.user_id
            )


# ============================================================
# SUBMIT APPLICATION TO STAFF CHANNEL
# ============================================================

async def submit_application(
    interaction: discord.Interaction,
    user_id: int
):

    application = active_applications.get(user_id)

    if application is None:
        return

    user = application["user"]

    channel = bot.get_channel(
        APPLICATION_REVIEW_CHANNEL_ID
    )

    if channel is None:
        print(
            "ERROR: Application review channel "
            "could not be found."
        )
        return

    embed = discord.Embed(
        title="📋 New Staff Application",
        description=(
            f"Application from {user.mention}"
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Applicant",
        value=(
            f"{user.mention}\n"
            f"`{user}`\n"
            f"ID: `{user.id}`"
        ),
        inline=False
    )

    for index, answer in enumerate(
        application["answers"]
    ):

        embed.add_field(
            name=f"Question {index + 1}",
            value=(
                f"**{QUESTIONS[index]}**\n"
                f"{answer}"
            ),
            inline=False
        )

    embed.set_thumbnail(
        url=user.display_avatar.url
    )

    embed.set_footer(
        text="MultipleSMP Staff Applications"
    )

    view = StaffReviewView(
        applicant_id=user.id
    )

    message = await channel.send(
        embed=embed,
        view=view
    )

    application["review_message_id"] = message.id


# ============================================================
# STAFF REVIEW VIEW
# ============================================================

class StaffReviewView(ui.View):

    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)

        self.applicant_id = applicant_id

    async def check_staff(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You don't have permission to review "
                "staff applications.",
                ephemeral=True
            )
            return False

        return True

    # --------------------------------------------------------
    # ACCEPT
    # --------------------------------------------------------

    @ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        custom_id="multiplesmp_staff_accept"
    )
    async def accept_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not await self.check_staff(interaction):
            return

        applicant = await bot.fetch_user(
            self.applicant_id
        )

        try:

            await applicant.send(
                "🎉 **Staff Application Accepted!**\n\n"
                "Congratulations!\n\n"
                "Your application for **Helper** "
                "at **MultipleSMP.net** has been accepted.\n\n"
                "A staff member will contact you "
                "with the next steps."
            )

            dm_status = "Applicant was notified via DM."

        except discord.Forbidden:

            dm_status = (
                "⚠️ I couldn't DM the applicant. "
                "Their DMs may be closed."
            )

        await interaction.response.send_message(
            f"✅ **Application accepted.**\n{dm_status}",
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(
            view=self
        )

    # --------------------------------------------------------
    # DENY
    # --------------------------------------------------------

    @ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id="multiplesmp_staff_deny"
    )
    async def deny_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not await self.check_staff(interaction):
            return

        applicant = await bot.fetch_user(
            self.applicant_id
        )

        try:

            await applicant.send(
                "❌ **Staff Application Denied**\n\n"
                "Thank you for applying for **Helper** "
                "at **MultipleSMP.net**.\n\n"
                "Unfortunately, your application "
                "was not accepted."
            )

            dm_status = "Applicant was notified via DM."

        except discord.Forbidden:

            dm_status = (
                "⚠️ I couldn't DM the applicant. "
                "Their DMs may be closed."
            )

        await interaction.response.send_message(
            f"❌ **Application denied.**\n{dm_status}",
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(
            view=self
        )

    # --------------------------------------------------------
    # DENY WITH REASON
    # --------------------------------------------------------

    @ui.button(
        label="Deny with reason",
        style=discord.ButtonStyle.danger,
        custom_id="multiplesmp_staff_deny_reason"
    )
    async def deny_reason_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not await self.check_staff(interaction):
            return

        await interaction.response.send_modal(
            DenyReasonModal(
                applicant_id=self.applicant_id,
                review_view=self
            )
        )


# ============================================================
# DENY WITH REASON MODAL
# ============================================================

class DenyReasonModal(ui.Modal):

    def __init__(
        self,
        applicant_id: int,
        review_view: StaffReviewView
    ):

        self.applicant_id = applicant_id
        self.review_view = review_view

        super().__init__(
            title="Deny Application"
        )

        self.reason = ui.TextInput(
            label="Reason for denial",
            placeholder="Explain why the application was denied...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1500
        )

        self.add_item(self.reason)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        applicant = await bot.fetch_user(
            self.applicant_id
        )

        try:

            await applicant.send(
                "❌ **Staff Application Denied**\n\n"
                "Thank you for applying for **Helper** "
                "at **MultipleSMP.net**.\n\n"
                f"**Reason:**\n"
                f"{self.reason.value}"
            )

            dm_status = "Applicant was notified via DM."

        except discord.Forbidden:

            dm_status = (
                "⚠️ I couldn't DM the applicant. "
                "Their DMs may be closed."
            )

        await interaction.response.send_message(
            f"❌ **Application denied with a reason.**\n"
            f"{dm_status}",
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

    if channel is None:

        await ctx.send(
            "❌ I couldn't find the application channel.",
            delete_after=10
        )

        print(
            f"ERROR: Channel {APPLICATION_POST_CHANNEL_ID} "
            "not found."
        )

        return

    embed = application_embed()

    await channel.send(
        embed=embed,
        view=ApplyView()
    )

    await ctx.send(
        "✅ Staff application panel posted.",
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
            value=member.joined_at.strftime(
                "%Y-%m-%d"
            ),
            inline=False
        )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await ctx.send(embed=embed)


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

    print(
        f"Logged in as {bot.user}"
    )

    print(
        f"Bot ID: {bot.user.id}"
    )

    print(
        f"Connected to {len(bot.guilds)} server(s)"
    )

    print(
        "Staff application system loaded."
    )

    # Persistent buttons
    bot.add_view(ApplyView())


# ============================================================
# RUN BOT
# ============================================================

bot.run(TOKEN)
