import os
import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
from keep_alive import keep_alive  # Imports the web server

# Define your intents
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

class AutoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced globally.")

bot = AutoBot()

# --- IN-MEMORY STORAGE ---
autorole_config = {}   
autoreact_config = {}  
sticky_config = {}

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')

# --- EVENT: NEW MEMBER JOINS ---
@bot.event
async def on_member_join(member: discord.Member):
    guild_id = member.guild.id
    if guild_id in autorole_config:
        role_id = autorole_config[guild_id]
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                print(f"Missing permissions to assign role in {member.guild.name}.")
            except discord.HTTPException:
                pass

# --- EVENT: MESSAGE RECEIVED ---
@bot.event
async def on_message(message: discord.Message):
    channel_id = message.channel.id

    # STICKY ANNOUNCEMENT LOGIC
    if channel_id in sticky_config:
        config = sticky_config[channel_id]
        if message.id != config["last_message_id"]:
            ignore_bot_messages = False 
            if not (ignore_bot_messages and message.author.bot):
                if config["last_message_id"]:
                    try:
                        old_msg = await message.channel.fetch_message(config["last_message_id"])
                        await old_msg.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
                try:
                    new_sticky = await message.channel.send(config["text"])
                    sticky_config[channel_id]["last_message_id"] = new_sticky.id
                except discord.Forbidden:
                    print(f"Missing 'Send Messages' permissions in channel {channel_id}.")
                except discord.HTTPException:
                    pass

    # AUTOREACT LOGIC
    if not message.author.bot and channel_id in autoreact_config:
        react_data = autoreact_config[channel_id]
        emoji = react_data["emoji"]
        trigger_on = react_data["trigger_on"]
        
        has_image = any(
            attachment.content_type and attachment.content_type.startswith("image/") 
            for attachment in message.attachments
        )
        
        should_react = False
        if trigger_on == "message" and not has_image:
            should_react = True
        elif trigger_on == "image" and has_image:
            should_react = True
        elif trigger_on == "both":
            should_react = True
            
        if should_react:
            try:
                await message.add_reaction(emoji)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

    await bot.process_commands(message)

# --- COMMANDS ---
@bot.tree.command(name="autorole", description="Set up a role to automatically give to new members when they join.")
@app_commands.describe(role="The role to assign to new members.")
@app_commands.checks.has_permissions(administrator=True)
async def autorole(interaction: discord.Interaction, role: discord.Role):
    autorole_config[interaction.guild_id] = role.id
    await interaction.response.send_message(f"✅ **Auto-role configured!** New members will get **{role.name}**.", ephemeral=True)

@bot.tree.command(name="autoreact", description="Configure a channel to automatically react to incoming content.")
@app_commands.describe(channel="The channel to auto-react.", emoji="The emoji (e.g., 👍, 🔥).", trigger_on="React to messages, images, or both.")
@app_commands.checks.has_permissions(administrator=True)
async def autoreact(interaction: discord.Interaction, channel: discord.TextChannel, emoji: str, trigger_on: Literal["message", "image", "both"]):
    autoreact_config[channel.id] = {"emoji": emoji, "trigger_on": trigger_on}
    await interaction.response.send_message(f"✅ **Auto-react configured!** Reacting with {emoji} to **{trigger_on}** in {channel.mention}.", ephemeral=True)

@bot.tree.command(name="stickyannouncement", description="Create an announcement that sticks to the bottom of a channel.")
@app_commands.describe(channel="The channel where the message should stick.", message="The announcement text (use \\n for new lines).")
@app_commands.checks.has_permissions(administrator=True)
async def stickyannouncement(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    if channel.id in sticky_config and sticky_config[channel.id]["last_message_id"]:
        try:
            old_msg = await channel.fetch_message(sticky_config[channel.id]["last_message_id"])
            await old_msg.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    formatted_message = message.replace("\\n", "\n")
    sticky_config[channel.id] = {"text": formatted_message, "last_message_id": None}
    
    initial_sticky = await channel.send(formatted_message)
    sticky_config[channel.id]["last_message_id"] = initial_sticky.id
    await interaction.response.send_message(f"📌 **Sticky announcement active** in {channel.mention}!", ephemeral=True)

@bot.tree.command(name="removesticky", description="Remove a sticky announcement from a channel.")
@app_commands.describe(channel="The channel to clear the sticky from.")
@app_commands.checks.has_permissions(administrator=True)
async def removesticky(interaction: discord.Interaction, channel: discord.TextChannel):
    if channel.id in sticky_config:
        if sticky_config[channel.id]["last_message_id"]:
            try:
                old_msg = await channel.fetch_message(sticky_config[channel.id]["last_message_id"])
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        del sticky_config[channel.id]
        await interaction.response.send_message(f"🛑 **Sticky announcement removed** from {channel.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No active sticky announcement in {channel.mention}.", ephemeral=True)

@autorole.error
@autoreact.error
@stickyannouncement.error
@removesticky.error
async def command_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You must have `Administrator` permissions to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)

# Starts the web server right before launching the bot
keep_alive()

# Securely fetches your bot token hidden in Render's environment dashboard
bot.run(os.getenv('DISCORD_TOKEN'))
