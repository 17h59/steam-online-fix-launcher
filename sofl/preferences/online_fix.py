"""Секция настроек Online-Fix."""

from __future__ import annotations

from typing import Any

from gettext import gettext as _

from gettext import gettext as _

from gi.repository import Adw, Gio, Gtk, GLib

from sofl import shared


class OnlineFixSectionMixin:
    def _init_online_fix_section(self) -> None:
        self.setup_online_fix_settings()

    def setup_online_fix_settings(self) -> None:
        from pathlib import Path
        try:
            current_path = shared.schema.get_string("online-fix-install-path")
        except GLib.Error:
            default_path = str(Path(shared.home) / "Games" / "Online-Fix")
            shared.schema.set_string("online-fix-install-path", default_path)
            current_path = default_path

        self.online_fix_entry_row.set_text(current_path)
        self.online_fix_entry_row.connect("changed", self._online_fix_path_changed)
        self.online_fix_file_chooser_button.connect(
            "clicked", self.online_fix_path_browse_handler
        )

        default_steam_home = str(Path.home() / ".local/share/Steam")
        try:
            steam_home_override = shared.schema.get_string("online-fix-steam-home").strip()
        except GLib.Error:
            steam_home_override = ""
            shared.schema.set_string("online-fix-steam-home", steam_home_override)

        self.online_fix_steam_home_entry_row.set_text(steam_home_override)
        if hasattr(self.online_fix_steam_home_entry_row, "set_placeholder_text"):
            self.online_fix_steam_home_entry_row.set_placeholder_text(default_steam_home)
        if hasattr(self.online_fix_steam_home_entry_row, "set_subtitle"):
            self.online_fix_steam_home_entry_row.set_subtitle(_("Path to your Steam installation directory"))

        self.online_fix_steam_home_entry_row.connect(
            "changed", self.on_steam_home_changed
        )
        self.online_fix_steam_home_button.connect(
            "clicked", self.online_fix_steam_home_browse_handler
        )

        default_prefix_path = self._get_default_prefix_path()
        try:
            prefix_override = shared.schema.get_string("online-fix-prefix-path").strip()
        except GLib.Error:
            prefix_override = ""
            shared.schema.set_string("online-fix-prefix-path", prefix_override)

        self.online_fix_prefix_entry_row.set_text(prefix_override)
        if hasattr(self.online_fix_prefix_entry_row, "set_placeholder_text"):
            self.online_fix_prefix_entry_row.set_placeholder_text(default_prefix_path)
        if hasattr(self.online_fix_prefix_entry_row, "set_subtitle"):
            self.online_fix_prefix_entry_row.set_subtitle(_("Single Wine prefix used for all Online-Fix games"))

        self.online_fix_prefix_entry_row.connect(
            "changed", self.on_prefix_path_changed
        )
        self.online_fix_prefix_button.connect(
            "clicked", self.online_fix_prefix_browse_handler
        )

        self._setup_dependency_switches()

        self.setup_proton_combo(
            self.online_fix_proton_combo,
            self.get_proton_versions(),
            "online-fix-proton-version",
        )

        shared.schema.bind(
            "online-fix-auto-patch",
            self.online_fix_auto_patch_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.online_fix_auto_patch_switch.connect(
            "notify::active", self.on_auto_patch_changed
        )

        self.online_fix_dll_override_entry.set_text(
            shared.schema.get_string("online-fix-dll-overrides")
        )
        self.online_fix_dll_override_entry.connect(
            "changed", self.on_dll_overrides_changed
        )

        shared.schema.bind(
            "online-fix-steam-appid-patch",
            self.online_fix_steam_appid_switch,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )

        shared.schema.bind(
            "online-fix-steamfix64-patch",
            self.online_fix_patch_steam_fix_64,
            "active",
            Gio.SettingsBindFlags.DEFAULT,
        )

        self.on_auto_patch_changed(self.online_fix_auto_patch_switch, None)

    def _online_fix_path_changed(self, *_args: Any) -> None:
        shared.schema.set_string(
            "online-fix-install-path", self.online_fix_entry_row.get_text()
        )

    def on_auto_patch_changed(self, switch: Adw.SwitchRow, _param: Any) -> None:
        is_auto = switch.get_active()
        self.online_fix_patches_group.set_visible(not is_auto)

    def on_dll_overrides_changed(self, entry: Adw.EntryRow) -> None:
        shared.schema.set_string("online-fix-dll-overrides", entry.get_text())

    def online_fix_path_browse_handler(self, *_args: Any) -> None:
        from pathlib import Path
        from gi.repository import GLib

        def set_online_fix_dir(_widget: Any, result: Gio.Task) -> None:
            try:
                path = Path(self.file_chooser.select_folder_finish(result).get_path())
                shared.schema.set_string("online-fix-install-path", str(path))
                self.online_fix_entry_row.set_text(str(path))
            except GLib.Error as error:
                import logging

                logging.debug(
                    "Error selecting folder for Online-Fix: %s", error
                )

        self.file_chooser.select_folder(shared.win, None, set_online_fix_dir)

    def on_steam_home_changed(self, entry: Adw.EntryRow) -> None:
        shared.schema.set_string("online-fix-steam-home", entry.get_text().strip())

    def online_fix_steam_home_browse_handler(self, *_args: Any) -> None:
        from pathlib import Path
        from gi.repository import GLib

        def set_steam_home_dir(_widget: Any, result: Gio.Task) -> None:
            try:
                path = Path(self.file_chooser.select_folder_finish(result).get_path())
                shared.schema.set_string("online-fix-steam-home", str(path))
                self.online_fix_steam_home_entry_row.set_text(str(path))
            except GLib.Error as error:
                import logging

                logging.debug("Error selecting folder for Steam: %s", error)

        self.file_chooser.select_folder(shared.win, None, set_steam_home_dir)

    def on_prefix_path_changed(self, entry: Adw.EntryRow) -> None:
        shared.schema.set_string("online-fix-prefix-path", entry.get_text().strip())

    def online_fix_prefix_browse_handler(self, *_args: Any) -> None:
        from pathlib import Path
        from gi.repository import GLib

        def set_prefix_dir(_widget: Any, result: Gio.Task) -> None:
            try:
                path = Path(self.file_chooser.select_folder_finish(result).get_path())
                shared.schema.set_string("online-fix-prefix-path", str(path))
                self.online_fix_prefix_entry_row.set_text(str(path))
            except GLib.Error as error:
                import logging

                logging.debug("Error selecting folder for Wine prefix: %s", error)

        self.file_chooser.select_folder(shared.win, None, set_prefix_dir)

    def _get_default_prefix_path(self) -> str:
        """Default shared Wine prefix path."""
        import os
        from pathlib import Path

        in_flatpak = os.path.exists("/.flatpak-info")
        if in_flatpak:
            return str(
                Path(shared.home)
                / ".var"
                / "app"
                / "org.badkiko.sofl"
                / "data"
                / "wine-prefixes"
                / "onlinefix"
            )

        return str(Path.home() / ".local/share/OnlineFix/prefix")

    def _setup_dependency_switches(self) -> None:
        dependency_switches: dict[str, Gtk.Switch] = {
            "vcredist_x64": self.online_fix_dep_vcredist_x64_switch,
            "vcredist_x86": self.online_fix_dep_vcredist_x86_switch,
        }

        try:
            enabled_deps = set(shared.schema.get_strv("online-fix-dependencies"))
        except GLib.Error:
            enabled_deps = set()

        for dep_id, switch in dependency_switches.items():
            switch.set_active(dep_id in enabled_deps)

        for dep_id, switch in dependency_switches.items():
            switch.connect(
                "notify::active",
                lambda sw, _param, dep=dep_id: self._on_dependency_switch_toggled(
                    dep, sw.get_active()
                ),
            )

    def _on_dependency_switch_toggled(self, dep_id: str, enabled: bool) -> None:
        try:
            dependencies = set(shared.schema.get_strv("online-fix-dependencies"))
        except GLib.Error:
            dependencies = set()

        if enabled:
            dependencies.add(dep_id)
        else:
            dependencies.discard(dep_id)

        shared.schema.set_strv("online-fix-dependencies", sorted(dependencies))


