from datetime import datetime, timedelta
import logging

from fastapi import FastAPI, Request, Form, Depends
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from pydantic import ValidationError

from auth import require_current_user, require_admin
from database import get_db
from schemas.user import UserCreate
from schemas.profile import ProfileUpdate
from schemas.preferences import PreferencesUpdate
from schemas.post import PostCreate, PostUpdate
from models.user import User
from models.post import Post
from models.comment import Comment
from models.like import Like
from models.post_view import PostView
from models.user_session import UserSession
from models.category import Category
from models.tag import Tag
from security import hash_password, verify_password, generate_session_id
from utils import generate_unique_slug


app = FastAPI()

# Phase 16: Serve frontend static files
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# ==========================================================
# PHASE 17: GLOBAL ERROR HANDLING
# ==========================================================

# Keep detailed exception information in the server logs,
# but never expose internal exception details to users.
logger = logging.getLogger(__name__)


def rollback_integrity_error(db: Session, operation: str):
    """
    Roll back a failed database transaction and log the internal error.
    The actual database exception is never shown to the user.
    """
    db.rollback()
    logger.exception("Database integrity error during %s", operation)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
):
    """
    Handle HTTP errors consistently across the application.

    404 -> custom Not Found page
    403 -> custom Access Denied page
    Other known HTTP errors -> safe user-facing message
    """

    if exc.status_code == 404:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={},
            status_code=404
        )

    if exc.status_code == 403:
        return templates.TemplateResponse(
            request=request,
            name="403.html",
            context={},
            status_code=403
        )

    if exc.status_code == 401:
        return HTMLResponse(
            content="""
            <div style="font-family: Arial, sans-serif; text-align: center; padding: 60px;">
                <h1>401</h1>
                <h2>Login Required</h2>
                <p>Please log in to access this page.</p>
                <a href="/login">Go to Login</a>
            </div>
            """,
            status_code=401
        )

    if exc.status_code == 400:
        return HTMLResponse(
            content="""
            <div style="font-family: Arial, sans-serif; text-align: center; padding: 60px;">
                <h1>400</h1>
                <h2>Invalid Request</h2>
                <p>The request could not be processed.</p>
                <a href="/">Back to Home</a>
            </div>
            """,
            status_code=400
        )

    return HTMLResponse(
        content="""
        <div style="font-family: Arial, sans-serif; text-align: center; padding: 60px;">
            <h1>Error</h1>
            <h2>Something went wrong</h2>
            <p>We could not process your request.</p>
            <a href="/">Back to Home</a>
        </div>
        """,
        status_code=exc.status_code
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    """
    Handle FastAPI validation errors without exposing Pydantic
    or internal validation details to the user.

    Invalid path parameters are treated as a missing resource,
    so URLs such as /comments/abc/edit receive a 404 page.
    Other malformed requests receive a safe 400 response.
    """

    has_path_error = any(
        error.get("loc", [None])[0] == "path"
        for error in exc.errors()
    )

    if has_path_error:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={},
            status_code=404
        )

    return HTMLResponse(
        content="""
        <div style="font-family: Arial, sans-serif; text-align: center; padding: 60px;">
            <h1>400</h1>
            <h2>Invalid Request</h2>
            <p>Please check the information you submitted and try again.</p>
            <a href="/">Back to Home</a>
        </div>
        """,
        status_code=400
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception
):
    """
    Catch unexpected server errors.

    The full exception is logged on the server for debugging,
    but the user only receives a safe generic 500 page.
    """

    logger.exception(
        "Unhandled exception while processing %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__)
    )

    return templates.TemplateResponse(
        request=request,
        name="500.html",
        context={},
        status_code=500
    )



def get_post_form_options(db: Session):
    categories = db.query(Category).order_by(Category.name.asc()).all()
    tags = db.query(Tag).order_by(Tag.name.asc()).all()
    return categories, tags


# ==========================================================
# Home
# ==========================================================

@app.get("/")
def home(
    request: Request,
    db: Session = Depends(get_db)
):
    username = "Sudhansu"

    current_user = None
    session_id = request.cookies.get("session_id")

    if session_id:
        current_user = db.query(User).join(
            UserSession,
            User.id == UserSession.user_id
        ).filter(
            UserSession.session_id == session_id
        ).first()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "username": username,
            "user": current_user
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
            "message_type": None,
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
                "message_type": "error",
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
                "message_type": "error",
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
                "message_type": "error",
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
                "message_type": "error",
                "username": username,
                "email": email
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "message": "User registered successfully",
            "message_type": "success",
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
                "message_type": "error",
                "email": email
            }
        )

    if not verify_password(password, user.password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "message": "Invalid email or password.",
                "message_type": "error",
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

    try:
        db.commit()
    except IntegrityError:
        rollback_integrity_error(db, "login session creation")
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "message": "Unable to complete login. Please try again.",
                "message_type": "error",
                "email": email
            },
            status_code=400
        )

    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "message": "Login successful!",
            "message_type": "success",
            "email": email,
            "user": user
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
# Phase 15: User Profile
# ==========================================================

