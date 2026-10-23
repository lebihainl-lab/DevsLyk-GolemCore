import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import re
from keep_alive import keep_alive

# Initialize bot with standard intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Helper function to parse time strings like 10m, 2h, 1d
def parse_duration(duration_str: str) -> int:
    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    matches = re.findall(r"(\d+)([smhd])", duration_str.lower())
    if not matches:
        return 0
    total_seconds = 0
    for amount, unit in matches:
        total_seconds += int(amount) * time_dict[unit]
    return total_seconds

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        # Syncs slash commands globally
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# The /giveaway create command
@bot.tree.command(name="giveaway", description="Create a new server giveaway!")
@app_commands.describe(
    duration="How long? (e.g., 30m, 2h, 1d)",
    winners="Number of lucky winners",
    prize="What are you giving away?"
)
async def giveaway(interaction: discord.Interaction, duration: str, winners: int, prize: str):
    seconds = parse_duration(duration)
    if seconds <= 0:
        await interaction.response.send_message("❌ Invalid duration format! Use something like `10m`, `2h`, or `1d`.", ephemeral=True)
        return

    # Acknowledge the command and create the giveaway post
    embed = discord.Embed(
        title="🎉 GIVEAWAY STARTED! 🎉",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Hosted By:** {interaction.user.mention}\n\nReact with 🎉 to enter!",
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"Ends in {duration}")
    
    await interaction.response.send_message("Creating your giveaway...", ephemeral=True)
    channel = interaction.channel
    giveaway_msg = await channel.send(embed=embed)
    await giveaway_msg.add_reaction("🎉")

    # Wait for the duration to run out
    await asyncio.sleep(seconds)

    # Fetch updated message content to count reactions accurately
    try:
        updated_msg = await channel.fetch_message(giveaway_msg.id)
    except discord.NotFound:
        await channel.send(f"❌ Could not finish giveaway for **{prize}** because the original post was deleted.")
        return

    # Gather participants from the specified reaction emoji
    reaction = discord.utils.get(updated_msg.reactions, emoji="🎉")
    users = [user async for user in reaction.users() if not user.bot]

    if len(users) == 0:
        await channel.send(f"😭 Nobody joined the giveaway! No one wins **{prize}**.")
        return

    import random
    # Select winners (ensuring we don't try to pick more than available users)
    actual_winners = min(winners, len(users))
    chosen_ones = random.sample(users, actual_winners)
    winner_mentions = ", ".join([winner.mention for winner in chosen_ones])

    # Announce the results
    end_embed = discord.Embed(
        title="🎉 GIVEAWAY ENDED 🎉",
        description=f"**Prize:** {prize}\n**Winners:** {winner_mentions}",
        color=discord.Color.gold()
    )
    await giveaway_msg.edit(embed=end_embed)
    await channel.send(f"Congratulations {winner_mentions}! You won **{prize}**! 🎁")

# Start the Flask keep-alive ping loop 
keep_alive()

# Retrieve your bot's token from Render Environment settings securely
bot.run(os.environ.get("DISCORD_TOKEN"))
