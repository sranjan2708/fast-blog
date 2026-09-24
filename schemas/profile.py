from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):

    username: str = Field(
        min_length=3,
        max_length=50
    )

    bio: str | None = Field(
        default=None,
        max_length=500
    )