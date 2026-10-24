import os
import asyncio
import discord
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button

class TicketBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced globally!")

bot = TicketBot()

class PersistentTicketView(View):
    def __init__(self, category_id: int, support_role_id: int):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.support_role_id = support_role_id

        button = Button(
            label="📩 Open Ticket",
            style=discord.ButtonStyle.primary,
            custom_id=f"open_ticket:{category_id}:{support_role_id}"
        )
        button.callback = self.open_ticket_callback
        self.add_item(button)

    async def open_ticket_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        category = guild.get_channel(self.category_id)
        support_role = guild.get_role(self.support_role_id)

        if not category:
            await interaction.followup.send("❌ Error: Target category no longer exists.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            bot.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        welcome_embed = discord.Embed(
            title="🎫 Ticket Created",
            description=f"Welcome {interaction.user.mention}! Support staff ({support_role.mention if support_role else 'Staff'}) will assist you shortly.\n\nClick below to close this room.",
            color=discord.Color.blue()
        )
        
        close_view = View(timeout=None)
        close_btn = Button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
        
        async def close_callback(close_inter: discord.Interaction):
            await close_inter.response.send_message("🔒 Closing ticket in 5 seconds...")
            await asyncio.sleep(5)
            try:
                await close_inter.channel.delete()
            except Exception as e:
                print(f"Failed deleting channel: {e}")

        close_btn.callback = close_callback
        close_view.add_item(close_btn)

        mention_str = f"{interaction.user.mention} | {support_role.mention}" if support_role else interaction.user.mention
        await ticket_channel.send(content=mention_str, embed=welcome_embed, view=close_view)
        await interaction.followup.send(f"✅ Ticket opened: {ticket_channel.mention}", ephemeral=True)

class TicketConfigModal(Modal, title="Configure Panel Content"):
    panel_title = TextInput(label="Panel Embed Title", placeholder="e.g., Support Ticket Desk", required=True)
    panel_description = TextInput(label="Panel Embed Description", style=discord.TextStyle.paragraph, placeholder="Describe how users can get support here...", required=True)

    def __init__(self, category: discord.CategoryChannel, support_role: discord.Role):
        super().__init__()
        self.category = category
        self.support_role = support_role

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title=self.panel_title.value,
            description=self.panel_description.value,
            color=discord.Color.dark_grey()
        )
        
        view = PersistentTicketView(self.category.id, self.support_role.id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ Ticket panel successfully deployed!", ephemeral=True)

@bot.tree.command(name="ticket_panel", description="Setup the interactive ticket panel system")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(category="The Category folder for new tickets", support_role="The support role notified on entry")
async def ticket_panel(interaction: discord.Interaction, category: discord.CategoryChannel, support_role: discord.Role):
    modal = TicketConfigModal(category, support_role)
    await interaction.response.send_modal(modal)

@bot.event
async def on_ready():
    print(f"🚀 Bot is online as {bot.user}")

bot.run(os.environ.get("DISCORD_TOKEN"))
