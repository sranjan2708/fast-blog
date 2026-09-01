from sqlalchemy import Column, Integer, ForeignKey
from database import Base


class PostCategory(Base):
    __tablename__ = "post_categories"

    post_id = Column(
        Integer,
        ForeignKey("posts.id"),
        primary_key=True
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        primary_key=True
    )