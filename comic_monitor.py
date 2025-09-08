import aiohttp
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import re

logger = logging.getLogger(__name__)

class ComicMonitor:
    def __init__(self, comicvine_api_key, kapowarr_client):
        self.api_key = comicvine_api_key
        self.kapowarr = kapowarr_client
        self.base_url = "https://comicvine.gamespot.com/api"
        self.monitored_publisher_ids = {
            "Marvel": 31,
            "DC": 10,
            "Dark Horse": 16
        }
        self.check_days_back = 7
        self.existing_comics_cache = set()
        self.last_cache_update = None
        self.cache_duration = timedelta(hours=1)
        
        self.notified_downloads = {}
        self.notification_cleanup_interval = timedelta(hours=24)
        self.last_cleanup = datetime.now()
        
    def log(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] ComicMonitor: {message}")

    async def get_existing_comics(self) -> Set[int]:
        try:
            if (self.last_cache_update and 
                datetime.now() - self.last_cache_update < self.cache_duration and
                self.existing_comics_cache):
                return self.existing_comics_cache
            
            self.log("Refreshing existing comics cache...")
            
            params = {
                'api_key': self.kapowarr.api_key
            }
            
            about_url = f"{self.kapowarr.url}/api/system/about"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector
            ) as session:
                try:
                    async with session.get(about_url, params=params) as about_response:
                        if about_response.status != 200:
                            self.log(f"Kapowarr not responsive: HTTP {about_response.status}")
                            return set()
                        
                        about_data = await about_response.json()
                        version = about_data.get('result', {}).get('version', 'Unknown')
                        self.log(f"Connected to Kapowarr {version}, checking for existing comics...")
                        
                except Exception as e:
                    self.log(f"Failed to connect to Kapowarr: {e}")
                    return set()
                
                stats_url = f"{self.kapowarr.url}/api/volumes/stats"
                try:
                    async with session.get(stats_url, params=params) as stats_response:
                        if stats_response.status == 200:
                            stats_data = await stats_response.json()
                            stats_result = stats_data.get('result', {})
                            total_volumes = stats_result.get('volumes', 0)
                            self.log(f"Kapowarr reports {total_volumes} total volumes")
                            
                            if total_volumes == 0:
                                self.existing_comics_cache = set()
                                self.last_cache_update = datetime.now()
                                return set()
                        else:
                            self.log(f"Stats endpoint failed: HTTP {stats_response.status}")
                            
                except Exception as e:
                    self.log(f"Stats endpoint error: {e}")
                
                volumes_url = f"{self.kapowarr.url}/api/volumes"
                
                volumes_params = {
                    'api_key': self.kapowarr.api_key,
                    'sort': 'title'
                }
                
                headers = {
                    'Accept': 'application/json',
                    'User-Agent': 'Comic-Bot/1.0',
                    'Connection': 'close'
                }
                
                try:
                    await asyncio.sleep(2)
                    
                    async with session.get(volumes_url, params=volumes_params, headers=headers) as response:
                        if response.status == 200:
                            volumes_data = await response.json()
                            volumes = volumes_data.get('result', [])
                            
                            comic_ids = set()
                            for volume in volumes:
                                cv_id = volume.get('comicvine_id')
                                if cv_id is not None:
                                    try:
                                        comic_ids.add(int(cv_id))
                                    except (ValueError, TypeError):
                                        self.log(f"Invalid comicvine_id format: {cv_id}")
                                        continue
                            
                            self.existing_comics_cache = comic_ids
                            self.last_cache_update = datetime.now()
                            self.log(f"Successfully cached {len(comic_ids)} existing comics")
                            
                            if comic_ids:
                                sample_ids = list(comic_ids)[:5]
                                self.log(f"Sample existing comic IDs: {sample_ids}")
                            
                            return comic_ids
                        else:
                            self.log(f"Failed to get existing comics: HTTP {response.status}")
                            try:
                                error_text = await response.text()
                                self.log(f"Error response: {error_text[:200]}")
                            except:
                                pass
                            return set()
                            
                except Exception as e:
                    self.log(f"Volumes endpoint failed: {e}")
                    return set()
                        
        except Exception as e:
            self.log(f"Error getting existing comics: {e}")
            return set()

    def _cleanup_old_notifications(self):
        current_time = datetime.now()
        
        if current_time - self.last_cleanup > self.notification_cleanup_interval:
            old_keys = []
            cleanup_threshold = current_time - timedelta(hours=48)
            
            for key, timestamp in self.notified_downloads.items():
                if timestamp < cleanup_threshold:
                    old_keys.append(key)
            
            for key in old_keys:
                del self.notified_downloads[key]
            
            self.last_cleanup = current_time
            if old_keys:
                self.log(f"Cleaned up {len(old_keys)} old notification entries")

    async def check_download_queue(self, discord_client):
        try:
            self._cleanup_old_notifications()
            
            params = {
                'api_key': self.kapowarr.api_key
            }
            
            url = f"{self.kapowarr.url}/api/activity/queue"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        queue_data = await response.json()
                        queue_items = queue_data.get('result', [])
                        
                        self.log(f"Found {len(queue_items)} items in download queue")
                        
                        for item in queue_items:
                            await self._process_queue_item(item, discord_client)
                    else:
                        self.log(f"Failed to get queue: HTTP {response.status}")
                        
        except Exception as e:
            self.log(f"Error checking download queue: {e}")

    async def _process_queue_item(self, queue_item: Dict, discord_client):
        try:
            volume_id = queue_item.get('volume_id')
            download_id = queue_item.get('id')
            status = queue_item.get('status', 'Unknown').lower()
            progress = queue_item.get('progress', 0)
            
            if not volume_id or not download_id:
                return
            
            notification_key = f"download_{download_id}_{status}"
            current_time = datetime.now()
            
            if notification_key in self.notified_downloads:
                if status in ['downloading', 'queued'] and progress > 0:
                    last_notification = self.notified_downloads[notification_key]
                    if current_time - last_notification < timedelta(minutes=30):
                        return
                else:
                    return
            
            notify_statuses = [
                'queued', 'downloading', 'snatched', 'grabbed', 'completed', 
                'importing', 'failed', 'canceled', 'cancelled', 'finished'
            ]
            
            if status in notify_statuses:
                volume_details = await self.kapowarr.get_volume_details(volume_id)
                if volume_details:
                    await self._send_download_notification(queue_item, volume_details, discord_client)
                    self.notified_downloads[notification_key] = current_time
                    self.log(f"Sent notification for download ID {download_id} with status '{status}'")
                else:
                    self.log(f"Could not get volume details for volume ID {volume_id}")
                    
        except Exception as e:
            self.log(f"Error processing queue item: {e}")

    async def _send_download_notification(self, queue_item: Dict, volume_details: Dict, discord_client):
        try:
            import config
            
            if not getattr(config, 'COMIC_NOTIFICATIONS_ENABLED', True):
                return
            
            channel_id = getattr(config, 'COMIC_NOTIFICATIONS_CHANNEL_ID', 1339430063502000210)
            channel = discord_client.get_channel(channel_id)
            
            if not channel:
                self.log(f"Could not find Discord channel {channel_id}")
                return
            
            import discord
            
            download_id = queue_item.get('id')
            status = queue_item.get('status', 'Unknown')
            progress = queue_item.get('progress', 0)
            size = queue_item.get('size', 0)
            speed = queue_item.get('speed', 0)
            source_name = queue_item.get('source_name', 'Unknown')
            source_type = queue_item.get('source_type', 'Unknown')
            download_title = queue_item.get('title', 'Unknown')
            web_title = queue_item.get('web_title', download_title)
            web_sub_title = queue_item.get('web_sub_title', '')
            web_link = queue_item.get('web_link', '')
            download_folder = queue_item.get('download_folder', '')
            file_path = queue_item.get('file', '')
            
            title = volume_details.get('title', 'Unknown Title')
            publisher = volume_details.get('publisher', 'Unknown Publisher')
            year = volume_details.get('year', 'Unknown')
            issue_count = volume_details.get('issue_count', 0)
            issues_downloaded = volume_details.get('issues_downloaded', 0)
            cv_id = volume_details.get('comicvine_id', 'N/A')
            monitored = volume_details.get('monitored', False)
            
            status_lower = status.lower()
            if status_lower in ['completed', 'finished', 'importing']:
                embed_color = discord.Color.green()
                embed_title = "✅ Comic Downloaded"
                embed_emoji = "🔥"
            elif status_lower in ['downloading', 'queued', 'snatched', 'grabbed']:
                embed_color = discord.Color.blue()
                embed_title = "⬇ Comic Downloading"
                embed_emoji = "🔥"
            elif status_lower in ['failed', 'canceled', 'cancelled']:
                embed_color = discord.Color.red()
                embed_title = "❌ Comic Download Failed"
                embed_emoji = "⚠️"
            else:
                embed_color = discord.Color.orange()
                embed_title = f"📡 Comic {status.title()}"
                embed_emoji = "📡"
            
            embed = discord.Embed(
                title=f"{embed_emoji} {embed_title}",
                color=embed_color,
                timestamp=datetime.now()
            )
            
            comic_display_title = f"**{title}**"
            if year and year != 'Unknown':
                comic_display_title += f" ({year})"
            
            embed.add_field(
                name="📚 Series",
                value=comic_display_title,
                inline=False
            )
            
            embed.add_field(
                name="🏢 Publisher",
                value=publisher,
                inline=True
            )
            
            embed.add_field(
                name="👁️ Monitored",
                value="✅ Yes" if monitored else "❌ No",
                inline=True
            )
            
            embed.add_field(
                name="📖 Issues",
                value=f"{issues_downloaded}/{issue_count}",
                inline=True
            )
            
            download_info = f"**Release:** {web_title}\n"
            if web_sub_title:
                download_info += f"**Details:** {web_sub_title}\n"
            
            embed.add_field(
                name="📦 Download Details",
                value=download_info,
                inline=False
            )
            
            embed.add_field(
                name="🌐 Source",
                value=f"{source_name} ({source_type})",
                inline=True
            )
            
            embed.add_field(
                name="📊 Status",
                value=status.title(),
                inline=True
            )
            
            if size > 0:
                size_mb = size / (1024 * 1024)
                if size_mb > 1024:
                    size_str = f"{size_mb / 1024:.1f} GB"
                else:
                    size_str = f"{size_mb:.1f} MB"
                
                embed.add_field(
                    name="💾 Size",
                    value=size_str,
                    inline=True
                )
            
            if status_lower in ['downloading', 'queued'] and progress > 0:
                progress_bar = self._create_progress_bar(progress)
                embed.add_field(
                    name="📈 Progress",
                    value=f"{progress_bar} {progress}%",
                    inline=False
                )
                
                if speed > 0:
                    speed_mb = speed / (1024 * 1024)
                    if speed_mb > 1:
                        speed_str = f"{speed_mb:.1f} MB/s"
                    else:
                        speed_kb = speed / 1024
                        speed_str = f"{speed_kb:.1f} KB/s"
                    
                    embed.add_field(
                        name="🚀 Speed",
                        value=speed_str,
                        inline=True
                    )
            
            if status_lower in ['completed', 'importing', 'finished'] and file_path:
                filename = file_path.split('/')[-1]
                if len(filename) > 50:
                    filename = filename[:47] + "..."
                
                embed.add_field(
                    name="📁 File",
                    value=f"`{filename}`",
                    inline=False
                )
            
            description = volume_details.get('description')
            if description:
                clean_description = self.kapowarr.clean_html(description)
                if clean_description and len(clean_description) > 50:
                    if len(clean_description) > 200:
                        clean_description = clean_description[:197] + "..."
                    embed.add_field(
                        name="📝 Description",
                        value=clean_description,
                        inline=False
                    )
            
            links_text = ""
            if cv_id and str(cv_id).isdigit():
                links_text += f"🔗 [ComicVine](https://comicvine.gamespot.com/volume/4050-{cv_id}/)\n"
            
            if web_link:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(web_link).netloc.replace('www.', '')
                    links_text += f"🌐 [Source]({web_link}) ({domain})"
                except:
                    links_text += f"🌐 [Source]({web_link})"
            
            if links_text:
                embed.add_field(
                    name="🔗 Links",
                    value=links_text,
                    inline=False
                )
            
            cover_url = None
            
            if volume_details.get('id'):
                kapowarr_cover_url = f"{self.kapowarr.url}/api/volumes/{volume_details['id']}/cover?api_key={self.kapowarr.api_key}"
                cover_url = kapowarr_cover_url
            
            if cv_id and str(cv_id).isdigit():
                try:
                    cv_cover = await self.get_comicvine_cover_enhanced(cv_id)
                    if cv_cover:
                        cover_url = cv_cover
                except Exception as e:
                    self.log(f"Failed to get ComicVine cover: {e}")
            
            if cover_url:
                embed.set_image(url=cover_url)
                embed.set_thumbnail(url=cover_url)
            
            footer_text = f"Kapowarr • Volume ID: {volume_details.get('id', 'N/A')} • Download ID: {download_id}"
            embed.set_footer(
                text=footer_text,
                icon_url="https://raw.githubusercontent.com/Kareadita/Kapowarr/main/frontend/public/assets/images/logo.png"
            )
            
            await channel.send(embed=embed)
            self.log(f"Sent detailed download notification for: {title} (Status: {status})")
            
        except Exception as e:
            self.log(f"Error sending download notification: {e}")
            import traceback
            self.log(f"Full traceback: {traceback.format_exc()}")

    def _create_progress_bar(self, progress: int, length: int = 10) -> str:
        filled = int(length * progress / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"

    async def get_comicvine_cover_enhanced(self, comicvine_id) -> Optional[str]:
        try:
            cv_url = f"https://comicvine.gamespot.com/api/volume/4050-{comicvine_id}/"
            
            params = {
                'api_key': self.api_key,
                'format': 'json',
                'field_list': 'image,name,publisher,start_year'
            }
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector,
                headers={'User-Agent': 'Kapowarr-Bot/1.0'}
            ) as session:
                async with session.get(cv_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('error') == 'OK' and data.get('results'):
                            results = data['results']
                            image_data = results.get('image', {})
                            
                            for size in ['super_url', 'medium_url', 'small_url', 'icon_url']:
                                if image_data.get(size):
                                    cover_url = image_data[size]
                                    self.log(f"Found ComicVine cover ({size}): {cover_url}")
                                    return cover_url
                        
                        self.log(f"No image found in ComicVine response for ID: {comicvine_id}")
                        return None
                    else:
                        self.log(f"ComicVine API error: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            self.log(f"Error fetching ComicVine cover for ID {comicvine_id}: {e}")
            return None

    async def start_queue_monitoring(self, discord_client, check_interval: int = None):
        if check_interval is None:
            import config
            check_interval = getattr(config, 'COMIC_QUEUE_CHECK_INTERVAL', 60)
        
        self.log(f"Starting download queue monitoring (checking every {check_interval} seconds)...")
        
        while True:
            try:
                await self.check_download_queue(discord_client)
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.log(f"Error in queue monitoring loop: {e}")
                import traceback
                self.log(f"Full traceback: {traceback.format_exc()}")
                await asyncio.sleep(check_interval)

    async def search_new_releases(self, days_back: int = None) -> List[Dict]:
        if days_back is None:
            days_back = self.check_days_back
            
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            date_filter = f"{start_date.strftime('%Y-%m-%d')}|{end_date.strftime('%Y-%m-%d')}"
            
            self.log(f"Searching for new releases from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            new_comics = []
            
            for publisher_name, publisher_id in self.monitored_publisher_ids.items():
                publisher_comics = await self._search_publisher_releases_by_id(publisher_name, publisher_id, date_filter)
                new_comics.extend(publisher_comics)
                
                await asyncio.sleep(1)
            
            if len(new_comics) < 5:
                self.log(f"Got only {len(new_comics)} results from publisher ID search, trying fallback method")
                fallback_comics = await self._search_recent_releases_all(date_filter)
                
                existing_ids = {comic.get('id') for comic in new_comics}
                for comic in fallback_comics:
                    if comic.get('id') not in existing_ids:
                        new_comics.append(comic)
            
            unique_comics = {}
            marvel_dc_count = 0
            filtered_count = 0
            
            for comic in new_comics:
                cv_id = comic.get('id')
                if cv_id and cv_id not in unique_comics:
                    if self._is_marvel_or_dc_comic(comic):
                        unique_comics[cv_id] = comic
                        marvel_dc_count += 1
                    else:
                        publisher_name = self._extract_publisher_name(comic)
                        self.log(f"Final filter: {comic.get('name')} ({publisher_name}) - not Marvel/DC")
                        filtered_count += 1
            
            self.log(f"Found {len(unique_comics)} unique Marvel/DC releases (filtered out {filtered_count} non-Marvel/DC)")
            return list(unique_comics.values())
            
        except Exception as e:
            self.log(f"Error searching new releases: {e}")
            return []

    async def _search_publisher_releases_by_id(self, publisher_name: str, publisher_id: int, date_filter: str) -> List[Dict]:
        try:
            url = f"{self.base_url}/volumes/"
            params = {
                'api_key': self.api_key,
                'format': 'json',
                'field_list': 'id,name,start_year,publisher,issue_count,description,image,deck',
                'filter': f'publisher:{publisher_id},date_added:{date_filter}',
                'sort': 'date_added:desc',
                'limit': 100
            }
            
            self.log(f"Searching {publisher_name} with URL: {url}")
            self.log(f"Params: {params}")
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector
            ) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('error') == 'OK':
                            comics = data.get('results', [])
                            self.log(f"Found {len(comics)} results from ComicVine API for {publisher_name}")
                            
                            if comics and len(comics) > 0:
                                sample_comic = comics[0]
                                sample_publisher = self._extract_publisher_name(sample_comic)
                                sample_pub_id = comics[0].get('publisher', {}).get('id') if isinstance(comics[0].get('publisher'), dict) else None
                                self.log(f"First result: name={sample_comic.get('name')}, publisher={sample_publisher}, pub_id={sample_pub_id}")
                                
                                correct_publisher_count = 0
                                for comic in comics[:10]:
                                    comic_pub_data = comic.get('publisher', {})
                                    if isinstance(comic_pub_data, dict):
                                        comic_pub_id = comic_pub_data.get('id')
                                        if comic_pub_id == publisher_id:
                                            correct_publisher_count += 1
                                
                                self.log(f"Out of first 10 results, {correct_publisher_count} have correct publisher ID {publisher_id}")
                            
                            publisher_filtered = []
                            for comic in comics:
                                comic_pub_data = comic.get('publisher', {})
                                if isinstance(comic_pub_data, dict):
                                    comic_pub_id = comic_pub_data.get('id')
                                    if comic_pub_id == publisher_id:
                                        publisher_filtered.append(comic)
                                        continue
                                
                                if self._is_marvel_or_dc_comic(comic):
                                    pub_name = self._extract_publisher_name(comic)
                                    if ((publisher_name == "Marvel" and any(marvel in pub_name.lower() for marvel in ['marvel'])) or
                                        (publisher_name == "DC" and any(dc in pub_name.lower() for dc in ['dc', 'detective comics'])) or
                                        (publisher_name == "Dark Horse" and 'dark horse' in pub_name.lower())):
                                        publisher_filtered.append(comic)
                                    else:
                                        self.log(f"Publisher mismatch: Expected {publisher_name}, got {pub_name}")
                                else:
                                    pub_name = self._extract_publisher_name(comic)
                                    self.log(f"Publisher verification failed: {comic.get('name')} - {pub_name}")
                            
                            self.log(f"Publisher filtered to {len(publisher_filtered)} verified {publisher_name} comics")
                            
                            filtered_comics = []
                            for comic in publisher_filtered:
                                try:
                                    if self._is_new_series(comic):
                                        filtered_comics.append(comic)
                                    else:
                                        self.log(f"Series filter: {comic.get('name')} - likely reprint/collection")
                                except Exception as e:
                                    self.log(f"Error filtering comic {comic.get('name', 'Unknown')}: {e}")
                                    continue
                            
                            self.log(f"Final filtered to {len(filtered_comics)} new {publisher_name} releases")
                            
                            if filtered_comics:
                                for comic in filtered_comics[:3]:
                                    pub_name = self._extract_publisher_name(comic)
                                    self.log(f"Final result: {comic.get('name')} ({pub_name}) - CV ID: {comic.get('id')}")
                            
                            return filtered_comics
                        else:
                            self.log(f"ComicVine API error for {publisher_name}: {data.get('error')}")
                    else:
                        self.log(f"HTTP error searching {publisher_name}: {response.status}")
                        try:
                            error_text = await response.text()
                            self.log(f"Error response: {error_text[:200]}")
                        except:
                            pass
                        
        except Exception as e:
            self.log(f"Error searching {publisher_name} releases: {e}")
        
        return []

    async def _search_recent_releases_all(self, date_filter: str) -> List[Dict]:
        try:
            self.log("Using fallback method: searching all recent releases")
            
            url = f"{self.base_url}/volumes/"
            params = {
                'api_key': self.api_key,
                'format': 'json',
                'field_list': 'id,name,start_year,publisher,issue_count,description,image,deck',
                'filter': f'date_added:{date_filter}',
                'sort': 'date_added:desc',
                'limit': 100
            }
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector
            ) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('error') == 'OK':
                            all_comics = data.get('results', [])
                            self.log(f"Found {len(all_comics)} total recent releases")
                            
                            marvel_dc_comics = []
                            for comic in all_comics:
                                if self._is_marvel_or_dc_comic(comic):
                                    marvel_dc_comics.append(comic)
                            
                            self.log(f"Filtered to {len(marvel_dc_comics)} Marvel/DC comics from all recent releases")
                            
                            filtered_comics = []
                            for comic in marvel_dc_comics:
                                try:
                                    if self._is_new_series(comic):
                                        filtered_comics.append(comic)
                                    else:
                                        pub_name = self._extract_publisher_name(comic)
                                        self.log(f"Series filter: {comic.get('name')} ({pub_name}) - likely reprint/collection")
                                except Exception as e:
                                    self.log(f"Error filtering comic {comic.get('name', 'Unknown')}: {e}")
                                    continue
                            
                            self.log(f"Final fallback filtered to {len(filtered_comics)} new Marvel/DC releases")
                            return filtered_comics
                        else:
                            self.log(f"ComicVine API error in fallback search: {data.get('error')}")
                    else:
                        self.log(f"HTTP error in fallback search: {response.status}")
                        
        except Exception as e:
            self.log(f"Error in fallback search: {e}")
        
        return []

    def _extract_publisher_name(self, comic: Dict) -> str:
        publisher_data = comic.get('publisher', {})
        if isinstance(publisher_data, dict):
            return publisher_data.get('name', 'Unknown')
        elif isinstance(publisher_data, str):
            return publisher_data
        else:
            return 'Unknown'

    def _is_marvel_or_dc_comic(self, comic: Dict) -> bool:
        publisher_name = self._extract_publisher_name(comic).lower()
        
        marvel_publishers = [
            'marvel', 'marvel comics', 'marvel entertainment', 'marvel worldwide',
            'marvel entertainment group', 'marvel comics group'
        ]
        
        dc_publishers = [
            'dc', 'dc comics', 'dc entertainment', 'dc universe',
            'detective comics', 'detective comics, inc.'
        ]
        
        dark_horse_publishers = [
            'dark horse', 'dark horse comics', 'dark horse entertainment'
        ]
        
        for marvel_pub in marvel_publishers:
            if marvel_pub in publisher_name:
                return True
                
        for dc_pub in dc_publishers:
            if dc_pub in publisher_name:
                return True
        
        for dh_pub in dark_horse_publishers:
            if dh_pub in publisher_name:
                return True
        
        publisher_data = comic.get('publisher', {})
        if isinstance(publisher_data, dict):
            publisher_id = publisher_data.get('id')
            if publisher_id in [31, 10, 16]:
                return True
        
        return False

    def _is_new_series(self, comic: Dict) -> bool:
        name = comic.get('name') or ''
        deck = comic.get('deck') or ''
        start_year = comic.get('start_year')
        
        name_lower = name.lower() if name else ''
        deck_lower = deck.lower() if deck else ''
        
        exclude_terms = [
            'collected', 'collection', 'omnibus', 'complete', 'essential',
            'masterworks', 'epic collection', 'treasury', 'archive',
            'reprint', 'classic', 'golden age', 'silver age',
            'hardcover', 'trade paperback', 'tpb', 'graphic novel'
        ]
        
        for term in exclude_terms:
            if term in name_lower or term in deck_lower:
                return False
        
        current_year = datetime.now().year
        if start_year and isinstance(start_year, int) and start_year < current_year - 3:
            return False
        
        return True

    async def check_and_add_new_comics(self, days_back: int = None) -> Dict:
        self.log("Starting automated comic check...")
        
        results = {
            'checked': 0,
            'new_found': 0,
            'added_successfully': 0,
            'failed_to_add': 0,
            'already_exists': 0,
            'details': []
        }
        
        try:
            existing_comics = await self.get_existing_comics()
            self.log(f"Found {len(existing_comics)} existing comics in library")
            
            new_releases = await self.search_new_releases(days_back)
            results['checked'] = len(new_releases)
            
            if not new_releases:
                self.log("No new releases found")
                return results
            
            self.log(f"Found {len(new_releases)} total releases from ComicVine")
            
            truly_new = []
            for comic in new_releases:
                cv_id = comic.get('id')
                if cv_id and cv_id not in existing_comics:
                    truly_new.append(comic)
                else:
                    results['already_exists'] += 1
                    if cv_id:
                        comic_name = comic.get('name', 'Unknown')
                        self.log(f"Skipping {comic_name} (CV ID: {cv_id}) - already in library")
            
            results['new_found'] = len(truly_new)
            self.log(f"Found {len(truly_new)} new comics not in library")
            
            for i, comic in enumerate(truly_new):
                self.log(f"Processing comic {i+1}/{len(truly_new)}")
                await self._process_new_comic(comic, results)
                
                await asyncio.sleep(2)
            
            if results['added_successfully'] > 0:
                self.log(f"Refreshing cache after adding {results['added_successfully']} comics...")
                self.existing_comics_cache.clear()
                self.last_cache_update = None
            
            self.log(f"Comic check complete: {results['added_successfully']} added, {results['failed_to_add']} failed, {results['already_exists']} already existed")
            
        except Exception as e:
            self.log(f"Error in comic check: {e}")
            results['details'].append(f"Error: {str(e)}")
        
        return results

    async def _process_new_comic(self, comic: Dict, results: Dict):
        try:
            title = comic.get('name') or 'Unknown Title'
            cv_id = comic.get('id')
            
            publisher = self._extract_publisher_name(comic)
            
            if not self._is_marvel_or_dc_comic(comic):
                self.log(f"Skipping non-Marvel/DC comic: {title} ({publisher})")
                results['failed_to_add'] += 1
                results['details'].append(f"❌ Skipped: {title} - Not Marvel/DC ({publisher})")
                return
            
            self.log(f"Processing: {title} ({publisher}) - CV ID: {cv_id}")
            
            if cv_id and cv_id in self.existing_comics_cache:
                self.log(f"Comic {title} (CV ID: {cv_id}) found in cache, skipping")
                results['already_exists'] += 1
                results['details'].append(f"⚠️ Skipped: {title} - Already in cache")
                return
            
            kapowarr_comic = {
                'title': title,
                'comicvine_id': cv_id,
                'year': comic.get('start_year'),
                'publisher': publisher,
                'issue_count': comic.get('issue_count', 0),
                'description': comic.get('description') or '',
                'image': comic.get('image', {})
            }
            
            success, volume_id, message = await self.kapowarr.add_comic(kapowarr_comic)
            
            if success and volume_id:
                results['added_successfully'] += 1
                results['details'].append(f"✅ Added: {title} (Kapowarr ID: {volume_id}, CV ID: {cv_id})")
                
                if cv_id:
                    self.existing_comics_cache.add(cv_id)
                
                await asyncio.sleep(2)
                await self._auto_search_comic(volume_id, title)
                
            else:
                if "already exists" in message.lower() or "unique constraint" in message.lower():
                    results['already_exists'] += 1
                    results['details'].append(f"ℹ️ Exists: {title} - Already in library")
                    
                    if cv_id:
                        self.existing_comics_cache.add(cv_id)
                else:
                    results['failed_to_add'] += 1
                    results['details'].append(f"❌ Failed: {title} - {message}")
                
        except Exception as e:
            results['failed_to_add'] += 1
            comic_name = comic.get('name', 'Unknown')
            results['details'].append(f"❌ Error processing {comic_name}: {str(e)}")
            self.log(f"Error processing comic: {e}")

    async def _auto_search_comic(self, volume_id: int, title: str):
        try:
            self.log(f"Auto-searching downloads for: {title}")
            search_results = await self.kapowarr.manual_search(volume_id)
            
            if search_results:
                self.log(f"Found {len(search_results)} download options for {title}")
                
                exact_matches = [r for r in search_results if r.get('is_exact_match', False)]
                if exact_matches:
                    self.log(f"Found {len(exact_matches)} exact matches for {title}")
                    
            else:
                self.log(f"No download options found for {title}")
                
        except Exception as e:
            self.log(f"Error auto-searching {title}: {e}")

    async def manual_check(self, days_back: int = 7) -> Dict:
        self.log(f"Manual comic check triggered (checking last {days_back} days)")
        return await self.check_and_add_new_comics(days_back)

    async def get_recent_additions(self, days: int = 7) -> List[Dict]:
        try:
            releases = await self.search_new_releases(days)
            existing_comics = await self.get_existing_comics()
            
            recent = []
            for comic in releases[:20]:
                if not self._is_marvel_or_dc_comic(comic):
                    continue
                    
                cv_id = comic.get('id')
                in_library = cv_id in existing_comics if cv_id else False
                
                publisher = self._extract_publisher_name(comic)
                
                recent.append({
                    'title': comic.get('name') or 'Unknown',
                    'publisher': publisher,
                    'year': comic.get('start_year'),
                    'issue_count': comic.get('issue_count', 0),
                    'in_library': in_library,
                    'comicvine_id': cv_id
                })
            
            return recent
            
        except Exception as e:
            self.log(f"Error getting recent additions: {e}")
            return []

    async def test_connection(self) -> bool:
        try:
            url = f"{self.base_url}/volumes/"
            params = {
                'api_key': self.api_key,
                'format': 'json',
                'limit': 1
            }
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            ) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('error') == 'OK':
                            self.log("ComicVine API connection successful")
                            return True
                    
            self.log("ComicVine API connection failed")
            return False
            
        except Exception as e:
            self.log(f"ComicVine API connection error: {e}")
            return False