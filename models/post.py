from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from database import Base
from models.post_category import PostCategory
from models.post_tag import PostTag


class Post(Base):
    __tablename__ = "posts"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    slug = Column(
        String(250),
        unique=True,
        nullable=False,
        index=True
    )

    title = Column(
        String(200),
        nullable=False
    )

    content = Column(
        String(5000),
        nullable=False
    )

    status = Column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    views = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="posts"
    )

    comments = relationship(
        "Comment",
        back_populates="post"
    )

    categories = relationship(
        "Category",
        secondary=PostCategory.__table__,
        back_populates="posts"
    )

    tags = relationship(
        "Tag",
        secondary=PostTag.__table__,
        back_populates="posts"
    )