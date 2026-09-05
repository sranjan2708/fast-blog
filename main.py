from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from database import get_db
from schemas.user import UserCreate
from models.user import User
from security import hash_password


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

    # CHANGE 1: Handle database errors
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except IntegrityError:
        # CHANGE 2: Roll back the failed transaction
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