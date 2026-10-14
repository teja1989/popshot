"""Library links (content.py): one canonical form, and a clear no for anything unsafe."""

import pytest

from popshot_api.content import BadLinkError, normalise_host, normalise_link

VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "link",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
        "https://m.youtube.com/watch?feature=share&v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?si=abc",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "  https://WWW.YouTube.com/watch?v=dQw4w9WgXcQ#comments  ",
    ],
)
def test_youtube_links_become_one_address(link: str) -> None:
    assert normalise_link(link) == VIDEO


def test_other_sites_keep_their_path_and_lose_the_fragment() -> None:
    assert normalise_link("https://Example.org/drills/drop?x=1#top") == (
        "https://example.org/drills/drop?x=1"
    )
    assert normalise_link("https://example.org") == "https://example.org/"


@pytest.mark.parametrize(
    "link",
    [
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "javascript:alert(1)",
        "data:text/html,hi",
        "//www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://user:pass@www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://evil.com@www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/@somechannel",
        "https://youtu.be/",
        "https://exa mple.org/",
        "https://example.org/\nnext",
        "https://localhost/",
        "https:///nohost",
        "ftp://example.org/",
    ],
)
def test_unsafe_or_unclear_links_are_refused(link: str) -> None:
    with pytest.raises(BadLinkError):
        normalise_link(link)


def test_hosts() -> None:
    assert normalise_host(" Coach.Example.ORG ") == "coach.example.org"
    for bad in (
        "localhost",
        "https://example.org",
        "example.org/path",
        "exa_mple.org",
        "a" * 99 + ".org",
    ):
        with pytest.raises(BadLinkError):
            normalise_host(bad)
