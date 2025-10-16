# Simplified preferences.py with simple accordion design for Proton Manager

import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional

from gi.repository import Adw, Gio, GLib, Gtk

from sofl.proton.proton_manager import ProtonManager


class SOFLPreferences(Adw.PreferencesWindow):
    """Preferences window for SOFL application"""

    __gtype_name__ = "SOFLPreferences"

    # Template children
    online_fix_proton_combo: Adw.ComboRow = Gtk.Template.Child()
    proton_page: Adw.PreferencesPage = Gtk.Template.Child()
    proton_manager_group: Adw.PreferencesGroup = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize Proton Manager
        self.proton_manager_instance = ProtonManager()
        self.setup_proton_manager_ui()
        self.refresh_proton_versions()

    def setup_proton_manager_ui(self) -> None:
        """Setup Proton Manager UI with simple accordion design"""
        # Create installed versions accordion
        self.proton_installed_expander = Adw.ExpanderRow()
        self.proton_installed_expander.set_title(_("Installed Versions"))
        self.proton_installed_expander.set_subtitle(_("Manage your downloaded Proton versions"))
        
        # Create available versions accordion
        self.proton_available_expander = Adw.ExpanderRow()
        self.proton_available_expander.set_title(_("Available Versions"))
        self.proton_available_expander.set_subtitle(_("Download the latest GE-Proton releases from GitHub"))
        
        # Add accordions to the group
        self.proton_manager_group.add(self.proton_installed_expander)
        self.proton_manager_group.add(self.proton_available_expander)
        
        # Store references to current children for proper cleanup
        self.proton_installed_children = []
        self.proton_available_children = []

    def refresh_proton_versions(self) -> None:
        """Refresh both installed and available Proton versions"""
        self.refresh_installed_versions()
        self.refresh_available_versions()

    def refresh_installed_versions(self) -> None:
        """Refresh the list of installed Proton versions"""
        try:
            logging.info("[Preferences] Refreshing installed Proton versions...")
            installed_versions = self.proton_manager_instance.get_installed_versions()
            logging.info(f"[Preferences] Found {len(installed_versions)} installed versions: {installed_versions}")
            
            # Clear existing children from installed accordion
            for child in self.proton_installed_children:
                self.proton_installed_expander.remove(child)
            self.proton_installed_children.clear()
            
            if not installed_versions:
                # Show simple empty state
                empty_label = Gtk.Label()
                empty_label.set_text(_("No Proton versions installed"))
                empty_label.set_css_classes(["dim-label"])
                empty_label.set_margin_top(12)
                empty_label.set_margin_bottom(12)
                empty_label.set_margin_start(12)
                empty_label.set_margin_end(12)
                
                self.proton_installed_expander.add_row(empty_label)
                self.proton_installed_children.append(empty_label)
                return
            
            # Add each installed version
            for version in installed_versions:
                logging.info(f"[Preferences] Creating row for installed version: {version}")
                row = self.create_installed_version_row(version)
                self.proton_installed_expander.add_row(row)
                self.proton_installed_children.append(row)
                
        except Exception as e:
            logging.error(f"[Preferences] Error refreshing installed versions: {e}")

    def create_installed_version_row(self, version: str) -> Adw.ActionRow:
        """Create a simple row for an installed Proton version"""
        row = Adw.ActionRow()
        row.set_title(version)
        row.set_subtitle(_("Installed"))
        
        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name("user-trash-symbolic")
        delete_button.set_tooltip_text(_("Delete this version"))
        delete_button.set_css_classes(["destructive-action", "circular"])
        delete_button.connect("clicked", self.on_delete_proton_version, version)
        
        row.add_suffix(delete_button)
        return row

    def refresh_available_versions(self) -> None:
        """Refresh the list of available Proton versions"""
        try:
            logging.info("[Preferences] Refreshing available Proton versions...")
            
            # Clear existing children from available accordion
            for child in self.proton_available_children:
                self.proton_available_expander.remove(child)
            self.proton_available_children.clear()
            
            # Show loading state
            loading_label = Gtk.Label()
            loading_label.set_text(_("Loading available versions..."))
            loading_label.set_css_classes(["dim-label"])
            loading_label.set_margin_top(12)
            loading_label.set_margin_bottom(12)
            loading_label.set_margin_start(12)
            loading_label.set_margin_end(12)
            
            self.proton_available_expander.add_row(loading_label)
            self.proton_available_children.append(loading_label)
            
            # Fetch available versions in a separate thread
            def fetch_versions():
                try:
                    versions = self.proton_manager_instance.get_available_versions()
                    GLib.idle_add(self.on_available_versions_loaded, versions)
                except Exception as e:
                    logging.error(f"[Preferences] Error fetching available versions: {e}")
                    GLib.idle_add(self.on_available_versions_error, str(e))
            
            thread = threading.Thread(target=fetch_versions, daemon=True)
            thread.start()
            
        except Exception as e:
            logging.error(f"[Preferences] Error refreshing available versions: {e}")

    def on_available_versions_loaded(self, versions: list) -> None:
        """Handle successful loading of available versions"""
        try:
            logging.info(f"[Preferences] Found {len(versions)} available versions")
            
            # Clear loading state
            for child in self.proton_available_children:
                self.proton_available_expander.remove(child)
            self.proton_available_children.clear()
            
            if not versions:
                # Show empty state
                empty_label = Gtk.Label()
                empty_label.set_text(_("No versions available"))
                empty_label.set_css_classes(["dim-label"])
                empty_label.set_margin_top(12)
                empty_label.set_margin_bottom(12)
                empty_label.set_margin_start(12)
                empty_label.set_margin_end(12)
                
                self.proton_available_expander.add_row(empty_label)
                self.proton_available_children.append(empty_label)
                return
            
            # Add each available version
            for version_info in versions:
                logging.info(f"[Preferences] Creating row for version: {version_info.get('tag_name', 'unknown')}")
                row = self.create_available_version_row(version_info)
                self.proton_available_expander.add_row(row)
                self.proton_available_children.append(row)
                
        except Exception as e:
            logging.error(f"[Preferences] Error handling loaded versions: {e}")

    def on_available_versions_error(self, error: str) -> None:
        """Handle error loading available versions"""
        try:
            logging.error(f"[Preferences] Error loading available versions: {error}")
            
            # Clear loading state
            for child in self.proton_available_children:
                self.proton_available_expander.remove(child)
            self.proton_available_children.clear()
            
            # Show error state
            error_label = Gtk.Label()
            error_label.set_text(_("Failed to load versions. Check your internet connection."))
            error_label.set_css_classes(["dim-label"])
            error_label.set_margin_top(12)
            error_label.set_margin_bottom(12)
            error_label.set_margin_start(12)
            error_label.set_margin_end(12)
            
            self.proton_available_expander.add_row(error_label)
            self.proton_available_children.append(error_label)
            
        except Exception as e:
            logging.error(f"[Preferences] Error handling version load error: {e}")

    def create_available_version_row(self, version_info: dict) -> Adw.ActionRow:
        """Create a simple row for an available Proton version"""
        row = Adw.ActionRow()
        tag_name = version_info.get("tag_name", "Unknown")
        name = version_info.get("name", tag_name)
        row.set_title(name)
        
        # Create subtitle with size and date
        size_bytes = version_info.get("size", 0)
        published_at = version_info.get("published_at", "")
        
        subtitle_parts = []
        if size_bytes > 0:
            size_mb = size_bytes / (1024 * 1024)
            subtitle_parts.append(_("Size: {:.1f} MB").format(size_mb))
        
        if published_at:
            try:
                from datetime import datetime
                date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime("%b %d, %Y")
                subtitle_parts.append(_("Released: {}").format(formatted_date))
            except:
                pass
        
        subtitle = " • ".join(subtitle_parts) if subtitle_parts else _("Available for download")
        row.set_subtitle(subtitle)
        
        # Simple download button
        download_button = Gtk.Button()
        download_button.set_icon_name("download-symbolic")
        download_button.set_tooltip_text(_("Download and install this version"))
        download_button.set_css_classes(["suggested-action", "circular"])
        download_button.connect("clicked", self.on_download_proton_version, version_info)
        
        row.add_suffix(download_button)
        return row

    def on_delete_proton_version(self, button: Gtk.Button, version: str) -> None:
        """Handle delete Proton version button click"""
        dialog = Adw.MessageDialog()
        parent_window = self.get_root()
        if isinstance(parent_window, Gtk.Window):
            dialog.set_transient_for(parent_window)
        dialog.set_heading(_("Delete Proton Version"))
        dialog.set_body(_("Are you sure you want to delete <b>{}</b>? This action cannot be undone.").format(version))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.connect("response", self.handle_delete_response, version)
        dialog.present()

    def handle_delete_response(self, dialog: Adw.MessageDialog, response: str, version: str) -> None:
        """Handle delete confirmation dialog response"""
        if response == "delete":
            try:
                self.proton_manager_instance.delete_version(version)
                self.add_toast(Adw.Toast.new(_("Version {} deleted successfully").format(version)))
                self.refresh_installed_versions()
                self.update_proton_combo()
            except Exception as e:
                logging.error(f"[Preferences] Error deleting version {version}: {e}")
                self.add_toast(Adw.Toast.new(_("Failed to delete version")))
        dialog.destroy()

    def on_download_proton_version(self, button: Gtk.Button, version_info: dict) -> None:
        """Handle download Proton version button click"""
        try:
            # Disable button and show loading state
            button.set_sensitive(False)
            button.set_icon_name("process-working-symbolic")
            
            # Start download in separate thread
            def download_thread():
                try:
                    tag_name = version_info.get("tag_name", "")
                    self.proton_manager_instance.download_version(tag_name, self.on_download_progress)
                    GLib.idle_add(self.on_download_complete, version_info)
                except Exception as e:
                    logging.error(f"[Preferences] Error downloading version: {e}")
                    GLib.idle_add(self.on_download_error, version_info, str(e))
            
            thread = threading.Thread(target=download_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            logging.error(f"[Preferences] Error starting download: {e}")
            self.add_toast(Adw.Toast.new(_("Failed to start download")))

    def on_download_progress(self, progress: float, status: str) -> None:
        """Handle download progress updates"""
        # This could be used to update a progress bar if needed
        pass

    def on_download_complete(self, version_info: dict) -> None:
        """Handle successful download completion"""
        try:
            tag_name = version_info.get("tag_name", "Unknown")
            self.add_toast(Adw.Toast.new(_("Version {} downloaded successfully").format(tag_name)))
            self.refresh_installed_versions()
            self.update_proton_combo()
        except Exception as e:
            logging.error(f"[Preferences] Error handling download completion: {e}")

    def on_download_error(self, version_info: dict, error: str) -> None:
        """Handle download error"""
        try:
            tag_name = version_info.get("tag_name", "Unknown")
            logging.error(f"[Preferences] Download error for {tag_name}: {error}")
            self.add_toast(Adw.Toast.new(_("Failed to download version")))
        except Exception as e:
            logging.error(f"[Preferences] Error handling download error: {e}")

    def update_proton_combo(self) -> None:
        """Update the proton combo box with current versions"""
        try:
            if hasattr(self, 'proton_manager_instance'):
                versions = self.proton_manager_instance.get_installed_versions()
                # Update the combo box model here if needed
        except Exception as e:
            logging.error(f"[Preferences] Error updating proton combo: {e}")

    def get_proton_versions(self) -> list:
        """Get list of available Proton versions"""
        if hasattr(self, 'proton_manager_instance'):
            return self.proton_manager_instance.get_installed_versions()
        return []
