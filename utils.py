import re

from sqlalchemy.orm import Session

from models.post import Post


def generate_slug(title: str) -> str:
    # Convert the title to lowercase
    title = title.lower()

    # Remove characters that are not letters, numbers, spaces, or hyphens
    title = re.sub(r"[^a-z0-9\s-]", "", title)

    # Replace spaces or multiple hyphens with a single hyphen
    title = re.sub(r"[\s-]+", "-", title)

    # Remove hyphens from the beginning and end
    return title.strip("-")


def generate_unique_slug(title: str, db: Session) -> str:
    base_slug = generate_slug(title)
    slug = base_slug
    counter = 2

    while db.query(Post).filter(Post.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug