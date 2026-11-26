"""Application update checker, verifier, and staged installer for Tunevia."""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import requests
from packaging import version

import constants
from translation_manager import _


def normalize_version(tag: str) -> str:
    """Strips leading v/V prefixes and whitespace from a release tag."""
    if not tag or not isinstance(tag, str):
        return "0.0.0"
    return tag.strip().lstrip("vV").strip() or "0.0.0"


def is_newer_version(remote_ver: str, current_ver: str) -> bool:
    """Safely compares two semantic or PEP-440 version strings."""
    try:
        return version.parse(normalize_version(remote_ver)) > version.parse(normalize_version(current_ver))
    except Exception:
        return False


def pick_release_asset(assets: list):
    """Selects the best package asset (.zip preferred over .exe) plus optional .sha256 companion."""
    if not isinstance(assets, list) or not assets:
        return None

    zip_candidates = []
    exe_candidates = []
    sha_map = {}

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = asset.get("browser_download_url") or ""
        if not name or not url:
            continue
        low = name.lower()
        if low.endswith(".sha256"):
            sha_map[low[:-7]] = url
        elif low.endswith(".zip"):
            zip_candidates.append(asset)
        elif low.endswith(".exe"):
            exe_candidates.append(asset)

    chosen = None
    if zip_candidates:
        preferred = [
            a for a in zip_candidates
            if "tunevia" in a["name"].lower() or "win" in a["name"].lower()
        ]
        chosen = preferred[0] if preferred else zip_candidates[0]
    elif exe_candidates:
        preferred = [a for a in exe_candidates if "tunevia" in a["name"].lower()]
        chosen = preferred[0] if preferred else exe_candidates[0]

    if not chosen:
        return None

    cname_low = chosen["name"].lower()
    sha_url = sha_map.get(cname_low)
    return {
        "name": chosen["name"],
        "url": chosen["browser_download_url"],
        "size": int(chosen.get("size") or 0),
        "sha256_url": sha_url,
    }


