from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterListing:
    position: int
    url: str
    toc_title: str


@dataclass(frozen=True)
class Chapter:
    index: int
    url: str
    title: str
    body: str

