from datetime import datetime

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.user_session import UserSession


def get_session_id(request: Request):
    return request.cookies.get("session_id")


def get_current_session(
    request: Request,
    db: Session
):
    session_id = get_session_id(request)

    if not session_id:
        return None

    user_session = db.query(UserSession).filter(
        UserSession.session_id == session_id
    ).first()

    if not user_session:
        return None

    # Check whether the session has expired
    if user_session.expires_at < datetime.utcnow():
        db.delete(user_session)
        db.commit()
        return None

    return user_session


def get_current_user(
    request: Request,
    db: Session
):
    user_session = get_current_session(request, db)

    if not user_session:
        return None

    user = db.query(User).filter(
        User.id == user_session.user_id
    ).first()

    return user


def require_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="You must be logged in."
        )

    return user