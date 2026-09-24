from typing import Literal
from pydantic import BaseModel, Field


class PreferencesUpdate(BaseModel):

    theme: Literal["light", "dark"] = Field(
        default="light"
    )

    posts_per_page: int = Field(
        default=10,
        ge=5,
        le=50
    )