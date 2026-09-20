from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from auth import require_current_user, require_admin
from database import get_db
from schemas.user import UserCreate
from schemas.post import PostCreate, PostUpdate
from models.user import User
from models.post import Post
from models.user_session import UserSession
from security import hash_password, verify_password, generate_session_id


app = FastAPI()

templates = Jinja2Templates(directory="templates")


# ==========================================================
# Home
# ==========================================================

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


# ==========================================================
# Registration
# ==========================================================

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
        password=hashed_password,
        role="user"
    )

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


# ==========================================================
# Login
# ==========================================================

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
    user = db.query(User).filter(
        User.email == email
    ).first()

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "message": "Invalid email or password.",
                "email": email
            }
        )

    if not verify_password(password, user.password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "message": "Invalid email or password.",
                "email": email
            }
        )

    session_id = generate_session_id()

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


# ==========================================================
# Profile
# ==========================================================

@app.get("/profile")
def profile(
    user: User = Depends(require_current_user)
):
    return {
        "message": "You are logged in.",
        "username": user.username,
        "email": user.email,
        "role": user.role
    }


# ==========================================================
# Admin
# ==========================================================

@app.get("/admin")
def admin_dashboard(
    user: User = Depends(require_admin)
):
    return {
        "message": "Welcome to the admin area.",
        "username": user.username,
        "role": user.role
    }


# ==========================================================
# Phase 10: Blog Post CRUD
# ==========================================================


# -----------------------------
# Create Post - GET
# -----------------------------

@app.get("/posts/create", response_class=HTMLResponse)
def create_post_page(
    request: Request,
    user: User = Depends(require_current_user)
):
    return templates.TemplateResponse(
        request=request,
        name="create_post.html",
        context={
            "message": None
        }
    )


# -----------------------------
# Create Post - POST
# -----------------------------

@app.post("/posts/create", response_class=HTMLResponse)
def create_post(
    request: Request,
    title: str = Form(),
    content: str = Form(),
    status: str = Form(),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    try:
        post_data = PostCreate(
            title=title,
            content=content,
            status=status
        )

    except ValidationError:
        return templates.TemplateResponse(
            request=request,
            name="create_post.html",
            context={
                "message": "Please enter valid post details."
            }
        )

    new_post = Post(
        title=post_data.title,
        content=post_data.content,
        status=post_data.status,
        user_id=user.id
    )

    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    return RedirectResponse(
        url=f"/posts/{new_post.id}",
        status_code=303
    )


# -----------------------------
# List Posts
# -----------------------------

@app.get("/posts", response_class=HTMLResponse)
def post_list(
    request: Request,
    db: Session = Depends(get_db)
):
    posts = db.query(Post).order_by(
        Post.created_at.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="posts.html",
        context={
            "posts": posts
        }
    )


# -----------------------------
# Edit Post - GET
# -----------------------------

@app.get("/posts/{post_id}/edit", response_class=HTMLResponse)
def edit_post_page(
    request: Request,
    post_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(
        Post.id == post_id
    ).first()

    if not post:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "message": "Post not found.",
                "current_user": user
            },
            status_code=404
        )

    if post.user_id != user.id:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "message": "You are not allowed to edit this post.",
                "current_user": user
            },
            status_code=403
        )

    return templates.TemplateResponse(
        request=request,
        name="edit_post.html",
        context={
            "post": post,
            "message": None
        }
    )


# -----------------------------
# Edit Post - POST
# -----------------------------

@app.post("/posts/{post_id}/edit", response_class=HTMLResponse)
def edit_post(
    request: Request,
    post_id: int,
    title: str = Form(),
    content: str = Form(),
    status: str = Form(),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(
        Post.id == post_id
    ).first()

    if not post:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "message": "Post not found.",
                "current_user": user
            },
            status_code=404
        )

    if post.user_id != user.id:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "message": "You are not allowed to edit this post.",
                "current_user": user
            },
            status_code=403
        )

    try:
        post_data = PostUpdate(
            title=title,
            content=content,
            status=status
        )

    except ValidationError:
        return templates.TemplateResponse(
            request=request,
            name="edit_post.html",
            context={
                "post": post,
                "message": "Please enter valid post details."
            }
        )

    post.title = post_data.title
    post.content = post_data.content
    post.status = post_data.status

    db.commit()
    db.refresh(post)

    return RedirectResponse(
        url=f"/posts/{post.id}",
        status_code=303
    )


# -----------------------------
# Post Detail
# -----------------------------

@app.get("/posts/{post_id}", response_class=HTMLResponse)
def post_detail(
    request: Request,
    post_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(
        Post.id == post_id
    ).first()

    if not post:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "message": "Post not found.",
                "current_user": user
            },
            status_code=404
        )

    return templates.TemplateResponse(
        request=request,
        name="post_detail.html",
        context={
            "post": post,
            "current_user": user
        }
    )


# -----------------------------
# Delete Post
# -----------------------------

@app.post("/posts/{post_id}/delete")
def delete_post(
    post_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(
        Post.id == post_id
    ).first()

    if not post:
        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    if post.user_id != user.id:
        return RedirectResponse(
            url=f"/posts/{post.id}",
            status_code=303
        )

    db.delete(post)
    db.commit()

    return RedirectResponse(
        url="/posts",
        status_code=303
    )


# ==========================================================
# Logout
# ==========================================================

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