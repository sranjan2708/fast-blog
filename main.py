from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
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

templates = Jinja2Templates(directory="templates")


def get_post_form_options(db: Session):
    categories = db.query(Category).order_by(Category.name.asc()).all()
    tags = db.query(Tag).order_by(Tag.name.asc()).all()
    return categories, tags


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
            "tags": tags
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
                "tags": tags
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
                    "tags": tags
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
                    "tags": tags
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
    db.commit()
    db.refresh(new_post)

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
    category_id: int | None = None,
    tag_id: int | None = None,
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
            "tag_id": tag_id
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

    categories, tags = get_post_form_options(db)

    return templates.TemplateResponse(
        request=request,
        name="edit_post.html",
        context={
            "post": post,
            "message": None,
            "categories": categories,
            "tags": tags
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
                "tags": tags
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
                    "tags": tags
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
                    "tags": tags
                }
            )

        tags.append(tag)

    post.title = post_data.title
    post.content = post_data.content
    post.status = post_data.status

    post.categories = categories
    post.tags = tags

    # Keep the existing slug unchanged
    db.commit()
    db.refresh(post)

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
        db.commit()

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
                "current_user": user
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
                "current_user": user
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
    db.commit()
    db.refresh(new_comment)

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
                "current_user": user
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
                    "current_user": user
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
                    "current_user": user
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
                "current_user": user
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
                "current_user": user
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
            "current_user": user
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
                "current_user": user
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
                    "current_user": user
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
                    "current_user": user
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
                "current_user": user
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
                "current_user": user
            },
            status_code=400
        )

    # ------------------------------------------------------
    # Update the comment
    # ------------------------------------------------------

    comment.content = content

    db.commit()
    db.refresh(comment)

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
    db.commit()

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
        db.commit()

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