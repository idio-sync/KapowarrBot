import os

def get_env_bool(key: str, default: bool = False) -> bool:
    """Convert environment variable to boolean."""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

def get_env_int(key: str, default: int = 0) -> int:
    """Convert environment variable to integer."""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def get_env_str(key: str, default: str = "") -> str:
    """Get environment variable as string."""
    return os.getenv(key, default)

# Discord Bot Configuration
TOKEN = get_env_str("DISCORD_TOKEN")
ADMIN_ROLE_ID = get_env_int("ADMIN_ROLE_ID")

# Kapowarr Configuration
KAPOWARR_URL = get_env_str("KAPOWARR_URL")
KAPOWARR_API_KEY = get_env_str("KAPOWARR_API_KEY")

# ComicVine Configuration
COMICVINE_API_KEY = get_env_str("COMICVINE_API_KEY")

# Comic Monitor Configuration
COMIC_CHECK_ENABLED = get_env_bool("COMIC_CHECK_ENABLED", True)
COMIC_CHECK_INTERVAL_HOURS = get_env_int("COMIC_CHECK_INTERVAL_HOURS", 24)
COMIC_CHECK_DAYS_BACK = get_env_int("COMIC_CHECK_DAYS_BACK", 7)
COMIC_AUTO_SEARCH = get_env_bool("COMIC_AUTO_SEARCH", True)

# Comic Download Notifications
COMIC_NOTIFICATIONS_ENABLED = get_env_bool("COMIC_NOTIFICATIONS_ENABLED", True)
COMIC_NOTIFICATIONS_CHANNEL_ID = get_env_int("COMIC_NOTIFICATIONS_CHANNEL_ID")
COMIC_QUEUE_CHECK_INTERVAL = get_env_int("COMIC_QUEUE_CHECK_INTERVAL", 60)

# Connection settings
MAX_RETRY_ATTEMPTS = get_env_int("MAX_RETRY_ATTEMPTS", 3)
RETRY_DELAY = get_env_int("RETRY_DELAY", 5)
RECONNECT_INTERVAL = get_env_int("RECONNECT_INTERVAL", 60)
