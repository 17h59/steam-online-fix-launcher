"""Общая секция диалога настроек."""

from __future__ import annotations

from typing import Any

from gi.repository import Adw, Gio

from sofl import shared
from sofl.game import Game


class GeneralSection:
    """Логика общей страницы настроек и действий над библиотекой."""

    def __init__(self, dialog: "SOFLPreferences") -> None:
        self.dialog = dialog

        dialog.remove_all_games_button_row.connect("activated", self.remove_all_games)

        theme = shared.schema.get_string("force-theme")
        dialog.force_theme_switch.set_active(theme == "dark")
        dialog.force_theme_switch.connect("notify::active", self.on_theme_switch)

        self.bind_switches(
            {
                "exit-after-launch",
                "cover-launches-game",
                "high-quality-images",
            }
        )

        if shared.PROFILE == "development":
            dialog.reset_button_row.set_visible(True)
            dialog.reset_button_row.connect("activated", self.reset_app)

    def bind_switches(self, settings: set[str]) -> None:
        for setting in settings:
            shared.schema.bind(
                setting,
                getattr(self.dialog, f"{setting.replace('-', '_')}_switch"),
                "active",
                Gio.SettingsBindFlags.DEFAULT,
            )

    def on_theme_switch(self, row: Adw.SwitchRow, _param: Any) -> None:
        from gi.repository import Adw as AdwLib

        shared.schema.set_string(
            "force-theme", "dark" if row.get_active() else "light"
        )
        style_manager = AdwLib.StyleManager.get_default()
        style_manager.set_color_scheme(
            AdwLib.ColorScheme.FORCE_DARK
            if row.get_active()
            else AdwLib.ColorScheme.FORCE_LIGHT
        )

    def undo_remove_all(self, *_args: Any) -> bool:
        dialog = self.dialog

        shared.win.get_application().state = shared.AppState.UNDO_REMOVE_ALL_GAMES
        for game in dialog.removed_games:
            game.removed = False
            game.save()
            game.update()

        dialog.removed_games = set()
        dialog.toast.dismiss()
        shared.win.get_application().state = shared.AppState.DEFAULT
        shared.win.create_source_rows()

        return True

    def remove_all_games(self, *_args: Any) -> None:
        dialog = self.dialog

        shared.win.get_application().state = shared.AppState.REMOVE_ALL_GAMES
        shared.win.row_selected(None, shared.win.all_games_row_box.get_parent())
        for game in shared.store:
            if not game.removed:
                dialog.removed_games.add(game)
                game.removed = True
                game.save()
                game.update()

        if shared.win.navigation_view.get_visible_page() == shared.win.details_page:
            shared.win.navigation_view.pop()

        dialog.add_toast(dialog.toast)
        shared.win.get_application().state = shared.AppState.DEFAULT
        shared.win.create_source_rows()

    def reset_app(self, *_args: Any) -> None:
        dialog = self.dialog

        dialog.cleanup_user_data()
        shared.win.get_application().quit()


# Импорт в конце, чтобы избежать циклической зависимости в типизации
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .dialog import SOFLPreferences


