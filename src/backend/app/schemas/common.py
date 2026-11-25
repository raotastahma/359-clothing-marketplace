from __future__ import annotations

import re

from pydantic import BaseModel

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
