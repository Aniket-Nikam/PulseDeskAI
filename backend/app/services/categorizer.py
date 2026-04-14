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
