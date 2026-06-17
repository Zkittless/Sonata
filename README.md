# 🌸 Sonata — Discord Music Bot

A holographic pink music bot with clean UI, button controls, and Spotify support.

---

## ⚡ Quick Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

You'll also need **FFmpeg** installed on your system:
- **Windows:** Download from https://ffmpeg.org/download.html and add to PATH
- **Mac:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

### 2. Configure your .env
```bash
cp .env.example .env
```
Fill in your tokens in `.env`:
- `DISCORD_TOKEN` — from https://discord.com/developers/applications
- `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET` — from https://developer.spotify.com/dashboard *(optional but recommended)*

### 3. Run the bot
```bash
python bot.py
```

---

## 🎵 Commands

| Command | Description |
|---|---|
| `/play <song or URL>` | Play a song by name, YouTube URL, or Spotify link |
| `/queue` | View the current queue |
| `/skip` | Skip the current song |
| `/pause` | Pause playback *(DJ only)* |
| `/resume` | Resume playback *(DJ only)* |
| `/stop` | Stop and disconnect *(DJ only)* |
| `/volume <0-100>` | Set playback volume |
| `/remove <position>` | Remove a song from the queue *(DJ only)* |
| `/lyrics [song]` | Get lyrics for current or searched song |

## 🎛 Button Controls (on Now Playing embed)
- ⏸ Pause / Resume
- ⏭ Skip
- 🔁 Loop toggle
- 🔀 Shuffle queue
- ⏹ Stop & disconnect

---

## 🔐 DJ Role
Create a role named **DJ** in your server. Only DJ role members and Admins can use `/pause`, `/resume`, `/stop`, and `/remove`.

---

## 🎨 Theme
Holographic pink embeds throughout — colors, progress bars, and footer branding all match the aesthetic.
