import asyncio
import discord
from datetime import datetime
from typing import Optional, Dict, Any


class KapowarrRichPresence:
    def __init__(self, client: discord.Client, kapowarr_client, log_func):
        """
        Initialize the Rich Presence handler
        
        Args:
            client: The Discord client instance
            kapowarr_client: Your existing KapowarrClient instance
            log_func: Your existing log function
        """
        self.client = client
        self.kapowarr = kapowarr_client
        self.log = log_func
        self.last_file_count = 0
        self.last_update = None
        self.is_running = False
        
    async def update_presence(self) -> bool:
        """
        Update Discord rich presence with current comic count
        
        Returns:
            True if successful, False otherwise
        """
        try:
            stats = await self.kapowarr.get_library_stats()
            
            if not stats:
                self.log("No stats available, skipping presence update")
                return False
            
            # Get the file count from stats
            file_count = stats.get('files', 0)
            
            # Only update if the count changed or it's been a while
            if file_count != self.last_file_count:
                self.last_file_count = file_count
                self.last_update = datetime.now()
                
                # Create the activity - use custom activity with state field for bots
                activity = discord.Activity(
                    type=discord.ActivityType.custom,
                    state=f"Reading {file_count:,} comics"
                )
                
                # Update the client's presence
                await self.client.change_presence(activity=activity)
                self.log(f"Updated presence: Reading {file_count:,} comics")
                return True
            
        except Exception as e:
            self.log(f"Error updating presence: {e}")
            return False
        
        return True
    
    async def start_presence_loop(self, update_interval: int = 43200) -> None:
        """
        Start the rich presence update loop
        
        Args:
            update_interval: How often to update presence in seconds (default: 12 hours)
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
    
    async def set_custom_presence(self, text: str, activity_type: str = "custom") -> None:
        """
        Set a custom presence text
        
        Args:
            text: Custom text to display
            activity_type: Type of activity ("playing", "watching", "listening", "custom")
        """
        try:
            if activity_type.lower() == "custom":
                # For custom activities, use state field for bots
                activity = discord.Activity(
                    type=discord.ActivityType.custom,
                    state=text
                )
            else:
                # Map string to Discord activity type for non-custom activities
                activity_types = {
                    "playing": discord.ActivityType.playing,
                    "watching": discord.ActivityType.watching,
                    "listening": discord.ActivityType.listening,
                    "competing": discord.ActivityType.competing
                }
                
                activity_type_enum = activity_types.get(activity_type.lower(), discord.ActivityType.watching)
                
                activity = discord.Activity(
                    type=activity_type_enum,
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
