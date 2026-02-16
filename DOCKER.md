# Klopfer-Bot Docker Deployment

Diese Anleitung beschreibt, wie du den Klopfer-Bot mit Docker und Lavalink deployen kannst.

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
   DISCORD_TOKEN=dein_discord_bot_token_hier
   ```

2. **Konfiguration anpassen (optional)**

   - `config.json`: Passe den Bot-Prefix und den Invite-Link an
   - `lavalink/application.yml`: Lavalink-Konfiguration (Passwort, Audio-Quellen, etc.)

   Hinweis: Beim `docker-compose up` wird automatisch eine Lavalink-Konfiguration
   in einem Docker-Volume erzeugt. Dabei wird die neueste `youtube-plugin` Version
   aus dem offiziellen `lavalink-devs/youtube-source` GitHub-Release verwendet.
   Du musst keine Plugin-JAR manuell in den Plugin-Ordner legen.

   Portainer-Hinweis: Der Stack verwendet absichtlich keine relativen Host-Bind-Mounts
   für Lavalink-Konfigurationsdateien, damit das Setup in Portainer stabil funktioniert.

## Deployment

### Mit Docker Compose starten

```bash
docker-compose up -d
```

Der Bot und Lavalink werden automatisch gestartet. Der Bot wartet, bis Lavalink vollständig hochgefahren ist.

### Logs ansehen

```bash
# Alle Logs
docker-compose logs -f

# Nur Bot-Logs
docker-compose logs -f bot

# Nur Lavalink-Logs
docker-compose logs -f lavalink
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

Der Setup besteht aus zwei Services:

1. **Lavalink** (Port 2333)
   - Audio-Verarbeitungsserver
   - Unterstützt YouTube, SoundCloud, Bandcamp, Twitch, Vimeo
   - Läuft in eigenem Container

2. **Klopfer-Bot**
   - Discord Bot mit allen Cogs (Fun, General, Klopfen, Moderation, Music, Owner, Rollbutler)
   - Verbindet sich automatisch mit Lavalink
   - Verwendet SQLite-Datenbank (in Volume gemountet)

## Volumes

- `./database`: Bot-Datenbank (persistent)
- `./lavalink/logs`: Lavalink-Logs (persistent)
- `./config.json`: Bot-Konfiguration (read-only)
- `./lavalink/application.yml`: Lavalink-Konfiguration (read-only)

## Netzwerk

Beide Services kommunizieren über das interne Docker-Netzwerk `klopfer-network`. Der Bot kann Lavalink über den Hostnamen `lavalink` erreichen.

## Troubleshooting

### Bot verbindet sich nicht mit Lavalink

1. Überprüfe, ob Lavalink läuft:
   ```bash
   docker-compose ps
   ```

2. Überprüfe die Lavalink-Logs:
   ```bash
   docker-compose logs lavalink
   ```

3. Stelle sicher, dass das Passwort in `docker-compose.yml` und `lavalink/application.yml` übereinstimmt

### Musik-Befehle funktionieren nicht

1. Stelle sicher, dass der Bot die nötigen Berechtigungen auf Discord hat:
   - Voice Channel beitreten
   - In Voice Channels sprechen
   - Nachrichten senden

2. Überprüfe die Bot-Logs auf Fehler:
   ```bash
   docker-compose logs bot
   ```

## Entwicklung

Für lokale Entwicklung ohne Docker:

1. Installiere die Dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Starte nur Lavalink mit Docker:
   ```bash
   docker-compose up -d lavalink
   ```

3. Führe den Bot lokal aus:
   ```bash
   python bot.py
   ```

Der Bot verwendet automatisch `localhost` als Lavalink-Host, wenn keine Umgebungsvariablen gesetzt sind.

## Produktions-Hinweise

- Ändere das Standard-Passwort in `lavalink/application.yml` und `docker-compose.yml`
- Verwende ein `.env` File für sensible Daten (nicht in Git committen!)
- Überwache die Logs regelmäßig
- Erstelle regelmäßige Backups der Datenbank
- Passe die Java Memory Settings (`_JAVA_OPTIONS=-Xmx2G`) basierend auf deiner Server-Kapazität an
