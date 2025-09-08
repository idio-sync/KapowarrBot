import aiohttp
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class KapowarrClient:
    def __init__(self, url, api_key, max_retry_attempts=3, retry_delay=5):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay = retry_delay
        self.base_url = f"{self.url}/api/volumes"
        
    def log(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Kapowarr: {message}")

    async def search_comics_detailed(self, query, limit=50):
        try:
            params = {
                'api_key': self.api_key,
                'query': query
            }
            
            search_url = f"{self.base_url}/search"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(search_url, params=params) as response:
                    if response.status == 200:
                        search_results = await response.json()
                        results = search_results.get('result', [])
                        
                        limited_results = results[:limit]
                        
                        self.log(f"Found {len(limited_results)} comics for '{query}' using detailed search")
                        return limited_results
                    else:
                        self.log(f"Detailed search failed with status: {response.status}")
                        return []
                        
        except Exception as e:
            self.log(f"Detailed search error: {e}")
            return []

    async def search_comics(self, query, limit=25):
        try:
            params = {
                'api_key': self.api_key,
                'query': query
            }
            
            search_url = f"{self.base_url}/search"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(search_url, params=params) as response:
                    if response.status == 200:
                        search_results = await response.json()
                        results = search_results.get('result', [])
                        
                        limited_results = results[:limit]
                        enhanced_results = []
                        
                        for comic in limited_results:
                            enhanced_comic = self.enhance_comic_data(comic)
                            enhanced_results.append(enhanced_comic)
                        
                        self.log(f"Found {len(enhanced_results)} comics for '{query}'")
                        return enhanced_results
                    else:
                        self.log(f"Search failed with status: {response.status}")
                        return []
                        
        except Exception as e:
            self.log(f"Search error: {e}")
            return []

    async def get_wanted_comics(self):
        try:
            params = {
                'api_key': self.api_key,
                'filter': 'wanted',
                'sort': 'title'
            }
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        wanted_data = await response.json()
                        results = wanted_data.get('result', [])
                        self.log(f"Found {len(results)} wanted comics")
                        return results
                    else:
                        self.log(f"Failed to get wanted comics: HTTP {response.status}")
                        return []
                        
        except Exception as e:
            self.log(f"Error getting wanted comics: {e}")
            return []

    async def get_comic_library(self):
        try:
            params = {
                'api_key': self.api_key,
                'sort': 'title'
            }
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        library_data = await response.json()
                        results = library_data.get('result', [])
                        self.log(f"Found {len(results)} comics in library")
                        return results
                    else:
                        self.log(f"Failed to get comic library: HTTP {response.status}")
                        return []
                        
        except Exception as e:
            self.log(f"Error getting comic library: {e}")
            return []

    async def search_comic_library(self, query):
        try:
            all_comics = await self.get_comic_library()
            
            matching_comics = []
            query_lower = query.lower()
            
            for comic in all_comics:
                title = comic.get('title', '').lower()
                if query_lower in title:
                    matching_comics.append(comic)
            
            self.log(f"Found {len(matching_comics)} comics matching '{query}'")
            return matching_comics
                        
        except Exception as e:
            self.log(f"Error searching comic library: {e}")
            return []

    async def get_library_stats(self):
        try:
            params = {
                'api_key': self.api_key
            }
            
            stats_url = f"{self.url}/api/volumes/stats"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
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

    async def get_rename_preview(self, volume_id):
        try:
            params = {
                'api_key': self.api_key
            }
            
            rename_url = f"{self.base_url}/{volume_id}/rename"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(rename_url, params=params) as response:
                    if response.status == 200:
                        rename_data = await response.json()
                        return rename_data.get('result', {})
                    else:
                        self.log(f"Failed to get rename preview: HTTP {response.status}")
                        return {}
                        
        except Exception as e:
            self.log(f"Error getting rename preview: {e}")
            return {}

    def enhance_comic_data(self, comic):
        enhanced = {
            'id': comic.get('comicvine_id'),
            'title': comic.get('title', 'Unknown Title'),
            'year': comic.get('year', 'Unknown'),
            'publisher': comic.get('publisher', 'Unknown Publisher'),
            'issue_count': comic.get('issue_count', 0),
            'comicvine_id': comic.get('comicvine_id'),
            'description': comic.get('description', ''),
            'cover_url': self.get_cover_url(comic),
            'raw_data': comic
        }
        
        if enhanced['year'] and enhanced['year'] != 'Unknown':
            enhanced['display_title'] = f"{enhanced['title']} ({enhanced['year']})"
        else:
            enhanced['display_title'] = enhanced['title']
            
        return enhanced

    def get_cover_url(self, comic):
        image_url = None
        
        if 'cover_link' in comic and comic['cover_link']:
            image_url = comic['cover_link'].strip()
        
        elif 'image' in comic and comic['image']:
            if isinstance(comic['image'], dict):
                for size in ['super_url', 'medium_url', 'small_url', 'icon_url']:
                    if size in comic['image'] and comic['image'][size]:
                        image_url = comic['image'][size]
                        break
            elif isinstance(comic['image'], str) and comic['image'].strip():
                image_url = comic['image']
        
        if not image_url:
            image_fields = ['poster_url', 'remote_poster_url', 'thumbnail', 'cover_url']
            for field_name in image_fields:
                if field_name in comic and comic[field_name]:
                    field_value = comic[field_name]
                    if isinstance(field_value, str) and field_value.strip():
                        image_url = field_value.strip()
                        break
        
        if image_url and 'comicvine.gamespot.com' in image_url:
            if 'scale_small' in image_url:
                image_url = image_url.replace('scale_small', 'scale_medium')
            elif 'scale_avatar' in image_url:
                image_url = image_url.replace('scale_avatar', 'scale_medium')
        
        return image_url

    async def add_comic(self, comic_data, root_folder_id=1):
        try:
            import json
            
            title = comic_data.get('title', 'Unknown Title')
            raw_cv_id = comic_data.get('comicvine_id')
            
            if isinstance(raw_cv_id, str) and raw_cv_id.startswith('cv:'):
                numeric_cv_id = raw_cv_id.replace('cv:', '')
            else:
                numeric_cv_id = raw_cv_id
            
            try:
                comicvine_id = int(numeric_cv_id)
            except (ValueError, TypeError):
                return False, None, f"Invalid ComicVine ID format: {raw_cv_id}"
            
            params = {
                'api_key': self.api_key
            }
            
            payload = {
                "comicvine_id": comicvine_id,
                "root_folder_id": root_folder_id,
                "monitor": True,
                "monitor_new_issues": True,
                "monitoring_scheme": "all",
                "auto_search": True,
                "special_version": "auto",
                "volume_folder": ""
            }
            
            self.log(f"Adding comic to Kapowarr: {title} (CV ID: {comicvine_id}) with automatic type detection and auto-search")
            self.log(f"Request payload: {payload}")
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector
            ) as session:
                async with session.post(self.base_url, params=params, json=payload) as response:
                    self.log(f"Response status: {response.status}")
                    
                    try:
                        response_content = await response.json()
                        result = response_content.get('result', {})
                        special_version = result.get('special_version')
                        special_version_locked = result.get('special_version_locked')
                        self.log(f"Result special_version: {special_version} (auto-detected)")
                        self.log(f"Result special_version_locked: {special_version_locked}")
                    except Exception as json_error:
                        response_text = await response.text()
                        self.log(f"Failed to parse JSON response: {json_error}")
                        self.log(f"Raw response text: {response_text}")
                        response_content = {"error": f"Invalid JSON response: {response_text}"}
                    
                    if response.status == 201:
                        volume_id = response_content.get('result', {}).get('id')
                        if volume_id:
                            detected_type = response_content.get('result', {}).get('special_version', 'unknown')
                            self.log(f"Successfully added '{title}' with volume ID: {volume_id} (Auto-detected as: {detected_type})")
                            return True, volume_id, f"Successfully added {title} to Kapowarr"
                        else:
                            return False, None, "Failed to retrieve volume ID from response"
                    else:
                        error_msg = response_content.get('error', f'HTTP {response.status}')
                        
                        if 'UNIQUE constraint failed' in str(error_msg) or 'already exists' in str(error_msg).lower():
                            self.log(f"Comic '{title}' already exists in Kapowarr")
                            return False, None, f"Comic already exists in library"
                        else:
                            self.log(f"Failed to add comic: {error_msg}")
                            return False, None, error_msg
                            
        except Exception as e:
            self.log(f"Error adding comic: {e}")
            return False, None, str(e)

    async def get_volume_details(self, volume_id):
        try:
            params = {
                'api_key': self.api_key
            }
            
            volume_url = f"{self.base_url}/{volume_id}"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                async with session.get(volume_url, params=params) as response:
                    if response.status == 200:
                        volume_data = await response.json()
                        return volume_data.get('result', {})
                    else:
                        self.log(f"Failed to get volume details: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            self.log(f"Error getting volume details: {e}")
            return None

    async def manual_search(self, volume_id):
        try:
            params = {
                'api_key': self.api_key
            }
            
            search_url = f"{self.base_url}/{volume_id}/manualsearch"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector
            ) as session:
                async with session.get(search_url, params=params) as response:
                    if response.status == 200:
                        search_content = await response.json()
                        results = search_content.get('result', [])
                        
                        self.log(f"Found {len(results)} download options for volume {volume_id}")
                        
                        matches_found = 0
                        for i, result in enumerate(results[:5]):
                            match_status = result.get('match', False)
                            title = result.get('display_title', 'Unknown')
                            source = result.get('source', 'Unknown')
                            if match_status:
                                matches_found += 1
                            self.log(f"Result {i+1}: {'✅' if match_status else '❌'} {title} ({source})")
                        
                        self.log(f"Total matches found: {matches_found}/{len(results)}")
                        return results
                    else:
                        self.log(f"Manual search failed: HTTP {response.status}")
                        return []
                        
        except Exception as e:
            self.log(f"Error in manual search: {e}")
            return []

    async def download_comic(self, volume_id, download_link, force_match=False):
        try:
            params = {
                'api_key': self.api_key,
                'link': download_link,
                'force_match': str(force_match).lower()
            }
            
            download_url = f"{self.base_url}/{volume_id}/download"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector
            ) as session:
                async with session.post(download_url, params=params) as response:
                    response_text = await response.text()
                    
                    try:
                        response_content = json.loads(response_text)
                    except json.JSONDecodeError:
                        response_content = {"error": f"Invalid JSON response: {response_text}"}
                    
                    if response.status in [200, 201, 202]:
                        mode_text = "Force download" if force_match else "Download"
                        self.log(f"{mode_text} accepted for volume {volume_id}")
                        return True, f"{mode_text} started successfully"
                    else:
                        error_msg = response_content.get("error", f"HTTP {response.status}")
                        self.log(f"Download failed: {error_msg}")
                        return False, error_msg
                        
        except Exception as e:
            self.log(f"Error downloading comic: {e}")
            return False, str(e)

    async def check_connection(self):
        try:
            params = {
                'api_key': self.api_key
            }
            
            about_url = f"{self.url}/api/system/about"
            
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, keepalive_timeout=30)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            ) as session:
                async with session.get(about_url, params=params) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            result = data.get('result', {})
                            version = result.get('version', 'Unknown')
                            self.log(f"Connected to Kapowarr {version}")
                            return True
                        except Exception as json_error:
                            self.log(f"Failed to parse response JSON: {json_error}")
                            return False
                    elif response.status == 401:
                        self.log("API key authentication failed")
                        return False
                    else:
                        self.log(f"Connection failed: HTTP {response.status}")
                        return False
                            
        except Exception as e:
            self.log(f"Connection failed: {e}")
            return False

    async def get_comicvine_cover(self, comicvine_id, api_key):
        try:
            cv_url = f"https://comicvine.gamespot.com/api/volume/4050-{comicvine_id}/"
            
            params = {
                'api_key': api_key,
                'format': 'json',
                'field_list': 'image'
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
                            image_data = data['results'].get('image', {})
                            
                            for size in ['medium_url', 'small_url', 'super_url', 'icon_url']:
                                if image_data.get(size):
                                    cover_url = image_data[size]
                                    self.log(f"Found ComicVine cover: {cover_url}")
                                    return cover_url
                        
                        self.log(f"No image found in ComicVine response for ID: {comicvine_id}")
                        return None
                    else:
                        self.log(f"ComicVine API error: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            self.log(f"Error fetching ComicVine cover for ID {comicvine_id}: {e}")
            return None

    def clean_html(self, html_text):
        if not html_text:
            return "No description available."
        
        def replace_link(match):
            url = match.group(1)
            text = match.group(2)
            return f"[{text}]({url})"
        
        cleaned = re.sub(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', replace_link, html_text)
        cleaned = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>([^<]+)</a>', replace_link, cleaned)
        
        cleaned = cleaned.replace("<p>", "").replace("</p>", "\n\n")
        cleaned = cleaned.replace("<br>", "\n").replace("<br />", "\n")
        
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
        cleaned = cleaned.strip()
        
        if len(cleaned) > 1000:
            cleaned = cleaned[:997] + "..."
            
        return cleaned

    def format_file_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        
        import math
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"