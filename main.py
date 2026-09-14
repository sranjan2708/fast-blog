from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from auth import require_current_user
from database import get_db
from schemas.user import UserCreate
from models.user import User
from models.user_session import UserSession
from security import hash_password, verify_password, generate_session_id


app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/")
def home(request: Request):
    username = "Sudhansu"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "username": username
        }
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "message": None,
            "username": "",
            "email": ""
        }
    )


@app.post("/register", response_class=HTMLResponse)
def register_user(
    request: Request,
    username: str = Form(),
    email: str = Form(),
    password: str = Form(),
    db: Session = Depends(get_db)
):

    # Handle Pydantic validation errors
    try:
        user_data = UserCreate(
            username=username,
            email=email,
            password=password
        )

    except ValidationError as error:

        error_details = error.errors()[0]

        field = error_details["loc"][0]
        error_type = error_details["type"]

        if field == "username" and error_type == "string_too_short":
            message = "Username must be at least 3 characters."

        elif field == "username" and error_type == "string_too_long":
            message = "Username must not exceed 50 characters."

        elif field == "email":
            message = "Please enter a valid email address."

        elif field == "password" and error_type == "string_too_short":
            message = "Password must be at least 8 characters."

        elif field == "password" and error_type == "string_too_long":
            message = "Password must not exceed 128 characters."

        else:
            message = "Please check your registration details."

        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "message": message,
                "username": username,
                "email": email
            }
        )

    existing_user = db.query(User).filter(
        User.username == user_data.username
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "message": "Username already exists",
                "username": username,
                "email": email
            }
        )

    existing_email = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_email:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "message": "Email already exists",
                "username": username,
                "email": email
            }
        )

    hashed_password = hash_password(user_data.password)

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password=hashed_password
    )

    # Handle database errors
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except IntegrityError:
        db.rollback()

        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "message": "Unable to register user. Username or email may already exist.",
                "username": username,
                "email": email
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "message": "User registered successfully",
            "username": "",
            "email": ""
        }
    )


# Phase 8: Login page
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


@app.post("/login", response_class=HTMLResponse)
def login_user(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    db: Session = Depends(get_db)
):

    # Find the user by email
    user = db.query(User).filter(
        User.email == email
    ).first()

    # Check whether the user exists
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "message": "Invalid email or password.",
                "email": email
            }
        )

    # Verify the entered password against the stored password hash
    if not verify_password(password, user.password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "message": "Invalid email or password.",
                "email": email
            }
        )

    # Credentials are correct
    session_id = generate_session_id()

    # Create a new login session
    new_session = UserSession(
        session_id=session_id,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.add(new_session)
    db.commit()

    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "message": "Login successful!",
            "email": email
        }
    )

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,
        samesite="lax"
    )

    return response


# Protected route
@app.get("/profile")
def profile(
    user: User = Depends(require_current_user)
):
    return {
        "message": "You are logged in.",
        "username": user.username,
        "email": user.email
    }


# Logout
@app.get("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get("session_id")

    if session_id:
        user_session = db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()

        if user_session:
            db.delete(user_session)
            db.commit()

    response = RedirectResponse(
        url="/login",
        status_code=303
    )

    response.delete_cookie(
        key="session_id"
    )

    return response