# Main Slash Command
@bot.tree.command(name="ticket_panel", description="Setup the interactive ticket panel system")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(category="The Category folder for new tickets", support_role="The support role notified on entry")
async def ticket_panel(interaction: discord.Interaction, category: discord.CategoryChannel, support_role: discord.Role):
    modal = TicketConfigModal(category, support_role)
    await interaction.response.send_modal(modal)
