# Discord Bot (Render)

## Files to upload to GitHub
- `main.py` — bot source code and existing commands
- `requirements.txt` — Python dependencies
- `.gitignore` — ignores local Python files and secrets

No `render.yaml` is required when configuring the service manually in Render.

## Render setup
1. Create a **Web Service** connected to this GitHub repository.
2. Runtime: **Python**.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python main.py`
5. In Render's **Environment** settings, add `DISCORD_TOKEN` with your Discord bot token as its value. Do not put the token in `main.py` or commit it to GitHub.
6. Deploy the service.

## Discord Developer Portal
Make sure the bot has the permissions it needs in your server. Since this bot uses prefix commands, enable **Message Content Intent** in the Bot settings. Give it permission to view/send messages, embed links, add reactions, and use external emojis if the custom emoji comes from another server.

The bot's giveaway command is `-gstart <duration> <number_of_winners> <prize>`, for example:
`-gstart 10m 1 Minecraft Rank`
