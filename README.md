# 🤖 BlkLine

> A serious Discord bot for starting, watching, and worshipping your Exaroton Minecraft server.

**BlkLine** is a sleek, focused bot built to remotely control and monitor a Minecraft server hosted on Exaroton. With automatic status checks, rich status embeds, and secure command-based startup, BlkLine is perfect for private communities or server admins who don’t want to rely on flaky browser sessions.

---

## ✨ Features

- 🛰️ **Scheduled Server Checks**  
  BlkLine automatically checks if your server is online every few hours and announces it when it wakes.

- 📟 **Manual Status Command**  
  Use `!mcstatus` in Discord to check player count, online status, and who's currently connected.

- 🚀 **Remote Server Start via Discord**  
  Use `!startserver` to remotely boot your Exaroton server using secure credentials.

- 🔐 **.env-Based Credential Storage**  
  Your Exaroton login and bot token stay out of the codebase and safe.

- 🎨 **Minimal, Beautiful Embeds**  
  No spammy blocks of text—just slick, readable updates in purple/gold cyberstyle.

---

## 🧰 Tech Stack

- Python 3.9+
- `discord.py`
- `mcstatus`
- `exaroton-api` (unofficial)
- `python-dotenv`

---

## 📦 Installation

1. Clone the repo:
   ```bash
   git clone https://github.com/yourusername/BlkLine.git
   cd BlkLine
