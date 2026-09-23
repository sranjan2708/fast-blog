from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from database import Base
from models.post_tag import PostTag


class Tag(Base):
    __tablename__ = "tags"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True
    )

    posts = relationship(
        "Post",
        secondary=PostTag.__table__,
        back_populates="tags"
    )