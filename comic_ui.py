import discord
from discord import app_commands
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)

class ComicDetailView(discord.ui.View):
    
    def __init__(self, results, query, kapowarr_client, current_index=0):
        super().__init__(timeout=300)
        self.results = results
        self.query = query
        self.kapowarr_client = kapowarr_client
        self.current_index = current_index
        
        self.update_buttons()
    
    @discord.ui.button(label="✅ Confirm Add", style=discord.ButtonStyle.green, row=0)
    async def confirm_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.results or self.current_index >= len(self.results):
            await interaction.response.send_message("❌ No comic selected", ephemeral=True)
            return
            
        current_comic = self.results[self.current_index]
        
        view = ComicAddConfirmView(current_comic, self.kapowarr_client)
        embed = view.create_comic_details_embed()
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="📋 Other Options", style=discord.ButtonStyle.secondary, row=0)
    async def show_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.results:
            await interaction.response.send_message("❌ No options available", ephemeral=True)
            return
        
        view = ComicOptionsView(self.results, self.query, self.kapowarr_client, self.current_index)
        embed = view.create_options_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    def update_buttons(self):
        has_results = bool(self.results)
        self.confirm_add.disabled = not has_results
        self.show_options.disabled = not has_results or len(self.results) <= 1
    
    def create_detailed_embed(self):
        if not self.results or self.current_index >= len(self.results):
            return discord.Embed(
                title="📚 No Comics Found",
                description="No comics match your search criteria.",
                color=discord.Color.red()
            )
        
        current_comic = self.results[self.current_index]
        
        embed = discord.Embed(
            title="📚 Comic Search Result",
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
        embed.add_field(name="📊 Issues", value=str(issue_count), inline=True)
        
        volume_number = current_comic.get('volume_number', 'N/A')
        embed.add_field(name="📚 Volume", value=str(volume_number), inline=True)
        
        cv_id = current_comic.get('comicvine_id')
        if cv_id:
            cv_link = f"https://comicvine.gamespot.com/volume/4050-{cv_id}/"
            embed.add_field(name="🔗 ComicVine", value=f"[View on ComicVine]({cv_link})", inline=False)
        
        already_added = current_comic.get('already_added')
        if already_added is not None:
            if already_added is None:
                already_added = 0
                
            if already_added > 0:
                status_text = f"⚠️ Already in library ({already_added} issues)"
                embed.add_field(name="📋 Status", value=status_text, inline=False)
            else:
                embed.add_field(name="📋 Status", value="✅ Available to add", inline=False)
        
        aliases = current_comic.get('aliases', [])
        if aliases:
            alias_text = ', '.join(aliases[:3])
            if len(aliases) > 3:
                alias_text += f" (+{len(aliases) - 3} more)"
            embed.add_field(name="📝 Aliases", value=alias_text, inline=False)
        
        description = current_comic.get('description')
        if description:
            clean_desc = self.kapowarr_client.clean_html(description)
            if clean_desc and clean_desc != "No description available.":
                if len(clean_desc) > 800:
                    clean_desc = clean_desc[:797] + "..."
                embed.add_field(name="📖 Description", value=clean_desc, inline=False)
        
        cover_url = current_comic.get('cover_link')
        if cover_url:
            embed.set_image(url=cover_url)
            embed.set_thumbnail(url=cover_url)
        
        embed.set_footer(
            text=f"Result {self.current_index + 1} of {len(self.results)} • Search: {self.query} • CV ID: {cv_id}"
        )
        
        return embed


class ComicOptionsView(discord.ui.View):
    
    def __init__(self, results, query, kapowarr_client, current_index=0):
        super().__init__(timeout=300)
        self.results = results
        self.query = query
        self.kapowarr_client = kapowarr_client
        self.current_index = current_index
        
        if results:
            self.add_item(ComicOptionSelector(results, self))
        
        self.add_item(self.create_back_button())
    
    def create_back_button(self):
        button = discord.ui.Button(
            label="◀ Back to Details",
            style=discord.ButtonStyle.gray,
            row=1
        )
        
        async def back_callback(interaction: discord.Interaction):
            detail_view = ComicDetailView(self.results, self.query, self.kapowarr_client, self.current_index)
            embed = detail_view.create_detailed_embed()
            await interaction.response.edit_message(embed=embed, view=detail_view)
        
        button.callback = back_callback
        return button
    
    def create_options_embed(self):
        embed = discord.Embed(
            title="📋 Comic Search Options",
            description=f"Select a comic from the search results for **{self.query}**",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📊 Search Results", 
            value=f"Found {len(self.results)} comics matching your search",
            inline=False
        )
        
        preview_text = ""
        for i, comic in enumerate(self.results[:10]):
            title = comic.get('title', 'Unknown')
            year = comic.get('year', '')
            publisher = comic.get('publisher', 'Unknown')
            issue_count = comic.get('issue_count', 0)
            already_added = comic.get('already_added', 0)
            
            if already_added is None:
                already_added = 0
            
            year_text = f" ({year})" if year else ""
            status_icon = "⚠️" if already_added > 0 else "📚"
            
            preview_text += f"{status_icon} **{title}**{year_text} - {publisher} ({issue_count} issues)\n"
        
        if len(self.results) > 10:
            preview_text += f"\n... and {len(self.results) - 10} more results"
        
        embed.add_field(name="📖 Available Comics", value=preview_text, inline=False)
        
        embed.set_footer(text="Use the dropdown below to select a comic for detailed view")
        
        return embed


class ComicOptionSelector(discord.ui.Select):
    
    def __init__(self, results, parent_view):
        self.results = results
        self.parent_view = parent_view
        
        options = []
        for i, comic in enumerate(results[:25]):
            title = comic.get('title', 'Unknown Title')
            year = comic.get('year', '')
            publisher = comic.get('publisher', 'Unknown')
            issue_count = comic.get('issue_count', 0)
            already_added = comic.get('already_added', 0)
            
            if already_added is None:
                already_added = 0
            
            if year:
                label = f"{title} ({year})"
            else:
                label = title
            
            if len(label) > 90:
                label = label[:87] + "..."
            
            description = f"{publisher} • {issue_count} issues"
            if already_added > 0:
                description += f" • In library"
            
            if len(description) > 90:
                description = description[:87] + "..."
            
            if already_added > 0:
                emoji = "⚠️"
            else:
                emoji = "📚"
            
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=str(i),
                emoji=emoji
            ))
        
        super().__init__(
            placeholder=f"Select a comic... ({len(results)} results)",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_idx = int(self.values[0])
        
        if selected_idx >= len(self.results):
            await interaction.response.send_message("❌ Invalid selection", ephemeral=True)
            return
        
        self.parent_view.current_index = selected_idx
        
        detail_view = ComicDetailView(
            self.results, 
            self.parent_view.query, 
            self.parent_view.kapowarr_client, 
            selected_idx
        )
        embed = detail_view.create_detailed_embed()
        
        await interaction.response.edit_message(embed=embed, view=detail_view)


class ComicAddConfirmView(discord.ui.View):
    
    def __init__(self, selected_comic, kapowarr_client):
        super().__init__(timeout=180)
        self.selected_comic = selected_comic
        self.kapowarr_client = kapowarr_client
    
    @discord.ui.button(label="✅ Add to Kapowarr", style=discord.ButtonStyle.green, row=0)
    async def confirm_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        title = self.selected_comic.get('title', 'Unknown')
        already_added = self.selected_comic.get('already_added', 0)
        
        if already_added is None:
            already_added = 0
        
        if already_added > 0:
            warning_embed = discord.Embed(
                title="⚠️ Already in Library",
                description=f"**{title}** is already in your Kapowarr library with {already_added} issues.",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=warning_embed, ephemeral=True)
            return
        
        processing_embed = discord.Embed(
            title="⏳ Adding Comic",
            description=f"Adding **{title}** to Kapowarr...",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        await interaction.followup.send(embed=processing_embed, ephemeral=True)
        
        try:
            success, volume_id, message = await self.kapowarr_client.add_comic(self.selected_comic)
            
            if success and volume_id:
                await asyncio.sleep(2)
                
                volume_data = await self.kapowarr_client.get_volume_details(volume_id)
                
                if volume_data:
                    search_results = await self.kapowarr_client.manual_search(volume_id)
                    
                    success_embed = discord.Embed(
                        title="✅ Comic Added Successfully",
                        description=f"**{title}** has been added to Kapowarr!",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    
                    success_embed.add_field(name="📖 Volume ID", value=str(volume_id), inline=True)
                    success_embed.add_field(name="📊 Issues", value=str(volume_data.get('issue_count', 0)), inline=True)
                    success_embed.add_field(name="🏢 Publisher", value=volume_data.get('publisher', 'Unknown'), inline=True)
                    
                    if search_results:
                        success_embed.add_field(
                            name="🔥 Download Options", 
                            value=f"Found {len(search_results)} download options. Check manual search for details.",
                            inline=False
                        )
                    else:
                        success_embed.add_field(
                            name="🔥 Download Options", 
                            value="No download options found automatically.",
                            inline=False
                        )
                    
                    cover_url = self.selected_comic.get('cover_link')
                    if cover_url:
                        success_embed.set_thumbnail(url=cover_url)
                    
                    await interaction.followup.send(embed=success_embed, ephemeral=True)
                else:
                    error_embed = discord.Embed(
                        title="⚠️ Partial Success",
                        description=f"**{title}** was added but failed to retrieve volume details.",
                        color=discord.Color.orange(),
                        timestamp=datetime.now()
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                failed_embed = discord.Embed(
                    title="❌ Failed to Add",
                    description=f"Failed to add **{title}** to Kapowarr.\n\n**Error:** {message}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await interaction.followup.send(embed=failed_embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error adding comic: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while adding **{title}**:\n```{str(e)}```",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    @discord.ui.button(label="🔥 Manual Download", style=discord.ButtonStyle.primary, row=0)
    async def manual_download(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        title = self.selected_comic.get('title', 'Unknown')
        already_added = self.selected_comic.get('already_added', 0)
        
        if already_added is None:
            already_added = 0
        
        volume_id = None
        
        if already_added > 0:
            try:
                library_comics = await self.kapowarr_client.get_comic_library()
                cv_id = self.selected_comic.get('comicvine_id')
                
                for comic in library_comics:
                    if comic.get('comicvine_id') == cv_id:
                        volume_id = comic.get('id')
                        break
                
                if not volume_id:
                    await interaction.followup.send("❌ Could not find comic in library", ephemeral=True)
                    return
                    
            except Exception as e:
                await interaction.followup.send(f"❌ Error finding comic in library: {str(e)}", ephemeral=True)
                return
        else:
            processing_embed = discord.Embed(
                title="⏳ Adding Comic & Searching Downloads",
                description=f"Adding **{title}** to Kapowarr and searching for downloads...",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=processing_embed, ephemeral=True)
            
            try:
                success, volume_id, message = await self.kapowarr_client.add_comic(self.selected_comic)
                
                if not success or not volume_id:
                    failed_embed = discord.Embed(
                        title="❌ Failed to Add Comic",
                        description=f"Failed to add **{title}** to Kapowarr: {message}",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    await interaction.followup.send(embed=failed_embed, ephemeral=True)
                    return
                
                await asyncio.sleep(3)
                
            except Exception as e:
                await interaction.followup.send(f"❌ Error adding comic: {str(e)}", ephemeral=True)
                return
        
        try:
            search_results = await self.kapowarr_client.manual_search(volume_id)
            
            if not search_results:
                no_results_embed = discord.Embed(
                    title="❌ No Download Options Found",
                    description=f"No download options found for **{title}**",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                await interaction.followup.send(embed=no_results_embed, ephemeral=True)
                return
            
            from comic_library_ui import ComicManualSearchView
            
            comic_info = {
                'title': title,
                'comicvine_id': self.selected_comic.get('comicvine_id'),
                'id': volume_id
            }
            
            search_view = ComicManualSearchView(search_results, volume_id, comic_info, self.kapowarr_client)
            embed = await search_view.create_search_embed()
            
            await interaction.followup.send(embed=embed, view=search_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in manual search: {e}")
            await interaction.followup.send(f"❌ Error searching for downloads: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.gray, row=1)
    async def cancel_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Comic addition cancelled", ephemeral=True)
    
    def create_comic_details_embed(self):
        title = self.selected_comic.get('title', 'Unknown Title')
        year = self.selected_comic.get('year', '')
        
        embed = discord.Embed(
            title="📚 Confirm Comic Addition",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        comic_display = title
        if year:
            comic_display += f" ({year})"
        
        embed.add_field(name="📖 Comic", value=comic_display, inline=False)
        
        if self.selected_comic.get('publisher'):
            embed.add_field(name="🏢 Publisher", value=self.selected_comic['publisher'], inline=True)
        
        if self.selected_comic.get('issue_count'):
            embed.add_field(name="📊 Issues", value=str(self.selected_comic['issue_count']), inline=True)
        
        if self.selected_comic.get('volume_number'):
            embed.add_field(name="📚 Volume", value=str(self.selected_comic['volume_number']), inline=True)
        
        cv_id = self.selected_comic.get('comicvine_id')
        if cv_id:
            embed.add_field(
                name="🔗 ComicVine ID",
                value=f"[{cv_id}](https://comicvine.gamespot.com/volume/4050-{cv_id}/)",
                inline=False
            )
        
        already_added = self.selected_comic.get('already_added', 0)
        if already_added is None:
            already_added = 0
            
        if already_added > 0:
            embed.add_field(
                name="⚠️ Warning",
                value=f"This comic is already in your library with {already_added} issues!",
                inline=False
            )
        
        description = self.selected_comic.get('description')
        if description:
            clean_description = self.kapowarr_client.clean_html(description)
            if clean_description and clean_description != "No description available.":
                if len(clean_description) > 500:
                    clean_description = clean_description[:497] + "..."
                embed.add_field(name="📝 Description", value=clean_description, inline=False)
        
        cover_url = self.selected_comic.get('cover_link')
        if cover_url:
            embed.set_thumbnail(url=cover_url)
        
        embed.add_field(
            name="❓ Confirmation",
            value="Click **Add to Kapowarr** to add this comic and search for downloads, or **Cancel** to abort.",
            inline=False
        )
        
        embed.set_footer(text="Kapowarr Comic Manager")
        
        return embed