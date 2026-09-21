from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from pydantic import ValidationError

from auth import require_current_user, require_admin
from database import get_db
from schemas.user import UserCreate
from schemas.post import PostCreate, PostUpdate
from models.user import User
from models.post import Post
from models.comment import Comment
from models.user_session import UserSession
from security import hash_password, verify_password, generate_session_id
from utils import generate_unique_slug


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
# Phase 11: Slugs, Search, Filtering & Pagination
# ==========================================================


# ==========================================================
# Create Post - GET
# ==========================================================

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


# ==========================================================
# Create Post - POST
# ==========================================================

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
    db: Session = Depends(get_db)
):

    # Number of posts displayed on each page
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
    # Count total matching posts
    # ------------------------------------------------------
    #
    # We count before applying ORDER BY.
    # The count only needs the filtering conditions.
    #

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
    #
    # joinedload(Post.user) eagerly loads the related user
    # in the same database operation.
    #
    # This avoids unnecessary additional queries when the
    # template accesses:
    #
    #     post.user.username
    #
    # ------------------------------------------------------

    posts = query.options(
        joinedload(Post.user)
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
            "total_posts": total_posts
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

    return templates.TemplateResponse(
        request=request,
        name="edit_post.html",
        context={
            "post": post,
            "message": None
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

    return templates.TemplateResponse(
        request=request,
        name="post_detail.html",
        context={
            "post": post,
            "comments": comments,
            "current_user": user
        }
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