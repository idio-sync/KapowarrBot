import discord
from discord import app_commands
from datetime import datetime
import asyncio
import logging
import json

logger = logging.getLogger(__name__)

class ComicLibraryView(discord.ui.View):
    """UI for browsing comic library with detailed pages"""
    
    def __init__(self, comics, query_type, kapowarr_client, search_query=None):
        super().__init__(timeout=300)
        self.comics = comics
        self.query_type = query_type
        self.kapowarr_client = kapowarr_client
        self.search_query = search_query
        self.current_page = 0
        self.max_pages = len(comics)
        
        self.update_buttons()
    
    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.gray, row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_view(interaction)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.gray, row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            await self.update_view(interaction)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="📥 Manual Search", style=discord.ButtonStyle.primary, row=1)
    async def manual_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.comics:
            await interaction.response.send_message("❌ No comic selected", ephemeral=True)
            return
        
        current_comic = self.comics[self.current_page]
        volume_id = current_comic.get('id')
        
        if not volume_id:
            await interaction.response.send_message("❌ Volume ID not found", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        search_results = await self.kapowarr_client.manual_search(volume_id)
        
        if not search_results:
            await interaction.followup.send("❌ No download options found", ephemeral=True)
            return
        
        search_view = ComicManualSearchView(search_results, volume_id, current_comic, self.kapowarr_client)
        embed = await search_view.create_search_embed()
        
        await interaction.followup.send(embed=embed, view=search_view, ephemeral=True)
    
    @discord.ui.button(label="🔄 Preview Rename", style=discord.ButtonStyle.secondary, row=1)
    async def preview_rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.comics:
            await interaction.response.send_message("❌ No comic selected", ephemeral=True)
            return
        
        current_comic = self.comics[self.current_page]
        volume_id = current_comic.get('id')
        
        if not volume_id:
            await interaction.response.send_message("❌ Volume ID not found", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        rename_data = await self.kapowarr_client.get_rename_preview(volume_id)
        
        if not rename_data:
            await interaction.followup.send("❌ No rename data available", ephemeral=True)
            return
        
        embed = self.create_rename_embed(current_comic, rename_data)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    def update_buttons(self):
        """Update button states"""
        self.previous_page.disabled = (self.current_page == 0)
        self.next_page.disabled = (self.current_page >= self.max_pages - 1)
        
        has_comics = bool(self.comics)
        self.manual_search.disabled = not has_comics
        self.preview_rename.disabled = not has_comics
    
    async def update_view(self, interaction):
        """Update the view with new page"""
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def create_embed(self):
        """Create embed for current comic"""
        if not self.comics:
            return discord.Embed(
                title="📚 No Comics Found",
                description="No comics match your criteria.",
                color=discord.Color.red()
            )
        
        current_comic = self.comics[self.current_page]
        
        if self.query_type == 'wanted':
            title = "📋 Wanted Comics"
        elif self.query_type == 'search':
            title = f"🔍 Comic Search: {self.search_query}"
        else:
            title = "📚 Comic Library"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        comic_title = current_comic.get('title', 'Unknown Title')
        year = current_comic.get('year')
        if year:
            comic_title += f" ({year})"
        
        embed.add_field(name="📖 Title", value=comic_title, inline=False)
        
        publisher = current_comic.get('publisher', 'Unknown')
        embed.add_field(name="🏢 Publisher", value=publisher, inline=True)
        
        issue_count = current_comic.get('issue_count', 0)
        issues_downloaded = current_comic.get('issues_downloaded', 0)
        embed.add_field(name="📊 Issues", value=f"{issues_downloaded}/{issue_count}", inline=True)
        
        monitored = current_comic.get('monitored', False)
        monitor_status = "✅ Monitored" if monitored else "❌ Not Monitored"
        embed.add_field(name="👁️ Status", value=monitor_status, inline=True)
        
        cv_id = current_comic.get('comicvine_id')
        if cv_id:
            cv_link = f"https://comicvine.gamespot.com/volume/4050-{cv_id}/"
            embed.add_field(name="🔗 ComicVine", value=f"[View on ComicVine]({cv_link})", inline=False)
        
        description = current_comic.get('description')
        if description:
            clean_desc = self.kapowarr_client.clean_html(description)
            if clean_desc and clean_desc != "No description available.":
                if len(clean_desc) > 500:
                    clean_desc = clean_desc[:497] + "..."
                embed.add_field(name="📝 Description", value=clean_desc, inline=False)
        
        cover_url = None
        
        if cv_id:
            try:
                import config
                if hasattr(config, 'COMICVINE_API_KEY') and config.COMICVINE_API_KEY:
                    cover_url = await self.kapowarr_client.get_comicvine_cover(cv_id, config.COMICVINE_API_KEY)
                    if cover_url:
                        embed.set_thumbnail(url=cover_url)
                    else:
                        volume_id = current_comic.get('id')
                        if volume_id:
                            kapowarr_cover_url = f"{self.kapowarr_client.url}/api/volumes/{volume_id}/cover?api_key={self.kapowarr_client.api_key}"
                            embed.set_thumbnail(url=kapowarr_cover_url)
                else:
                    volume_id = current_comic.get('id')
                    if volume_id:
                        kapowarr_cover_url = f"{self.kapowarr_client.url}/api/volumes/{volume_id}/cover?api_key={self.kapowarr_client.api_key}"
                        embed.set_thumbnail(url=kapowarr_cover_url)
            except Exception as e:
                volume_id = current_comic.get('id')
                if volume_id:
                    kapowarr_cover_url = f"{self.kapowarr_client.url}/api/volumes/{volume_id}/cover?api_key={self.kapowarr_client.api_key}"
                    embed.set_thumbnail(url=kapowarr_cover_url)
        else:
            volume_id = current_comic.get('id')
            if volume_id:
                kapowarr_cover_url = f"{self.kapowarr_client.url}/api/volumes/{volume_id}/cover?api_key={self.kapowarr_client.api_key}"
                embed.set_thumbnail(url=kapowarr_cover_url)
        
        volume_id = current_comic.get('id')
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.max_pages} | Volume ID: {volume_id}")
        
        return embed
    
    def create_rename_embed(self, comic, rename_data):
        """Create embed showing rename preview"""
        embed = discord.Embed(
            title="🔄 Rename Preview",
            description=f"Preview of file renames for **{comic.get('title', 'Unknown')}**",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        if isinstance(rename_data, dict) and rename_data:
            rename_items = list(rename_data.items())[:10]
            
            rename_text = ""
            for old_path, new_path in rename_items:
                old_name = old_path.split('/')[-1]
                new_name = new_path.split('/')[-1]
                
                if len(old_name) > 40:
                    old_name = old_name[:37] + "..."
                if len(new_name) > 40:
                    new_name = new_name[:37] + "..."
                
                rename_text += f"**From:** `{old_name}`\n**To:** `{new_name}`\n\n"
            
            if len(rename_data) > 10:
                rename_text += f"... and {len(rename_data) - 10} more files"
            
            embed.add_field(name="📁 File Renames", value=rename_text or "No renames needed", inline=False)
            embed.add_field(name="📊 Total Files", value=str(len(rename_data)), inline=True)
        else:
            embed.add_field(name="ℹ️ Status", value="No rename operations needed", inline=False)
        
        return embed


class ComicManualSearchView(discord.ui.View):
    """View for manual comic search and download"""
    
    def __init__(self, search_results, volume_id, comic_info, kapowarr_client):
        super().__init__(timeout=300)
        self.search_results = search_results
        self.volume_id = volume_id
        self.comic_info = comic_info
        self.kapowarr_client = kapowarr_client
        
        if search_results:
            self.add_item(ComicDownloadSelector(search_results, self))
    
    async def create_search_embed(self):
        """Create embed for manual search results"""
        embed = discord.Embed(
            title="📥 Manual Search Results",
            description=f"Download options for **{self.comic_info.get('title', 'Unknown')}**",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        if not self.search_results:
            embed.add_field(name="❌ No Results", value="No download options found", inline=False)
            return embed
        
        embed.add_field(name="📊 Results Found", value=str(len(self.search_results)), inline=True)
        embed.add_field(name="📖 Volume ID", value=str(self.volume_id), inline=True)
        
        preview_text = ""
        for i, result in enumerate(self.search_results[:5]):
            title = result.get('display_title', result.get('title', 'Unknown'))
            source = result.get('source', 'Unknown')
            is_match = result.get('match', False)
            match_status = "✅" if is_match else "❌"
            
            self.kapowarr_client.log(f"Result {i}: match={is_match}, title={title}")
            
            preview_text += f"{match_status} **{title}**\n└ Source: {source}\n\n"
        
        if len(self.search_results) > 5:
            preview_text += f"... and {len(self.search_results) - 5} more options"
        
        embed.add_field(name="🎯 Available Downloads", value=preview_text, inline=False)
        
        cover_url = None
        
        if self.volume_id:
            cover_url = f"{self.kapowarr_client.url}/api/volumes/{self.volume_id}/cover?api_key={self.kapowarr_client.api_key}"
        
        if self.comic_info:
            cv_id = self.comic_info.get('comicvine_id')
            if cv_id:
                try:
                    import config
                    if hasattr(config, 'COMICVINE_API_KEY'):
                        cv_cover = await self.kapowarr_client.get_comicvine_cover(cv_id, config.COMICVINE_API_KEY)
                        if cv_cover:
                            cover_url = cv_cover
                except:
                    pass
        
        if cover_url:
            embed.set_thumbnail(url=cover_url)
        
        return embed


class ComicDownloadSelector(discord.ui.Select):
    """Dropdown for selecting comic downloads"""
    
    def __init__(self, search_results, parent_view):
        self.search_results = search_results
        self.parent_view = parent_view
        
        options = []
        for i, result in enumerate(search_results[:25]):
            title = result.get('display_title', result.get('title', 'Unknown'))
            source = result.get('source', 'Unknown')
            match_status = result.get('match_issue', 'No match info')
            
            is_match = result.get('match', False)
            
            print(f"Dropdown item {i}: match={is_match}, title={title}")
            
            if is_match:
                label = f"✅ {title}"
                emoji = "📚"
            else:
                label = f"❌ {title}"
                emoji = "📖"
            
            if len(label) > 90:
                label = label[:87] + "..."
            
            description = f"{source} | {match_status if match_status else 'No match info'}"
            if len(description) > 90:
                description = description[:87] + "..."
            
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=str(i),
                emoji=emoji
            ))
        
        super().__init__(
            placeholder="Select a download option...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle download selection"""
        selected_idx = int(self.values[0])
        
        if selected_idx >= len(self.search_results):
            await interaction.response.send_message("❌ Invalid selection", ephemeral=True)
            return
        
        selected_result = self.search_results[selected_idx]
        
        confirm_view = ComicDownloadConfirmView(
            selected_result, 
            self.parent_view.volume_id, 
            self.parent_view.comic_info,
            self.parent_view.kapowarr_client
        )
        
        embed = confirm_view.create_confirm_embed()
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class ComicDownloadConfirmView(discord.ui.View):
    """Confirmation view for comic download"""
    
    def __init__(self, download_result, volume_id, comic_info, kapowarr_client):
        super().__init__(timeout=180)
        self.download_result = download_result
        self.volume_id = volume_id
        self.comic_info = comic_info
        self.kapowarr_client = kapowarr_client
    
    @discord.ui.button(label="📥 Download", style=discord.ButtonStyle.success)
    async def confirm_download(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        download_link = self.download_result.get('link')
        if not download_link:
            await interaction.followup.send("❌ No download link found", ephemeral=True)
            return
        
        processing_embed = discord.Embed(
            title="⏳ Starting Download",
            description=f"Initiating download for **{self.download_result.get('display_title', self.download_result.get('title', 'Unknown'))}**...",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=processing_embed, ephemeral=True)
        
        try:
            success, message = await self.kapowarr_client.download_comic(
                self.volume_id, 
                download_link, 
                force_match=False
            )
            
            if success:
                success_embed = discord.Embed(
                    title="✅ Download Started",
                    description=f"Successfully started download for **{self.comic_info.get('title', 'Unknown')}**",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                
                success_embed.add_field(name="📦 Source", value=self.download_result.get('source', 'Unknown'), inline=True)
                success_embed.add_field(name="🔗 Title", value=self.download_result.get('display_title', self.download_result.get('title', 'Unknown')), inline=False)
                success_embed.add_field(name="📋 Status", value=message, inline=False)
                
                await interaction.followup.send(embed=success_embed, ephemeral=True)
            else:
                error_embed = discord.Embed(
                    title="❌ Download Failed",
                    description=f"Failed to start download: {message}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="⚡ Force Download", style=discord.ButtonStyle.danger)
    async def force_download(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        download_link = self.download_result.get('link')
        if not download_link:
            await interaction.followup.send("❌ No download link found", ephemeral=True)
            return
        
        try:
            success, message = await self.kapowarr_client.download_comic(
                self.volume_id, 
                download_link, 
                force_match=True
            )
            
            if success:
                success_embed = discord.Embed(
                    title="⚡ Force Download Started",
                    description=f"Force download started for **{self.comic_info.get('title', 'Unknown')}**",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                
                success_embed.add_field(name="⚠️ Force Mode", value="Download will proceed regardless of naming conflicts", inline=False)
                success_embed.add_field(name="📦 Source", value=self.download_result.get('source', 'Unknown'), inline=True)
                
                await interaction.followup.send(embed=success_embed, ephemeral=True)
            else:
                error_embed = discord.Embed(
                    title="❌ Force Download Failed",
                    description=f"Failed to start force download: {message}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.gray)
    async def cancel_download(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Download cancelled", ephemeral=True)
    
    def create_confirm_embed(self):
        """Create confirmation embed"""
        embed = discord.Embed(
            title="📥 Confirm Download",
            description="Confirm download selection:",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="📚 Comic", value=self.comic_info.get('title', 'Unknown'), inline=False)
        embed.add_field(name="📦 Download Title", value=self.download_result.get('display_title', self.download_result.get('title', 'Unknown')), inline=False)
        embed.add_field(name="🌐 Source", value=self.download_result.get('source', 'Unknown'), inline=True)
        
        is_match = self.download_result.get('match', False)
        match_status = "✅ Match" if is_match else "❌ No Match"
        match_reason = self.download_result.get('match_issue', 'N/A')
        embed.add_field(name="🎯 Match Status", value=f"{match_status}\n{match_reason}", inline=True)
        
        series = self.download_result.get('series', 'Unknown')
        vol_num = self.download_result.get('volume_number', 'N/A')
        embed.add_field(name="📖 Series", value=f"{series} Vol. {vol_num}", inline=True)
        
        if not is_match:
            embed.add_field(
                name="⚠️ Warning",
                value="This download doesn't match the expected comic. Use 'Force Download' if you're sure this is correct.",
                inline=False
            )
        
        return embed