# Discord Bot Configuration
TOKEN = ""
ADMIN_ROLE_ID =   # Your admin role ID

# Kapowarr Configuration
KAPOWARR_URL = ""  # Your Kapowarr URL
KAPOWARR_API_KEY = ""

# ComicVine Configuration
COMICVINE_API_KEY = ""  # Get from https://comicvine.gamespot.com/api/

# Comic Monitor Configuration
COMIC_CHECK_ENABLED = True  # Enable/disable automatic comic checking
COMIC_CHECK_INTERVAL_HOURS = 24  # How often to check for new comics (in hours)
COMIC_CHECK_DAYS_BACK = 7  # How many days back to check for new releases
COMIC_AUTO_SEARCH = True  # Automatically search for downloads after adding comics

# Comic Download Notifications
COMIC_NOTIFICATIONS_ENABLED = True  # Enable/disable download notifications
COMIC_NOTIFICATIONS_CHANNEL_ID =   # Discord channel ID for notifications
COMIC_QUEUE_CHECK_INTERVAL = 60  # How often to check download queue (in seconds)

# Connection settings
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
RECONNECT_INTERVAL = 60  # Check connection every 60 seconds