"""Секция настройки импортируемых источников."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from sys import platform
from typing import Iterable

from gi.repository import Gio, Gtk

from sofl import shared
from sofl.importer.location import UnresolvableLocationError
from sofl.importer.source import Source
from sofl.utils.create_dialog import create_dialog


class ImportSourcesSection:
    """Логика страницы импортируемых источников."""

    def __init__(self, dialog: "SOFLPreferences") -> None:
        self.dialog = dialog

        from sofl.importer.bottles_source import BottlesSource
        from sofl.importer.desktop_source import DesktopSource
        from sofl.importer.flatpak_source import FlatpakSource
        from sofl.importer.heroic_source import HeroicSource
        from sofl.importer.itch_source import ItchSource
        from sofl.importer.legendary_source import LegendarySource
        from sofl.importer.lutris_source import LutrisSource
        from sofl.importer.retroarch_source import RetroarchSource
        from sofl.importer.steam_source import SteamSource

        for source_class in (
            BottlesSource,
            FlatpakSource,
            HeroicSource,
            ItchSource,
            LegendarySource,
            LutrisSource,
            RetroarchSource,
            SteamSource,
        ):
            source = source_class()
            if not source.is_available:
                expander_row = getattr(dialog, f"{source.source_id}_expander_row")
                expander_row.set_visible(False)
            else:
                self.init_source_row(source)

        if not DesktopSource().is_available:
            dialog.desktop_switch.set_visible(False)

        dialog.bind_switches(
            {
                "auto-import",
                "remove-missing",
                "lutris-import-steam",
                "lutris-import-flatpak",
                "heroic-import-epic",
                "heroic-import-gog",
                "heroic-import-amazon",
                "heroic-import-sideload",
                "flatpak-import-launchers",
                "desktop",
            }
        )

    def init_source_row(self, source: Source) -> None:
        dialog = self.dialog

        expander_row = getattr(dialog, f"{source.source_id}_expander_row")
        shared.schema.bind(
            source.source_id,
            expander_row,
            "enable-expansion",
            Gio.SettingsBindFlags.DEFAULT,
        )

        for location_name in source.locations._asdict():
            button = getattr(
                dialog, f"{source.source_id}_{location_name}_file_chooser_button", None
            )
            if button is not None:
                button.connect(
                    "clicked",
                    dialog.choose_folder,
                    self._make_set_dir_callback(source),
                    location_name,
                )

        dialog.resolve_locations(source)
        dialog.update_source_action_row_paths(source)

    def _make_set_dir_callback(self, source: Source):
        dialog = self.dialog

        def set_dir(_widget, result, location_name: str) -> None:
            try:
                path = Path(dialog.file_chooser.select_folder_finish(result).get_path())
            except Gtk.GError as error:
                logging.error("Error selecting directory: %s", error)
                return

            location = source.locations._asdict()[location_name]
            if location.check_candidate(path):
                shared.schema.set_string(location.schema_key, str(path))
                dialog.update_source_action_row_paths(source)
                if dialog.warning_menu_buttons.get(source.source_id):
                    action_row = getattr(
                        dialog, f"{source.source_id}_{location_name}_action_row", None
                    )
                    action_row.remove(dialog.warning_menu_buttons[source.source_id])
                    dialog.warning_menu_buttons.pop(source.source_id)
            else:
                dialog = self.dialog

                dlg = create_dialog(
                    dialog,
                    _("Invalid Directory"),
                    location.invalid_subtitle.format(source.name),
                    "choose_folder",
                    _("Set Location"),
                )

                def on_response(widget, response: str) -> None:
                    if response == "choose_folder":
                        dialog.choose_folder(widget, set_dir, location_name)

                dlg.connect("response", on_response)

        return set_dir

    def update_source_action_row_paths(self, source: Source) -> None:
        dialog = self.dialog

        for location_name, location in source.locations._asdict().items():
            action_row = getattr(
                dialog, f"{source.source_id}_{location_name}_action_row", None
            )
            if not action_row:
                continue

            subtitle = str(Path(shared.schema.get_string(location.schema_key)))

            if platform == "linux":
                subtitle = re.sub("/run/user/\\d*/doc/.*/", "", subtitle)
                subtitle = re.sub(f"^{str(shared.home)}", "~", subtitle)

            action_row.set_subtitle(subtitle)

    def resolve_locations(self, source: Source) -> None:
        dialog = self.dialog

        for location_name, location in source.locations._asdict().items():
            action_row = getattr(
                dialog, f"{source.source_id}_{location_name}_action_row", None
            )
            if not action_row:
                continue

            try:
                location.resolve()
            except UnresolvableLocationError:
                title = _("Installation Not Found")
                description = _("Select a valid directory")

                popover = Gtk.Popover(
                    focusable=True,
                    child=Gtk.Label(
                        label=f'<span rise="12pt"><b><big>{title}</big></b></span>\n{description}',
                        use_markup=True,
                        wrap=True,
                        max_width_chars=50,
                        halign=Gtk.Align.CENTER,
                        valign=Gtk.Align.CENTER,
                        justify=Gtk.Justification.CENTER,
                        margin_top=9,
                        margin_bottom=9,
                        margin_start=12,
                        margin_end=12,
                    ),
                )

                popover.update_property(
                    (Gtk.AccessibleProperty.LABEL,), (title + description,)
                )

                def set_a11y_label(widget: Gtk.Popover) -> None:
                    dialog.set_focus(widget)

                popover.connect("show", set_a11y_label)

                menu_button = Gtk.MenuButton(
                    icon_name="dialog-warning-symbolic",
                    valign=Gtk.Align.CENTER,
                    popover=popover,
                    tooltip_text=_("Warning"),
                )
                menu_button.add_css_class("warning")

                action_row.add_prefix(menu_button)
                dialog.warning_menu_buttons[source.source_id] = menu_button


from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .dialog import SOFLPreferences


