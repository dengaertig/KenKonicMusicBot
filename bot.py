import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import yt_dlp
import os
import json
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests

# Bot Konfiguration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Entferne den Standard-Hilfe-Befehl
bot.remove_command('help')

# Spotify API Konfiguration
SPOTIFY_CLIENT_ID = ''
SPOTIFY_CLIENT_SECRET = ''

# Spotify Client initialisieren
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    ))
except Exception as e:
    print(f"Fehler bei der Spotify-Authentifizierung: {e}")
    sp = None

# YT-DLP Konfigurationsoptionen
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': True,
    'quiet': False,
    'no_warnings': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# Spotify URL Pattern
SPOTIFY_TRACK_URL_REGEX = r'https?://open\.spotify\.com/(?:[a-z-]+/)?track/([a-zA-Z0-9]+)(?:\?.*)?'
SPOTIFY_ALBUM_URL_REGEX = r'https?://open\.spotify\.com/(?:[a-z-]+/)?album/([a-zA-Z0-9]+)(?:\?.*)?'
SPOTIFY_PLAYLIST_URL_REGEX = r'https?://open\.spotify\.com/(?:[a-z-]+/)?playlist/([a-zA-Z0-9]+)(?:\?.*)?'

async def process_spotify_url(url):
    """Verarbeitet eine Spotify-URL und gibt eine Liste von YouTube-Suchbegriffen zurück"""
    if not sp:
        print("Spotify-API ist nicht konfiguriert")
        return None
    
    try:
        # Track URL
        track_match = re.match(SPOTIFY_TRACK_URL_REGEX, url)
        if track_match:
            track_id = track_match.group(1)
            print(f"Track ID erkannt: {track_id}")
            track_info = sp.track(track_id)
            artist = track_info['artists'][0]['name']
            title = track_info['name']
            print(f"Track Info gefunden: {artist} - {title}")
            return [(f"{artist} - {title}", "track")]
    
        # Album URL
        album_match = re.match(SPOTIFY_ALBUM_URL_REGEX, url)
        if album_match:
            album_id = album_match.group(1)
            album_info = sp.album(album_id)
            results = []
            for track in album_info['tracks']['items']:
                artist = track['artists'][0]['name']
                title = track['name']
                results.append((f"{artist} - {title}", "album_track"))
            return results
        
        # Playlist URL
        playlist_match = re.match(SPOTIFY_PLAYLIST_URL_REGEX, url)
        if playlist_match:
            playlist_id = playlist_match.group(1)
            results = []
            
            # Initial request
            playlist_tracks = sp.playlist_tracks(playlist_id, limit=100)
            
            # Process tracks
            for track_info in playlist_tracks['items']:
                if track_info['track']:
                    artist = track_info['track']['artists'][0]['name']
                    title = track_info['track']['name']
                    results.append((f"{artist} - {title}", "playlist_track"))
            
            # Handle pagination for playlists with more than 100 tracks
            while playlist_tracks['next']:
                playlist_tracks = sp.next(playlist_tracks)
                for track_info in playlist_tracks['items']:
                    if track_info['track']:
                        artist = track_info['track']['artists'][0]['name']
                        title = track_info['track']['name']
                        results.append((f"{artist} - {title}", "playlist_track"))
            
            return results
    
    except Exception as e:
        print(f"Fehler beim Verarbeiten der Spotify-URL: {str(e)}")
        raise e
    
    print(f"Keine passende URL-Struktur gefunden für: {url}")
    return None

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.2):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    def cleanup(self):
        if hasattr(self, 'process'):
            self.process.kill()
        if hasattr(self, 'original'):
            self.original.cleanup()

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            print(f"Erfolgreich Daten von URL erhalten: {url}")
            
            if 'entries' in data:
                # Bei Playlists nur das erste Video nehmen
                data = data['entries'][0]
            
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            print(f"Dateiname/URL: {filename}")
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            print(f"Fehler beim Verarbeiten der URL {url}: {str(e)}")
            raise e

    @classmethod
    async def from_search(cls, search_query, *, loop=None, stream=True):
        """Erstellt eine Source aus einer Textsuche statt einer direkten URL"""
        loop = loop or asyncio.get_event_loop()
        try:
            # YoutubeDL verwendet eine Suche, wenn keine URL erkannt wird
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{search_query}", download=not stream))
            print(f"Erfolgreich nach '{search_query}' gesucht")
            
            if 'entries' in data:
                # Bei Suchergebnissen das erste Video nehmen
                data = data['entries'][0]
            
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            print(f"Dateiname/URL: {filename}")
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            print(f"Fehler bei der Suche nach '{search_query}': {str(e)}")
            raise e

