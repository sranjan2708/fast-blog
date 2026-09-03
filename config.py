from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_PORT = os.getenv("DATABASE_PORT")
ENVIRONMENT = os.getenv("ENVIRONMENT")
SECRET_KEY = os.getenv("SECRET_KEY")


if not DATABASE_HOST:
    raise ValueError("DATABASE_HOST is missing")

if not DATABASE_NAME:
    raise ValueError("DATABASE_NAME is missing")

if not DATABASE_USER:
    raise ValueError("DATABASE_USER is missing")

if not DATABASE_PASSWORD:
    raise ValueError("DATABASE_PASSWORD is missing")

if not DATABASE_PORT:
    raise ValueError("DATABASE_PORT is missing")

if not ENVIRONMENT:
    raise ValueError("ENVIRONMENT is missing")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing")