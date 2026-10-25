
import os
import io
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
import chat_exporter

from keep_alive import keep_alive


# --- BOT INTENTS ---

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True


# --- IN-MEMORY STORAGE ---

autorole_config = {}
autoreact_config = {}
sticky_config = {}

# Structure: {ticket_channel_id: creator_id}
active_tickets = {}


# --- TICKET PANEL VIEW ---

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.green,
        emoji="📩",
        custom_id="persistent:create_ticket",
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild
        member = interaction.user

        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ This button can only be used inside a server.",
                ephemeral=True,
            )
            return

        embed = (
            interaction.message.embeds[0]
            if interaction.message.embeds
            else None
        )

        support_role = None
        category = None

        if embed:
            for field in embed.fields:
                if field.name == "Support Team":
                    try:
                        role_id = int(
                            field.value.replace("<@&", "").replace(">", "")
                        )
                        support_role = guild.get_role(role_id)
                    except ValueError:
                        pass

                elif field.name == "Category":
                    category = discord.utils.get(
                        guild.categories,
                        name=field.value,
                    )

        # Prevent users from opening duplicate tickets.
        for ticket_id, creator_id in active_tickets.items():
            if creator_id == member.id:
                existing_channel = guild.get_channel(ticket_id)

                if existing_channel:
                    await interaction.response.send_message(
                        f"❌ You already have an open ticket: "
                        f"{existing_channel.mention}",
                        ephemeral=True,
                    )
                    return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }

        bot_member = guild.me

        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            )

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{member.name.lower()}",
            category=category,
            overwrites=overwrites,
        )

        active_tickets[ticket_channel.id] = member.id

        control_embed = discord.Embed(
            title="🎫 Ticket Opened",
            description=(
                f"Welcome {member.mention}. Our support team will assist "
                "you shortly.\n"
                "Use the button below or type `-delete` to close this ticket."
            ),
            color=discord.Color.gold(),
        )

        await ticket_channel.send(
            embed=control_embed,
            view=TicketControlView(),
        )

        await interaction.response.send_message(
            f"✅ Ticket opened! Head over to {ticket_channel.mention}",
            ephemeral=True,
        )


# --- TICKET CONTROL VIEW ---

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="persistent:close_ticket",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        channel = interaction.channel
        guild = interaction.guild

        if guild is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ This button can only be used inside a ticket channel.",
                ephemeral=True,
            )
            return

        creator_id = active_tickets.get(channel.id)

        if creator_id is None:
            await interaction.response.send_message(
                "❌ This ticket is not registered as active.",
                ephemeral=True,
            )
            return

        # Allow the ticket creator or authorized staff to close the ticket.
        member = interaction.user

        is_creator = member.id == creator_id
        is_staff = (
            isinstance(member, discord.Member)
            and (
                member.guild_permissions.manage_channels
                or member.guild_permissions.administrator
            )
        )

        if not is_creator and not is_staff:
            await interaction.response.send_message(
                "❌ Only the ticket creator or authorized staff "
                "can close this ticket.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        transcript_file = None

        try:
            transcript = await chat_exporter.export(channel)

            if transcript:
                transcript_file = discord.File(
                    io.BytesIO(transcript.encode("utf-8")),
                    filename=f"transcript-{channel.name}.html",
                )

        except Exception as error:
            print(f"Transcript error: {error}")

        try:
            creator = (
                guild.get_member(creator_id)
                or await bot.fetch_user(creator_id)
            )

            dm_embed = discord.Embed(
                title="📨 Ticket Closed",
                description=(
                    f"Your ticket in **{guild.name}** has been closed. "
                    "Download your transcript below if available."
                ),
                color=discord.Color.green(),
            )

            if transcript_file:
                await creator.send(
                    embed=dm_embed,
                    file=transcript_file,
                )
            else:
                await creator.send(embed=dm_embed)

        except discord.Forbidden:
            try:
                await channel.send(
                    "⚠️ Unable to DM the ticket transcript to the creator."
                )
            except discord.HTTPException:
                pass

        except discord.HTTPException as error:
            print(f"Ticket notification error: {error}")

        active_tickets.pop(channel.id, None)

        try:
            await channel.delete()
        except discord.HTTPException as error:
            print(f"Ticket deletion error: {error}")


# --- BOT CLASS ---

class AutoBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):
        # Register persistent views after the bot starts.
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())

        await self.tree.sync()
        print("Slash commands synced globally.")


