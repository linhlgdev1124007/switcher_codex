#!/usr/bin/env python3
r"""
Codex Account Manager — Modern Developer Luxury Edition
Designed by Tuan03

Windows Codex multi-account launcher:
- Auto-discovers %USERPROFILE%\.codex and %USERPROFILE%\.codex-*
- Reads account email / plan / rate limits using `codex app-server` (JSON-RPC)
- Opens an isolated terminal session with selected CODEX_HOME
- Creates and manages multiple isolated CODEX_HOME accounts
- Modern Developer Luxury Dark Theme (Linear / Vercel / Raycast aesthetic)

Dependency:
    pip install customtkinter

Run:
    python codex_switcher.py
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    bundle_dir = Path(sys._MEIPASS)
    sys.path.insert(0, str(bundle_dir))
    sys.path.insert(0, str(Path(sys.executable).parent))
    os.environ["TCL_LIBRARY"] = str(bundle_dir / "tcl" / "tcl8.6")
    os.environ["TK_LIBRARY"] = str(bundle_dir / "tcl" / "tk8.6")

import tkinter as tk
from tkinter import messagebox, simpledialog

try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit(
        "\nMissing dependency: customtkinter\n"
        "Install it with:\n\n"
        "    pip install customtkinter\n"
    )


# =============================================================================
# App constants & Theme Configuration
# =============================================================================

APP_NAME = "Codex Profile Manager"
APP_VERSION = "2.2.0"
GITHUB_URL = "https://github.com/tuan03"

RPC_TIMEOUT = 18.0
MAX_REFRESH_WORKERS = 4

# Configure Dark Mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# =============================================================================
# Design Tokens (Modern Developer Luxury: Deep Zinc / OLED Dark)
# =============================================================================

C = {
    # Surfaces & Canvas
    "window": "#09090B",        # Deep Zinc Canvas
    "sidebar": "#0D0D11",       # Darkened Sidebar Surface
    "surface": "#121216",       # Primary Card Background
    "surface_2": "#17171D",     # Inner Element / Metric Box Surface
    "surface_hover": "#1C1C24", # Interactive Hover Surface
    "surface_active": "#22222C",

    # Borders & Outlines (Ultra-subtle 1px borders)
    "border": "#23232C",
    "border_subtle": "#1B1B22",
    "border_strong": "#32323E",
    "border_highlight": "#4B4B5C",

    # Typography
    "text": "#F4F4F7",          # Crisp White Primary Text
    "text_2": "#9E9EAF",        # Muted Secondary Text
    "text_3": "#606072",        # Tertiary / Sub-labels
    "text_accent": "#A5B4FC",   # Soft Indigo for code tags

    # Accents & Brands
    "indigo": "#6366F1",        # Primary Indigo Action
    "indigo_hover": "#4F46E5",
    "indigo_soft": "#1E1B4B",
    "indigo_glow": "#818CF8",

    "emerald": "#10B981",       # Active / Healthy Status
    "emerald_hover": "#059669",
    "emerald_soft": "#064E3B",

    "amber": "#F59E0B",         # Warning / Mid-Quota
    "amber_soft": "#451A03",

    "rose": "#F43F5E",          # Error / Critical Quota (<15%)
    "rose_soft": "#4C0519",

    "track": "#1E1E26",         # Modern Progress Track
}

FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"


# =============================================================================
# Helper Functions
# =============================================================================

def codex_executable() -> str | None:
    return (
        shutil.which("codex")
        or shutil.which("codex.exe")
        or shutil.which("codex.cmd")
        or shutil.which("codex.bat")
    )


def codex_process_args(codex_bin: str, *args: str) -> list[str]:
    suffix = Path(codex_bin).suffix.lower()
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        return ["cmd.exe", "/d", "/s", "/c", codex_bin, *args]
    return [codex_bin, *args]


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def safe_rmtree(path: Path) -> None:
    """Robustly delete a directory tree on Windows, handling read-only git files."""
    if not path.exists():
        return

    def _remove_readonly(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IWUSR)
            func(p)
        except Exception:
            pass

    try:
        shutil.rmtree(path, onexc=lambda fn, p, err: (os.chmod(p, stat.S_IWRITE | stat.S_IWUSR), fn(p)))
    except TypeError:
        shutil.rmtree(path, onerror=_remove_readonly)
    except Exception:
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run(["cmd.exe", "/d", "/c", "rd", "/s", "/q", str(path)], creationflags=flags)

    if path.exists() and os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(["cmd.exe", "/d", "/c", "rd", "/s", "/q", str(path)], creationflags=flags)

    if path.exists():
        raise RuntimeError(f"Could not completely remove directory: {path}")


def plan_display(plan: str | None) -> str:
    if not plan:
        return "Unknown"
    mapping = {
        "free": "Free",
        "plus": "Plus",
        "pro": "Pro",
        "prolite": "Pro",
        "team": "Team",
        "business": "Business",
        "enterprise": "Enterprise",
        "edu": "Edu",
    }
    return mapping.get(plan.lower(), plan.replace("_", " ").title())


def plan_palette(plan: str) -> tuple[str, str, str]:
    """Returns (bg_color, text_color, border_color) for plan badges."""
    p = plan.lower()
    if p in {"enterprise"}:
        return "#2E1065", "#C084FC", "#581C87"
    if p in {"pro", "team", "business"}:
        return "#1E1B4B", "#A5B4FC", "#3730A3"
    if p in {"plus"}:
        return "#172554", "#93C5FD", "#1E40AF"
    if p in {"free"}:
        return "#064E3B", "#6EE7B7", "#065F46"
    return "#18181B", C["text_2"], C["border"]


def usage_color(remaining: float | None) -> str:
    if remaining is None:
        return C["text_3"]
    if remaining < 5:
        return C["rose"]
    if remaining <= 30:
        return C["amber"]
    return C["emerald"]


def human_window(minutes: int | float | None) -> str:
    if minutes is None:
        return "Session Quota"

    try:
        m = int(minutes)
    except Exception:
        return "Session Quota"

    if 270 <= m <= 330:
        return "5-Hour Limit"
    if 1380 <= m <= 1500:
        return "Daily Limit"
    if 9900 <= m <= 10200:
        return "Weekly Limit"
    if 39000 <= m <= 46000:
        return "Monthly Limit"

    if m < 60:
        return f"{m}-Minute Limit"
    if m % 1440 == 0:
        return f"{m // 1440}-Day Limit"
    if m % 60 == 0:
        return f"{m // 60}-Hour Limit"

    return f"{m}-Minute Limit"


def format_reset(ts: float | int | str | None) -> str:
    if not ts:
        return "—"

    try:
        dt = datetime.fromtimestamp(float(ts)).astimezone()
        now = datetime.now().astimezone()

        if dt.date() == now.date():
            return f"{dt:%H:%M} today"

        return f"{dt:%H:%M} on {dt:%d %b}"
    except Exception:
        return "—"


def format_credit_expiry(ts: float | int | str | None) -> str:
    if not ts:
        return "Expiry unknown"

    try:
        dt = datetime.fromtimestamp(float(ts)).astimezone()
        now = datetime.now().astimezone()

        if dt.date() == now.date():
            return f"Expires {dt:%H:%M} today"

        return f"Expires {dt:%d %b %Y}"
    except Exception:
        return "Expiry unknown"


def short_path(path: Path, max_len: int = 42) -> str:
    s = str(path)
    if len(s) <= max_len:
        return s
    return "…" + s[-(max_len - 1):]


def now_display() -> str:
    return datetime.now().strftime("%H:%M:%S")


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class LimitInfo:
    name: str
    remaining: float | None
    used: float | None
    resets_at: float | None
    window_minutes: int | None
    bucket_id: str = "codex"

    @property
    def reset_text(self) -> str:
        return format_reset(self.resets_at)


@dataclass
class AccountSnapshot:
    home: Path
    label: str
    email: str = "Loading…"
    plan: str = "Unknown"
    auth_type: str = ""
    limits: list[LimitInfo] = field(default_factory=list)
    reset_credits_available: int | None = None
    reset_credits_expires_at: float | None = None
    error: str | None = None
    refreshed_at: float | None = None


# =============================================================================
# Codex JSON-RPC Client (`codex app-server`)
# =============================================================================

class CodexRPC:
    """Minimal stdio JSON-RPC client for `codex app-server`."""

    def __init__(self, codex_bin: str, codex_home: Path):
        self.codex_bin = codex_bin
        self.codex_home = codex_home
        self.proc: subprocess.Popen | None = None
        self.messages: queue.Queue[dict] = queue.Queue()
        self.stderr_lines: queue.Queue[str] = queue.Queue()
        self._next_id = 1

    def start(self) -> None:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.codex_home)

        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self.proc = subprocess.Popen(
            codex_process_args(self.codex_bin, "app-server"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=flags,
        )

        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

        init_id = self._request_raw(
            "initialize",
            {
                "clientInfo": {
                    "name": "codex_account_manager",
                    "title": APP_NAME,
                    "version": APP_VERSION,
                },
                "capabilities": {
                    "optOutNotificationMethods": [
                        "thread/started",
                        "item/agentMessage/delta",
                    ]
                },
            },
        )

        self._wait_for_id(init_id, RPC_TIMEOUT)
        self._send({"method": "initialized", "params": {}})

    def _read_stdout(self) -> None:
        if not self.proc or not self.proc.stdout:
            return

        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    def _read_stderr(self) -> None:
        if not self.proc or not self.proc.stderr:
            return

        for line in self.proc.stderr:
            line = line.strip()
            if line:
                self.stderr_lines.put(line)

    def _send(self, obj: dict) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("Codex app-server is not running")

        self.proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def _request_raw(self, method: str, params=None) -> int:
        req_id = self._next_id
        self._next_id += 1

        payload = {
            "method": method,
            "id": req_id,
        }

        if params is not None:
            payload["params"] = params

        self._send(payload)
        return req_id

    def request(self, method: str, params=None, timeout: float = RPC_TIMEOUT):
        req_id = self._request_raw(method, params)
        return self._wait_for_id(req_id, timeout)

    def _wait_for_id(self, req_id: int, timeout: float):
        deadline = time.monotonic() + timeout
        deferred: list[dict] = []

        try:
            while time.monotonic() < deadline:
                remaining = max(0.05, deadline - time.monotonic())

                try:
                    msg = self.messages.get(timeout=min(0.25, remaining))
                except queue.Empty:
                    if self.proc and self.proc.poll() is not None:
                        raise RuntimeError(
                            self._stderr_summary()
                            or "codex app-server exited unexpectedly"
                        )
                    continue

                if msg.get("id") == req_id:
                    if "error" in msg:
                        err = msg["error"]
                        if isinstance(err, dict):
                            raise RuntimeError(
                                err.get("message") or json.dumps(err)
                            )
                        raise RuntimeError(str(err))

                    return msg.get("result")

                deferred.append(msg)

            raise TimeoutError(
                f"Timed out waiting for Codex response ({timeout:.0f}s)"
            )
        finally:
            for msg in deferred:
                self.messages.put(msg)

    def _stderr_summary(self) -> str:
        lines: list[str] = []

        while len(lines) < 5:
            try:
                lines.append(self.stderr_lines.get_nowait())
            except queue.Empty:
                break

        return " | ".join(lines[-5:])

    def close(self) -> None:
        if not self.proc:
            return

        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass

        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def snapshot_for(home: Path, label: str, codex_bin: str) -> AccountSnapshot:
    snap = AccountSnapshot(home=home, label=label)
    rpc = CodexRPC(codex_bin, home)

    try:
        rpc.start()

        account_result = rpc.request(
            "account/read",
            {"refreshToken": False},
        ) or {}

        account = account_result.get("account")

        if not account:
            snap.email = "Not signed in"
            snap.plan = "Unknown"
            snap.error = "No active Codex login"
            snap.refreshed_at = time.time()
            return snap

        snap.auth_type = str(account.get("type") or "")
        snap.email = account.get("email") or (
            "API key account"
            if snap.auth_type == "apiKey"
            else "Signed in"
        )
        snap.plan = plan_display(account.get("planType"))

        rate_result = rpc.request("account/rateLimits/read") or {}
        reset_credits = rate_result.get("rateLimitResetCredits")

        if isinstance(reset_credits, dict):
            raw_available = reset_credits.get("availableCount")

            try:
                snap.reset_credits_available = (
                    int(raw_available)
                    if raw_available is not None
                    else None
                )
            except Exception:
                snap.reset_credits_available = None

            credits = reset_credits.get("credits")
            expiries: list[float] = []

            if isinstance(credits, list):
                for credit in credits:
                    if not isinstance(credit, dict):
                        continue

                    raw_expiry = credit.get("expiresAt")
                    if raw_expiry is None:
                        continue

                    try:
                        expiries.append(float(raw_expiry))
                    except Exception:
                        continue

            if expiries:
                snap.reset_credits_expires_at = min(expiries)

        rate_obj = None
        by_id = rate_result.get("rateLimitsByLimitId") or {}

        if isinstance(by_id, dict):
            rate_obj = by_id.get("codex")

        if not rate_obj:
            rate_obj = rate_result.get("rateLimits")

        if isinstance(rate_obj, dict) and snap.plan == "Unknown":
            snap.plan = plan_display(rate_obj.get("planType"))

        def add_limit(window: dict | None, bucket_id: str = "codex") -> None:
            if not isinstance(window, dict):
                return

            raw_used = window.get("usedPercent")

            try:
                used = float(raw_used) if raw_used is not None else None
            except Exception:
                used = None

            remaining = (
                None
                if used is None
                else max(0.0, min(100.0, 100.0 - used))
            )

            raw_minutes = window.get("windowDurationMins")

            try:
                minutes = int(raw_minutes) if raw_minutes is not None else None
            except Exception:
                minutes = None

            snap.limits.append(
                LimitInfo(
                    name=human_window(minutes),
                    remaining=remaining,
                    used=used,
                    resets_at=window.get("resetsAt"),
                    window_minutes=minutes,
                    bucket_id=bucket_id,
                )
            )

        if isinstance(rate_obj, dict):
            bucket_id = str(rate_obj.get("limitId") or "codex")
            add_limit(rate_obj.get("primary"), bucket_id)
            add_limit(rate_obj.get("secondary"), bucket_id)

        if not snap.limits and isinstance(by_id, dict):
            for bucket_id, bucket in by_id.items():
                if not isinstance(bucket, dict):
                    continue

                add_limit(bucket.get("primary"), str(bucket_id))
                add_limit(bucket.get("secondary"), str(bucket_id))

        # De-duplicate windows
        result: list[LimitInfo] = []
        seen = set()

        for lim in snap.limits:
            key = (
                lim.bucket_id,
                lim.window_minutes,
                lim.resets_at,
                lim.used,
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(lim)

        snap.limits = result[:4]
        snap.refreshed_at = time.time()
        return snap

    except Exception as exc:
        snap.error = str(exc)
        snap.refreshed_at = time.time()
        return snap

    finally:
        rpc.close()


# =============================================================================
# Modern Micro-Components & Badges
# =============================================================================

class Badge(ctk.CTkLabel):
    """Refined luxury pill badge with subtle borders."""
    def __init__(
        self,
        master,
        text: str,
        fg_color: str = "#18181E",
        text_color: str = C["text_2"],
        border_color: str = C["border"],
        border_width: int = 1,
        font_size: int = 11,
        is_mono: bool = False,
        **kwargs,
    ):
        super().__init__(
            master,
            text=text,
            fg_color=fg_color,
            text_color=text_color,
            corner_radius=6,
            height=24,
            font=(FONT_MONO if is_mono else FONT_FAMILY, font_size, "bold"),
            padx=8,
            **kwargs,
        )


class NavButton(ctk.CTkButton):
    """Sleek sidebar navigation item with active indicator."""
    def __init__(
        self,
        master,
        text: str,
        symbol: str,
        command,
        active: bool = False,
    ):
        super().__init__(
            master,
            text=f"  {symbol}    {text}",
            command=command,
            anchor="w",
            height=42,
            corner_radius=8,
            fg_color="#181822" if active else "transparent",
            hover_color="#1F1F2C",
            text_color=C["text"] if active else C["text_2"],
            font=(FONT_FAMILY, 13, "bold" if active else "normal"),
            border_width=1 if active else 0,
            border_color=C["border_highlight"] if active else C["border"],
        )


class UsageBlock(ctk.CTkFrame):
    """Compact rate limit gauge with dark luxury styling."""
    def __init__(self, master, limit: LimitInfo):
        super().__init__(
            master,
            fg_color=C["surface_2"],
            border_width=1,
            border_color=C["border_subtle"],
            corner_radius=8,
        )

        color = usage_color(limit.remaining)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Header: Name & Remaining %
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 4))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text=f"◈  {limit.name}",
            text_color=C["text_2"],
            font=(FONT_FAMILY, 11, "bold"),
        )
        title_label.grid(row=0, column=0, sticky="w")

        pct_text = "—" if limit.remaining is None else f"{limit.remaining:.0f}% left"
        pct_label = ctk.CTkLabel(
            header_frame,
            text=pct_text,
            text_color=color,
            font=(FONT_MONO, 11, "bold"),
        )
        pct_label.grid(row=0, column=1, sticky="e")

        # Ultra-slim modern progress bar
        progress = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=4,
            fg_color=C["track"],
            progress_color=color,
        )
        progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 6))
        progress.set(0.0 if limit.remaining is None else max(0.02, min(1.0, limit.remaining / 100.0)))

        # Subtext: Reset Time & Usage
        meta_frame = ctk.CTkFrame(self, fg_color="transparent")
        meta_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        meta_frame.grid_columnconfigure(0, weight=1)

        used_str = "—" if limit.used is None else f"{limit.used:.0f}% used"
        used_label = ctk.CTkLabel(
            meta_frame,
            text=used_str,
            text_color=C["text_3"],
            font=(FONT_FAMILY, 10),
        )
        used_label.grid(row=0, column=0, sticky="w")

        reset_label = ctk.CTkLabel(
            meta_frame,
            text=f"⏱ {limit.reset_text}",
            text_color=C["text_2"],
            font=(FONT_FAMILY, 10),
        )
        reset_label.grid(row=0, column=1, sticky="e")


# =============================================================================
# Redesigned Profile Card (Modern Developer Luxury - Compact Square Card)
# =============================================================================

class AccountCard(ctk.CTkFrame):
    """Compact square-proportioned profile card for modern grid dashboard."""
    def __init__(
        self,
        master,
        app: "CodexAccountManager",
        snap: AccountSnapshot,
    ):
        is_main = snap.home.name == ".codex-tuan03" or snap.label.lower() == "tuan03"
        
        super().__init__(
            master,
            fg_color=C["indigo_soft"] if is_main else C["surface"],
            border_width=2 if is_main else 1,
            border_color=C["indigo"] if is_main else C["border"],
            corner_radius=12,
        )

        self.app = app
        self.snap = snap
        self.is_main = is_main

        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        # 1. Top Header Row (Avatar + Label/Badge + Context Menu)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(1, weight=1)

        # Avatar with luxury initial
        initial_source = (
            self.snap.email
            if "@" in self.snap.email
            else self.snap.label
        )
        initial = (initial_source[:1] or "C").upper()

        plan_bg, plan_fg, _ = plan_palette(self.snap.plan)

        avatar = ctk.CTkLabel(
            header,
            text=initial,
            width=36,
            height=36,
            corner_radius=8,
            fg_color=plan_bg,
            text_color=plan_fg,
            font=(FONT_FAMILY, 15, "bold"),
        )
        avatar.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 10))

        # Identity Details
        identity = ctk.CTkFrame(header, fg_color="transparent")
        identity.grid(row=0, column=1, rowspan=2, sticky="ew")
        identity.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(identity, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="w")

        display_label = f"★ {self.snap.label} (Main) ★" if getattr(self, "is_main", False) else self.snap.label
        label_text = ctk.CTkLabel(
            title_row,
            text=display_label,
            text_color=C["indigo_glow"] if getattr(self, "is_main", False) else C["text"],
            font=(FONT_FAMILY, 13, "bold"),
        )
        label_text.pack(side="left")

        # Plan Badge
        p_bg, p_fg, p_border = plan_palette(self.snap.plan)
        badge = Badge(
            title_row,
            text=self.snap.plan.upper(),
            fg_color=p_bg,
            text_color=p_fg,
            border_color=p_border,
            font_size=9,
        )
        badge.pack(side="left", padx=(6, 0))

        if self.snap.reset_credits_available is not None:
            reset_badge = Badge(
                title_row,
                text=f"RESET x{self.snap.reset_credits_available}",
                fg_color=C["amber_soft"] if self.snap.reset_credits_available else C["surface_2"],
                text_color=C["amber"] if self.snap.reset_credits_available else C["text_3"],
                border_color=C["amber"] if self.snap.reset_credits_available else C["border"],
                font_size=9,
            )
            reset_badge.pack(side="left", padx=(6, 0))

        # Email
        email_str = self.snap.email
        if len(email_str) > 28:
            email_str = email_str[:26] + "…"
        email_label = ctk.CTkLabel(
            identity,
            text=email_str,
            text_color=C["text_2"],
            font=(FONT_MONO, 10),
        )
        email_label.grid(row=1, column=0, sticky="w", pady=(1, 0))

        # Context Menu Button in top right
        menu_btn = ctk.CTkButton(
            header,
            text="•••",
            command=lambda: self.app.show_account_menu(self.snap, menu_btn),
            width=28,
            height=28,
            corner_radius=6,
            fg_color=C["surface_2"],
            hover_color=C["surface_hover"],
            text_color=C["text_2"],
            border_width=1,
            border_color=C["border"],
            font=(FONT_FAMILY, 11, "bold"),
        )
        menu_btn.grid(row=0, column=2, sticky="ne")

        # 2. Path Strip (Folder with click to copy)
        strip = ctk.CTkFrame(
            self,
            fg_color=C["surface_2"],
            corner_radius=6,
            border_width=1,
            border_color=C["border_subtle"],
        )
        strip.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        strip.grid_columnconfigure(0, weight=1)

        path_text = short_path(self.snap.home, 26)
        path_label = ctk.CTkLabel(
            strip,
            text=f"📁 {path_text}",
            text_color=C["text_3"],
            font=(FONT_MONO, 10),
        )
        path_label.grid(row=0, column=0, sticky="w", padx=8, pady=4)

        self.copy_btn = ctk.CTkButton(
            strip,
            text="Copy",
            command=self._handle_copy_path,
            width=48,
            height=20,
            corner_radius=4,
            fg_color="#22222C",
            hover_color="#2C2C38",
            text_color=C["text_2"],
            font=(FONT_FAMILY, 10),
        )
        self.copy_btn.grid(row=0, column=1, sticky="e", padx=4, pady=3)

        next_row = 2

        if self.snap.reset_credits_available is not None:
            reset_strip = ctk.CTkFrame(
                self,
                fg_color=C["surface_2"],
                corner_radius=6,
                border_width=1,
                border_color=C["border_subtle"],
            )
            reset_strip.grid(row=next_row, column=0, sticky="ew", padx=14, pady=(0, 10))
            reset_strip.grid_columnconfigure(0, weight=1)

            count = self.snap.reset_credits_available
            count_text = f"{count} reset credit available" if count == 1 else f"{count} reset credits available"

            ctk.CTkLabel(
                reset_strip,
                text=f"↻ {count_text}",
                text_color=C["amber"] if count else C["text_3"],
                font=(FONT_FAMILY, 10, "bold"),
            ).grid(row=0, column=0, sticky="w", padx=8, pady=4)

            ctk.CTkLabel(
                reset_strip,
                text=format_credit_expiry(self.snap.reset_credits_expires_at),
                text_color=C["text_3"],
                font=(FONT_MONO, 10),
            ).grid(row=0, column=1, sticky="e", padx=8, pady=4)

            next_row += 1

        # 3. Body: Limits & Quotas
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=next_row, column=0, sticky="ew", padx=14, pady=(0, 12))

        if self.snap.error:
            self._build_error(body)
        elif not self.snap.limits:
            no_usage = ctk.CTkFrame(
                body,
                fg_color=C["surface_2"],
                border_width=1,
                border_color=C["border_subtle"],
                corner_radius=8,
            )
            no_usage.pack(fill="x")

            ctk.CTkLabel(
                no_usage,
                text="ℹ  Metrics pending refresh…",
                text_color=C["text_3"],
                font=(FONT_FAMILY, 10),
            ).pack(anchor="w", padx=10, pady=8)
        else:
            # Display top 1-2 limit gauges in compact card
            for i, lim in enumerate(self.snap.limits[:2]):
                block = UsageBlock(body, lim)
                block.pack(
                    fill="x",
                    pady=(0, 6 if i < len(self.snap.limits[:2]) - 1 else 0),
                )

        # 4. Footer Launch Button
        launch_btn = ctk.CTkButton(
            self,
            text=">_  Launch Codex",
            command=lambda: self.app.open_codex(self.snap),
            height=32,
            corner_radius=7,
            fg_color="#FFFFFF",
            hover_color="#E4E4E7",
            text_color="#09090B",
            font=(FONT_FAMILY, 11, "bold"),
        )
        launch_btn.grid(row=next_row + 1, column=0, sticky="ew", padx=14, pady=(0, 14))

    def _handle_copy_path(self):
        self.app.copy_to_clipboard(str(self.snap.home))
        self.copy_btn.configure(text="✓", text_color=C["emerald"])
        self.after(1600, lambda: self.copy_btn.configure(text="Copy", text_color=C["text_2"]))

    def _build_error(self, parent):
        signed_out = self.snap.email == "Not signed in"

        box = ctk.CTkFrame(
            parent,
            fg_color=C["amber_soft"] if signed_out else C["rose_soft"],
            border_width=1,
            border_color=C["amber"] if signed_out else C["rose"],
            corner_radius=8,
        )
        box.pack(fill="x")
        box.grid_columnconfigure(0, weight=1)

        msg = (
            "Auth required"
            if signed_out
            else f"Status error: {self.snap.error[:28]}…"
        )

        ctk.CTkLabel(
            box,
            text=msg,
            text_color="#FDE68A" if signed_out else "#FECDD3",
            font=(FONT_FAMILY, 10),
            justify="left",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=6)

        if signed_out:
            ctk.CTkButton(
                box,
                text="Login",
                command=lambda: self.app.login_account(self.snap),
                width=55,
                height=22,
                corner_radius=4,
                fg_color=C["indigo"],
                hover_color=C["indigo_hover"],
                text_color="white",
                font=(FONT_FAMILY, 10, "bold"),
            ).grid(row=0, column=1, padx=6, pady=4)


# =============================================================================
# Main Application Shell
# =============================================================================

class CodexAccountManager(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1400x880")
        self.minsize(1080, 680)
        self.configure(fg_color=C["window"])

        self.codex_bin = codex_executable()
        self.executor = ThreadPoolExecutor(max_workers=MAX_REFRESH_WORKERS)

        self.snapshots: dict[Path, AccountSnapshot] = {}
        self.account_cards: dict[Path, AccountCard] = {}

        self.state_dir = Path(os.getenv("APPDATA", str(Path.home()))) / "CodexAccountManager"
        self.state_file = self.state_dir / "settings.json"
        self.explicit_accounts = self._load_explicit_accounts()

        self.current_page = "accounts"
        self.nav_buttons: dict[str, NavButton] = {}
        self.search_query = ""
        self.plan_filter = "All Plans"

        self._build_shell()
        self.discover_and_render()

        self.after(350, self.refresh_all)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -------------------------------------------------------------------------
    # Layout Builder
    # -------------------------------------------------------------------------

    def _build_shell(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Sidebar
        self.sidebar = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0,
            fg_color=C["sidebar"],
            border_width=1,
            border_color=C["border"],
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(7, weight=1)

        self._build_sidebar()

        # 2. Main Content Canvas
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=C["window"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self._build_main_header()
        self._build_accounts_page()

    def _build_sidebar(self):
        # Brand Header
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 28))

        logo = ctk.CTkLabel(
            brand,
            text="◈",
            width=42,
            height=42,
            corner_radius=10,
            fg_color=C["indigo_soft"],
            text_color=C["indigo_glow"],
            font=(FONT_FAMILY, 20, "bold"),
        )
        logo.pack(side="left")

        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=(12, 0))

        ctk.CTkLabel(
            brand_text,
            text="Codex Switcher",
            text_color=C["text"],
            font=(FONT_FAMILY, 15, "bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            brand_text,
            text="Enterprise Launcher",
            text_color=C["text_3"],
            font=(FONT_FAMILY, 11),
        ).pack(anchor="w")

        # Navigation Links
        nav_items = [
            ("accounts", "Profiles", "⊞"),
            ("nexus", "Nexus Link", "🔗"),
            ("activity", "Activity Log", "⌁"),
            ("settings", "Preferences", "⚙"),
            ("about", "About", "ⓘ"),
        ]

        for row, (key, label, symbol) in enumerate(nav_items, start=1):
            btn = NavButton(
                self.sidebar,
                text=label,
                symbol=symbol,
                command=lambda k=key: self.switch_page(k),
                active=(key == "accounts"),
            )
            btn.grid(row=row, column=0, sticky="ew", padx=14, pady=3)
            self.nav_buttons[key] = btn

        # Developer Attribution Card
        author_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=C["surface"],
            border_width=1,
            border_color=C["border"],
            corner_radius=12,
        )
        author_card.grid(row=8, column=0, sticky="sew", padx=14, pady=20)

        author_top = ctk.CTkFrame(author_card, fg_color="transparent")
        author_top.pack(fill="x", padx=12, pady=(12, 8))

        avatar = ctk.CTkLabel(
            author_top,
            text="T",
            width=32,
            height=32,
            corner_radius=8,
            fg_color=C["indigo_soft"],
            text_color=C["indigo_glow"],
            font=(FONT_FAMILY, 13, "bold"),
        )
        avatar.pack(side="left")

        text_wrap = ctk.CTkFrame(author_top, fg_color="transparent")
        text_wrap.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            text_wrap,
            text="Designed by",
            text_color=C["text_3"],
            font=(FONT_FAMILY, 10),
        ).pack(anchor="w")

        author_link = ctk.CTkLabel(
            text_wrap,
            text="Tuan03",
            text_color=C["text"],
            font=(FONT_FAMILY, 12, "bold"),
            cursor="hand2",
        )
        author_link.pack(anchor="w")
        author_link.bind("<Button-1>", lambda _e: webbrowser.open(GITHUB_URL))

        ctk.CTkButton(
            author_card,
            text="GitHub Profile   ↗",
            command=lambda: webbrowser.open(GITHUB_URL),
            height=30,
            corner_radius=6,
            fg_color=C["surface_2"],
            hover_color=C["surface_hover"],
            text_color=C["text_2"],
            font=(FONT_FAMILY, 11),
        ).pack(fill="x", padx=8, pady=(0, 8))

    def _build_main_header(self):
        self.header = ctk.CTkFrame(self.main, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=36, pady=(28, 16))
        self.header.grid_columnconfigure(0, weight=1)

        # Title & Subtitle
        title_wrap = ctk.CTkFrame(self.header, fg_color="transparent")
        title_wrap.grid(row=0, column=0, sticky="w")

        self.page_title = ctk.CTkLabel(
            title_wrap,
            text="Codex Profiles",
            text_color=C["text"],
            font=(FONT_FAMILY, 26, "bold"),
        )
        self.page_title.pack(anchor="w")

        self.page_subtitle = ctk.CTkLabel(
            title_wrap,
            text="Manage isolated CODEX_HOME environments and monitor rate limits in real-time.",
            text_color=C["text_2"],
            font=(FONT_FAMILY, 13),
        )
        self.page_subtitle.pack(anchor="w", pady=(2, 0))

        # Top Action Buttons
        actions = ctk.CTkFrame(self.header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        self.refresh_btn = ctk.CTkButton(
            actions,
            text="↻  Sync Quotas",
            command=self.refresh_all,
            width=125,
            height=36,
            corner_radius=8,
            fg_color=C["surface"],
            hover_color=C["surface_hover"],
            text_color=C["text"],
            border_width=1,
            border_color=C["border"],
            font=(FONT_FAMILY, 12, "bold"),
        )
        self.refresh_btn.pack(side="left", padx=(0, 10))

        self.add_btn = ctk.CTkButton(
            actions,
            text="+  New Profile",
            command=self.add_account,
            width=125,
            height=36,
            corner_radius=8,
            fg_color=C["indigo"],
            hover_color=C["indigo_hover"],
            text_color="white",
            font=(FONT_FAMILY, 12, "bold"),
        )
        self.add_btn.pack(side="left")

        # Search Bar & Filter Strip
        self.filter_bar = ctk.CTkFrame(self.header, fg_color="transparent")
        self.filter_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        self.filter_bar.grid_columnconfigure(0, weight=1)

        # Search Input
        self.search_entry = ctk.CTkEntry(
            self.filter_bar,
            placeholder_text="Search profiles by name, email, or path...",
            height=36,
            corner_radius=8,
            fg_color=C["surface"],
            border_color=C["border"],
            text_color=C["text"],
            placeholder_text_color=C["text_3"],
            font=(FONT_FAMILY, 12),
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.search_entry.bind("<KeyRelease>", self._on_search_changed)

        # Plan Filter Combobox
        self.plan_combo = ctk.CTkComboBox(
            self.filter_bar,
            values=["All Plans", "Enterprise", "Pro", "Plus", "Free"],
            command=self._on_plan_filter_changed,
            width=130,
            height=36,
            corner_radius=8,
            fg_color=C["surface"],
            border_color=C["border"],
            button_color=C["surface_2"],
            text_color=C["text"],
            dropdown_fg_color=C["surface"],
            dropdown_text_color=C["text"],
            font=(FONT_FAMILY, 12),
        )
        self.plan_combo.grid(row=0, column=1, sticky="e", padx=(0, 12))

        # Status Chips
        chips = ctk.CTkFrame(self.filter_bar, fg_color="transparent")
        chips.grid(row=0, column=2, sticky="e")

        self.accounts_badge = Badge(chips, text="0 profiles")
        self.accounts_badge.pack(side="left", padx=(0, 8))

        self.system_badge = Badge(
            chips,
            text="● Checking CLI…",
            fg_color=C["emerald_soft"],
            text_color=C["emerald"],
            border_color=C["emerald"],
        )
        self.system_badge.pack(side="left")

    def _build_accounts_page(self):
        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=(36, 24), pady=(0, 18))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(
            self.content,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#272732",
            scrollbar_button_hover_color="#363645",
        )
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        self.scroll.grid_columnconfigure(1, weight=1)
        self.scroll.grid_columnconfigure(2, weight=1)

        # Footer banner
        self.footer = ctk.CTkFrame(
            self.content,
            fg_color=C["surface"],
            border_width=1,
            border_color=C["border"],
            corner_radius=8,
        )
        self.footer.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        ctk.CTkLabel(
            self.footer,
            text="🛡️  All credentials and tokens remain strictly isolated in their respective CODEX_HOME directories.",
            text_color=C["text_3"],
            font=(FONT_FAMILY, 11),
        ).pack(anchor="w", padx=14, pady=8)

    # -------------------------------------------------------------------------
    # Filtering & Navigation
    # -------------------------------------------------------------------------

    def _on_search_changed(self, event=None):
        self.search_query = self.search_entry.get().strip().lower()
        self.discover_and_render()

    def _on_plan_filter_changed(self, choice: str):
        self.plan_filter = choice
        self.discover_and_render()

    def switch_page(self, page: str):
        if page == self.current_page:
            return

        self.current_page = page

        for key, btn in self.nav_buttons.items():
            active = key == page
            btn.configure(
                fg_color="#181822" if active else "transparent",
                text_color=C["text"] if active else C["text_2"],
                border_width=1 if active else 0,
                border_color=C["border_highlight"] if active else C["border"],
            )

        titles = {
            "accounts": ("Codex Profiles", "Manage isolated CODEX_HOME environments and monitor rate limits in real-time."),
            "nexus": ("Nexus Link", "Drag and drop the energy wire to link the Main profile with another."),
            "activity": ("Activity Log", "Recent CLI execution and login session history."),
            "settings": ("Preferences", "Application configuration and terminal emulator bindings."),
            "about": ("About Codex Switcher", f"Version {APP_VERSION} • Modern Developer Luxury Edition"),
        }

        title, subtitle = titles.get(page, ("Codex Switcher", ""))
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)

        if page == "accounts":
            self.filter_bar.grid()
            self.discover_and_render()
            return
            
        if page == "nexus":
            self.filter_bar.grid_remove()
            self._render_nexus_page()
            return

        self.filter_bar.grid_remove()
        self._render_placeholder_page(page)


    def _render_nexus_page(self):
        self._clear_scroll()
        import tkinter as tk
        
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=C["surface"],
            border_width=1,
            border_color=C["border"],
            corner_radius=14,
        )
        card.grid(row=0, column=0, sticky="ew", pady=(8, 0))
        
        accounts = self.discover_accounts()
        accounts.sort(key=lambda x: (0 if x[1].lower() == "tuan03" or x[0].name == ".codex-tuan03" else 1, x[1].lower()))
        
        if not accounts:
            return
            
        main_acc = accounts[0]
        others = accounts[1:]
        
        # Grid Layout Calculation
        req_height = max(460, (((len(others) - 1) // 2) + 1) * 160 + 100) if others else 460
        cv = tk.Canvas(card, bg=C["surface"], height=req_height, highlightthickness=0)
        cv.pack(fill="x", padx=10, pady=10)
        
        # Banner hướng dẫn & thông báo trạng thái
        notice_id = cv.create_text(
            480, 24,
            text="⚡ Nexus Link: Chỉ cho phép liên kết profile Main với tài khoản Plus hoặc Free",
            fill=C["text_3"],
            font=(FONT_FAMILY, 10, "bold"),
        )
        
        def set_notice(msg: str, color: str):
            cv.itemconfig(notice_id, text=msg, fill=color)
            card.after(3500, lambda: cv.itemconfig(
                notice_id,
                text="⚡ Nexus Link: Chỉ cho phép liên kết profile Main với tài khoản Plus hoặc Free",
                fill=C["text_3"]
            ))

        # Tải lại profile đã từng liên kết trước đó từ settings.json
        saved_target = self._load_nexus_target()
        self.nexus_nodes = []
        self.nexus_active_target = None

        # 1. Nếu đã lưu target từ lần trước, kiểm tra xem còn tồn tại và hợp lệ không
        if saved_target:
            for path, _ in others:
                if path.resolve() == saved_target.resolve():
                    snap = self.snapshots.get(path)
                    p = (snap.plan or "Free").lower() if snap else "free"
                    if p not in ("pro", "prolite", "team", "business"):
                        self.nexus_active_target = path
                    break

        # 2. Nếu chưa từng lưu hoặc profile cũ không còn hợp lệ, chọn profile Plus/Free đầu tiên
        if not self.nexus_active_target:
            for path, _ in others:
                snap = self.snapshots.get(path)
                p = (snap.plan or "Free").lower() if snap else "free"
                if p not in ("pro", "prolite", "team", "business"):
                    self.nexus_active_target = path
                    self._save_nexus_target(path)
                    break
            
        main_x, main_y = 120, req_height / 2
        
        def draw_node_limits(path, cx, cy, tag=None):
            snap = self.snapshots.get(path)
            tags = ("any_node", "target_node", tag) if tag else ()
            if not snap or not snap.limits:
                cv.create_text(cx, cy, text="No limit data", fill=C["text_3"], font=(FONT_FAMILY, 9), tags=tags)
                return
            
            y_offset = cy
            for lim in snap.limits[:2]:
                name = str(lim.name).replace(" window", "")
                rem = lim.remaining if lim.remaining is not None else 0
                color = usage_color(rem)
                
                cv.create_text(cx, y_offset, text=f"{name} ({int(rem)}%)", fill=color, font=(FONT_FAMILY, 9, "bold"), tags=tags)
                
                # Draw Progress Bar
                w = 36
                y_bar = y_offset + 10
                cv.create_line(cx - w, y_bar, cx + w, y_bar, fill=C["border_strong"], width=4, capstyle="round", tags=tags)
                if rem > 0:
                    pct = max(0.02, min(1.0, rem / 100.0))
                    cv.create_line(cx - w, y_bar, cx - w + (2*w * pct), y_bar, fill=color, width=4, capstyle="round", tags=tags)
                
                y_offset += 26

        # Draw Main Node
        cv.create_oval(main_x-40, main_y-40, main_x+40, main_y+40, fill=C["surface_2"], outline=C["indigo"], width=3)
        cv.create_text(main_x, main_y, text="★", fill=C["indigo_glow"], font=(FONT_FAMILY, 24, "bold"))
        cv.create_text(main_x, main_y+60, text=main_acc[1], fill=C["text"], font=(FONT_FAMILY, 12, "bold"))
        draw_node_limits(main_acc[0], main_x, main_y+84)
        
        # Calculate positions for others in Grid
        for i, (path, label) in enumerate(others):
            col = i % 2
            row = i // 2
            ox = 380 + col * 200
            oy = 100 + row * 160
            
            snap = self.snapshots.get(path)
            plan_name = snap.plan if snap and snap.plan else "Unknown"
            is_pro = plan_name.lower() in ("pro", "prolite", "team", "business")
            
            tag = f"node_{i}"
            tag_type = "blocked_node" if is_pro else "target_node"
            node_tags = ("any_node", tag_type, tag)
            
            # Thiết lập màu sắc và giao diện theo gói Plan
            if is_pro:
                card_bg = C["surface"]
                card_border = "#3a2024"
                circle_border = "#5c2a30"
                badge_text = "PRO • KHÔNG CHO PHÉP"
                badge_color = C["rose"]
            else:
                card_bg = C["surface_2"]
                card_border = C["border"]
                circle_border = C["border_strong"]
                p_lower = plan_name.lower()
                badge_text = "PLUS" if p_lower == "plus" else ("FREE" if p_lower == "free" else plan_name.upper())
                badge_color = "#93C5FD" if p_lower == "plus" else ("#6EE7B7" if p_lower == "free" else C["text_3"])

            # Khung thẻ bao quanh profile
            card_id = cv.create_rectangle(ox-85, oy-35, ox+85, oy+125, fill=card_bg, outline=card_border, width=1, tags=node_tags)
            
            # Huy hiệu Plan
            cv.create_text(ox, oy-20, text=badge_text, fill=badge_color, font=(FONT_FAMILY, 8, "bold"), tags=node_tags)
            
            circle_id = cv.create_oval(ox-25, oy-25, ox+25, oy+25, fill=C["surface"], outline=circle_border, width=2, tags=node_tags)
            cv.create_text(ox, oy, text=(label[:1] or "C").upper(), fill=C["text_2"] if not is_pro else C["text_3"], font=(FONT_FAMILY, 14, "bold"), tags=node_tags)
            cv.create_text(ox, oy+42, text=label, fill=C["text_2"] if not is_pro else C["text_3"], font=(FONT_FAMILY, 11, "bold"), tags=node_tags)
            draw_node_limits(path, ox, oy+64, tag=tag)
            
            self.nexus_nodes.append({
                "path": path,
                "label": label,
                "x": ox,
                "y": oy,
                "card_id": card_id,
                "circle_id": circle_id,
                "tag": tag,
                "idx": i,
                "is_pro": is_pro,
                "plan": plan_name,
            })
            
        # Draw Wire & Glow
        wire_glow = cv.create_line(0, 0, 0, 0, fill=C["indigo_soft"], width=8, smooth=True)
        wire_id = cv.create_line(0, 0, 0, 0, fill=C["indigo_glow"], width=3, smooth=True)
        head_id = cv.create_oval(0, 0, 0, 0, fill=C["emerald"], outline=C["window"], width=2)
        
        def update_wire(end_x, end_y):
            mid_x = (main_x + end_x) / 2
            cv.coords(wire_glow, main_x+40, main_y, mid_x, main_y, mid_x, end_y, end_x-25, end_y)
            cv.coords(wire_id, main_x+40, main_y, mid_x, main_y, mid_x, end_y, end_x-25, end_y)
            cv.coords(head_id, end_x-32, end_y-7, end_x-18, end_y+7)
            
        def snap_to_target():
            if not self.nexus_active_target:
                update_wire(main_x+40, main_y)
                return
            for n in self.nexus_nodes:
                if n["path"] == self.nexus_active_target:
                    update_wire(n["x"], n["y"])
                    cv.itemconfig(n["card_id"], outline=C["emerald"], width=2)
                    cv.itemconfig(n["circle_id"], outline=C["emerald"], width=3)
                else:
                    cv.itemconfig(n["card_id"], outline="#3a2024" if n["is_pro"] else C["border"], width=1)
                    cv.itemconfig(n["circle_id"], outline="#5c2a30" if n["is_pro"] else C["border_strong"], width=2)
                    
        def copy_nexus_file(src_dir: Path, dst_dir: Path) -> tuple[bool, str]:
            src_file = src_dir / "auth.json"
            dst_file = dst_dir / "auth.json"
            try:
                # Nếu file auth.json ở profile Main đã có sẵn thì xóa đi trước
                if dst_file.exists():
                    if dst_file.is_dir():
                        shutil.rmtree(dst_file)
                    else:
                        dst_file.unlink()
            except Exception as e:
                return False, f"Không thể xóa auth.json cũ ở P Main: {e}"

            if not src_file.exists():
                return False, "Không tìm thấy auth.json ở profile nguồn"

            try:
                shutil.copy2(src_file, dst_file)
                return True, "Đã sao chép auth.json sang P Main"
            except Exception as e:
                return False, f"Lỗi copy auth.json: {e}"

        def select_node_by_index(idx):
            if 0 <= idx < len(self.nexus_nodes):
                node_data = self.nexus_nodes[idx]
                if node_data["is_pro"]:
                    # Hiệu ứng cảnh báo khi cố tình bấm vào tài khoản Pro
                    cv.itemconfig(node_data["card_id"], outline=C["rose"], width=2)
                    set_notice(f"⛔ Không cho phép: Profile '{node_data['label']}' là tài khoản PRO! (Chỉ hỗ trợ Plus hoặc Free)", C["rose"])
                    card.after(700, lambda: cv.itemconfig(node_data["card_id"], outline="#3a2024", width=1))
                    return

                self.nexus_active_target = node_data["path"]
                self._save_nexus_target(node_data["path"])
                snap_to_target()
                
                # Thực hiện copy file auth.json từ profile Free/Plus sang Profile Main
                success, sync_msg = copy_nexus_file(node_data["path"], main_acc[0])
                if success:
                    set_notice(f"✓ Đã kết nối với {node_data['label']} ({node_data['plan'].upper()}) • {sync_msg}", C["emerald"])
                else:
                    set_notice(f"✓ Đã kết nối với {node_data['label']} ({node_data['plan'].upper()}) • ⚠️ {sync_msg}", C["amber"])

        def on_click(event):
            # 1. Kiểm tra nếu bấm trực tiếp vào phần tử có tag node_
            items = cv.find_withtag("current")
            if items:
                for t in cv.gettags(items[0]):
                    if t.startswith("node_"):
                        try:
                            idx = int(t.split("_")[1])
                            select_node_by_index(idx)
                            return
                        except ValueError:
                            pass
            # 2. Dự phòng hình học: kiểm tra khoảng cách đến các node
            closest_idx = None
            min_d = 100**2
            for n in self.nexus_nodes:
                d = (n["x"] - event.x)**2 + (n["y"] - event.y)**2
                if d < min_d:
                    min_d = d
                    closest_idx = n["idx"]
            if closest_idx is not None:
                select_node_by_index(closest_idx)

        # Bắt sự kiện click
        cv.tag_bind("any_node", "<ButtonPress-1>", on_click)
        cv.bind("<ButtonPress-1>", on_click)
        
        # Con trỏ bàn tay chỉ hiển thị cho Plus/Free, Pro hiển thị biểu tượng cấm
        def on_enter_target(e): cv.config(cursor="hand2")
        def on_enter_blocked(e): cv.config(cursor="no")
        def on_leave(e): cv.config(cursor="")
        
        cv.tag_bind("target_node", "<Enter>", on_enter_target)
        cv.tag_bind("target_node", "<Leave>", on_leave)
        cv.tag_bind("blocked_node", "<Enter>", on_enter_blocked)
        cv.tag_bind("blocked_node", "<Leave>", on_leave)

        # Kích hoạt snap lần đầu tiên và đồng bộ file nếu có profile hợp lệ
        if self.nexus_active_target:
            copy_nexus_file(self.nexus_active_target, main_acc[0])
        snap_to_target()

    def _render_placeholder_page(self, page: str):
        self._clear_scroll()

        card = ctk.CTkFrame(
            self.scroll,
            fg_color=C["surface"],
            border_width=1,
            border_color=C["border"],
            corner_radius=14,
        )
        card.grid(row=0, column=0, sticky="ew", pady=(8, 0))

        if page == "about":
            ctk.CTkLabel(
                card,
                text=APP_NAME,
                text_color=C["text"],
                font=(FONT_FAMILY, 20, "bold"),
            ).pack(anchor="w", padx=24, pady=(24, 6))

            ctk.CTkLabel(
                card,
                text=f"Version {APP_VERSION}\nDesigned and Crafted with precision by Tuan03.",
                text_color=C["text_2"],
                font=(FONT_FAMILY, 13),
                justify="left",
            ).pack(anchor="w", padx=24, pady=(0, 16))

            ctk.CTkButton(
                card,
                text="Visit GitHub Repository   ↗",
                command=lambda: webbrowser.open(GITHUB_URL),
                width=200,
                height=36,
                corner_radius=8,
                fg_color=C["indigo"],
                hover_color=C["indigo_hover"],
                font=(FONT_FAMILY, 12, "bold"),
            ).pack(anchor="w", padx=24, pady=(0, 24))
        else:
            ctk.CTkLabel(
                card,
                text=f"◈  {page.capitalize()}",
                text_color=C["text"],
                font=(FONT_FAMILY, 18, "bold"),
            ).pack(anchor="w", padx=24, pady=(24, 6))

            ctk.CTkLabel(
                card,
                text="This module is actively being developed for future releases.",
                text_color=C["text_3"],
                font=(FONT_FAMILY, 13),
            ).pack(anchor="w", padx=24, pady=(0, 24))

    # -------------------------------------------------------------------------
    # Account Discovery & Rendering
    # -------------------------------------------------------------------------

    def _load_explicit_accounts(self):
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            result = []
            for item in data.get("accounts", []):
                p = Path(item["path"]).expanduser()
                result.append({"path": p, "label": item.get("label") or p.name})
            return result
        except Exception:
            return []

    def _save_explicit_accounts(self):
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            data = {}
            if self.state_file.is_file():
                try:
                    data = json.loads(self.state_file.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            data["accounts"] = [
                {"path": str(item["path"]), "label": item["label"]}
                for item in self.explicit_accounts
            ]
            self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_nexus_target(self) -> Path | None:
        try:
            if not self.state_file.is_file():
                return None
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            target_str = data.get("nexus_linked_profile")
            if target_str:
                p = Path(target_str).expanduser()
                if p.is_dir():
                    return p.resolve()
        except Exception:
            pass
        return None

    def _save_nexus_target(self, target_path: Path | None):
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            data = {}
            if self.state_file.is_file():
                try:
                    data = json.loads(self.state_file.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            data["nexus_linked_profile"] = str(target_path.resolve()) if target_path else None
            self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def discover_accounts(self) -> list[tuple[Path, str]]:
        found: dict[Path, str] = {}
        home = Path.home()

        # --- Auto-create Tuan03 Main Profile ---
        tuan03_profile = home / ".codex-tuan03"
        if not tuan03_profile.exists():
            try:
                tuan03_profile.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass


        default = home / ".codex"
        if default.is_dir():
            found[default.resolve()] = "Default"

        try:
            for p in sorted(home.glob(".codex-*"), key=lambda x: x.name.lower()):
                if p.is_dir():
                    label = p.name[len(".codex-"):] or p.name
                    found[p.resolve()] = label
        except Exception:
            pass

        for item in self.explicit_accounts:
            p = item["path"]
            if p.is_dir():
                found[p.resolve()] = item["label"]

        return list(found.items())

    def _clear_scroll(self):
        for widget in self.scroll.winfo_children():
            widget.destroy()
        self.account_cards.clear()

    def discover_and_render(self):
        if self.current_page != "accounts":
            return

        all_accounts = self.discover_accounts()

        # Apply Filters (Search Query + Plan)
        filtered_accounts = []
        for path, label in all_accounts:
            snap = self.snapshots.get(path)
            email = snap.email if snap else ""
            plan = snap.plan if snap else "Unknown"

            if self.search_query:
                q = self.search_query
                match = (
                    q in label.lower()
                    or q in email.lower()
                    or q in str(path).lower()
                )
                if not match:
                    continue

            if self.plan_filter not in {"All Plans", "All", ""}:
                if plan.lower() != self.plan_filter.lower():
                    continue

            filtered_accounts.append((path, label))

        # --- Pin Tuan03 Main Profile to Top ---
        filtered_accounts.sort(
            key=lambda x: (
                0 if x[1].lower() == "tuan03" or x[0].name == ".codex-tuan03" else 1,
                x[1].lower()
            )
        )

        self.accounts_badge.configure(
            text=f"{len(filtered_accounts)} of {len(all_accounts)} profiles"
        )

        if self.codex_bin:
            self.system_badge.configure(
                text="● Codex Ready",
                fg_color=C["emerald_soft"],
                text_color=C["emerald"],
                border_color=C["emerald"],
            )
        else:
            self.system_badge.configure(
                text="● CLI Not Found",
                fg_color=C["rose_soft"],
                text_color=C["rose"],
                border_color=C["rose"],
            )

        self._clear_scroll()

        if not filtered_accounts:
            self._render_empty_state()
            return

        GRID_COLS = 3
        for idx, (path, label) in enumerate(filtered_accounts):
            snap = self.snapshots.get(path)
            if not snap:
                snap = AccountSnapshot(home=path, label=label)
            snap.label = label

            row = idx // GRID_COLS
            col = idx % GRID_COLS

            card = AccountCard(self.scroll, self, snap)
            card.grid(row=row, column=col, sticky="nsew", pady=6, padx=6)
            self.account_cards[path] = card

    def _render_empty_state(self):
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=C["surface"],
            border_width=1,
            border_color=C["border"],
            corner_radius=14,
        )
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        ctk.CTkLabel(
            card,
            text="No matching profiles found",
            text_color=C["text"],
            font=(FONT_FAMILY, 16, "bold"),
        ).pack(anchor="w", padx=24, pady=(24, 4))

        ctk.CTkLabel(
            card,
            text="Create an isolated CODEX_HOME or adjust your search filter to continue.",
            text_color=C["text_3"],
            font=(FONT_FAMILY, 12),
        ).pack(anchor="w", padx=24)

        ctk.CTkButton(
            card,
            text="+  Create New Profile",
            command=self.add_account,
            width=160,
            height=34,
            corner_radius=8,
            fg_color=C["indigo"],
            hover_color=C["indigo_hover"],
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(anchor="w", padx=24, pady=(16, 24))

    def _rerender_one(self, snap: AccountSnapshot):
        if self.current_page != "accounts":
            return

        old = self.account_cards.get(snap.home)
        if not old:
            self.discover_and_render()
            return

        grid = old.grid_info()
        old.destroy()

        card = AccountCard(self.scroll, self, snap)
        card.grid(**grid)
        self.account_cards[snap.home] = card

    # -------------------------------------------------------------------------
    # Threaded Refresh
    # -------------------------------------------------------------------------

    def refresh_all(self):
        if not self.codex_bin:
            messagebox.showerror(
                APP_NAME,
                "Codex CLI was not found in PATH.\n\n"
                "Please run `codex --version` in terminal first.",
            )
            return

        accounts = self.discover_accounts()
        if not accounts:
            return

        self.refresh_btn.configure(text="Syncing…", state="disabled")

        pending = {"count": len(accounts)}
        lock = threading.Lock()

        for path, label in accounts:
            future = self.executor.submit(snapshot_for, path, label, self.codex_bin)

            def done(fut, path=path):
                try:
                    snap = fut.result()
                except Exception as exc:
                    snap = AccountSnapshot(
                        home=path,
                        label=path.name,
                        error=str(exc),
                        refreshed_at=time.time(),
                    )

                def apply():
                    self.snapshots[path] = snap
                    self._rerender_one(snap)

                    with lock:
                        pending["count"] -= 1
                        left = pending["count"]

                    if left <= 0:
                        self.refresh_btn.configure(text="↻  Sync Quotas", state="normal")
                        self.system_badge.configure(
                            text=f"● Synced {now_display()}",
                            fg_color=C["emerald_soft"],
                            text_color=C["emerald"],
                            border_color=C["emerald"],
                        )

                self.after(0, apply)

            future.add_done_callback(done)

    def refresh_one(self, home: Path):
        if not self.codex_bin:
            return

        label = self._label_for(home)
        future = self.executor.submit(snapshot_for, home, label, self.codex_bin)

        def done(fut):
            try:
                snap = fut.result()
            except Exception as exc:
                snap = AccountSnapshot(
                    home=home,
                    label=label,
                    error=str(exc),
                    refreshed_at=time.time(),
                )

            self.after(0, lambda: self._apply_single_snapshot(snap))

        future.add_done_callback(done)

    def _apply_single_snapshot(self, snap: AccountSnapshot):
        self.snapshots[snap.home] = snap
        self._rerender_one(snap)

    def _label_for(self, home: Path) -> str:
        for path, label in self.discover_accounts():
            if path == home:
                return label
        return home.name

    # -------------------------------------------------------------------------
    # Account Actions & Context Menu
    # -------------------------------------------------------------------------

    def show_account_menu(self, snap: AccountSnapshot, button: ctk.CTkButton):
        menu = tk.Menu(
            self,
            tearoff=0,
            font=(FONT_FAMILY, 10),
            bg="#18181E",
            fg=C["text"],
            activebackground=C["indigo"],
            activeforeground="#FFFFFF",
            relief="solid",
            bd=1,
        )

        is_main = snap.home.name == ".codex-tuan03" or snap.label.lower() == "tuan03"

        menu.add_command(label=">_ Launch Codex Terminal", command=lambda: self.open_codex(snap))
        menu.add_command(label="↻  Refresh Rate Limits", command=lambda: self.refresh_one(snap.home))
        
        if not is_main:
            menu.add_separator()
            menu.add_command(label="🔑 Authenticate / Change Account", command=lambda: self.login_account(snap))
            if snap.email != "Not signed in":
                menu.add_command(label="🚪 Logout from Profile", command=lambda: self.logout_account(snap))

        menu.add_separator()
        menu.add_command(label="📁 Open CODEX_HOME Folder", command=lambda: self.open_folder(snap.home))
        menu.add_command(label="📋 Copy CODEX_HOME Path", command=lambda: self.copy_to_clipboard(str(snap.home)))
        
        if not is_main:
            menu.add_separator()
            menu.add_command(label="🗑️ Delete Profile...", command=lambda: self.delete_profile(snap))

        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def open_folder(self, path: Path):
        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def open_codex(self, snap: AccountSnapshot):
        if not self.codex_bin:
            messagebox.showerror(APP_NAME, "Codex CLI was not found in PATH.")
            return

        if not snap.home.exists():
            messagebox.showerror(APP_NAME, f"CODEX_HOME does not exist:\n{snap.home}")
            return

        self._launch_terminal(snap.home, [], f"Codex - {snap.label}")

    def login_account(self, snap: AccountSnapshot):
        self._launch_terminal(snap.home, ["login"], f"Codex Login - {snap.label}")

    def logout_account(self, snap: AccountSnapshot):
        if not self.codex_bin:
            messagebox.showerror(APP_NAME, "Codex CLI was not found in PATH.")
            return

        account_name = snap.email if snap.email not in {"Loading…", "Not signed in"} else snap.label

        confirmed = messagebox.askyesno(
            "Logout Account",
            f"Log out this Codex profile?\n\n"
            f"Account: {account_name}\n"
            f"CODEX_HOME: {snap.home}\n\n"
            "Only credentials stored under this profile will be cleared.",
            parent=self,
        )

        if not confirmed:
            return

        self.system_badge.configure(
            text="● Logging out…",
            fg_color=C["amber_soft"],
            text_color=C["amber"],
            border_color=C["amber"],
        )

        def worker():
            env = os.environ.copy()
            env["CODEX_HOME"] = str(snap.home)

            flags = 0
            if os.name == "nt":
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            try:
                result = subprocess.run(
                    codex_process_args(self.codex_bin, "logout"),
                    env=env,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                    creationflags=flags,
                )

                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "").strip()
                    raise RuntimeError(detail or f"codex logout exited with code {result.returncode}")

            except Exception as exc:
                self.after(0, lambda e=str(exc): self._logout_failed(snap, e))
                return

            self.after(0, lambda: self._logout_finished(snap))

        threading.Thread(target=worker, daemon=True).start()

    def _logout_finished(self, snap: AccountSnapshot):
        self.system_badge.configure(
            text="● Logged Out",
            fg_color=C["emerald_soft"],
            text_color=C["emerald"],
            border_color=C["emerald"],
        )
        messagebox.showinfo(
            "Logout complete",
            f"Successfully logged out:\n{snap.email}\n\n"
            f"Profile folder was kept intact:\n{snap.home}",
            parent=self,
        )
        self.refresh_one(snap.home)

    def _logout_failed(self, snap: AccountSnapshot, error: str):
        self.system_badge.configure(
            text="● Logout Failed",
            fg_color=C["rose_soft"],
            text_color=C["rose"],
            border_color=C["rose"],
        )
        messagebox.showerror(
            "Logout failed",
            f"Could not log out this profile:\n\n{error}",
            parent=self,
        )

    def delete_profile(self, snap: AccountSnapshot):
        home = snap.home.resolve()
        default_home = (Path.home() / ".codex").resolve()
        account_name = snap.email if snap.email not in {"Loading…", "Not signed in"} else snap.label

        warning = (
            "Permanently delete this local Codex profile?\n\n"
            f"Account: {account_name}\n"
            f"CODEX_HOME: {home}\n\n"
            "This will delete all local configuration, session logs, auth.json, and cache files.\n"
            "Your OpenAI cloud account is not affected."
        )

        if home == default_home:
            warning += "\n\n⚠️ WARNING: This is the DEFAULT .codex profile."

        if not messagebox.askyesno("Delete Codex Profile", warning, parent=self):
            return

        confirm_text = simpledialog.askstring(
            "Confirm Deletion",
            "Type DELETE to permanently remove this profile:",
            parent=self,
        )

        if confirm_text != "DELETE":
            if confirm_text is not None:
                messagebox.showinfo("Cancelled", "Confirmation text did not match DELETE.", parent=self)
            return

        self.system_badge.configure(
            text="● Deleting Profile…",
            fg_color=C["amber_soft"],
            text_color=C["amber"],
            border_color=C["amber"],
        )

        def worker():
            logout_error = None
            if self.codex_bin:
                env = os.environ.copy()
                env["CODEX_HOME"] = str(home)
                flags = 0
                if os.name == "nt":
                    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

                try:
                    subprocess.run(
                        codex_process_args(self.codex_bin, "logout"),
                        env=env,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30,
                        creationflags=flags,
                    )
                except Exception as exc:
                    logout_error = str(exc)

            try:
                if home.exists():
                    safe_rmtree(home)
            except Exception as exc:
                self.after(0, lambda e=str(exc), le=logout_error: self._delete_profile_failed(snap, e, le))
                return

            self.after(0, lambda le=logout_error: self._delete_profile_finished(snap, le))

        threading.Thread(target=worker, daemon=True).start()

    def _delete_profile_finished(self, snap: AccountSnapshot, logout_error: str | None):
        resolved = snap.home.resolve()

        self.explicit_accounts = [
            item for item in self.explicit_accounts if item["path"].resolve() != resolved
        ]
        self._save_explicit_accounts()

        self.snapshots.pop(resolved, None)
        self.account_cards.pop(resolved, None)

        try:
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", snap.home.name)
            launcher = self.state_dir / "launchers" / f"launch_{safe_name}.ps1"
            if launcher.exists():
                launcher.unlink()
        except Exception:
            pass

        self.system_badge.configure(
            text="● Profile Deleted",
            fg_color=C["emerald_soft"],
            text_color=C["emerald"],
            border_color=C["emerald"],
        )

        messagebox.showinfo(
            "Profile Deleted",
            f"Successfully deleted local profile:\n{snap.home}",
            parent=self,
        )
        self.discover_and_render()

    def _delete_profile_failed(self, snap: AccountSnapshot, error: str, logout_error: str | None):
        self.system_badge.configure(
            text="● Delete Failed",
            fg_color=C["rose_soft"],
            text_color=C["rose"],
            border_color=C["rose"],
        )
        detail = f"Could not delete:\n{snap.home}\n\n{error}"
        if logout_error:
            detail += f"\n\nLogout reported:\n{logout_error}"
        messagebox.showerror("Delete profile failed", detail, parent=self)

    def add_account(self):
        name = simpledialog.askstring(
            "New Codex Profile",
            "Enter profile name (e.g. Work, Team-Beta, Personal):",
            parent=self,
        )

        if name is None:
            return

        name = name.strip()
        if not name:
            return

        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
        if not slug:
            messagebox.showerror(APP_NAME, "Please use alphanumeric characters for the label.")
            return

        path = Path.home() / f".codex-{slug}"

        if path.exists() and any(path.iterdir()):
            use_existing = messagebox.askyesno(
                APP_NAME,
                f"{path} already exists and is not empty.\n\n"
                "Use this existing CODEX_HOME directory?",
            )
            if not use_existing:
                return
        else:
            path.mkdir(parents=True, exist_ok=True)
            default_config = Path.home() / ".codex" / "config.toml"

            if default_config.is_file():
                copy_config = messagebox.askyesno(
                    APP_NAME,
                    "Copy settings from default .codex (config.toml)?\n\n"
                    "Only configuration is copied. auth.json is never copied.",
                )
                if copy_config:
                    try:
                        shutil.copy2(default_config, path / "config.toml")
                    except Exception as exc:
                        messagebox.showwarning(APP_NAME, f"Could not copy config.toml:\n{exc}")

        resolved = path.resolve()
        existing = next((item for item in self.explicit_accounts if item["path"].resolve() == resolved), None)

        if existing:
            existing["label"] = name
        else:
            self.explicit_accounts.append({"path": resolved, "label": name})

        self._save_explicit_accounts()
        self.discover_and_render()

        messagebox.showinfo(
            APP_NAME,
            "A terminal session will open.\n\n"
            "Complete `codex login` in the terminal to authenticate.",
        )

        self._launch_terminal(resolved, ["login"], f"Codex Login - {name}")

    def _launch_terminal(self, codex_home: Path, codex_args: list[str], title: str):
        codex_home.mkdir(parents=True, exist_ok=True)

        if not self.codex_bin:
            messagebox.showerror(APP_NAME, "Codex CLI was not found in PATH.")
            return

        working_dir = Path.cwd()
        launch_dir = self.state_dir / "launchers"
        launch_dir.mkdir(parents=True, exist_ok=True)

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", codex_home.name)
        script_path = launch_dir / f"launch_{safe_name}.ps1"

        arg_text = " ".join(ps_quote(str(arg)) for arg in codex_args)

        script = (
            f"$env:CODEX_HOME = {ps_quote(str(codex_home))}\n"
            f"Set-Location {ps_quote(str(working_dir))}\n"
            f"$Host.UI.RawUI.WindowTitle = {ps_quote(title)}\n"
            f"& {ps_quote(str(self.codex_bin))}"
        )

        if arg_text:
            script += f" {arg_text}"

        script += "\n"
        script_path.write_text(script, encoding="utf-8-sig")

        try:
            powershell = (
                shutil.which("pwsh.exe")
                or shutil.which("powershell.exe")
                or "powershell.exe"
            )

            wt = shutil.which("wt.exe") or shutil.which("wt")

            if wt:
                subprocess.Popen(
                    [
                        wt,
                        "new-tab",
                        "--title",
                        title,
                        powershell,
                        "-NoExit",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(script_path),
                    ],
                    cwd=str(working_dir),
                )
                return

            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                [
                    powershell,
                    "-NoExit",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                cwd=str(working_dir),
                creationflags=flags,
            )

        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open terminal:\n{exc}")

    def _on_close(self):
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        self.destroy()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    if os.name != "nt":
        raise SystemExit("Codex Profile Manager is designed for Windows.")

    if "--self-test-tk" in sys.argv:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return

    app = CodexAccountManager()
    app.mainloop()


if __name__ == "__main__":
    main()
