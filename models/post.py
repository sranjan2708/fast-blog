from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from database import Base
from models.post_category import PostCategory


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
        server_default="draft"
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
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
        nullable=False
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