def sanitize_release_notes(body: str, max_len: int = 1200) -> str:
    """Strips markdown syntax, URLs, and backend words so release notes read cleanly on screen readers."""
    if not body or not isinstance(body, str):
        return ""
    text = body.replace("\r\n", "\n")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"(?i)\b(github|api|http|json|repository|repo)\b", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def check_for_update(current_version: str = constants.APP_VERSION, timeout: int = 10) -> dict:
    """Checks for newer Tunevia releases silently without exposing backend details in user_message."""
    try:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{constants.APP_NAME}/{normalize_version(current_version)}",
        }
        resp = requests.get(constants.UPDATE_RELEASE_API_URL, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json() or {}
        latest = normalize_version(str(data.get("tag_name") or ""))
        if not latest or latest == "0.0.0":
            return {
                "status": "error",
                "latest_version": "",
                "notes": "",
                "download_url": "",
                "asset_name": "",
                "asset_size": 0,
                "sha256_url": None,
                "user_message": _("Could not check for updates right now. Please try again later."),
            }

        notes = sanitize_release_notes(str(data.get("body") or ""))
        if is_newer_version(latest, current_version):
            asset = pick_release_asset(data.get("assets") or [])
            return {
                "status": "available",
                "latest_version": latest,
                "notes": notes,
                "download_url": asset["url"] if asset else constants.UPDATE_RELEASES_PAGE_URL,
                "asset_name": asset["name"] if asset else f"Tunevia-{latest}",
                "asset_size": asset["size"] if asset else 0,
                "sha256_url": asset["sha256_url"] if asset else None,
                "user_message": _("A new version of Tunevia ({version}) is available.").format(version=latest),
            }

        return {
            "status": "up_to_date",
            "latest_version": latest,
            "notes": notes,
            "download_url": "",
            "asset_name": "",
            "asset_size": 0,
            "sha256_url": None,
            "user_message": _("You are using the latest version of Tunevia ({version}).").format(
                version=normalize_version(current_version)
            ),
        }
    except Exception as e:
        print(f"Update check internal detail: {e}")
        return {
            "status": "error",
            "latest_version": "",
            "notes": "",
            "download_url": "",
            "asset_name": "",
            "asset_size": 0,
            "sha256_url": None,
            "user_message": _("Could not check for updates right now. Please try again later."),
        }


def download_and_verify_update(
    download_url: str,
    asset_name: str,
    dest_dir: str,
    progress_cb=None,
    cancel_event=None,
    sha256_url: str = None,
):
    """Downloads an update package in 64 KB chunks, verifying zip integrity and optional SHA-256."""
    os.makedirs(dest_dir, exist_ok=True)
    safe_name = os.path.basename(asset_name or "tunevia_update.zip")
    dest_path = os.path.join(dest_dir, safe_name)

    try:
        headers = {"User-Agent": f"{constants.APP_NAME}/{normalize_version(constants.APP_VERSION)}"}
        with requests.get(download_url, headers=headers, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or 0)
            downloaded = 0
            last_pct = -1
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if cancel_event is not None and cancel_event.is_set():
                        return False, _("Update download cancelled.")
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        pct = min(99, int((downloaded * 100) / total))
                        if pct != last_pct:
                            last_pct = pct
                            progress_cb(pct)

        if sha256_url:
            sha_resp = requests.get(sha256_url, headers=headers, timeout=15)
            sha_resp.raise_for_status()
            expected_hash = sha_resp.text.strip().split()[0].lower()
            h = hashlib.sha256()
            with open(dest_path, "rb") as f:
                for blk in iter(lambda: f.read(65536), b""):
                    h.update(blk)
            if h.hexdigest().lower() != expected_hash:
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                return False, _("The downloaded update file could not be verified. Please try again.")

        if safe_name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(dest_path, "r") as zf:
                    if zf.testzip() is not None:
                        raise zipfile.BadZipFile("Corrupt zip member")
            except Exception as ze:
                print(f"Update archive integrity failure: {ze}")
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                return False, _("The downloaded update package was incomplete. Please try again.")

        if progress_cb:
            progress_cb(100)
        return True, dest_path
    except Exception as e:
        print(f"Update download internal error: {e}")
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except OSError:
            pass
        return False, _("Could not download the update right now. Please check your connection and try again.")


def launch_frozen_update_installer(package_path: str, app_dir: str, exe_name: str = "Tunevia.exe"):
    """Stages extracted update files and launches a detached script to swap files after app exit."""
    try:
        stage_root = os.path.join(tempfile.gettempdir(), "tunevia_update_stage")
        if os.path.exists(stage_root):
            shutil.rmtree(stage_root, ignore_errors=True)
        os.makedirs(stage_root, exist_ok=True)

        source_dir = os.path.join(stage_root, "payload")
        os.makedirs(source_dir, exist_ok=True)

        if package_path.lower().endswith(".zip"):
            with zipfile.ZipFile(package_path, "r") as zf:
                zf.extractall(source_dir)
            # If archive wraps files inside a single top-level directory (e.g. Tunevia/), unwrap it.
            entries = os.listdir(source_dir)
            if len(entries) == 1 and os.path.isdir(os.path.join(source_dir, entries[0])):
                inner = os.path.join(source_dir, entries[0])
                if os.path.exists(os.path.join(inner, exe_name)):
                    source_dir = inner
        else:
            shutil.copy2(package_path, os.path.join(source_dir, exe_name))

        bat_path = os.path.join(stage_root, "apply_tunevia_update.bat")
        pid = os.getpid()
        target_exe = os.path.join(app_dir, exe_name)
        bat_lines = [
            "@echo off",
            "setlocal",
            f'set "APP_DIR={app_dir}"',
            f'set "SRC_DIR={source_dir}"',
            f'set "STAGE_ROOT={stage_root}"',
            f'set "PKG_FILE={package_path}"',
            ":waitloop",
            f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul',
            "if not errorlevel 1 (",
            "    timeout /t 1 /nobreak >nul",
            "    goto waitloop",
            ")",
            'robocopy "%SRC_DIR%" "%APP_DIR%" /E /IS /IT /R:5 /W:1 /XF portable.dat portable.txt youtube_player_settings.json www.youtube.com_cookies.txt /XD data >nul',
            f'start "" "{target_exe}"',
            'del "%PKG_FILE%" >nul 2>&1',
            'rmdir /s /q "%STAGE_ROOT%" >nul 2>&1',
        ]
        with open(bat_path, "w", encoding="utf-8") as bf:
            bf.write("\r\n".join(bat_lines) + "\r\n")

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=creation_flags, close_fds=True)
        return True, _("Update is ready. Tunevia will restart to complete installation.")
    except Exception as e:
        print(f"Update installer internal error: {e}")
        return False, _("Could not prepare the update installer. Please try again.")
