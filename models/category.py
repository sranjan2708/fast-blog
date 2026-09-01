from sqlalchemy import Column, Integer, String
from database import Base
from sqlalchemy.orm import relationship


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True
    )

    posts = relationship(
    "Post",
    secondary="post_categories",
    back_populates="categories"
    )