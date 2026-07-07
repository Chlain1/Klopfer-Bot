# Klopfer-Bot Docker Deployment

Diese Anleitung beschreibt, wie du den Klopfer-Bot mit Docker deployen kannst.

## Voraussetzungen

- Docker und Docker Compose installiert
- Discord Bot Token

## Setup

1. **Umgebungsvariablen konfigurieren**

   Kopiere die `.env.example` Datei zu `.env`:
   ```bash
   cp .env.example .env
   ```

   Öffne die `.env` Datei und füge deinen Discord Bot Token ein:
   ```
   TOKEN=dein_discord_bot_token_hier
   ```

2. **Konfiguration anpassen (optional)**

   - `config.json`: Passe den Bot-Prefix und den Invite-Link an

## Deployment

### Mit Docker Compose starten

```bash
docker-compose up -d
```

### Logs ansehen

```bash
docker-compose logs -f bot
```

### Services stoppen

```bash
docker-compose down
```

### Services neu starten

```bash
docker-compose restart
```

## Architektur

Der Bot spielt Musik (YouTube, SoundCloud, Bandcamp, ...) ohne einen externen
Lavalink-Server. Tracks werden über `yt-dlp` aufgelöst und per FFmpeg direkt in
den Voice-Channel gestreamt - es wird zu keinem Zeitpunkt etwas heruntergeladen
oder auf die Festplatte geschrieben. Das spart Speicherplatz und Zeit und
entfällt die Abhängigkeit von einem separaten, ausfallanfälligen Lavalink-Dienst.

## Volumes

- `bot-database`: Bot-Datenbank (persistent)
- `bot-leaderboard`: Leaderboard-Daten (persistent)

## Troubleshooting

### Musik-Befehle funktionieren nicht

1. Stelle sicher, dass der Bot die nötigen Berechtigungen auf Discord hat:
   - Voice Channel beitreten
   - In Voice Channels sprechen
   - Nachrichten senden

2. Überprüfe die Bot-Logs auf Fehler:
   ```bash
   docker-compose logs bot
   ```

3. Manche Plattformen (z.B. YouTube) ändern gelegentlich ihre interne API, worauf
   `yt-dlp` reagieren muss. Falls Songs plötzlich nicht mehr laden, hilft meist
   ein Update von `yt-dlp` in `requirements.txt` gefolgt von einem Rebuild des
   Images.

## Entwicklung

Für lokale Entwicklung ohne Docker:

1. Installiere die Dependencies (inklusive FFmpeg, das systemweit installiert sein muss):
   ```bash
   pip install -r requirements.txt
   ```

2. Führe den Bot lokal aus:
   ```bash
   python bot.py
   ```

## Produktions-Hinweise

- Verwende ein `.env` File für sensible Daten (nicht in Git committen!)
- Überwache die Logs regelmäßig
- Erstelle regelmäßige Backups der Datenbank
