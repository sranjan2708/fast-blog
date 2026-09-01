from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DATABASE_USER"),
    password=os.getenv("DATABASE_PASSWORD"),
    host=os.getenv("DATABASE_HOST"),
    port=int(os.getenv("DATABASE_PORT")),
    database=os.getenv("DATABASE_NAME")
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()