import discord
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

from kapowarr import KapowarrClient
from comic_monitor import ComicMonitor
from comic_ui import ComicDetailView
from comic_library_ui import ComicLibraryView
from rich_presence import setup_rich_presence

import config

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
rich_presence = None

kapowarr = KapowarrClient(
    url=config.KAPOWARR_URL,
    api_key=config.KAPOWARR_API_KEY,
    max_retry_attempts=config.MAX_RETRY_ATTEMPTS,
    retry_delay=config.RETRY_DELAY
)

comic_monitor = ComicMonitor(
    comicvine_api_key=config.COMICVINE_API_KEY,
    kapowarr_client=kapowarr
)

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Bot: {message}")

async def daily_comic_check():
    await client.wait_until_ready()
    
    while not client.is_closed():
        try:
            if config.COMIC_CHECK_ENABLED:
                log("Starting daily comic check...")
                
                comicvine_ok = await comic_monitor.test_connection()
                kapowarr_ok = await kapowarr.check_connection()
                
                if comicvine_ok and kapowarr_ok:
                    results = await comic_monitor.check_and_add_new_comics(
                        days_back=config.COMIC_CHECK_DAYS_BACK
                    )
                    
                    log(f"Daily comic check complete: {results['added_successfully']} new comics added")
                    
                else:
                    log("Skipping comic check - ComicVine or Kapowarr unavailable")
            else:
                log("Daily comic check disabled in config")
            
        except Exception as e:
            log(f"Error in daily comic check: {e}")
        
        await asyncio.sleep(config.COMIC_CHECK_INTERVAL_HOURS * 3600)

async def queue_monitoring():
    await client.wait_until_ready()
    
    await asyncio.sleep(60)
    
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            kapowarr_ready = await kapowarr.check_connection()
            if kapowarr_ready:
                log("Kapowarr is ready, starting queue monitoring...")
                break
            else:
                retry_count += 1
                log(f"Kapowarr not ready yet, retry {retry_count}/{max_retries}")
                await asyncio.sleep(30)
        except Exception as e:
            retry_count += 1
            log(f"Error checking Kapowarr readiness: {e}, retry {retry_count}/{max_retries}")
            await asyncio.sleep(30)
    
    if retry_count >= max_retries:
        log("Failed to connect to Kapowarr after multiple retries, disabling queue monitoring")
        return
    
    await comic_monitor.start_queue_monitoring(client, check_interval=60)

async def connection_monitor():
    await client.wait_until_ready()
    
    await asyncio.sleep(120)
    
    while not client.is_closed():
        try:
            try:
                kapowarr_status = await kapowarr.check_connection()
                if not kapowarr_status:
                    log("Kapowarr connection check failed")
            except Exception as e:
                log(f"Kapowarr connection monitor error: {e}")
            
            try:
                await comic_monitor.test_connection()
            except Exception as e:
                log(f"ComicVine connection monitor error: {e}")
            
        except Exception as e:
            log(f"Connection monitor error: {e}")
        
        await asyncio.sleep(config.RECONNECT_INTERVAL * 2)

