"""Секция настроек Online-Fix."""

from __future__ import annotations

from typing import Any

from gi.repository import Adw, Gio

from sofl import shared


class OnlineFixSectionMixin:
    def _init_online_fix_section(self) -> None:
        self.setup_online_fix_settings()

    def setup_online_fix_settings(self) -> None:
        from pathlib import Path
        from gi.repository import GLib

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


