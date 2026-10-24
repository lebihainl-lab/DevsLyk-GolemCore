import asyncio
import datetime
import re
import os
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ==========================================
#         RENDER KEEP-ALIVE SYSTEM
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and kicking!"

def run():
    # Render binds automatically to this environment port
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ==========================================
#             BOT CONFIGURATION
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN")
COMMAND_PREFIX = "-"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Exact Custom Emojis provided by you
TICKET_EMOJI = "<a:Tickets:1559407509641363549>"
GIVEAWAY_EMOJI = "<a:nctada:1559720922494144512>"


# ==========================================
#        TICKET TOOL LAYOUT SYSTEM
# ==========================================
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Keeps button working 24/7 across bot restarts
        self.add_item(discord.ui.Button(
            label="Create Ticket",
            style=discord.ButtonStyle.secondary, # Gray button style matching TicketTool
            custom_id="create_ticket_btn",
            emoji=TICKET_EMOJI
        ))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    # Monitor button interactions globally
    if interaction.type == discord.InteractionType.component:
        if interaction.data.get("custom_id") == "create_ticket_btn":
            guild = interaction.guild
            member = interaction.user
            
            # Setup isolated permissions for the ticket channel
            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{member.name}",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                },
                topic=f"Ticket opened by {member.mention}"
            )
            
            await interaction.response.send_message(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)
            
            # First greeting embed within the open ticket
            embed = discord.Embed(
                title="🎫 Ticket Opened",
                description=f"Welcome {member.mention}. Support will be with you shortly.\nType your issue here.",
                color=discord.Color.green()
            )
            await ticket_channel.send(embed=embed)

@bot.tree.command(name="ticket_panel", description="Set up a TicketTool.xyz style layout panel.")
@app_commands.describe(
    title="The main title of your support panel",
    description="The explanation text on how to open a ticket"
)
async def ticket_panel(interaction: discord.Interaction, title: str, description: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
        
    # TicketTool.xyz dark gray theme replication
    embed = discord.Embed(
        title=title, 
        description=description, 
        color=discord.Color.from_rgb(43, 45, 49) # Hex #2B2D31 profile
    )
    
    # Official Ticket Tool baseline layout signature
    embed.set_footer(text="🎫 TicketTool.xyz - Ticketing without clutter")
    
    await interaction.response.send_message("✅ Panel spawned below:", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketButton())


# ==========================================
#             GIVEAWAY SYSTEM
# ==========================================
def parse_duration(duration_str: str) -> int:
    """Helper to convert strings like 1d, 12h, 30m, 45s into integers"""
    match = re.match(r"(\d+)([dhms])", duration_str.lower())
    if not match: return 0
    amount, unit = match.groups()
    amount = int(amount)
    if unit == 'd': return amount * 86400
    if unit == 'h': return amount * 3600
    if unit == 'm': return amount * 60
    if unit == 's': return amount

@bot.command(name="gstart")
@commands.has_permissions(administrator=True)
async def gstart(ctx, duration: str, winners: int, *, prize: str):
    seconds = parse_duration(duration)
    if seconds <= 0:
        return await ctx.send("❌ Invalid format! Use `1d`, `12h`, `30m`, or `45s`.")
        
    end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
    unix_timestamp = int(end_time.timestamp())
    
    # Falcon/GolemCore embed styling layout matching your screen reference
    embed = discord.Embed(
        title=f"🎁 **{prize}** 🎁",
        description=(
            f"🔹 **Winners:** {winners}\n"
            f"🔹 **Ends:** <t:{unix_timestamp}:R> (<t:{unix_timestamp}:F>)\n"
            f"🔹 **Hosted by:** {ctx.author.mention}\n\n"
            f"🔹 React with {GIVEAWAY_EMOJI} to participate!"
        ),
        color=discord.Color.from_rgb(241, 196, 15) # Gold layout profile
    )
    embed.set_footer(text="Ends at")
    embed.timestamp = end_time
    
    giveaway_msg = await ctx.send(embed=embed)
    await giveaway_msg.add_reaction(GIVEAWAY_EMOJI)
    
    # Wait out the length of the giveaway safely in the background
    await asyncio.sleep(seconds)
    
    try:
        giveaway_msg = await ctx.channel.fetch_message(giveaway_msg.id)
    except discord.NotFound:
        return # Message deleted manually
        
    reaction = discord.utils.get(giveaway_msg.reactions, emoji=GIVEAWAY_EMOJI)
    users = []
    if reaction:
        async for user in reaction.users():
            if not user.bot: users.append(user)
                
    if len(users) == 0:
        ended_embed = giveaway_msg.embeds[0]
        ended_embed.description = f"🔹 **Winners:** None\n🔹 **Hosted by:** {ctx.author.mention}\n\nNo valid entrants participated."
        await giveaway_msg.edit(embed=ended_embed)
        return await ctx.send(f"⚠️ The giveaway for **{prize}** ended with no participants.")
        
    import random
    actual_winners = random.sample(users, min(winners, len(users)))
    winner_mentions = ", ".join([w.mention for w in actual_winners])
    
    # Update active layout to complete status
    ended_embed = giveaway_msg.embeds[0]
    ended_embed.description = f"🔹 **Winners:** {winner_mentions}\n🔹 **Hosted by:** {ctx.author.mention}\n\nThe giveaway has ended!"
    await giveaway_msg.edit(embed=ended_embed)
    
    # Send public announcement message block
    await ctx.send(f"🎉 **Congratulations** {winner_mentions}! You won **{prize}**!")


# ==========================================
#               BOT INITIALIZATION
# ==========================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        # Registers slash trees globally to Discord
        await bot.tree.sync()
        print("Synced slash commands globally.")
    except Exception as e:
        print(f"Failed to sync command trees: {e}")

if __name__ == "__main__":
    # Start web server baseline loop, then boot bot execution instance
    keep_alive()
    bot.run(TOKEN)
