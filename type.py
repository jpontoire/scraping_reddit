from typing import List, Optional, Dict, Tuple, Iterable

from dataclasses import dataclass
from casanova import TabularRecord

@dataclass
class RedditPost(TabularRecord):
    title: str
    url: str
    author: str
    author_text: str
    upvote: str
    published_date: str
    link: Optional[str]


@dataclass
class RedditComment(TabularRecord):
    author: str
    parent: str
    points: Optional[str]
    published_date: str
    comment: str
