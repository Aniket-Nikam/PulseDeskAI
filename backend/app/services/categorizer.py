"""
Rule-based app categorizer.
Maps app names to productivity categories.
No ML — pure string matching with configurable rules.
Admins can add custom ProductivityRules via the API.
"""

from functools import lru_cache
from typing import Optional

# Default category mappings (keyword → category)
# Priority: first match wins. More specific patterns should come first.
APP_CATEGORY_RULES: list[tuple[list[str], str]] = [
    # Productivity tools
    (["vscode", "visual studio", "intellij", "pycharm", "webstorm", "xcode",
      "sublime text", "vim", "neovim", "emacs", "cursor", "zed"], "development"),
    (["terminal", "iterm", "cmd", "powershell", "bash", "zsh", "konsole",
      "gnome-terminal", "alacritty", "warp"], "development"),
    (["figma", "sketch", "adobe xd", "invision", "zeplin", "framer"], "design"),
    (["photoshop", "illustrator", "premiere", "after effects", "lightroom",
      "davinci resolve", "final cut", "canva"], "creative"),
    (["word", "google docs", "pages", "libreoffice writer", "notion"], "writing"),
    (["excel", "google sheets", "numbers", "libreoffice calc", "tableau",
      "power bi", "looker"], "data"),
    (["powerpoint", "google slides", "keynote", "prezi"], "presentation"),
    (["jira", "linear", "asana", "trello", "monday", "clickup", "basecamp"], "project management"),
    (["slack", "teams", "discord", "zoom", "meet", "webex", "skype",
      "loom", "around"], "communication"),
    (["gmail", "outlook", "apple mail", "thunderbird", "spark", "hey"], "email"),
    (["github", "gitlab", "bitbucket", "sourcetree", "gitkraken"], "development"),
    (["postman", "insomnia", "tableplus", "datagrip", "sequel pro", "pgadmin"], "development"),
    (["notion", "obsidian", "roam", "logseq", "bear", "craft"], "notes"),
    (["confluence", "sharepoint", "nuclino", "slab", "coda"], "documentation"),

    # Browsers (neutral — can be work or distraction)
    (["chrome", "firefox", "safari", "edge", "brave", "arc"], "browser"),

    # Entertainment / distractions
    (["youtube", "netflix", "spotify", "apple music", "twitch", "hulu",
      "disney+", "prime video", "vlc", "mpv"], "entertainment"),
    (["steam", "epic games", "battle.net", "gog", "origin", "valorant",
      "minecraft", "fortnite", "league of legends"], "gaming"),
    (["twitter", "x.com", "instagram", "facebook", "tiktok", "reddit",
      "linkedin", "pinterest"], "social media"),

    # System
    (["finder", "explorer", "files", "system preferences", "system settings",
      "activity monitor", "task manager", "control panel"], "system"),
]


@lru_cache(maxsize=512)
def categorize_app(app_name: str) -> Optional[str]:
    """
    Returns a category string for the given app name, or None if unknown.
    Case-insensitive substring match.
    """
    if not app_name:
        return None

    lower = app_name.lower().strip()

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
