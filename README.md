Discord bot to interface with [Kapowarr](https://github.com/Casvt/Kapowarr) and manage your comic book collection. Original code by stan42069.

# Features
- Automatically checks every 24 hours for new comics that matches your set publisher(s) and will add/search them on Kapowarr (Currently set to Marvel, DC, and Dark Horse Comics)
- Search comics using the /search command to add comics to your library
- Browse your comic library using /comiclibrary command
- Manually check up to 60 days back for comics not in your library using and add/search them automatically /comic_check
- Lookup recently released comics on ComicVine using /comics_recent
- Browse your wanted comics that are missing issues and manually search for results within discord using /wantedcomics
- Queue notifications for downloads, imports, etc.
- Automatic and manual download supported if comic doesn't match

# Screenshots

<img width="500" height="481" alt="image" src="https://github.com/user-attachments/assets/65f53747-8ba4-4332-933e-479b86dec879" />

<img width="500" height="819" alt="image" src="https://github.com/user-attachments/assets/0bc6e0be-cd89-4407-adb8-3c3c985b3d40" />

<img width="500" height="796" alt="image" src="https://github.com/user-attachments/assets/60178b0f-e638-47cd-9185-2f31359ae807" />

# Usage
Docker:
```
docker pull idiosync000/kapowarrbot:latest
```
Then set the env veriables listed below.

Alternatively, run main.py with an .env file populated as shown below. 

# Enviornment Variable Configuration
```
DISCORD_TOKEN = "Your Bot Token"
ADMIN_ROLE_ID = "Your Admin Role ID"
KAPOWARR_URL = "Your Kapowarr URL"
KAPOWARR_API_KEY = " Your Kapowarr API Key"
COMICVINE_API_KEY = "Your Comicvine API Key""  # Get from https://comicvine.gamespot.com/api/
COMIC_CHECK_ENABLED = True  # Enable/disable automatic comic checking
COMIC_CHECK_INTERVAL_HOURS = 24  # How often to check for new comics (in hours)
COMIC_CHECK_DAYS_BACK = 7  # How many days back to check for new releases
COMIC_AUTO_SEARCH = True  # Automatically search for downloads after adding comics
COMIC_NOTIFICATIONS_ENABLED = True  # Enable/disable download notifications
COMIC_NOTIFICATIONS_CHANNEL_ID = "Your Channel ID"  # Discord channel ID for notifications
COMIC_QUEUE_CHECK_INTERVAL = 60  # How often to check download queue (in seconds)
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
RECONNECT_INTERVAL = 60  # Check connection every 60 seconds
```
