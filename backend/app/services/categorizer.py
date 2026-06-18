"""
Rule-based app categorizer.
Maps app names / process names to productivity categories.
No ML — pure string matching.

Windows process names arrive title-cased from psutil via the agent:
  "netflix.exe" -> "Netflix"
  "epicgameslauncher.exe" -> "Epicgameslauncher"
  "discord.exe" -> "Discord"
So keywords must match the title-cased or lowercased form.

Priority: first match wins. More specific patterns come first.
"""

from functools import lru_cache
from typing import Optional

# Default category mappings (keyword → category)
APP_CATEGORY_RULES: list[tuple[list[str], str]] = [
    # ── Development ──────────────────────────────────────────────────────────
    (["vscode", "visual studio", "visual studio code", "code",
      "intellij", "pycharm", "webstorm", "xcode",
      "sublime text", "sublime", "vim", "neovim", "emacs",
      "cursor", "zed", "android studio", "rider", "clion",
      "goland", "phpstorm", "rubymine", "datagrip"], "development"),
    (["terminal", "iterm", "cmd", "powershell", "bash", "zsh",
      "konsole", "gnome-terminal", "gnome terminal", "wt",   # Windows Terminal
      "alacritty", "warp", "hyper", "conhost", "windowsterminal"], "development"),
    (["github", "gitlab", "bitbucket", "sourcetree", "gitkraken", "fork"], "development"),
    (["postman", "insomnia", "tableplus", "datagrip", "sequel pro",
      "pgadmin", "dbeaver", "mongodb compass", "redis insight"], "development"),
    (["figma", "sketch", "adobe xd", "invision", "zeplin", "framer"], "design"),
    (["photoshop", "illustrator", "premiere", "after effects", "lightroom",
      "davinci resolve", "davinci", "final cut", "canva", "inkscape",
      "gimp", "affinity"], "creative"),
    (["word", "google docs", "pages", "libreoffice writer", "writer"], "writing"),
    (["excel", "google sheets", "numbers", "libreoffice calc",
      "libre office", "libreoffice", "tableau", "power bi", "looker"], "data"),
    (["powerpoint", "google slides", "keynote", "prezi", "impress"], "presentation"),
    (["jira", "linear", "asana", "trello", "monday", "clickup", "basecamp",
      "notion", "height", "shortcut", "plane"], "project management"),
    (["slack", "teams", "microsoft teams", "discord", "zoom", "meet",
      "webex", "skype", "loom", "around", "gather", "whereby"], "communication"),
    (["gmail", "outlook", "apple mail", "thunderbird", "spark",
      "hey", "mailspring", "mail"], "email"),
    (["notion", "obsidian", "roam", "logseq", "bear", "craft",
      "onenote", "evernote", "joplin", "standard notes"], "notes"),
    (["confluence", "sharepoint", "nuclino", "slab", "coda",
      "tettra", "guru", "helpjuice"], "documentation"),

    # ── Browsers (neutral) ────────────────────────────────────────────────────
    (["chrome", "firefox", "safari", "edge", "brave", "arc",
      "opera", "vivaldi", "msedge"], "browser"),

    # ── Entertainment / Streaming ─────────────────────────────────────────────
    # Include both web names AND Windows process names (title-cased by agent)
    (["netflix", "netflix.exe",
      "youtube", "youtubemusic",
      "spotify", "spotify.exe",
      "apple music", "itunes",
      "twitch", "twitch.exe",
      "hulu", "disney", "disney+", "disneyplus",
      "primevideo", "prime video", "amazon prime",
      "hbomax", "max", "peacock", "paramountplus",
      "vlc", "mpv", "mpc-hc", "mpc hc", "kmplayer", "potplayer",
      "plex", "jellyfin", "emby",
      "crunchyroll", "funimation",
      "soundcloud", "deezer", "tidal", "pandora"], "entertainment"),

    # ── Gaming ────────────────────────────────────────────────────────────────
    # Actual process names on Windows get title-cased: "steam.exe" -> "Steam"
    (["steam", "steam.exe",
      "epic games", "epicgameslauncher", "epicgames",
      "battle.net", "battlenet", "blizzard",
      "gog", "gog galaxy",
      "origin", "ea desktop", "ea app",
      "ubisoft connect", "uplay",
      "xbox", "xbox app", "gamebar", "game bar",
      "valorant", "valorant.exe",
      "minecraft", "minecraftlauncher",
      "fortnite", "fortniteclient",
      "league of legends", "leagueoflegends",
      "roblox", "robloxplayerbeta",
      "counter-strike", "csgo", "cs2",
      "dota2", "dota 2",
      "overwatch", "overwatch2",
      "pubg", "apexlegends", "apex legends",
      "genshin", "genshinimpact",
      "cyberpunk", "elden ring", "eldenring",
      "geforce now", "nvidia geforce"], "gaming"),

    # ── Social Media ──────────────────────────────────────────────────────────
    (["twitter", "x.com", "x app",
      "instagram",
      "facebook", "messenger",
      "tiktok",
      "reddit",
      "linkedin",
      "pinterest",
      "snapchat",
      "whatsapp",
      "telegram", "signal"], "social media"),

    # ── System (low priority) ─────────────────────────────────────────────────
    (["finder", "explorer", "files",
      "system preferences", "system settings",
      "activity monitor", "task manager", "taskmgr",
      "control panel", "settings", "regedit",
      "calculator", "calc",
      "clock"], "system"),
]


