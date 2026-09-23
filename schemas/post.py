from pydantic import BaseModel, Field


class PostCreate(BaseModel):

    title: str = Field(
        min_length=1,
        max_length=200
    )

    content: str = Field(
        min_length=1,
        max_length=5000
    )

    status: str = Field(
        default="draft"
    )

    category_ids: list[int] = Field(
        default_factory=list
    )

    tag_ids: list[int] = Field(
        default_factory=list
    )


class PostUpdate(BaseModel):

    title: str = Field(
        min_length=1,
        max_length=200
    )

    content: str = Field(
        min_length=1,
        max_length=5000
    )

    status: str = Field(
        default="draft"
    )

    category_ids: list[int] = Field(
        default_factory=list
    )

    tag_ids: list[int] = Field(
        default_factory=list
    )