@app.get("/profile", response_class=HTMLResponse)
def profile(
    request: Request,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Fetch the current user's posts
    # ------------------------------------------------------

    posts = db.query(Post).filter(
        Post.user_id == user.id
    ).order_by(
        Post.created_at.desc()
    ).all()

    # ------------------------------------------------------
    # Fetch the current user's active comments
    # ------------------------------------------------------

    comments = db.query(Comment).options(
        joinedload(Comment.post)
    ).filter(
        Comment.user_id == user.id,
        Comment.is_deleted == False
    ).order_by(
        Comment.id.desc()
    ).all()

    # ------------------------------------------------------
    # Render profile page
    # ------------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "user": user,
            "posts": posts,
            "comments": comments
        }
    )


# ==========================================================
# Phase 15: Edit Profile - GET
# ==========================================================

@app.get("/profile/edit", response_class=HTMLResponse)
def edit_profile_page(
    request: Request,
    user: User = Depends(require_current_user)
):
    return templates.TemplateResponse(
        request=request,
        name="edit_profile.html",
        context={
            "user": user,
            "message": None
        }
    )


# ==========================================================
# Phase 15: Edit Profile - POST
# ==========================================================

@app.post("/profile/edit", response_class=HTMLResponse)
def edit_profile(
    request: Request,
    username: str = Form(),
    bio: str = Form(default=""),
    theme: str = Form(),
    posts_per_page: int = Form(),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Clean user input
    # ------------------------------------------------------

    username = username.strip()
    bio = bio.strip()
    theme = theme.strip()

    # ------------------------------------------------------
    # Validate profile data
    # ------------------------------------------------------

    try:
        profile_data = ProfileUpdate(
            username=username,
            bio=bio if bio else None
        )

        preferences_data = PreferencesUpdate(
            theme=theme,
            posts_per_page=posts_per_page
        )

    except ValidationError:
        return templates.TemplateResponse(
            request=request,
            name="edit_profile.html",
            context={
                "user": user,
                "message": (
                    "Please enter valid profile and preference "
                    "details."
                )
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Check whether another user already has this username
    # ------------------------------------------------------

    existing_user = db.query(User).filter(
        User.username == profile_data.username,
        User.id != user.id
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="edit_profile.html",
            context={
                "user": user,
                "message": "Username already exists."
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Update current user's profile
    # ------------------------------------------------------

    user.username = profile_data.username
    user.bio = profile_data.bio

    # ------------------------------------------------------
    # Update current user's preferences
    # ------------------------------------------------------

    user.theme = preferences_data.theme
    user.posts_per_page = preferences_data.posts_per_page

    # ------------------------------------------------------
    # Save changes
    # ------------------------------------------------------

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        return templates.TemplateResponse(
            request=request,
            name="edit_profile.html",
            context={
                "user": user,
                "message": (
                    "Unable to update profile. "
                    "Username may already exist."
                )
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Redirect to profile page
    # ------------------------------------------------------

    return RedirectResponse(
        url="/profile",
        status_code=303
    )


# ==========================================================
# Admin
# ==========================================================

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin)
):
    # Phase 16: Render the administrator dashboard.
    # The existing require_admin dependency is preserved so
    # only authenticated administrators can access this page.
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "message": "Welcome to the admin area.",
            "username": user.username,
            "role": user.role,
            "user": user
        }
    )


# ==========================================================
# Phase 11: Slugs, Search, Filtering & Pagination
# ==========================================================


# ==========================================================
# Create Post - GET
# ==========================================================

@app.get("/posts/create", response_class=HTMLResponse)
def create_post_page(
    request: Request,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    categories = db.query(Category).order_by(
        Category.name.asc()
    ).all()

    tags = db.query(Tag).order_by(
        Tag.name.asc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="create_post.html",
        context={
            "message": None,
            "categories": categories,
            "tags": tags,
            "user": user
        }
    )


# ==========================================================
# Create Post - POST
# ==========================================================

@app.post("/posts/create", response_class=HTMLResponse)
def create_post(
    request: Request,
    title: str = Form(),
    content: str = Form(),
    status: str = Form(),
    category_ids: list[int] = Form(default=[]),
    tag_ids: list[int] = Form(default=[]),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    try:
        post_data = PostCreate(
            title=title,
            content=content,
            status=status,
            category_ids=category_ids,
            tag_ids=tag_ids
        )

    except ValidationError:
        categories, tags = get_post_form_options(db)
        return templates.TemplateResponse(
            request=request,
            name="create_post.html",
            context={
                "message": "Please enter valid post details.",
                "categories": categories,
                "tags": tags,
                "user": user
            }
        )

    categories = []

    for category_id in post_data.category_ids:

        category = db.query(Category).filter(
            Category.id == category_id
        ).first()

        if not category:
            categories, tags = get_post_form_options(db)
            return templates.TemplateResponse(
                request=request,
                name="create_post.html",
                context={
                    "message": f"Category with ID {category_id} not found.",
                    "categories": categories,
                    "tags": tags,
                    "user": user
                }
            )

        categories.append(category)

    tags = []

    for tag_id in post_data.tag_ids:

        tag = db.query(Tag).filter(
            Tag.id == tag_id
        ).first()

        if not tag:
            categories, tags = get_post_form_options(db)
            return templates.TemplateResponse(
                request=request,
                name="create_post.html",
                context={
                    "message": f"Tag with ID {tag_id} not found.",
                    "categories": categories,
                    "tags": tags,
                    "user": user
                }
            )

        tags.append(tag)

    slug = generate_unique_slug(
        post_data.title,
        db
    )

    new_post = Post(
        slug=slug,
        title=post_data.title,
        content=post_data.content,
        status=post_data.status,
        user_id=user.id
    )

    new_post.categories = categories
    new_post.tags = tags

    db.add(new_post)

    try:
        db.commit()
        db.refresh(new_post)
    except IntegrityError:
        rollback_integrity_error(db, "post creation")
        categories, tags = get_post_form_options(db)
        return templates.TemplateResponse(
            request=request,
            name="create_post.html",
            context={
                "message": "Unable to create the post. Please try again.",
                "categories": categories,
                "tags": tags,
                "user": user
            },
            status_code=400
        )

    return RedirectResponse(
        url=f"/posts/{new_post.slug}",
        status_code=303
    )


# ==========================================================
# List Posts + Search + Filtering + Sorting + Pagination
# ==========================================================

@app.get("/posts", response_class=HTMLResponse)
def post_list(
    request: Request,
    search: str = "",
    status: str = "",
    sort: str = "newest",
    page: int = 1,
    category_id: str | None = None,
    tag_id: str | None = None,
    db: Session = Depends(get_db)
):

    # Number of posts displayed on each page
    # Logged-in users use their saved preference.
    # Logged-out users keep the existing default of 5.
    current_user = None

    session_id = request.cookies.get("session_id")

    if session_id:
        current_user = db.query(User).join(
            UserSession,
            User.id == UserSession.user_id
        ).filter(
            UserSession.session_id == session_id
        ).first()

    if current_user:
        posts_per_page = current_user.posts_per_page
    else:
        posts_per_page = 5

    # Prevent invalid page numbers
    if page < 1:
        page = 1

    # ------------------------------------------------------
    # Normalize optional filter values
    # ------------------------------------------------------
    # HTML forms submit an empty string when "All Categories"
    # or "All Tags" is selected. Convert empty strings to None
    # so the filters are treated as not selected.
    #
    # If a non-empty value cannot be converted to an integer,
    # use -1 so the existing invalid-ID behavior returns no posts.

    if category_id is not None:
        category_id = category_id.strip()

        if category_id == "":
            category_id = None
        else:
            try:
                category_id = int(category_id)
            except ValueError:
                category_id = -1

    if tag_id is not None:
        tag_id = tag_id.strip()

        if tag_id == "":
            tag_id = None
        else:
            try:
                tag_id = int(tag_id)
            except ValueError:
                tag_id = -1

    # ------------------------------------------------------
    # Start with all posts
    # ------------------------------------------------------

    query = db.query(Post)

    # ------------------------------------------------------
    # Search
    # ------------------------------------------------------

    if search.strip():
        search_term = f"%{search.strip()}%"

        query = query.filter(
            or_(
                Post.title.like(search_term),
                Post.content.like(search_term)
            )
        )

    # ------------------------------------------------------
    # Filtering by Status
    # ------------------------------------------------------

    # Allow only the statuses used by the application
    if status not in ("", "draft", "published"):
        status = ""

    if status:
        query = query.filter(
            Post.status == status
        )

    # ------------------------------------------------------
    # PHASE 14: Filtering by Category
    # ------------------------------------------------------

    if category_id is not None:
        category = db.query(Category).filter(
            Category.id == category_id
        ).first()

        if category:
            query = query.filter(
                Post.categories.any(
                    Category.id == category_id
                )
            )
        else:
            # Invalid category ID should return no posts
            query = query.filter(Post.id == -1)

    # ------------------------------------------------------
    # PHASE 14: Filtering by Tag
    # ------------------------------------------------------

    if tag_id is not None:
        tag = db.query(Tag).filter(
            Tag.id == tag_id
        ).first()

        if tag:
            query = query.filter(
                Post.tags.any(
                    Tag.id == tag_id
                )
            )
        else:
            # Invalid tag ID should return no posts
            query = query.filter(Post.id == -1)

    # ------------------------------------------------------
    # Load filter options
    # ------------------------------------------------------

    categories = db.query(Category).order_by(
        Category.name.asc()
    ).all()

    tags = db.query(Tag).order_by(
        Tag.name.asc()
    ).all()

    # ------------------------------------------------------
    # Count total matching posts
    # ------------------------------------------------------

    # We count before applying ORDER BY.
    # The count only needs the filtering conditions.

    total_posts = query.count()

    # ------------------------------------------------------
    # Calculate total pages
    # ------------------------------------------------------

    total_pages = (
        total_posts + posts_per_page - 1
    ) // posts_per_page

    # If requested page is beyond the last page,
    # move back to the last available page.
    if total_pages > 0 and page > total_pages:
        page = total_pages

    # ------------------------------------------------------
    # Sorting
    # ------------------------------------------------------

    if sort == "oldest":

        query = query.order_by(
            Post.created_at.asc()
        )

    else:

        # Default sorting
        # Also handles invalid sort values
        sort = "newest"

        query = query.order_by(
            Post.created_at.desc()
        )

    # ------------------------------------------------------
    # Calculate OFFSET
    # ------------------------------------------------------

    offset = (
        page - 1
    ) * posts_per_page

    # ------------------------------------------------------
    # Fetch only the posts needed for this page
    # ------------------------------------------------------

    # joinedload(Post.user) eagerly loads the related user.
    # selectinload is used for the many-to-many category/tag
    # relationships so the template can display them efficiently.

    posts = query.options(
        joinedload(Post.user),
        selectinload(Post.categories),
        selectinload(Post.tags)
    ).offset(
        offset
    ).limit(
        posts_per_page
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="posts.html",
        context={
            "posts": posts,
            "search": search,
            "status": status,
            "sort": sort,
            "page": page,
            "total_pages": total_pages,
            "total_posts": total_posts,
            "categories": categories,
            "tags": tags,
            "category_id": category_id,
            "tag_id": tag_id,
            "user": current_user
        }
    )


# ==========================================================
# Edit Post - GET
# ==========================================================

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
                "current_user": user,
                "user": user
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
                "current_user": user,
                "user": user
            },
            status_code=403
        )

    categories, tags = get_post_form_options(db)

    return templates.TemplateResponse(
        request=request,
        name="edit_post.html",
        context={
            "post": post,
            "message": None,
            "categories": categories,
            "tags": tags,
            "user": user
        }
    )


# ==========================================================
# Edit Post - POST
# ==========================================================

@app.post("/posts/{post_id}/edit", response_class=HTMLResponse)
def edit_post(
    request: Request,
    post_id: int,
    title: str = Form(),
    content: str = Form(),
    status: str = Form(),
    category_ids: list[int] = Form(default=[]),
    tag_ids: list[int] = Form(default=[]),
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
                "current_user": user,
                "user": user
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
                "current_user": user,
                "user": user
            },
            status_code=403
        )

    try:
        post_data = PostUpdate(
            title=title,
            content=content,
            status=status,
            category_ids=category_ids,
            tag_ids=tag_ids
        )

    except ValidationError:
        categories = db.query(Category).order_by(
            Category.name.asc()
        ).all()

        tags = db.query(Tag).order_by(
            Tag.name.asc()
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="edit_post.html",
            context={
                "post": post,
                "message": "Please enter valid post details.",
                "categories": categories,
                "tags": tags,
                "user": user
            }
        )

    categories = []

    for category_id in post_data.category_ids:

        category = db.query(Category).filter(
            Category.id == category_id
        ).first()

        if not category:
            categories = db.query(Category).order_by(
                Category.name.asc()
            ).all()

            tags = db.query(Tag).order_by(
                Tag.name.asc()
            ).all()

            return templates.TemplateResponse(
                request=request,
                name="edit_post.html",
                context={
                    "post": post,
                    "message": f"Category with ID {category_id} not found.",
                    "categories": categories,
                    "tags": tags,
                    "user": user
                }
            )

        categories.append(category)

    tags = []

    for tag_id in post_data.tag_ids:

        tag = db.query(Tag).filter(
            Tag.id == tag_id
        ).first()

        if not tag:
            categories = db.query(Category).order_by(
                Category.name.asc()
            ).all()

            tags = db.query(Tag).order_by(
                Tag.name.asc()
            ).all()

            return templates.TemplateResponse(
                request=request,
                name="edit_post.html",
                context={
                    "post": post,
                    "message": f"Tag with ID {tag_id} not found.",
                    "categories": categories,
                    "tags": tags,
                    "user": user
                }
            )

        tags.append(tag)

    post.title = post_data.title
    post.content = post_data.content
    post.status = post_data.status

    post.categories = categories
    post.tags = tags

    # Keep the existing slug unchanged
    try:
        db.commit()
        db.refresh(post)
    except IntegrityError:
        rollback_integrity_error(db, "post update")
        categories, tags = get_post_form_options(db)
        return templates.TemplateResponse(
            request=request,
            name="edit_post.html",
            context={
                "post": post,
                "message": "Unable to update the post. Please try again.",
                "categories": categories,
                "tags": tags,
                "user": user
            },
            status_code=400
        )

    return RedirectResponse(
        url=f"/posts/{post.slug}",
        status_code=303
    )


# ==========================================================
# Post Detail - Slug Based
# ==========================================================

@app.get("/posts/{slug}", response_class=HTMLResponse)
def post_detail(
    request: Request,
    slug: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # Eagerly load the related user because the post detail
    # template may access post.user.username.
    post = db.query(Post).options(
        joinedload(Post.user)
    ).filter(
        Post.slug == slug
    ).first()

    if not post:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "message": "Post not found.",
                "current_user": user,
                "user": user,
                "comments": []
            },
            status_code=404
        )

    # ======================================================
    # PHASE 12: FETCH COMMENTS
    # ======================================================

    comment_query = db.query(Comment).options(
        joinedload(Comment.user)
    ).filter(
        Comment.post_id == post.id
    )

    # Normal users see only active comments.
    # Admins can also see soft-deleted comments for moderation.
    if user.role != "admin":
        comment_query = comment_query.filter(
            Comment.is_deleted == False
        )

    comments = comment_query.order_by(
        Comment.id.desc()
    ).all()

    # ======================================================
    # PHASE 13: POST VIEW TRACKING
    # ======================================================

    # Check whether this user has already viewed this post.
    existing_view = db.query(PostView).filter(
        PostView.user_id == user.id,
        PostView.post_id == post.id
    ).first()

    # Count this user's first view only.
    if not existing_view:
        new_view = PostView(
            user_id=user.id,
            post_id=post.id
        )

        db.add(new_view)
        post.views += 1

        try:
            db.commit()
        except IntegrityError:
            # Another request may have created the same view first.
            db.rollback()

    # ======================================================
    # PHASE 13: FETCH LIKE INFORMATION
    # ======================================================

    # Check whether the current user has already liked this post.
    existing_like = db.query(Like).filter(
        Like.user_id == user.id,
        Like.post_id == post.id
    ).first()

    liked = existing_like is not None

    # Count all likes belonging to this post.
    like_count = db.query(Like).filter(
        Like.post_id == post.id
    ).count()

    return templates.TemplateResponse(
        request=request,
        name="post_detail.html",
        context={
            "post": post,
            "comments": comments,
            "current_user": user,
                "user": user,
            "liked": liked,
            "like_count": like_count
        }
    )


# ==========================================================
# Phase 13: Like Post
# ==========================================================

@app.post("/posts/{slug}/like")
def like_post(
    slug: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Find the post using its slug
    # ------------------------------------------------------

    post = db.query(Post).filter(
        Post.slug == slug
    ).first()

    if not post:
        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    # ------------------------------------------------------
    # Check whether the current user already liked the post
    # ------------------------------------------------------

    existing_like = db.query(Like).filter(
        Like.user_id == user.id,
        Like.post_id == post.id
    ).first()

    # ------------------------------------------------------
    # Prevent duplicate likes
    # ------------------------------------------------------

    if existing_like:
        return RedirectResponse(
            url=f"/posts/{post.slug}",
            status_code=303
        )

    # ------------------------------------------------------
    # Create the Like
    # ------------------------------------------------------

    new_like = Like(
        user_id=user.id,
        post_id=post.id
    )

    db.add(new_like)

    try:
        db.commit()
    except IntegrityError:
        # The database UNIQUE constraint on (user_id, post_id)
        # is the final protection against duplicate likes.
        db.rollback()

    # ------------------------------------------------------
    # Redirect back to the post
    # ------------------------------------------------------

    return RedirectResponse(
        url=f"/posts/{post.slug}",
        status_code=303
    )


# ==========================================================
# Phase 13: Unlike Post
# ==========================================================

@app.post("/posts/{slug}/unlike")
def unlike_post(
    slug: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Find the post using its slug
    # ------------------------------------------------------

    post = db.query(Post).filter(
        Post.slug == slug
    ).first()

    if not post:
        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    # ------------------------------------------------------
    # Find the existing Like record
    # ------------------------------------------------------

    existing_like = db.query(Like).filter(
        Like.user_id == user.id,
        Like.post_id == post.id
    ).first()

    # ------------------------------------------------------
    # Remove the Like if it exists
    # ------------------------------------------------------

    if existing_like:
        db.delete(existing_like)
        try:
            db.commit()
        except IntegrityError:
            rollback_integrity_error(db, "unlike operation")

    # ------------------------------------------------------
    # Redirect back to the post
    # ------------------------------------------------------

    return RedirectResponse(
        url=f"/posts/{post.slug}",
        status_code=303
    )


# ==========================================================
# Phase 12: Create Comment
# ==========================================================

@app.post(
    "/posts/{slug}/comments",
    response_class=HTMLResponse
)
def create_comment(
    request: Request,
    slug: str,
    content: str = Form(),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Find the post using its slug
    # ------------------------------------------------------

    post = db.query(Post).filter(
        Post.slug == slug
    ).first()

    if not post:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "comments": [],
                "message": "Post not found.",
                "current_user": user,
                "user": user
            },
            status_code=404
        )

    # ------------------------------------------------------
    # Basic comment validation
    # ------------------------------------------------------

    content = content.strip()

    if not content:
        comments = db.query(Comment).options(
            joinedload(Comment.user)
        ).filter(
            Comment.post_id == post.id,
            Comment.is_deleted == False
        ).order_by(
            Comment.id.desc()
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "comments": comments,
                "message": "Comment cannot be empty.",
                "current_user": user,
                "user": user
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Create the comment
    # ------------------------------------------------------
    #
    # user.id = logged-in user who wrote the comment
    #
    # post.id = post on which the comment was written
    #
    # We NEVER take user_id from the form.
    #

    new_comment = Comment(
        content=content,
        user_id=user.id,
        post_id=post.id,
        is_deleted=False
    )

    db.add(new_comment)
    try:
        db.commit()
        db.refresh(new_comment)
    except IntegrityError:
        rollback_integrity_error(db, "comment creation")
        comments = db.query(Comment).options(
            joinedload(Comment.user)
        ).filter(
            Comment.post_id == post.id,
            Comment.is_deleted == False
        ).order_by(
            Comment.id.desc()
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "comments": comments,
                "message": "Unable to add your comment. Please try again.",
                "current_user": user,
                "user": user
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Redirect back to the post
    # ------------------------------------------------------

    return RedirectResponse(
        url=f"/posts/{post.slug}",
        status_code=303
    )


# ==========================================================
# Phase 12: Edit Comment - GET
# ==========================================================

@app.get(
    "/comments/{comment_id}/edit",
    response_class=HTMLResponse
)
def edit_comment_page(
    request: Request,
    comment_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Find the comment
    # ------------------------------------------------------

    comment = db.query(Comment).filter(
        Comment.id == comment_id
    ).first()

    if not comment:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "comments": [],
                "message": "Comment not found.",
                "current_user": user,
                "user": user
            },
            status_code=404
        )

    # ------------------------------------------------------
    # Prevent editing a soft-deleted comment
    # ------------------------------------------------------

    if comment.is_deleted:
        post = db.query(Post).filter(
            Post.id == comment.post_id
        ).first()

        if not post:
            return templates.TemplateResponse(
                request=request,
                name="post_detail.html",
                context={
                    "post": None,
                    "comments": [],
                    "message": "Post not found.",
                    "current_user": user,
                "user": user
                },
                status_code=404
            )

        return RedirectResponse(
            url=f"/posts/{post.slug}",
            status_code=303
        )

    # ------------------------------------------------------
    # Check comment ownership
    # ------------------------------------------------------
    #
    # Only the user who created the comment can edit it.
    #

    if comment.user_id != user.id:
        post = db.query(Post).filter(
            Post.id == comment.post_id
        ).first()

        if not post:
            return templates.TemplateResponse(
                request=request,
                name="post_detail.html",
                context={
                    "post": None,
                    "comments": [],
                    "message": "Post not found.",
                    "current_user": user,
                "user": user
                },
                status_code=404
            )

        comments = db.query(Comment).options(
            joinedload(Comment.user)
        ).filter(
            Comment.post_id == post.id,
            Comment.is_deleted == False
        ).order_by(
            Comment.id.desc()
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "comments": comments,
                "message": "You are not allowed to edit this comment.",
                "current_user": user,
                "user": user
            },
            status_code=403
        )

    # ------------------------------------------------------
    # Find the post to which the comment belongs
    # ------------------------------------------------------

    post = db.query(Post).options(
        joinedload(Post.user)
    ).filter(
        Post.id == comment.post_id
    ).first()

    if not post:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "comments": [],
                "message": "Post not found.",
                "current_user": user,
                "user": user
            },
            status_code=404
        )

    comments = db.query(Comment).options(
        joinedload(Comment.user)
    ).filter(
        Comment.post_id == post.id,
        Comment.is_deleted == False
    ).order_by(
        Comment.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="post_detail.html",
        context={
            "post": post,
            "comments": comments,
            "edit_comment": comment,
            "current_user": user,
                "user": user
        }
    )


