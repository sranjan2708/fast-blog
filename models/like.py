from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    post_id = Column(
        Integer,
        ForeignKey("posts.id"),
        nullable=False
    )

    user = relationship("User")

    post = relationship("Post")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "post_id",
            name="uq_user_post_like"
        ),
    )