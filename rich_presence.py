"""
Discord Rich Presence module for Kapowarr comic library stats
Shows "Reading X comics" where X is the total file count from Kapowarr
"""

import asyncio
import aiohttp
import discord
from datetime import datetime
from typing import Optional, Dict, Any

# Import configuration from your config file
from config import (
    KAPOWARR_URL,
    KAPOWARR_API_KEY,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY,
    RECONNECT_INTERVAL
)


class KapowarrRichPresence:
    def __init__(self, bot: discord.Client):
        """
        Initialize the Rich Presence handler
        
        Args:
            bot: The Discord bot client instance
        """
        self.bot = bot
        self.url = KAPOWARR_URL.rstrip('/')  # Remove trailing slash if present
        self.api_key = KAPOWARR_API_KEY
        self.last_file_count = 0
        self.last_update = None
        self.is_running = False
        
    async def get_library_stats(self) -> Dict[str, Any]:
        """
        Fetch library statistics from Kapowarr API
        
        Returns:
            Dict containing library stats or empty dict if failed
        """
        try:
            params = {
                'api_key': self.api_key
            }
            
            stats_url = f"{self.url}/api/volumes/stats"
            
            connector = aiohttp.TCPConnector(
                limit=10, 
                limit_per_host=5, 
                keepalive_timeout=30
            )
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(stats_url, params=params) as response:
                    if response.status == 200:
                        stats_data = await response.json()
                        return stats_data.get('result', {})
                    else:
                        self.log(f"Failed to get library stats: HTTP {response.status}")
                        return {}
                        
        except Exception as e:
            self.log(f"Error getting library stats: {e}")
            return {}
    
    async def update_presence(self) -> bool:
        """
        Update Discord rich presence with current comic count
        
        Returns:
            True if successful, False otherwise
        """
        try:
            stats = await self.get_library_stats()
            
            if not stats:
                self.log("No stats available, skipping presence update")
                return False
            
            # Get the file count from stats
            file_count = stats.get('files', 0)
            
            # Only update if the count changed or it's been a while
            if file_count != self.last_file_count:
                self.last_file_count = file_count
                self.last_update = datetime.now()
                
                # Create the activity
                activity = discord.Activity(
                    type=discord.ActivityType.custom,
                    name=f"Reading {file_count:,} comics"
                )
                
                # Update the bot's presence
                await self.bot.change_presence(activity=activity)
                self.log(f"Updated presence: Reading {file_count:,} comics")
                return True
            
        except Exception as e:
            self.log(f"Error updating presence: {e}")
            return False
        
        return True
    
    async def start_presence_loop(self, update_interval: int = 300) -> None:
        """
        Start the rich presence update loop
        
        Args:
            update_interval: How often to update presence in seconds (default: 5 minutes)
        """
        if self.is_running:
            self.log("Presence loop is already running")
            return
            
        self.is_running = True
        self.log(f"Starting rich presence loop (updates every {update_interval}s)")
        
        while self.is_running:
            try:
                await self.update_presence()
                await asyncio.sleep(update_interval)
                
            except asyncio.CancelledError:
                self.log("Presence loop cancelled")
                break
            except Exception as e:
                self.log(f"Error in presence loop: {e}")
                await asyncio.sleep(10)  # Short delay on error
    
    def stop_presence_loop(self) -> None:
        """Stop the rich presence update loop"""
        self.is_running = False
        self.log("Stopping rich presence loop")
    
    async def set_custom_presence(self, text: str) -> None:
        """
        Set a custom presence text
        
        Args:
            text: Custom text to display
        """
        try:
            activity = discord.Activity(
                type=discord.ActivityType.custom,
                name=text
            )
            await self.client.change_presence(activity=activity)
            self.log(f"Set custom presence: {text}")
        except Exception as e:
            self.log(f"Error setting custom presence: {e}")
    
    async def clear_presence(self) -> None:
        """Clear the client's presence"""
        try:
            await self.client.change_presence(activity=None)
            self.log("Cleared client presence")
        except Exception as e:
            self.log(f"Error clearing presence: {e}")


# Convenience function for easy integration
async def setup_rich_presence(client: discord.Client, kapowarr_client, log_func, auto_start: bool = True) -> KapowarrRichPresence:
    """
    Setup rich presence for the client
    
    Args:
        client: Discord client instance
        kapowarr_client: KapowarrClient instance
        log_func: Logging function
        auto_start: Whether to automatically start the update loop
        
    Returns:
        KapowarrRichPresence instance
    """
    presence = KapowarrRichPresence(client, kapowarr_client, log_func)
    
    if auto_start:
        # Start the presence loop as a background task
        asyncio.create_task(presence.start_presence_loop())
    
    return presence