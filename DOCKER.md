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

Suchanfragen werden zuerst auf YouTube und bei Fehlschlag automatisch auf
SoundCloud aufgelöst. `yt-dlp` läuft als Subprozess und aktualisiert sich beim
Start sowie alle 12 Stunden selbst (`pip install --upgrade`), sodass Änderungen
an den Plattform-APIs ohne Rebuild oder Neustart des Containers geheilt werden -
es sind keine Cookies oder API-Tokens nötig.

Gegen YouTubes Bot-Erkennung ("Sign in to confirm you're not a bot", typisch bei
Server-/Datacenter-IPs) läuft der Sidecar-Service `pot-provider`
([bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)),
der die von YouTube verlangten "PO Tokens" automatisch generiert - ohne Account
und ohne Cookies. Der Bot findet ihn über die Umgebungsvariable
`POT_PROVIDER_URL` (gesetzt in `docker-compose.yml`). Fällt der Service aus oder
ist die Variable nicht gesetzt (z.B. lokale Entwicklung), läuft die Musik ganz
normal weiter; YouTube kann dann lediglich wieder einzelne Anfragen ablehnen,
wofür der SoundCloud-Fallback greift.

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
   `yt-dlp` reagieren muss. Der Bot aktualisiert `yt-dlp` (samt PO-Token-Plugin)
   deshalb automatisch beim Start und alle 12 Stunden - ein manuelles Update oder
   Rebuild ist normalerweise nicht nötig. Falls Songs trotzdem länger nicht laden,
   zeigen die Logs (`yt-dlp self-update ...`), ob das Update fehlschlägt.

4. Meldet YouTube "Sign in to confirm you're not a bot", prüfe, ob der
   `pot-provider`-Service läuft (`docker-compose ps`, `docker-compose logs
   pot-provider`). Gelegentliches `docker-compose pull pot-provider` hält das
   Provider-Image aktuell, falls sich Client- und Server-Version zu weit
   auseinanderentwickeln (yt-dlp warnt dann in den Logs).

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