# Music Queue-System
class MusicPlayer:
    def __init__(self, interaction):
        self.bot = interaction.client
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.cog = interaction.guild.voice_client

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        
        self.current = None
        self.volume = 0.5
        
        self.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            self.next.clear()
            
            # Warten auf das nächste Lied in der Queue
            try:
                async with asyncio.timeout(300):  # 5 Minuten timeout
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self.guild)
            
            # Voice Client absichern
            if not self.guild.voice_client:
                return
                
            # Aktuelles Lied setzen und abspielen
            self.current = source
            self.guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            await self.channel.send(f'**Spiele jetzt:** `{source.title}`')
            
            # Warten bis das Lied fertig ist
            await self.next.wait()
            
            # Datei aufräumen
            source.cleanup()
            self.current = None

    def destroy(self, guild):
        return self.bot.loop.create_task(self.cleanup(guild))
    
    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass


# Player Dictionary zur Verwaltung der Musik-Player pro Server
players = {}

def get_player(interaction):
    """Retrieve or create a player for a guild."""
    guild_id = interaction.guild_id
    try:
        player = players[guild_id]
    except KeyError:
        player = MusicPlayer(interaction)
        players[guild_id] = player
        
    return player

async def cleanup(guild):
    """Bereinigt den Voice-Client und den Player für eine Guild."""
    try:
        await guild.voice_client.disconnect()
    except AttributeError:
        pass
        
    try:
        del players[guild.id]
    except KeyError:
        pass

@bot.event
async def on_ready():
    print(f'Bot ist gestartet als {bot.user}')
    
    # Synchronisiere die Slash Commands mit Discord
    try:
        synced = await bot.tree.sync()
        print(f'{len(synced)} Slash-Commands synchronisiert.')
    except Exception as e:
        print(f'Fehler beim Synchronisieren der Slash-Commands: {e}')