@lru_cache(maxsize=1024)
def categorize_app(app_name: str) -> Optional[str]:
    """
    Returns a category string for the given app name, or 'other' if unknown.
    Case-insensitive substring match. LRU-cached for performance.
    """
    if not app_name:
        return None

    lower = app_name.lower().strip()
    # Strip .exe suffix that agent may still pass through
    if lower.endswith(".exe"):
        lower = lower[:-4]

    for keywords, category in APP_CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return category

    return "other"


def is_productive_category(category: Optional[str]) -> bool:
    productive = {
        "development", "design", "creative", "writing", "data",
        "presentation", "project management", "email", "notes",
        "documentation",
    }
    return category in productive


def is_distraction_category(category: Optional[str]) -> bool:
    distractions = {"entertainment", "gaming", "social media"}
    return category in distractions


import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.ai.providers.factory import get_active_provider
from app.core.logging import get_logger

log = get_logger("smart_categorizer")

_smart_categories_cache: dict[str, str] = {}
_pending_categorizations: set[str] = set()

SYSTEM_PROMPT = """You are an expert software app and window title categorizer.
You must categorize a given application process name and its active window title into one of the following exact categories:
- development (terminals, editors, git tools, databases)
- design (figma, sketch, etc.)
- creative (video/audio editing, canvas, image tools)
- writing (word processors, docs)
- data (spreadsheets, BI tools)
- presentation (slides)
- project management (jira, asana, monday, notion)
- communication (slack, teams, zoom)
- email (gmail, outlook)
- notes (obsidian, craft, onenote)
- documentation (confluence, sharepoint)
- entertainment (netflix, youtube, spotify)
- gaming (steam, games)
- social media (twitter, facebook, reddit)
- system (file explorer, settings, clock)
- other (any other generic or unidentifiable app)

Respond with ONLY the category name. Do not include any explanation, headers, or punctuation."""

ALLOWED_CATEGORIES = {
    "development", "design", "creative", "writing", "data", "presentation",
    "project management", "communication", "email", "notes", "documentation",
    "entertainment", "gaming", "social media", "system", "other"
}

async def _run_smart_categorization(app_name: str, window_title: Optional[str]):
    try:
        from app.core.config import settings
        if not settings.AI_ENABLED:
            return

        provider = get_active_provider()
        prompt = f"App Name: {app_name}\nWindow Title: {window_title or ''}"
        
        category_raw = await provider.generate_text(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=20
        )
        
        category = category_raw.strip().lower()
        if category not in ALLOWED_CATEGORIES:
            category = "other"
            
        _smart_categories_cache[app_name] = category
        log.info("app_categorized_by_ai", app=app_name, category=category)

        # Update database records
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE activity_events SET app_category = :cat WHERE active_app = :app AND app_category = 'other'"),
                {"cat": category, "app": app_name}
            )
            await db.execute(
                text("UPDATE app_usage_daily SET app_category = :cat WHERE app_name = :app AND app_category = 'other'"),
                {"cat": category, "app": app_name}
            )
            await db.commit()
            
    except Exception as e:
        log.warning("smart_categorization_failed", app=app_name, error=str(e))
    finally:
        _pending_categorizations.discard(app_name)

def trigger_smart_categorization(app_name: str, window_title: Optional[str]):
    if app_name in _smart_categories_cache or app_name in _pending_categorizations:
        return
    from app.core.config import settings
    if not settings.AI_ENABLED:
        return
    _pending_categorizations.add(app_name)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run_smart_categorization(app_name, window_title))
    except RuntimeError:
        import threading
        def run_in_thread():
            asyncio.run(_run_smart_categorization(app_name, window_title))
        threading.Thread(target=run_in_thread, daemon=True).start()