# ==========================================================
# Phase 12: Edit Comment - POST
# ==========================================================

@app.post(
    "/comments/{comment_id}/edit",
    response_class=HTMLResponse
)
def edit_comment(
    request: Request,
    comment_id: int,
    content: str = Form(),
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Find the comment
    # ------------------------------------------------------

    comment = db.query(Comment).filter(
        Comment.id == comment_id
    ).first()

    if not comment:
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": None,
                "comments": [],
                "message": "Comment not found.",
                "current_user": user,
                "user": user
            },
            status_code=404
        )

    # ------------------------------------------------------
    # Prevent editing a soft-deleted comment
    # ------------------------------------------------------

    if comment.is_deleted:
        post = db.query(Post).filter(
            Post.id == comment.post_id
        ).first()

        if not post:
            return templates.TemplateResponse(
                request=request,
                name="post_detail.html",
                context={
                    "post": None,
                    "comments": [],
                    "message": "Post not found.",
                    "current_user": user,
                "user": user
                },
                status_code=404
            )

        return RedirectResponse(
            url=f"/posts/{post.slug}",
            status_code=303
        )

    # ------------------------------------------------------
    # Check comment ownership
    # ------------------------------------------------------

    if comment.user_id != user.id:
        post = db.query(Post).filter(
            Post.id == comment.post_id
        ).first()

        if not post:
            return templates.TemplateResponse(
                request=request,
                name="post_detail.html",
                context={
                    "post": None,
                    "comments": [],
                    "message": "Post not found.",
                    "current_user": user,
                "user": user
                },
                status_code=404
            )

        comments = db.query(Comment).options(
            joinedload(Comment.user)
        ).filter(
            Comment.post_id == post.id,
            Comment.is_deleted == False
        ).order_by(
            Comment.id.desc()
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "comments": comments,
                "message": "You are not allowed to edit this comment.",
                "current_user": user,
                "user": user
            },
            status_code=403
        )

    # ------------------------------------------------------
    # Validate updated content
    # ------------------------------------------------------

    content = content.strip()

    if not content:
        post = db.query(Post).options(
            joinedload(Post.user)
        ).filter(
            Post.id == comment.post_id
        ).first()

        comments = db.query(Comment).options(
            joinedload(Comment.user)
        ).filter(
            Comment.post_id == comment.post_id,
            Comment.is_deleted == False
        ).order_by(
            Comment.id.desc()
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "comments": comments,
                "edit_comment": comment,
                "message": "Comment cannot be empty.",
                "current_user": user,
                "user": user
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Update the comment
    # ------------------------------------------------------

    comment.content = content

    try:
        db.commit()
        db.refresh(comment)
    except IntegrityError:
        rollback_integrity_error(db, "comment update")
        return templates.TemplateResponse(
            request=request,
            name="post_detail.html",
            context={
                "post": post,
                "comments": comments,
                "edit_comment": comment,
                "message": "Unable to update your comment. Please try again.",
                "current_user": user,
                "user": user
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Find the post and redirect back to it
    # ------------------------------------------------------

    post = db.query(Post).filter(
        Post.id == comment.post_id
    ).first()

    return RedirectResponse(
        url=f"/posts/{post.slug}",
        status_code=303
    )


# ==========================================================
# Phase 12: Delete Comment
# ==========================================================

@app.post("/comments/{comment_id}/delete")
def delete_comment(
    comment_id: int,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Find the comment
    # ------------------------------------------------------

    comment = db.query(Comment).filter(
        Comment.id == comment_id
    ).first()

    if not comment:
        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    # ------------------------------------------------------
    # Ignore comments that are already soft-deleted
    # ------------------------------------------------------

    if comment.is_deleted:
        post = db.query(Post).filter(
            Post.id == comment.post_id
        ).first()

        if post:
            return RedirectResponse(
                url=f"/posts/{post.slug}",
                status_code=303
            )

        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    # ------------------------------------------------------
    # Check comment ownership
    # ------------------------------------------------------
    #
    # Only the comment author can delete the comment.
    #

    if comment.user_id != user.id:
        post = db.query(Post).filter(
            Post.id == comment.post_id
        ).first()

        if post:
            return RedirectResponse(
                url=f"/posts/{post.slug}",
                status_code=303
            )

        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    # ------------------------------------------------------
    # Save the post ID before deleting the comment
    # ------------------------------------------------------

    post_id = comment.post_id

    comment.is_deleted = True
    try:
        db.commit()
    except IntegrityError:
        rollback_integrity_error(db, "comment deletion")
        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    # ------------------------------------------------------
    # Redirect back to the post
    # ------------------------------------------------------

    post = db.query(Post).filter(
        Post.id == post_id
    ).first()

    if post:
        return RedirectResponse(
            url=f"/posts/{post.slug}",
            status_code=303
        )

    return RedirectResponse(
        url="/posts",
        status_code=303
    )


# ==========================================================
# Phase 12: Admin Comment Moderation
# ==========================================================

@app.post("/admin/comments/{comment_id}/delete")
def admin_delete_comment(
    comment_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # ------------------------------------------------------
    # Find the comment
    # ------------------------------------------------------

    comment = db.query(Comment).filter(
        Comment.id == comment_id
    ).first()

    if not comment:
        return RedirectResponse(
            url="/posts",
            status_code=303
        )

    # ------------------------------------------------------
    # Soft delete the comment
    # ------------------------------------------------------
    #
    # require_admin already checked that the logged-in
    # user is an admin.
    #

    post_id = comment.post_id

    if not comment.is_deleted:
        comment.is_deleted = True
        try:
            db.commit()
        except IntegrityError:
            rollback_integrity_error(db, "admin comment deletion")
            return RedirectResponse(
                url="/posts",
                status_code=303
            )

    # ------------------------------------------------------
    # Redirect back to the post
    # ------------------------------------------------------

    post = db.query(Post).filter(
        Post.id == post_id
    ).first()

    if post:
        return RedirectResponse(
            url=f"/posts/{post.slug}",
            status_code=303
        )

    return RedirectResponse(
        url="/posts",
        status_code=303
    )


# ==========================================================
# Delete Post
# ==========================================================

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
            url=f"/posts/{post.slug}",
            status_code=303
        )

    # ------------------------------------------------------
    # Delete related post views first
    # ------------------------------------------------------
    # PostView.post_id references posts.id, so these records
    # must be removed before deleting the parent post.

    db.query(PostView).filter(
        PostView.post_id == post.id
    ).delete(
        synchronize_session=False
    )

    # ------------------------------------------------------
    # Delete related likes
    # ------------------------------------------------------

    db.query(Like).filter(
        Like.post_id == post.id
    ).delete(
        synchronize_session=False
    )

    # ------------------------------------------------------
    # Delete related comments
    # ------------------------------------------------------

    db.query(Comment).filter(
        Comment.post_id == post.id
    ).delete(
        synchronize_session=False
    )

    # ------------------------------------------------------
    # Remove many-to-many category/tag associations
    # ------------------------------------------------------

    post.categories = []
    post.tags = []

    # ------------------------------------------------------
    # Delete the post itself
    # ------------------------------------------------------

    db.delete(post)

    try:
        db.commit()
    except IntegrityError:
        rollback_integrity_error(db, "post deletion")
        return RedirectResponse(
            url="/posts",
            status_code=303
        )

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
            try:
                db.commit()
            except IntegrityError:
                rollback_integrity_error(db, "logout session deletion")

    response = RedirectResponse(
        url="/login",
        status_code=303
    )

    response.delete_cookie(
        key="session_id"
    )

    return response