@bot.tree.command(name="join", description="Bot tritt deinem Sprachkanal bei")
async def join(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("Du musst in einem Voice-Channel sein!")
        return
            
    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client
    
    if voice_client is not None:
        await voice_client.move_to(channel)
    else:
        await channel.connect()
        
    await interaction.response.send_message(f'Mit Voice-Channel **{channel}** verbunden.')

@bot.tree.command(name="play", description="Spielt Musik, Playlists oder Spotify-Links ab")
@app_commands.describe(url="URL oder Suchbegriff (YouTube-Video, YouTube-Playlist, Spotify-Link oder freier Suchbegriff)")
async def play(interaction: discord.Interaction, url: str):
    # Verzögerte Antwort, da der Befehl möglicherweise länger dauert
    await interaction.response.defer()
    
    # Überprüfen, ob der Nutzer in einem Voice-Channel ist
    if interaction.guild.voice_client is None:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            await interaction.followup.send("Du bist nicht mit einem Voice-Channel verbunden.")
            return
    
    player = get_player(interaction)
    
    # FALL 1: Spotify-Link verarbeiten
    if 'open.spotify.com' in url:
        try:
            await interaction.followup.send("Spotify-Link erkannt, verarbeite...")
            spotify_results = await process_spotify_url(url)
            
            if not spotify_results:
                await interaction.followup.send("Konnte den Spotify-Link nicht verarbeiten.")
                return
            
            # Bei einzelnem Track
            if len(spotify_results) == 1 and spotify_results[0][1] == "track":
                search_query = spotify_results[0][0]
                await interaction.followup.send(f"Suche nach: **{search_query}**")
                source = await YTDLSource.from_search(search_query, loop=bot.loop)
                await player.queue.put(source)
                await interaction.followup.send(f'**{source.title}** zur Warteschlange hinzugefügt.')
            
            # Bei Album oder Playlist
            else:
                await interaction.followup.send(f'**{len(spotify_results)} Songs** gefunden. Füge sie zur Warteschlange hinzu...')
                songs_added = 0
                
                # Begrenze auf 15 Songs, um API-Limits zu respektieren
                max_songs = min(15, len(spotify_results))
                
                for i, (search_query, _) in enumerate(spotify_results[:max_songs]):
                    try:
                        source = await YTDLSource.from_search(search_query, loop=bot.loop)
                        await player.queue.put(source)
                        songs_added += 1
                        
                        # Feedback alle 5 Songs
                        if songs_added % 5 == 0:
                            await interaction.followup.send(f'**{songs_added}/{max_songs}** Songs zur Warteschlange hinzugefügt...')
                    except Exception as e:
                        print(f"Fehler beim Hinzufügen von '{search_query}': {str(e)}")
                
                if len(spotify_results) > max_songs:
                    await interaction.followup.send(f'**{songs_added}** Songs zur Warteschlange hinzugefügt. (Auf {max_songs} begrenzt)')
                else:
                    await interaction.followup.send(f'**{songs_added}** Songs zur Warteschlange hinzugefügt!')
        
        except Exception as e:
            await interaction.followup.send(f'Fehler beim Verarbeiten des Spotify-Links: {str(e)}')
            import traceback
            traceback.print_exc()
    
    # FALL 2: YouTube-Playlist verarbeiten
    elif "list=" in url:
        await interaction.followup.send(f'YouTube-Playlist erkannt, verarbeite...')
        
        playlist_id = url.split("list=")[1].split("&")[0]
        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        await interaction.followup.send(f'Playlist-ID erkannt: {playlist_id}')
        
        # Playlist-spezifische Optionen
        playlist_opts = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'noplaylist': False,  # Wichtig: Playlists erlauben
            'playlist_items': '1-15',  # Erhöht auf 15 Videos
            'extract_flat': True
        }
        
        try:
            # Direktes Extrahieren der Playlist
            with yt_dlp.YoutubeDL(playlist_opts) as ydl:
                print(f"Versuche Playlist zu laden: {playlist_url}")
                info = ydl.extract_info(playlist_url, download=False)
                
                if info is None:
                    await interaction.followup.send(f'Fehler: Konnte keine Playlist-Informationen abrufen.')
                    return
                    
                if 'entries' not in info:
                    # Spezielle Behandlung für Mix-Playlists (oft mit RD beginnend)
                    if playlist_id.startswith("RD"):
                        await interaction.followup.send("YouTube-Mix erkannt. Diese Art von Playlist wird nicht vollständig unterstützt. Versuche, das erste Video zu spielen...")
                        # Versuchen, zumindest das erste Video zu spielen
                        try:
                            # Extrahiere nur das erste Video aus dem Mix
                            with yt_dlp.YoutubeDL({**playlist_opts, 'noplaylist': True}) as single_ydl:
                                single_info = single_ydl.extract_info(url, download=False)
                                if single_info:
                                    video_url = single_info.get('webpage_url') or url
                                    source = await YTDLSource.from_url(video_url, loop=bot.loop)
                                    await player.queue.put(source)
                                    await interaction.followup.send(f'**{source.title}** zur Warteschlange hinzugefügt.')
                                else:
                                    await interaction.followup.send("Konnte kein Video aus dem Mix extrahieren.")
                        except Exception as e:
                            await interaction.followup.send(f'Fehler beim Hinzufügen des Videos: {str(e)}')
                    else:
                        await interaction.followup.send(f'Fehler: Keine Videos gefunden. Stelle sicher, dass die Playlist öffentlich ist.')
                    return
                    
                entries = info['entries']
                if not entries:
                    await interaction.followup.send('Keine Videos in der Playlist gefunden.')
                    return
                    
                # Filtern Sie None-Einträge heraus
                valid_entries = [entry for entry in entries if entry is not None]
                
                if not valid_entries:
                    await interaction.followup.send('Keine gültigen Videos in der Playlist gefunden.')
                    return
                    
                await interaction.followup.send(f'**{len(valid_entries)} Videos** in der Playlist gefunden. Füge sie zur Warteschlange hinzu...')
                
                videos_added = 0
                
                for entry in valid_entries:
                    try:
                        video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                        print(f"Versuche Video hinzuzufügen: {video_url}")
                        source = await YTDLSource.from_url(video_url, loop=bot.loop)
                        await player.queue.put(source)
                        videos_added += 1
                        if videos_added % 5 == 0:
                            await interaction.followup.send(f'**{videos_added}/{len(valid_entries)}** Videos zur Warteschlange hinzugefügt...')
                    except Exception as e:
                        print(f"Fehler beim Hinzufügen von Video {entry.get('id', 'unbekannt')}: {str(e)}")
                        # Weitermachen mit dem nächsten Video
                
                await interaction.followup.send(f'**{videos_added}** Videos zur Warteschlange hinzugefügt!')
                
        except Exception as e:
            await interaction.followup.send(f'Fehler beim Laden der Playlist: {str(e)}')
            print(f"Ausführlicher Fehler: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # FALL 3: Normales YouTube-Video oder Suchbegriff
    else:
        try:
            if "youtube.com/watch" in url or "youtu.be/" in url:
                # Direkter YouTube-Link
                source = await YTDLSource.from_url(url, loop=bot.loop)
            else:
                # Suchbegriff
                await interaction.followup.send(f'Suche nach: **{url}**')
                source = await YTDLSource.from_search(url, loop=bot.loop)
            
            await player.queue.put(source)
            await interaction.followup.send(f'**{source.title}** zur Warteschlange hinzugefügt.')
        except Exception as e:
            await interaction.followup.send(f'Ein Fehler ist aufgetreten: {str(e)}')
            import traceback
            traceback.print_exc()

@bot.tree.command(name="playnext", description="Spielt ein Lied direkt nach dem aktuellen Lied ab")
@app_commands.describe(url="URL oder Suchbegriff für das Lied")
async def playnext(interaction: discord.Interaction, url: str):
    # Verzögerte Antwort, da der Befehl möglicherweise länger dauert
    await interaction.response.defer()
    
    # Überprüfen, ob der Nutzer in einem Voice-Channel ist
    if interaction.guild.voice_client is None:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            await interaction.followup.send("Du bist nicht mit einem Voice-Channel verbunden.")
            return
    
    player = get_player(interaction)
    
    # Verarbeite den Link oder die Suche
    try:
        # Überprüfen, ob es ein Spotify-Link ist
        if 'open.spotify.com' in url:
            await interaction.followup.send("Spotify-Link erkannt, verarbeite...")
            spotify_results = await process_spotify_url(url)
            
            if not spotify_results:
                await interaction.followup.send("Konnte den Spotify-Link nicht verarbeiten.")
                return
            
            # Bei einzelnem Track
            if len(spotify_results) == 1 and spotify_results[0][1] == "track":
                search_query = spotify_results[0][0]
                await interaction.followup.send(f"Suche nach: **{search_query}**")
                source = await YTDLSource.from_search(search_query, loop=bot.loop)
            else:
                await interaction.followup.send("Der `playnext` Befehl unterstützt nur einzelne Tracks, keine Alben oder Playlists.")
                return
        else:
            # Normaler YouTube- oder direkter Link
            source = await YTDLSource.from_url(url, loop=bot.loop)
        
        # Füge den Track an die erste Position in der Queue ein
        current_queue = list(player.queue._queue)
        
        # Leere die aktuelle Queue
        while not player.queue.empty():
            await player.queue.get()
        
        # Füge den neuen Song hinzu
        await player.queue.put(source)
        
        # Füge die restlichen Songs wieder hinzu
        for item in current_queue:
            await player.queue.put(item)
        
        await interaction.followup.send(f'**{source.title}** wird als nächstes abgespielt.')
        
    except Exception as e:
        await interaction.followup.send(f'Ein Fehler ist aufgetreten: {str(e)}')

@bot.tree.command(name="pause", description="Pausiert die aktuelle Wiedergabe")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client is None:
        await interaction.response.send_message("Ich bin nicht mit einem Voice-Channel verbunden.")
    elif interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("Wiedergabe pausiert.")
    else:
        await interaction.response.send_message("Es wird derzeit nichts abgespielt.")

@bot.tree.command(name="resume", description="Setzt die pausierte Wiedergabe fort")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client is None:
        await interaction.response.send_message("Ich bin nicht mit einem Voice-Channel verbunden.")
    elif interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("Wiedergabe fortgesetzt.")
    else:
        await interaction.response.send_message("Die Wiedergabe ist nicht pausiert.")

@bot.tree.command(name="skip", description="Überspringt das aktuelle Lied")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client is None:
        await interaction.response.send_message("Ich bin nicht mit einem Voice-Channel verbunden.")
    elif not interaction.guild.voice_client.is_playing():
        await interaction.response.send_message("Es wird derzeit nichts abgespielt.")
    else:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Lied übersprungen.")

@bot.tree.command(name="stop", description="Stoppt die Wiedergabe und löscht die Queue")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client is None:
        await interaction.response.send_message("Ich bin nicht mit einem Voice-Channel verbunden.")
    else:
        await cleanup(interaction.guild)
        await interaction.response.send_message("Wiedergabe gestoppt und Queue geleert.")

@bot.tree.command(name="geier", description="Ein lustiger Geier-Befehl")
async def geier(interaction: discord.Interaction):
    await interaction.response.send_message("Es wurde wieder gegeiert. Verdammte Geier!")

@bot.tree.command(name="leave", description="Verlässt den Voice-Channel")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client is not None:
        await cleanup(interaction.guild)
        await interaction.response.send_message("Voice-Channel verlassen.")
    else:
        await interaction.response.send_message("Ich bin nicht mit einem Voice-Channel verbunden.")

@bot.tree.command(name="queue", description="Zeigt die aktuelle Warteschlange an")
async def queue_info(interaction: discord.Interaction):
    if interaction.guild.voice_client is None:
        await interaction.response.send_message("Ich bin nicht mit einem Voice-Channel verbunden.")
        return

    player = get_player(interaction)
    
    if player.current is None:
        await interaction.response.send_message("Es wird derzeit nichts abgespielt.")
        return
        
    # Queue Ausgabe vorbereiten
    upcoming = list(player.queue._queue)
    
    # Aktuelle Queue-Länge berechnen
    queue_length = len(upcoming)
    
    # Embed-Nachricht erstellen
    embed = discord.Embed(
        title="Musik-Warteschlange",
        description=f"Aktuell **{queue_length}** Lieder in der Warteschlange",
        color=discord.Color.blue()
    )
    
    # Aktuelles Lied hinzufügen
    embed.add_field(
        name="Aktuell spielt:",
        value=f"🎵 **{player.current.title}**",
        inline=False
    )
    
    # Queue-Einträge hinzufügen (maximal 10 anzeigen)
    if upcoming:
        queue_list = ""
        for i, song in enumerate(upcoming[:10], 1):
            queue_list += f"{i}. **{song.title}**\n"
            
        if len(upcoming) > 10:
            queue_list += f"\n... und **{len(upcoming) - 10}** weitere Lieder"
            
        embed.add_field(
            name="Als nächstes:",
            value=queue_list,
            inline=False
        )
    else:
        embed.add_field(
            name="Als nächstes:",
            value="Keine weiteren Lieder in der Warteschlange",
            inline=False
        )
        
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Zeigt die Hilfe für die Bot-Befehle an")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="GeierMusicAPP - Hilfe",
        description="Hier sind alle verfügbaren Befehle:",
        color=discord.Color.blue()
    )
    
    # Music commands
    music_commands = """
    `/join` - Bot tritt deinem Voice-Channel bei
    `/leave` - Bot verlässt den Voice-Channel
    `/play [url/suchbegriff]` - Spielt Musik von YouTube, YouTube-Playlists oder Spotify
    `/playnext [url/suchbegriff]` - Spielt ein Lied direkt nach dem aktuellen Lied ab
    `/pause` - Pausiert die aktuelle Wiedergabe
    `/resume` - Setzt die pausierte Wiedergabe fort
    `/skip` - Überspringt das aktuelle Lied
    `/stop` - Stoppt die Wiedergabe und löscht die Queue
    `/queue` - Zeigt die aktuelle Warteschlange an
    `/geier` - Ein lustiger Geier-Befehl
    """
    
    embed.add_field(name="Musik-Befehle", value=music_commands, inline=False)
    
    # Set footer with author info
    embed.set_footer(text="Erstellt von KenKo", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
    
    await interaction.response.send_message(embed=embed)

# Hier deinen Bot-Token einfügen
bot.run('')