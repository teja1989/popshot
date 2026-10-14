"""Links for the content library (migration 0033): checked and tidied before they're stored.

The database has the last word (an allowed https host, by trigger); this turns what an admin
pastes into one canonical form first, so the same video can't be added twice under two
addresses, and gives a clear reason when a link won't do.
"""

import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


class BadLinkError(ValueError):
    """A link that can't go in the library, with a reason an admin can act on."""


def _youtube_id(host: str, path: str, query: str) -> str | None:
    if host == "youtu.be":
        candidate = path.strip("/").split("/")[0]
    elif path == "/watch":
        candidate = (parse_qs(query).get("v") or [""])[0]
    elif path.startswith(("/shorts/", "/embed/", "/live/")):
        candidate = path.split("/")[2]
    else:
        return None
    return candidate if _VIDEO_ID.match(candidate) else None


def normalise_link(link: str) -> str:
    """The canonical form of a link, or BadLinkError. YouTube videos become
    https://www.youtube.com/watch?v=<id>; other links lose their #fragment."""
    link = link.strip()
    if any(c.isspace() or ord(c) < 32 for c in link):
        raise BadLinkError("A link can't contain spaces.")
    parts = urlsplit(link)
    if parts.scheme != "https":
        raise BadLinkError("Links have to start with https://.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise BadLinkError("Links can't include a user name or password.")
    if ":" in parts.netloc:
        raise BadLinkError("Links can't include a port.")
    host = parts.netloc.lower()
    if not _HOST.match(host):
        raise BadLinkError("That doesn't look like a web address.")
    if host in YOUTUBE_HOSTS:
        video = _youtube_id(host, parts.path, parts.query)
        if video is None:
            raise BadLinkError("Use a link to one YouTube video.")
        return f"https://www.youtube.com/watch?v={video}"
    return urlunsplit(("https", host, parts.path or "/", parts.query, ""))


def normalise_host(host: str) -> str:
    host = host.strip().lower()
    if not _HOST.match(host) or len(host) > 100:
        raise BadLinkError("Use a site's name, like www.example.com.")
    return host
