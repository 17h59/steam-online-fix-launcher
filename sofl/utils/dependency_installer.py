"""Utility for installing required Windows dependencies into the shared Wine prefix."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

from sofl import shared
from sofl.utils.steam_launcher import SteamLauncher


@dataclass(frozen=True)
class DependencyDefinition:
    """Metadata describing a dependency installer."""

    identifier: str
    name: str
    url: str
    installer_args: Tuple[str, ...] = ()
    expected_sha256: Optional[str] = None
    target_checks: Tuple[str, ...] = ()
    cache_name: Optional[str] = None


class DependencyInstaller:
    """Install Windows redistributables into the shared prefix."""

    _DEPENDENCIES: Dict[str, DependencyDefinition] = {
        "vcredist_x64": DependencyDefinition(
            identifier="vcredist_x64",
            name="Microsoft Visual C++ 2015-2022 Redistributable (x64)",
            url="https://aka.ms/vs/17/release/vc_redist.x64.exe",
            installer_args=("/quiet", "/norestart"),
            # vc runtime installs to system32
            target_checks=(
                os.path.join("pfx", "drive_c", "windows", "system32", "vcruntime140.dll"),
            ),
            cache_name="vc_redist.x64.exe",
        ),
        "vcredist_x86": DependencyDefinition(
            identifier="vcredist_x86",
            name="Microsoft Visual C++ 2015-2022 Redistributable (x86)",
            url="https://aka.ms/vs/17/release/vc_redist.x86.exe",
            installer_args=("/quiet", "/norestart"),
            target_checks=(
                os.path.join("pfx", "drive_c", "windows", "syswow64", "vcruntime140.dll"),
            ),
            cache_name="vc_redist.x86.exe",
        ),
    }

    def __init__(
        self,
        prefix_path: str,
        proton_path: str,
        steam_home: str,
        user_home: str,
        in_flatpak: bool,
    ) -> None:
        self.prefix_path = Path(prefix_path)
        self.proton_path = proton_path
        self.steam_home = steam_home
        self.user_home = user_home
        self.in_flatpak = in_flatpak
        self.cache_dir = Path(shared.cache_dir) / "online-fix" / "dependencies"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def available_dependencies(cls) -> Dict[str, DependencyDefinition]:
        return dict(cls._DEPENDENCIES)

    def install_selected(self, dependency_ids: Iterable[str]) -> Tuple[List[str], List[str]]:
        """Install a set of dependencies. Returns (installed, failed)."""
        installed: List[str] = []
        failed: List[str] = []

        for dep_id in dependency_ids:
            definition = self._DEPENDENCIES.get(dep_id)
            if not definition:
                logging.warning(f"[SOFL] Unknown dependency requested: {dep_id}")
                failed.append(dep_id)
                continue

            if self._is_dependency_installed(definition):
                logging.info(f"[SOFL] Dependency already present: {definition.name}")
                continue

            try:
                self._install_dependency(definition)
                if self._is_dependency_installed(definition):
                    installed.append(dep_id)
                else:
                    raise RuntimeError("Verification after install failed")
            except Exception as exc:  # pylint: disable=broad-except
                logging.error(
                    "[SOFL] Failed installing dependency %s: %s",
                    definition.identifier,
                    exc,
                )
                failed.append(dep_id)

        return installed, failed

    def _is_dependency_installed(self, definition: DependencyDefinition) -> bool:
        for relative_path in definition.target_checks:
            if not (self.prefix_path / relative_path).exists():
                return False
        return True

    def _install_dependency(self, definition: DependencyDefinition) -> None:
        installer_path = self._ensure_installer_downloaded(definition)
        env = SteamLauncher.prepare_environment(
            str(self.prefix_path), self.user_home, self.steam_home
        )

        cmd = [self.proton_path, "run", str(installer_path), *definition.installer_args]
        process = SteamLauncher.launch_game_with_tracking(
            cmd,
            env,
            self.prefix_path,
            self.in_flatpak,
        )

        if process is None:
            raise RuntimeError("Failed to spawn installer process")

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"Installer exited with code {return_code}")

    def _ensure_installer_downloaded(self, definition: DependencyDefinition) -> Path:
        cache_name = definition.cache_name or os.path.basename(definition.url)
        installer_path = self.cache_dir / cache_name

        if installer_path.exists():
            if self._verify_sha(installer_path, definition.expected_sha256):
                return installer_path
            installer_path.unlink(missing_ok=True)

        logging.info("[SOFL] Downloading dependency %s", definition.identifier)
        with tempfile.NamedTemporaryFile(dir=self.cache_dir, delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            try:
                self._download_to_file(definition.url, tmp_path)
                if not self._verify_sha(tmp_path, definition.expected_sha256):
                    raise RuntimeError("Checksum mismatch after download")
                tmp_path.replace(installer_path)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

        return installer_path

    def _download_to_file(self, url: str, destination: Path) -> None:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        with destination.open("wb") as file_handle:
            shutil.copyfileobj(response.raw, file_handle)

    @staticmethod
    def _verify_sha(file_path: Path, expected_sha: Optional[str]) -> bool:
        if not expected_sha:
            return True

        sha256 = hashlib.sha256()
        with file_path.open("rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                sha256.update(chunk)

        return sha256.hexdigest().lower() == expected_sha.lower()

