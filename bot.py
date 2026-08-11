## Staff Application System — `bot.py`

```python
import discord
from discord.ext import commands
from discord import ui
import os

# ============================================================
# CONFIG
# ============================================================

APPLICATION_POST_CHANNEL_ID = 1536742885200756856
APPLICATION_REVIEW_CHANNEL_ID = 1536744148042911974

TOKEN = os.environ["TOKEN"]

# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================================
# APPLICATION QUESTIONS
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

# Stores active applications in memory.
# user_id -> application data
active_applications = {}


# ============================================================
# APPLICATION EMBED
# ============================================================

def create_application_embed():
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

    embed.set_footer(text="MultipleSMP Staff Applications")

    return embed


# ============================================================
# APPLY BUTTON
# ============================================================

class ApplyButton(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Apply",
        style=discord.ButtonStyle.success,
        custom_id="staff_application_apply"
    )
    async def apply(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):
        user_id = interaction.user.id

        # Prevent multiple active applications
        if user_id in active_applications:
            await interaction.response.send_message(
                "❌ You already have an active application.",
                ephemeral=True
            )
            return

        active_applications[user_id] = {
            "user": interaction.user,
            "answers": [],
            "question": 0
        }

        await interaction.response.send_message(
            "Your staff application is starting.",
            ephemeral=True
        )

        await send_question(interaction, user_id)


# ============================================================
# QUESTION MODAL
# ============================================================

class QuestionModal(ui.Modal):

    def __init__(self, user_id: int, question_number: int):
        self.user_id = user_id
        self.question_number = question_number

        question = QUESTIONS[question_number]

        super().__init__(
            title=f"Question {question_number + 1} of {len(QUESTIONS)}"
        )

        self.answer = ui.TextInput(
            label=question[:45],
            placeholder="Type your answer here...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):

        user_id = self.user_id

        # Make sure application still exists
        if user_id not in active_applications:
            await interaction.response.send_message(
                "❌ Your application is no longer active.",
                ephemeral=True
            )
            return

        application = active_applications[user_id]

        # Save answer
        application["answers"].append(self.answer.value)

        next_question = self.question_number + 1

        # More questions
        if next_question < len(QUESTIONS):

            application["question"] = next_question

            await interaction.response.send_message(
                f"✅ Answer saved.\n\n"
                f"Next: **Question {next_question + 1} of {len(QUESTIONS)}**",
                ephemeral=True
            )

            await send_question(interaction, user_id)

        # Finished
        else:

            await interaction.response.send_message(
                "✅ **Application complete!**\n\n"
                "Your application has been sent to the staff team.",
                ephemeral=True
            )

            await submit_application(interaction, user_id)


# ============================================================
# SEND QUESTION
# ============================================================

async def send_question(interaction, user_id):

    application = active_applications.get(user_id)

    if not application:
        return

    question_number = application["question"]

    # Send modal
    modal = QuestionModal(
        user_id=user_id,
        question_number=question_number
    )

    await interaction.followup.send(
        f"**Question {question_number + 1} of {len(QUESTIONS)}**\n\n"
        f"{QUESTIONS[question_number]}",
        ephemeral=True
    )

    # Discord requires the modal interaction itself to be triggered
    # by an interaction. Therefore use a temporary button.
    view = QuestionView(user_id, question_number)

    await interaction.followup.send(
        "Click below to answer this question.",
        view=view,
        ephemeral=True
    )


# ============================================================
# QUESTION BUTTON
# ============================================================

class QuestionView(ui.View):

    def __init__(self, user_id: int, question_number: int):
        super().__init__(timeout=None)

        self.user_id = user_id
        self.question_number = question_number

        button = ui.Button(
            label="Answer Question",
            style=discord.ButtonStyle.primary
        )

        button.callback = self.open_modal
        self.add_item(button)

    async def open_modal(self, interaction: discord.Interaction):

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
# SUBMIT APPLICATION
# ============================================================

async def submit_application(interaction, user_id):

    application = active_applications.get(user_id)

    if not application:
        return

    user = application["user"]

    channel = bot.get_channel(APPLICATION_REVIEW_CHANNEL_ID)

    if channel is None:
        print("ERROR: Application review channel not found.")
        return

    embed = discord.Embed(
        title="📋 New Staff Application",
        description=f"Application from {user.mention}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Applicant",
        value=f"{user.mention}\n`{user}`\nID: `{user.id}`",
        inline=False
    )

    for index, answer in enumerate(application["answers"]):
        embed.add_field(
            name=f"Question {index + 1}",
            value=(
                f"**{QUESTIONS[index]}**\n"
                f"{answer}"
            ),
            inline=False
        )

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="MultipleSMP Staff Application")

    view = StaffReviewView(user_id)

    message = await channel.send(
        embed=embed,
        view=view
    )

    # Save review message ID
    application["review_message_id"] = message.id


# ============================================================
# STAFF REVIEW BUTTONS
# ============================================================

class StaffReviewView(ui.View):

    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)

        self.applicant_id = applicant_id

    def staff_check(self, interaction: discord.Interaction):

        # Staff channel permission check.
        # Change this if you want to use a specific role.
        return interaction.user.guild_permissions.manage_guild

    @ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        custom_id="staff_application_accept"
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not self.staff_check(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to review applications.",
                ephemeral=True
            )
            return

        applicant = await bot.fetch_user(self.applicant_id)

        try:
            await applicant.send(
                "🎉 **Staff Application Accepted!**\n\n"
                "Congratulations! Your application for **Helper** "
                "at **MultipleSMP.net** has been accepted.\n\n"
                "A staff member will contact you with the next steps."
            )

            dm_status = "Applicant was notified via DM."

        except discord.Forbidden:
            dm_status = "⚠️ Couldn't DM the applicant."

        await interaction.response.send_message(
            f"✅ Application accepted. {dm_status}",
            ephemeral=True
        )

        # Disable buttons
        for child in self.children:
            child.disabled = True

        await interaction.message.edit(view=self)

    @ui.button(
        label="Deny",
        style=discord.ButtonStyle.danger,
        custom_id="staff_application_deny"
    )
    async def deny(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not self.staff_check(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to review applications.",
                ephemeral=True
            )
            return

        applicant = await bot.fetch_user(self.applicant_id)

        try:
            await applicant.send(
                "❌ **Staff Application Denied**\n\n"
                "Thank you for applying for **Helper** "
                "at **MultipleSMP.net**.\n\n"
                "Unfortunately, your application was not accepted."
            )

            dm_status = "Applicant was notified via DM."

        except discord.Forbidden:
            dm_status = "⚠️ Couldn't DM the applicant."

        await interaction.response.send_message(
            f"❌ Application denied. {dm_status}",
            ephemeral=True
        )

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(view=self)

    @ui.button(
        label="Deny with reason",
        style=discord.ButtonStyle.danger,
        custom_id="staff_application_deny_reason"
    )
    async def deny_reason(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        if not self.staff_check(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to review applications.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            DenyReasonModal(self.applicant_id)
        )


# ============================================================
# DENY WITH REASON MODAL
# ============================================================

class DenyReasonModal(ui.Modal):

    def __init__(self, applicant_id: int):

        self.applicant_id = applicant_id

        super().__init__(
            title="Deny Application"
        )

        self.reason = ui.TextInput(
            label="Why are they being denied?",
            placeholder="Enter the reason...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1500
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):

        applicant = await bot.fetch_user(self.applicant_id)

        try:
            await applicant.send(
                "❌ **Staff Application Denied**\n\n"
                "Thank you for applying for **Helper** "
                "at **MultipleSMP.net**.\n\n"
                f"**Reason:**\n{self.reason.value}"
            )

            dm_status = "Applicant was notified via DM."

        except discord.Forbidden:
            dm_status = "⚠️ Couldn't DM the applicant."

        await interaction.response.send_message(
            f"❌ Application denied with a reason.\n{dm_status}",
            ephemeral=True
        )


# ============================================================
# SECRET COMMAND
# ============================================================

@bot.command(
    name="ajudfheuhfjrjfjwi2w3j3wpijd3eijfoj30pi4ripj"
)
async def staff_application(ctx):

    channel = bot.get_channel(APPLICATION_POST_CHANNEL_ID)

    if channel is None:
        await ctx.send(
            "❌ Application channel wasn't found.",
            delete_after=10
        )
        return

    embed = create_application_embed()

    await channel.send(
        embed=embed,
        view=ApplyButton()
    )

    await ctx.send(
        "✅ Staff application panel posted.",
        delete_after=5
    )


# ============================================================
# ERROR HANDLER
# ============================================================

@staff_application.error
async def staff_application_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "❌ You don't have permission to use this command.",
            delete_after=5
        )


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Connected to {len(bot.guilds)} server(s)")

    # Register persistent views
    bot.add_view(ApplyButton())

    print("Staff application system loaded.")


# ============================================================
# BASIC TEST COMMAND
# ============================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        f"🏓 Pong! `{round(bot.latency * 1000)}ms`"
    )


# ============================================================
# RUN
# ============================================================

bot.run(TOKEN)
```

### `requirements.txt`

Use:

```txt
discord.py>=2.5.0
```

You don't need Flask for this version unless you're keeping your existing Railway web server.

### How to use it

After deploying:

```text
!ajudfheuhfjrjfjwi2w3j3wpijd3eijfoj30pi4ripj
```

The bot posts the application panel in:

```text
1536742885200756856
```

Applicant clicks:

**🟢 Apply**

Then they answer:

1. Age
2. Discord username
3. Country & timezone
4. Hours per week
5. Previous staff experience
6. Why they want Helper
7. How they'd handle an argument
8. Punishments
9. What makes them stand out
10. Anything else

There is **no 5-minute timeout**.

After Question 10, the completed application is sent to:

```text
1536744148042911974
```

Staff gets:

**🟢 Accept**

**🔴 Deny**

**🔴 Deny with reason**

The applicant receives the decision through Discord DMs.

```
```
