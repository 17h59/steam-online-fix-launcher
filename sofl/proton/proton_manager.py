# proton_manager.py
#
# Copyright 2024 badkiko
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

import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Dict, Any
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError

from sofl import shared
from sofl.utils.steam_launcher import SteamLauncher


class ProtonManager:
    """Manager for Proton versions - download, install, and remove GE-Proton versions"""
    
    GITHUB_API_URL = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"
    MAX_AVAILABLE_VERSIONS = 10
    
    def __init__(self):
        self._cached_available_versions: Optional[List[Dict[str, Any]]] = None

    def _get_resolved_steam_home(self) -> Path:
        """Resolve the Steam installation directory, honoring user overrides."""
        in_flatpak = os.path.exists("/.flatpak-info")
        host_home = SteamLauncher.get_host_home(in_flatpak)
        resolved = SteamLauncher.resolve_steam_home(host_home, in_flatpak)
        return Path(resolved)
    
    def get_steam_compat_path(self) -> Path:
        """Get the correct path to compatibilitytools.d directory"""
        try:
            override = shared.schema.get_string("online-fix-steam-home").strip()
        except Exception:
            override = ""

        resolved_home = self._get_resolved_steam_home()
        compat_path = resolved_home / "compatibilitytools.d"

        if override:
            return compat_path

        if compat_path.exists():
            return compat_path

        in_flatpak = os.path.exists("/.flatpak-info")
        host_home = SteamLauncher.get_host_home(in_flatpak)

        candidates: List[Path] = []
        if host_home:
            host_base = Path(host_home)
            candidates.extend(
                [
                    host_base / ".local/share/Steam/compatibilitytools.d",
                    host_base / ".steam/root/compatibilitytools.d",
                    host_base / ".steam/steam/compatibilitytools.d",
                ]
            )

        sandbox_home = Path.home()
        candidates.extend(
            [
                sandbox_home / ".local/share/Steam/compatibilitytools.d",
                sandbox_home / ".steam/root/compatibilitytools.d",
                sandbox_home / ".steam/steam/compatibilitytools.d",
            ]
        )

        for path in candidates:
            if path.exists():
                return path

        return compat_path
    
    def get_installed_versions(self) -> List[str]:
        """Get list of installed Proton versions"""
        versions = []

        # Check compatibilitytools.d directories for GE-Proton (user and system)
        compat_paths = [
            self.get_steam_compat_path(),  # User path
            Path("/usr/share/steam/compatibilitytools.d")  # System path
        ]

        resolved_home = self._get_resolved_steam_home()

        for compat_path in compat_paths:
            if compat_path.exists():
                try:
                    for item in compat_path.iterdir():
                        if item.is_dir() and (
                            item.name.startswith("GE-Proton") or
                            item.name.startswith("Proton")
                        ):
                            # Check if it's a valid Proton installation
                            proton_script = item / "proton"
                            if proton_script.exists() and proton_script.is_file():
                                versions.append(item.name)
                except Exception as e:
                    logging.error(f"[ProtonManager] Error reading {compat_path}: {e}")
        
        # Also check Steam's common directory for standard Proton
        steam_common_candidates = [
            resolved_home / "steamapps/common",
            Path.home() / ".local/share/Steam/steamapps/common",
            Path.home() / ".steam/steam/steamapps/common",
        ]

        seen_common_paths: set[Path] = set()
        for common_path in steam_common_candidates:
            if common_path in seen_common_paths:
                continue
            seen_common_paths.add(common_path)
            if common_path.exists():
                try:
                    for item in common_path.iterdir():
                        if item.is_dir() and item.name.startswith("Proton"):
                            # Check if it's a valid Proton installation
                            proton_script = item / "proton"
                            if proton_script.exists() and proton_script.is_file():
                                versions.append(item.name)
                except Exception as e:
                    logging.error(f"[ProtonManager] Error reading {common_path}: {e}")
        
        # Remove duplicates and sort
        versions = list(set(versions))
        versions.sort(reverse=True)
        
        return versions
    
    def get_available_versions(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get list of available GE-Proton versions from GitHub"""
        if self._cached_available_versions and not force_refresh:
            return self._cached_available_versions
        
        try:
            with urlopen(self.GITHUB_API_URL) as response:
                data = json.loads(response.read().decode())
            
            versions = []
            for release in data[:self.MAX_AVAILABLE_VERSIONS]:
                # Find tar.gz asset
                tar_asset = None
                for asset in release.get("assets", []):
                    if asset["name"].endswith(".tar.gz"):
                        tar_asset = asset
                        break
                
                if tar_asset:
                    versions.append({
                        "tag_name": release["tag_name"],
                        "name": release["name"],
                        "published_at": release["published_at"],
                        "download_url": tar_asset["browser_download_url"],
                        "size": tar_asset["size"],
                        "download_count": tar_asset["download_count"]
                    })
            
            self._cached_available_versions = versions
            return versions
            
        except URLError as e:
            logging.error(f"[ProtonManager] Failed to fetch available versions: {e}")
            return []
        except Exception as e:
            logging.error(f"[ProtonManager] Error parsing available versions: {e}")
            return []
    
    def download_version(self, version_info: Dict[str, Any], progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """Download and install a Proton version"""
        tag_name = version_info.get('tag_name', 'Unknown')

        try:
            logging.info(f"[ProtonManager] Starting download for {tag_name}...")

            compat_path = self.get_steam_compat_path()
            compat_path.mkdir(parents=True, exist_ok=True)

            # Create temporary directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                tar_file = temp_path / f"{tag_name}.tar.gz"

                # Download with progress
                def download_progress(block_num, block_size, total_size):
                    if progress_callback and total_size > 0:
                        progress = (block_num * block_size) / total_size
                        progress_callback(min(progress, 1.0))

                logging.info(f"[ProtonManager] Downloading {tag_name}...")
                urlretrieve(version_info["download_url"], tar_file, download_progress)

                if progress_callback:
                    progress_callback(1.0)

                # Extract to compatibilitytools.d
                logging.info(f"[ProtonManager] Extracting {tag_name}...")
                with tarfile.open(tar_file, "r:gz") as tar:
                    tar.extractall(compat_path)

                logging.info(f"[ProtonManager] Successfully installed {tag_name}")
                return True

        except Exception as e:
            logging.error(f"[ProtonManager] Failed to download {tag_name}: {e}")
            return False
    
    def delete_version(self, version: str) -> bool:
        """Delete an installed Proton version"""
        try:
            # First try to delete from compatibilitytools.d (user installed versions)
            compat_path = self.get_steam_compat_path()
            version_path = compat_path / version

            if version_path.exists():
                shutil.rmtree(version_path)
                logging.info(f"[ProtonManager] Successfully deleted {version} from compatibilitytools.d")
                return True

            # If not found in compatibilitytools.d, try steamapps/common (official versions)
            resolved_home = self._get_resolved_steam_home()
            steam_common_candidates = [
                resolved_home / "steamapps/common",
                Path.home() / ".local/share/Steam/steamapps/common",
                Path.home() / ".steam/steam/steamapps/common",
            ]

            seen_common_paths: set[Path] = set()
            for common_path in steam_common_candidates:
                if common_path in seen_common_paths:
                    continue
                seen_common_paths.add(common_path)
                if common_path.exists():
                    version_path = common_path / version
                    if version_path.exists():
                        shutil.rmtree(version_path)
                        logging.info(f"[ProtonManager] Successfully deleted {version} from {common_path}")
                        return True

            # Version not found in any location
            logging.warning(f"[ProtonManager] Version {version} not found in any location")
            return False

        except Exception as e:
            logging.error(f"[ProtonManager] Failed to delete {version}: {e}")
            return False
    
    def check_proton_available(self) -> bool:
        """Check if at least one Proton version is available"""
        return len(self.get_installed_versions()) > 0
    
    def get_proton_path(self, version: str) -> Optional[Path]:
        """Get the path to a specific Proton version's proton script"""
        # Check compatibilitytools.d directories (user and system)
        compat_paths = [
            self.get_steam_compat_path(),  # User path
            Path("/usr/share/steam/compatibilitytools.d")  # System path
        ]

        for compat_path in compat_paths:
            proton_path = compat_path / version / "proton"
            if proton_path.exists() and proton_path.is_file():
                return proton_path

        # If not found in compatibilitytools.d, try steamapps/common (official versions)
        resolved_home = self._get_resolved_steam_home()
        steam_common_candidates = [
            resolved_home / "steamapps/common",
            Path.home() / ".local/share/Steam/steamapps/common",
            Path.home() / ".steam/steam/steamapps/common",
        ]

        seen_common_paths: set[Path] = set()
        for common_path in steam_common_candidates:
            if common_path in seen_common_paths:
                continue
            seen_common_paths.add(common_path)
            if common_path.exists():
                proton_path = common_path / version / "proton"
                if proton_path.exists() and proton_path.is_file():
                    return proton_path

        return None
    
    def check_proton_exists(self, version: str) -> bool:
        """Check if a specific Proton version exists and is valid"""
        return self.get_proton_path(version) is not None
    
    def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific version"""
        installed_versions = self.get_installed_versions()
        if version not in installed_versions:
            return None
        
        compat_path = self.get_steam_compat_path()
        version_path = compat_path / version
        
        try:
            # Get version from version file if it exists
            version_file = version_path / "version"
            version_text = ""
            if version_file.exists():
                version_text = version_file.read_text().strip()
            
            return {
                "name": version,
                "path": str(version_path),
                "version_text": version_text,
                "size": sum(f.stat().st_size for f in version_path.rglob('*') if f.is_file())
            }
        except Exception as e:
            logging.error(f"[ProtonManager] Error getting version info for {version}: {e}")
            return None

