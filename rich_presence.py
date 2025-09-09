
import asyncio
import discord
import traceback
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
            self.log("DEBUG: Starting presence update...")
            
            # Debug: Check if client is ready
            if not self.client.is_ready():
                self.log("DEBUG: Client is not ready yet")
                return False
            self.log("DEBUG: Client is ready")
            
            self.log("DEBUG: Getting library stats from Kapowarr...")
            stats = await self.kapowarr.get_library_stats()
            self.log(f"DEBUG: Received stats: {stats}")
            
            if not stats:
                self.log("DEBUG: No stats available, skipping presence update")
                return False
            
            # Get the file count from stats
            file_count = stats.get('files', 0)
            self.log(f"DEBUG: File count extracted: {file_count}")
            
            # Debug: Always update for testing (remove the count check temporarily)
            self.log(f"DEBUG: Last count was {self.last_file_count}, new count is {file_count}")
            
            self.last_file_count = file_count
            self.last_update = datetime.now()
            
            self.log("DEBUG: Creating Discord activity...")
            # Create the activity - use Playing librarian
            activity = discord.Activity(
                type=discord.ActivityType.playing,
                name=f"librarian with {file_count:,} comics"
            )
            self.log(f"DEBUG: Created activity: type={activity.type}, name='{activity.name}'")
            
            # Debug: Check client user
            self.log(f"DEBUG: Client user: {self.client.user}")
            self.log(f"DEBUG: Client guilds: {len(self.client.guilds)} guilds")
            
            self.log("DEBUG: Calling change_presence...")
            # Update the client's presence
            await self.client.change_presence(activity=activity)
            self.log("DEBUG: change_presence call completed successfully")
            
            # Debug: Check current activity after setting
            if self.client.user:
                current_activity = getattr(self.client.user, 'activity', None)
                self.log(f"DEBUG: Current bot activity after update: {current_activity}")
            
            self.log(f"Updated presence: Playing librarian with {file_count:,} comics")
            return True
            
        except Exception as e:
            self.log(f"ERROR: Exception in update_presence: {type(e).__name__}: {e}")
            self.log(f"DEBUG: Full traceback: {traceback.format_exc()}")
            return False
    
    async def start_presence_loop(self, update_interval: int = 300) -> None:
        """
        Start the rich presence update loop
        
        Args:
            update_interval: How often to update presence in seconds (default: 5 minutes)
        """
        if self.is_running:
            self.log("DEBUG: Presence loop is already running")
            return
            
        self.is_running = True
        self.log(f"DEBUG: Starting rich presence loop (updates every {update_interval}s)")
        
        while self.is_running:
            try:
                self.log("DEBUG: Presence loop iteration starting...")
                await self.update_presence()
                self.log(f"DEBUG: Sleeping for {update_interval} seconds...")
                await asyncio.sleep(update_interval)
                
            except asyncio.CancelledError:
                self.log("DEBUG: Presence loop cancelled")
                break
            except Exception as e:
                self.log(f"ERROR: Error in presence loop: {e}")
                self.log(f"DEBUG: Presence loop traceback: {traceback.format_exc()}")
                await asyncio.sleep(10)  # Short delay on error
    
    def stop_presence_loop(self) -> None:
        """Stop the rich presence update loop"""
        self.is_running = False
        self.log("DEBUG: Stopping rich presence loop")
    
    async def set_custom_presence(self, text: str, activity_type: str = "playing") -> None:
        """
        Set a custom presence text
        
        Args:
            text: Custom text to display
            activity_type: Type of activity ("playing", "watching", "listening", "custom")
        """
        try:
            self.log(f"DEBUG: Setting custom presence: {activity_type} {text}")
            
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
                
                activity_type_enum = activity_types.get(activity_type.lower(), discord.ActivityType.playing)
                
                activity = discord.Activity(
                    type=activity_type_enum,
                    name=text
                )
            
            await self.client.change_presence(activity=activity)
            self.log(f"DEBUG: Set custom presence successfully: {text}")
        except Exception as e:
            self.log(f"ERROR: Error setting custom presence: {e}")
            self.log(f"DEBUG: Custom presence traceback: {traceback.format_exc()}")
    
    async def clear_presence(self) -> None:
        """Clear the client's presence"""
        try:
            self.log("DEBUG: Clearing client presence...")
            await self.client.change_presence(activity=None)
            self.log("DEBUG: Cleared client presence successfully")
        except Exception as e:
            self.log(f"ERROR: Error clearing presence: {e}")
            self.log(f"DEBUG: Clear presence traceback: {traceback.format_exc()}")


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
    log_func("DEBUG: Setting up rich presence...")
    presence = KapowarrRichPresence(client, kapowarr_client, log_func)
    
    if auto_start:
        log_func("DEBUG: Auto-starting presence loop...")
        # Start the presence loop as a background task
        asyncio.create_task(presence.start_presence_loop())
    
    return presence
