import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread

# ── Keep-alive web server (stops host from sleeping) ──────────────
app = Flask('')

@app.route('/')
def home():
    return "Bot is running."

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# ── Bot setup ─────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ── Events ────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f'Online: {bot.user} | Servers: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Game(name="6767"))

@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        await channel.send(f'Welcome {member.mention}!')

# ── Commands ──────────────────────────────────────────────────────
@bot.command()
async def ping(ctx):
    await ctx.send(f'🏓 Pong! `{round(bot.latency * 1000)}ms`')

@bot.command()
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

@bot.command()
async def info(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Info — {member}", color=0x2b2d31)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined", value=member.joined_at.strftime("%Y-%m-%d"))
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f'Kicked {member.mention}. Reason: {reason}')

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f'Banned {member.mention}. Reason: {reason}')

# ── Run ───────────────────────────────────────────────────────────
keep_alive()
bot.run(os.environ['TOKEN'])