@client.event
async def on_ready():
    log(f'Logged in as {client.user}')
    
    await asyncio.sleep(2)
    
    kapowarr_connected = False
    for attempt in range(3):
        try:
            kapowarr_connected = await kapowarr.check_connection()
            if kapowarr_connected:
                break
            else:
                log(f"Kapowarr connection attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(5)
        except Exception as e:
            log(f"Kapowarr connection error on attempt {attempt + 1}: {e}")
            await asyncio.sleep(5)
    
    await asyncio.sleep(2)
    comicvine_connected = await comic_monitor.test_connection()
    
    if kapowarr_connected:
        log("✅ Connected to Kapowarr")
    else:
        log("❌ Failed to connect to Kapowarr")
    
    if comicvine_connected:
        log("✅ Connected to ComicVine")
        if config.COMIC_CHECK_ENABLED:
            log(f"📚 Comic monitoring enabled (checking every {config.COMIC_CHECK_INTERVAL_HOURS} hours)")
        else:
            log("📚 Comic monitoring disabled")
    else:
        log("❌ Failed to connect to ComicVine")
    
    try:
        commands = await tree.sync()
        log(f"Synced {len(commands)} commands")
    except Exception as e:
        log(f"Failed to sync commands: {e}")
    
    client.loop.create_task(connection_monitor())
    
    if config.COMIC_CHECK_ENABLED and comicvine_connected and kapowarr_connected:
        client.loop.create_task(daily_comic_check())
    
    if kapowarr_connected:
        client.loop.create_task(queue_monitoring())
        log("🔥 Comic download queue monitoring enabled")
    else:
        log("🔥 Comic download queue monitoring disabled (Kapowarr not connected)")

    if kapowarr_connected:
        rich_presence = await setup_rich_presence(client, kapowarr, log, auto_start=True)
        log("📊 Rich presence started - showing comic count")
    else:
        log("📊 Rich presence disabled (Kapowarr not connected)")
    
    log("Bot ready!")

@tree.command(name="search", description="Search for comics")
@app_commands.describe(query="Comic title to search for")
async def search_command(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    log(f"Comic search: {query}")
    
    comic_results = await kapowarr.search_comics_detailed(query, limit=50)
    
    if not comic_results:
        no_results_embed = discord.Embed(
            title="📚 No Comics Found",
            description=f"No comics found matching **{query}**",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        no_results_embed.add_field(
            name="💡 Search Tips",
            value="• Check spelling and try simpler terms\n• Use series name without issue numbers\n• Try partial titles (e.g., 'spider' instead of 'spider-man')\n• Search for main character names",
            inline=False
        )
        no_results_embed.add_field(
            name="📖 Examples",
            value="`/search query:batman`\n`/search query:x-men`\n`/search query:walking dead`",
            inline=False
        )
        await interaction.followup.send(embed=no_results_embed)
        return
    
    view = ComicDetailView(comic_results, query, kapowarr, current_index=0)
    embed = view.create_detailed_embed()
    
    await interaction.followup.send(embed=embed, view=view)

@tree.command(name="wantedcomics", description="Browse your wanted comics list")
async def wanted_comics_command(interaction: discord.Interaction):
    await interaction.response.defer()
    
    wanted_comics = await kapowarr.get_wanted_comics()
    
    if not wanted_comics:
        embed = discord.Embed(
            title="📋 Wanted Comics",
            description="No wanted comics found in your library.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=embed)
        return
    
    view = ComicLibraryView(wanted_comics, 'wanted', kapowarr)
    embed = await view.create_embed()
    
    await interaction.followup.send(embed=embed, view=view)

@tree.command(name="comiclibrary", description="Browse your complete comic library")
async def comic_library_command(interaction: discord.Interaction):
    await interaction.response.defer()
    
    library_comics = await kapowarr.get_comic_library()
    
    if not library_comics:
        embed = discord.Embed(
            title="📚 Comic Library",
            description="No comics found in your library.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=embed)
        return
    
    view = ComicLibraryView(library_comics, 'library', kapowarr)
    embed = await view.create_embed()
    
    await interaction.followup.send(embed=embed, view=view)

@tree.command(name="searchcomic", description="Search for comics in your library")
@app_commands.describe(query="Comic title to search for")
async def search_comic_command(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    matching_comics = await kapowarr.search_comic_library(query)
    
    if not matching_comics:
        embed = discord.Embed(
            title="🔍 Comic Search",
            description=f"No comics found matching '{query}' in your library.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=embed)
        return
    
    view = ComicLibraryView(matching_comics, 'search', kapowarr, search_query=query)
    embed = await view.create_embed()
    
    await interaction.followup.send(embed=embed, view=view)

@tree.command(name="comicstats", description="Display detailed comic library statistics")
async def comic_stats_command(interaction: discord.Interaction):
    await interaction.response.defer()
    
    stats = await kapowarr.get_library_stats()
    
    if not stats:
        embed = discord.Embed(
            title="📊 Comic Library Stats",
            description="Unable to retrieve library statistics.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="📊 Comic Library Statistics",
        description="Detailed overview of your comic collection",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    total_volumes = stats.get('volumes', 0)
    total_issues = stats.get('issues', 0)
    downloaded_issues = stats.get('downloaded_issues', 0)
    monitored = stats.get('monitored', 0)
    unmonitored = stats.get('unmonitored', 0)
    total_files = stats.get('files', 0)
    total_file_size = stats.get('total_file_size', 0)
    
    embed.add_field(
        name="📚 Collection Overview",
        value=f"**Volumes:** {total_volumes:,}\n**Issues:** {downloaded_issues:,}/{total_issues:,}\n**Files:** {total_files:,}",
        inline=True
    )
    
    if total_issues > 0:
        completion_percentage = (downloaded_issues / total_issues) * 100
    else:
        completion_percentage = 0
    
    embed.add_field(
        name="📈 Progress",
        value=f"**Completion:** {completion_percentage:.1f}%\n**Missing:** {total_issues - downloaded_issues:,} issues",
        inline=True
    )
    
    embed.add_field(
        name="👁️ Monitoring",
        value=f"**Monitored:** {monitored:,}\n**Unmonitored:** {unmonitored:,}",
        inline=True
    )
    
    formatted_size = kapowarr.format_file_size(total_file_size)
    if total_files > 0:
        avg_file_size = kapowarr.format_file_size(total_file_size // total_files)
    else:
        avg_file_size = "0 B"
    
    embed.add_field(
        name="💾 Storage",
        value=f"**Total Size:** {formatted_size}\n**Average File:** {avg_file_size}",
        inline=True
    )
    
    if total_volumes > 0:
        avg_issues_per_volume = total_issues / total_volumes
        avg_downloaded_per_volume = downloaded_issues / total_volumes
    else:
        avg_issues_per_volume = 0
        avg_downloaded_per_volume = 0
    
    embed.add_field(
        name="📊 Averages",
        value=f"**Issues/Volume:** {avg_issues_per_volume:.1f}\n**Downloaded/Volume:** {avg_downloaded_per_volume:.1f}",
        inline=True
    )
    
    health_color = "🟢"
    if completion_percentage < 50:
        health_color = "🔴"
    elif completion_percentage < 80:
        health_color = "🟡"
    
    embed.add_field(
        name="🏥 Library Health",
        value=f"{health_color} **{completion_percentage:.1f}%** Complete\n📋 **{monitored}** Series Monitored",
        inline=True
    )
    
    embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    await interaction.followup.send(embed=embed)

@tree.command(name="comics_check", description="Manually check for new Marvel/DC comic releases")
@app_commands.describe(days_back="How many days back to check (default: 7, max: 60)")
async def comics_check_command(interaction: discord.Interaction, days_back: int = 7):
    await interaction.response.defer(ephemeral=True)
    
    if days_back < 1 or days_back > 60:
        await interaction.followup.send("❌ Days back must be between 1 and 60", ephemeral=True)
        return
    
    comicvine_ok = await comic_monitor.test_connection()
    
    if not comicvine_ok:
        await interaction.followup.send("❌ ComicVine API unavailable", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📚 Comic Release Check",
        description=f"Checking for new Marvel and DC releases from the last {days_back} days...",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)
    
    try:
        results = await comic_monitor.manual_check(days_back)
        
        if results['added_successfully'] > 0 or results['new_found'] > 0:
            color = discord.Color.green()
            title = "✅ Comic Check Complete"
        elif results['checked'] > 0:
            color = discord.Color.orange()
            title = "⚠️ Comic Check Complete"
        else:
            color = discord.Color.red()
            title = "❌ Comic Check Complete"
        
        results_embed = discord.Embed(
            title=title,
            description=f"Checked the last {days_back} days for new releases",
            color=color,
            timestamp=datetime.now()
        )
        
        summary = f"**📊 Summary:**\n"
        summary += f"• Releases checked: {results['checked']}\n"
        summary += f"• New releases found: {results['new_found']}\n"
        summary += f"• Successfully added: {results['added_successfully']}\n"
        summary += f"• Failed to add: {results['failed_to_add']}\n"
        summary += f"• Already in library: {results['already_exists']}"
        
        results_embed.add_field(name="Results", value=summary, inline=False)
        
        if results['details']:
            details_text = "\n".join(results['details'][:10])
            if len(results['details']) > 10:
                details_text += f"\n... and {len(results['details']) - 10} more"
            
            results_embed.add_field(name="Details", value=details_text, inline=False)
        
        await interaction.followup.send(embed=results_embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Comic Check Error",
            description=f"An error occurred during the comic check:\n```{str(e)}```",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

@tree.command(name="comics_recent", description="Show recent comic releases and their status")
@app_commands.describe(days="How many days back to show (default: 7, max: 60)")
async def comics_recent_command(interaction: discord.Interaction, days: int = 7):
    await interaction.response.defer(ephemeral=True)
    
    if days < 1 or days > 60:
        await interaction.followup.send("❌ Days must be between 1 and 60", ephemeral=True)
        return
    
    if not await comic_monitor.test_connection():
        await interaction.followup.send("❌ ComicVine API unavailable", ephemeral=True)
        return
    
    try:
        recent_comics = await comic_monitor.get_recent_additions(days)
        
        if not recent_comics:
            embed = discord.Embed(
                title="📚 Recent Comic Releases",
                description=f"No Marvel/DC releases found in the last {days} days",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📚 Recent Comic Releases",
            description=f"Marvel and DC releases from the last {days} days",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        in_library = [c for c in recent_comics if c['in_library']]
        not_in_library = [c for c in recent_comics if not c['in_library']]
        
        if in_library:
            library_text = ""
            for comic in in_library[:10]:
                library_text += f"✅ **{comic['title']}** ({comic['publisher']})\n"
            
            if len(in_library) > 10:
                library_text += f"... and {len(in_library) - 10} more in library"
            
            embed.add_field(name="📚 In Library", value=library_text, inline=False)
        
        if not_in_library:
            available_text = ""
            for comic in not_in_library[:10]:
                available_text += f"📖 **{comic['title']}** ({comic['publisher']})\n"
            
            if len(not_in_library) > 10:
                available_text += f"... and {len(not_in_library) - 10} more available"
            
            embed.add_field(name="🆕 Available to Add", value=available_text, inline=False)
        
        summary = f"Total: {len(recent_comics)} | In Library: {len(in_library)} | Available: {len(not_in_library)}"
        embed.add_field(name="📊 Summary", value=summary, inline=False)
        
        embed.set_footer(text="Use /comics_check to add new releases automatically")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to get recent comics:\n```{str(e)}```",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

@tree.command(name="reconnect", description="Force reconnection to comic services")
async def reconnect_command(interaction: discord.Interaction):
    if config.ADMIN_ROLE_ID and config.ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("❌ Admin role required", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    kapowarr_connected = await kapowarr.check_connection()
    comicvine_connected = await comic_monitor.test_connection()
    
    all_connected = kapowarr_connected and comicvine_connected
    
    embed = discord.Embed(
        title="🔄 Reconnection Results",
        color=discord.Color.green() if all_connected else discord.Color.red()
    )
    
    kapowarr_status = "✅ Connected" if kapowarr_connected else "❌ Failed"
    comicvine_status = "✅ Connected" if comicvine_connected else "❌ Failed"
    
    embed.add_field(name="Kapowarr", value=kapowarr_status, inline=True)
    embed.add_field(name="ComicVine", value=comicvine_status, inline=True)
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"❌ An error occurred: {str(error)}", ephemeral=True
        )
    
    log(f"Command error: {str(error)}")

if __name__ == "__main__":
    client.run(config.TOKEN)
