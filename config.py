
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "local-development-only"
    )

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" + str(BASE_DIR / "compensation.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
