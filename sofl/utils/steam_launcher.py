# steam_launcher.py
#
# Copyright 2023-2024 badkiko
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import subprocess
import logging
import shlex
from pathlib import Path
from typing import Dict, List, Optional

from sofl import shared


class SteamLauncher:
    """Utilities for launching games through Steam API"""

    @staticmethod
    def check_steam_running(in_flatpak: bool = False) -> bool:
        """Checks if Steam is running"""
        try:
            if in_flatpak:
                result = subprocess.run(
                    ["flatpak-spawn", "--host", "pgrep", "-x", "steam"],
                    capture_output=True,
                    text=True,
                )
            else:
                result = subprocess.run(
                    ["pgrep", "-x", "steam"], capture_output=True, text=True
                )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception as e:
            logging.error(f"[SOFL] Failed to check Steam status: {str(e)}")
            return False

    @staticmethod
    def get_host_home(in_flatpak: bool = False) -> str:
        """Gets host home directory"""
        if not in_flatpak:
            return os.path.expanduser("~")

        try:
            result = subprocess.run(
                ["flatpak-spawn", "--host", "printenv", "HOME"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logging.error(f"[SOFL] Failed to get host home: {e}")

        return os.path.expanduser("~")

    @staticmethod
    def resolve_steam_home(host_home: str, in_flatpak: bool = False) -> str:
        """Resolve Steam installation path, honoring user overrides."""
        try:
            custom_path = shared.schema.get_string("online-fix-steam-home").strip()
        except Exception:
            custom_path = ""

        if custom_path:
            expanded = os.path.expanduser(custom_path)
            if not os.path.isabs(expanded):
                base_home = host_home or os.path.expanduser("~")
                expanded = os.path.abspath(os.path.join(base_home, expanded))
            return expanded

        if host_home:
            return os.path.join(host_home, ".local/share/Steam")

        # Fallback to effective home directory in the current environment
        return os.path.join(os.path.expanduser("~"), ".local/share/Steam")

    @staticmethod
    def check_proton_exists(proton_version: str, steam_home: str, in_flatpak: bool = False) -> bool:
        """Checks Proton version existence"""
        proton_path = os.path.join(
            steam_home, "compatibilitytools.d", proton_version, "proton"
        )

        try:
            return SteamLauncher._check_path_exists(proton_path, in_flatpak)
        except Exception:
            return False

    @staticmethod
    def _check_path_exists(path: str, in_flatpak: bool = False) -> bool:
        """Checks path existence (file or directory)."""
        if not path:
            return False

        try:
            if in_flatpak:
                result = subprocess.run(
                    ["flatpak-spawn", "--host", "test", "-e", path],
                    capture_output=True,
                )
                return result.returncode == 0

            return os.path.exists(path)
        except Exception:
            return False

    @staticmethod
    def _check_file_exists(file_path: str, in_flatpak: bool = False) -> bool:
        """Checks file existence"""
        try:
            if in_flatpak:
                result = subprocess.run(
                    ["flatpak-spawn", "--host", "test", "-f", file_path],
                    capture_output=True,
                )
                return result.returncode == 0
            else:
                return os.path.isfile(file_path)
        except Exception:
            return False

    @staticmethod
    def check_steam_installed(steam_home: str, in_flatpak: bool = False) -> bool:
        """Check whether Steam appears to be installed at the given location."""
        if not SteamLauncher._check_path_exists(steam_home, in_flatpak):
            return False

        candidate_paths = [
            os.path.join(steam_home, "steam.sh"),
            os.path.join(steam_home, "steam"),
            os.path.join(steam_home, "ubuntu12_32", "steam"),
            os.path.join(steam_home, "steamapps"),
        ]

        for candidate in candidate_paths:
            if SteamLauncher._check_path_exists(candidate, in_flatpak):
                return True

        return False

    @staticmethod
    def prepare_environment(prefix_path: str, user_home: str, steam_home: str) -> Dict[str, str]:
        """Prepares environment variables for launch"""
        dll_overrides = shared.schema.get_string("online-fix-dll-overrides")
        debug_mode = shared.schema.get_boolean("online-fix-debug-mode")

        default_library_path = os.path.join(user_home, ".local/share/Steam")
        library_path = steam_home or default_library_path
        client_path = steam_home or os.path.join(user_home, ".steam/steam")

        # Base environment variables
        env = {
            "WINEDLLOVERRIDES": f"d3d11=n;d3d10=n;d3d10core=n;dxgi=n;openvr_api_dxvk=n;d3d12=n;d3d12core=n;d3d9=n;d3d8=n;{dll_overrides}",
            "WINEDEBUG": "+warn,+err,+trace" if debug_mode else "-all",
            "STEAM_COMPAT_DATA_PATH": prefix_path,
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": client_path,
        }

        # Add Steam Overlay if enabled
        use_steam_overlay = shared.schema.get_boolean("online-fix-use-steam-overlay")
        if use_steam_overlay:
            existing_preload = env.get("LD_PRELOAD", "")
            new_preload_paths = f"{library_path}/ubuntu12_32/gameoverlayrenderer.so:{library_path}/ubuntu12_64/gameoverlayrenderer.so"

            preload_parts = [part for part in [existing_preload, new_preload_paths] if part]
            env["LD_PRELOAD"] = ":".join(preload_parts)

        return env

    @staticmethod
    def build_launch_command(
        proton_path: str,
        game_exec: str,
        steam_runtime_path: Optional[str] = None,
        args_before: Optional[str] = None,
        args_after: Optional[str] = None,
    ) -> List[str]:
        """Builds game launch command"""
        cmd_argv = [proton_path, "run", game_exec]

        if steam_runtime_path:
            cmd_argv.insert(0, steam_runtime_path)

        # Safely add arguments
        if args_before:
            try:
                args_before_list = shlex.split(args_before)
                cmd_argv = args_before_list + cmd_argv
            except ValueError as e:
                logging.warning(f"[SOFL] Failed to parse args_before '{args_before}': {e}")

        if args_after:
            try:
                args_after_list = shlex.split(args_after)
                cmd_argv.extend(args_after_list)
            except ValueError as e:
                logging.warning(f"[SOFL] Failed to parse args_after '{args_after}': {e}")

        return cmd_argv

    @staticmethod
    def launch_game(cmd_argv: List[str], env: Dict[str, str], game_dir: Path, in_flatpak: bool = False) -> None:
        """Launches game in appropriate environment"""
        if in_flatpak:
            # In Flatpak use flatpak-spawn
            env_args = []
            for key, value in env.items():
                str_value = str(value) if value is not None else ""
                if str_value.strip():
                    env_args.append(f"--env={key}={str_value}")

            full_cmd = ["flatpak-spawn", "--host"] + env_args + cmd_argv

            # Add directory change
            if game_dir:
                full_cmd = ["sh", "-c", f"cd {shlex.quote(str(game_dir))} && exec \"$@\"", "sh"] + full_cmd

            logging.info(f"[SOFL] Executing command via flatpak-spawn: {' '.join(shlex.quote(str(arg)) for arg in full_cmd)}")
            subprocess.Popen(full_cmd, start_new_session=True)
        else:
            # In native environment launch directly
            logging.info(f"[SOFL] Executing command: {' '.join(shlex.quote(str(arg)) for arg in cmd_argv)}")
            subprocess.Popen(cmd_argv, cwd=str(game_dir), env={**os.environ, **env}, start_new_session=True)

    @staticmethod
    def launch_game_with_tracking(cmd_argv: List[str], env: Dict[str, str], game_dir: Path, in_flatpak: bool = False):
        """Launches game in appropriate environment and returns process for tracking"""
        if in_flatpak:
            # In Flatpak use flatpak-spawn
            env_args = []
            for key, value in env.items():
                str_value = str(value) if value is not None else ""
                if str_value.strip():
                    env_args.append(f"--env={key}={str_value}")

            full_cmd = ["flatpak-spawn", "--host"] + env_args + cmd_argv

            # Add directory change
            if game_dir:
                full_cmd = ["sh", "-c", f"cd {shlex.quote(str(game_dir))} && exec \"$@\"", "sh"] + full_cmd

            logging.info(f"[SOFL] Executing command via flatpak-spawn: {' '.join(shlex.quote(str(arg)) for arg in full_cmd)}")
            return subprocess.Popen(full_cmd, start_new_session=True)
        else:
            # In native environment launch directly
            logging.info(f"[SOFL] Executing command: {' '.join(shlex.quote(str(arg)) for arg in cmd_argv)}")
            return subprocess.Popen(cmd_argv, cwd=str(game_dir), env={**os.environ, **env}, start_new_session=True)
