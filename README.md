# 🎵 KenKonic - Discord Music Bot

**KenKonic** is a powerful and feature-rich Discord bot that plays music from **YouTube**, **YouTube Playlists**, and **Spotify links**. It supports modern **slash commands**, **queues**, and has intelligent Spotify-to-YouTube conversion via search.

---

## 🚀 Features

- ✅ Slash command interface (Discord API v10)
- ✅ Play music via:
  - YouTube search terms
  - YouTube video or playlist URLs
  - Spotify **track**, **album**, or **playlist** links
- 🎧 Queue system with priority support (`/playnext`)
- 🎵 Supports pause/resume/skip/stop
- 🔊 Plays high-quality audio via FFmpeg
- 🦅 Includes a fun `/geier` command

---

## 🛠 Requirements

- Python 3.10+
- A Discord Bot Token
- [FFmpeg](https://ffmpeg.org/download.html) installed and in PATH
- Spotify API credentials (for Spotify support)

---

## 📦 Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd YOUR_REPO_NAME
   ```

2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   > Make sure `ffmpeg` is installed and accessible from your command line.

3. Create a `.env` file or set these variables in your script:

   ```env
   DISCORD_TOKEN=your-discord-token
   SPOTIFY_CLIENT_ID=your-client-id
   SPOTIFY_CLIENT_SECRET=your-client-secret
   ```

   Or hardcode them in your Python file:

   ```python
   SPOTIFY_CLIENT_ID = 'your-client-id'
   SPOTIFY_CLIENT_SECRET = 'your-client-secret'
   bot.run('your-discord-token')
   ```

---

## 📚 Commands

| Command             | Description                                        |
|---------------------|----------------------------------------------------|
| `/join`             | Join your current voice channel                    |
| `/leave`            | Leave the voice channel                            |
| `/play [url/query]` | Play music via YouTube, Spotify, or a search term  |
| `/playnext`         | Queue a song to play immediately after the current |
| `/pause`            | Pause the current song                             |
| `/resume`           | Resume the paused song                             |
| `/skip`             | Skip the current song                              |
| `/stop`             | Stop playback and clear the queue                  |
| `/queue`            | Show the current queue                             |
| `/geier`            | Just... see for yourself 😅                         |
| `/help`             | Show help message                                  |

---

## 🧠 How Spotify Support Works

When you input a Spotify **track**, **album**, or **playlist** link, the bot uses the [Spotify API](https://developer.spotify.com/) to retrieve song titles and artists, then **searches YouTube** for playable matches using `yt-dlp`.

- Only the first **15 tracks** are queued for albums/playlists (can be adjusted).
- Purely search-based: there’s no direct streaming from Spotify.

---

## 🐞 Troubleshooting

- **Nothing plays?**
  - Make sure your bot has permission to **join and speak** in the voice channel.
  - Check that **FFmpeg** is correctly installed.

- **Spotify errors?**
  - Double-check your **client ID/secret**.
  - Ensure the Spotify API is accessible.

- **Command not working?**
  - Use `/` to see registered commands.
  - Try restarting the bot to re-sync slash commands.

---

## 🧑‍💻 Credits

- Built with [discord.py](https://discordpy.readthedocs.io/)
- Music powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Spotify integration via [spotipy](https://spotipy.readthedocs.io/)

---

## 📜 License

MIT License. Free to use, modify, and share.

---

⚠️ **Disclaimer**

This project is intended for educational and personal use only.

- This bot does **not stream music from Spotify**. It only uses the **Spotify Web API** to retrieve public metadata (track name, artist).
- Audio is played using YouTube via `yt-dlp`.
- Please make sure to comply with the Terms of Service of **Discord**, **YouTube**, and **Spotify**.
- The author does not take any responsibility for misuse or violations of platform rules.

## ❤️ Support

Give the repo a ⭐ if you like it!  
Made with 💡