bot = AutoBot()


# --- INITIALIZE CHAT EXPORTER ---

chat_exporter.init_exporter(bot)


# --- BOT EVENTS ---

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.event
async def on_member_join(member: discord.Member):
    guild_id = member.guild.id

    if guild_id not in autorole_config:
        return

    role_id = autorole_config[guild_id]
    role = member.guild.get_role(role_id)

    if role:
        try:
            await member.add_roles(role)

        except discord.Forbidden:
            print(
                f"Missing permissions to assign role in "
                f"{member.guild.name}."
            )

        except discord.HTTPException as error:
            print(f"Autorole error: {error}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = message.channel.id

    # --- DELETE TICKET COMMAND ---

    if message.content.strip().lower() == "-delete":
        if channel_id not in active_tickets:
            await message.channel.send(
                "❌ This command can only be used inside an active ticket."
            )
            return

        if not (
            message.author.guild_permissions.manage_channels
            or message.author.guild_permissions.administrator
        ):
            await message.channel.send(
                "❌ You need Manage Channels or Administrator permissions "
                "to use `-delete`."
            )
            return

        await message.channel.send(
            "📁 Generating transcript and closing ticket..."
        )

        creator_id = active_tickets.get(channel_id)
        transcript_file = None

        try:
            transcript = await chat_exporter.export(message.channel)

            if transcript:
                transcript_file = discord.File(
                    io.BytesIO(transcript.encode("utf-8")),
                    filename=f"transcript-{message.channel.name}.html",
                )

        except Exception as error:
            print(f"Transcript generation error: {error}")

        if creator_id:
            try:
                creator = (
                    message.guild.get_member(creator_id)
                    or await bot.fetch_user(creator_id)
                )

                dm_embed = discord.Embed(
                    title="📨 Ticket Closed",
                    description=(
                        f"Your ticket in **{message.guild.name}** "
                        "was deleted by staff."
                    ),
                    color=discord.Color.red(),
                )

                if transcript_file:
                    await creator.send(
                        embed=dm_embed,
                        file=transcript_file,
                    )
                else:
                    await creator.send(embed=dm_embed)

            except discord.Forbidden:
                pass

            except discord.HTTPException as error:
                print(f"Ticket DM error: {error}")

        active_tickets.pop(channel_id, None)

        try:
            await message.channel.delete()
        except discord.HTTPException as error:
            print(f"Ticket deletion error: {error}")

        return

    # --- STICKY ANNOUNCEMENTS ---

    if channel_id in sticky_config:
        config = sticky_config[channel_id]

        if message.id != config["last_message_id"]:
            if config["last_message_id"]:
                try:
                    old_message = await message.channel.fetch_message(
                        config["last_message_id"]
                    )
                    await old_message.delete()

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    pass

            embed = discord.Embed(
                title="📌 Announcement",
                description=config["text"],
                color=discord.Color.blue(),
            )

            embed.set_footer(
                text="This is a sticky message pinned to the bottom."
            )

            try:
                new_sticky = await message.channel.send(embed=embed)
                sticky_config[channel_id]["last_message_id"] = new_sticky.id

            except discord.Forbidden:
                pass

            except discord.HTTPException as error:
                print(f"Sticky message error: {error}")

    # --- AUTOREACT ---

    if channel_id in autoreact_config:
        react_data = autoreact_config[channel_id]
        emoji = react_data["emoji"]
        trigger_on = react_data["trigger_on"]

        has_image = any(
            attachment.content_type
            and attachment.content_type.startswith("image/")
            for attachment in message.attachments
        )

        should_react = (
            trigger_on == "both"
            or (trigger_on == "image" and has_image)
            or (trigger_on == "message" and not has_image)
        )

        if should_react:
            try:
                await message.add_reaction(emoji)

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

    await bot.process_commands(message)


# --- SLASH COMMANDS ---

@bot.tree.command(
    name="ticket_panel",
    description="Deploy a permanent ticket creation panel.",
)
@app_commands.describe(
    description="The introduction text for your support module.",
    support_role="Staff role allowed into tickets.",
    category="The category where new tickets will be created.",
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(
    interaction: discord.Interaction,
    description: str,
    support_role: discord.Role,
    category: discord.CategoryChannel,
):
    panel_embed = discord.Embed(
        title="🎫 Support Desk Center",
        description=description,
        color=discord.Color.green(),
    )

    panel_embed.add_field(
        name="Support Team",
        value=support_role.mention,
        inline=True,
    )

    panel_embed.add_field(
        name="Category",
        value=category.name,
        inline=True,
    )

    panel_embed.set_footer(
        text="Click the green button below to open a private ticket."
    )

    await interaction.channel.send(
        embed=panel_embed,
        view=TicketPanelView(),
    )

    await interaction.response.send_message(
        "✅ Support setup panel successfully deployed here.",
        ephemeral=True,
    )


@bot.tree.command(
    name="stickyannouncement",
    description="Create a sticky announcement embed in a channel.",
)
@app_commands.describe(
    channel="The channel where the announcement should stick.",
    message="The announcement text. New lines are supported.",
)
@app_commands.checks.has_permissions(administrator=True)
async def stickyannouncement(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
):
    if channel.id in sticky_config:
        old_message_id = sticky_config[channel.id]["last_message_id"]

        if old_message_id:
            try:
                old_message = await channel.fetch_message(old_message_id)
                await old_message.delete()

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

    formatted_message = message

    sticky_config[channel.id] = {
        "text": formatted_message,
        "last_message_id": None,
    }

    embed = discord.Embed(
        title="📌 Announcement",
        description=formatted_message,
        color=discord.Color.blue(),
    )

    embed.set_footer(
        text="This is a sticky message pinned to the bottom."
    )

    initial_sticky = await channel.send(embed=embed)
    sticky_config[channel.id]["last_message_id"] = initial_sticky.id

    await interaction.response.send_message(
        f"📌 Sticky announcement active in {channel.mention}!",
        ephemeral=True,
    )


@bot.tree.command(
    name="removesticky",
    description="Remove a sticky announcement from a channel.",
)
@app_commands.describe(
    channel="The channel to clear the sticky announcement from."
)
@app_commands.checks.has_permissions(administrator=True)
async def removesticky(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
):
    if channel.id not in sticky_config:
        await interaction.response.send_message(
            f"❌ No active sticky announcement found in {channel.mention}.",
            ephemeral=True,
        )
        return

    message_id = sticky_config[channel.id]["last_message_id"]

    if message_id:
        try:
            old_message = await channel.fetch_message(message_id)
            await old_message.delete()

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass

    del sticky_config[channel.id]

    await interaction.response.send_message(
        f"🛑 Sticky announcement removed from {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(
    name="autorole",
    description="Automatically assign a role to new members.",
)
@app_commands.describe(
    role="The role to assign to new members."
)
@app_commands.checks.has_permissions(administrator=True)
async def autorole(
    interaction: discord.Interaction,
    role: discord.Role,
):
    autorole_config[interaction.guild_id] = role.id

    await interaction.response.send_message(
        f"✅ Auto-role configured! New members will get **{role.name}**.",
        ephemeral=True,
    )


@bot.tree.command(
    name="autoreact",
    description="Automatically react to messages or images in a channel.",
)
@app_commands.describe(
    channel="The channel to auto-react in.",
    emoji="The emoji to use, such as 👍 or 🔥.",
    trigger_on="Choose messages, images, or both.",
)
@app_commands.checks.has_permissions(administrator=True)
async def autoreact(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    emoji: str,
    trigger_on: Literal["message", "image", "both"],
):
    autoreact_config[channel.id] = {
        "emoji": emoji,
        "trigger_on": trigger_on,
    }

    await interaction.response.send_message(
        f"✅ Auto-react configured! Reacting with {emoji} to "
        f"**{trigger_on}** in {channel.mention}.",
        ephemeral=True,
    )


# --- SLASH COMMAND ERROR HANDLER ---

@autorole.error
@autoreact.error
@stickyannouncement.error
@removesticky.error
@ticket_panel.error
async def command_error_handler(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        message = (
            "❌ You must have Administrator permissions to run "
            "this setup command."
        )
    else:
        print(f"Slash command error: {error}")
        message = f"❌ An unexpected error occurred: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )


# --- START BOT ---

keep_alive()

token = os.getenv("DISCORD_TOKEN")

if not token:
    raise RuntimeError(
        "DISCORD_TOKEN is missing. Set it in your hosting environment."
    )

bot.run(token)
