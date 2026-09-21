from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True
    )

    email = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True
    )

    password = Column(
        String(255),
        nullable=False
    )

    bio = Column(
        String(500),
        nullable=True
    )

    role = Column(
        String(20),
        nullable=False,
        default="user"
    )

    posts = relationship(
        "Post",
        back_populates="user"
    )

    comments = relationship(
        "Comment",
        back_populates="user"
    )

    auth_sessions = relationship(
        "UserSession",
        back_populates="user"
    )