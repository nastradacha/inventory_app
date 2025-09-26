import os
from datetime import timedelta
basedir = os.path.abspath(os.path.dirname(__file__))
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(basedir, 'inventory.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Currency settings ---------------------------------------------
    # Default symbol set to Ghanaian Cedi. Change via env var later:
    #   Windows:   set CURRENCY_SYMBOL=$
    #   macOS/Linux: export CURRENCY_SYMBOL=$
    # Or on Render: add env var CURRENCY_SYMBOL=₦ etc.
    CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "GH₵")
    # --------------------------------------------------------------------
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,        # each worker ≤ 5 → total 10 < 20-conn cap
        "max_overflow": 2,
        "pool_pre_ping": True,
        "pool_recycle": 180,   # recycle more frequently to avoid idle EOF
        "pool_timeout": 15,
    }

    # Flask-Limiter storage backend (silence warning in local dev)
    # Use Redis in production by setting RATELIMIT_STORAGE_URI=redis://<host>:<port>
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    # Keep cashier sessions alive through the workday (can override via SESSION_HOURS)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_HOURS", "12")))
    # Optional owner contact used in prefilled share links (not sent automatically)
    ERROR_REPORT_EMAIL_TO = os.getenv("ERROR_REPORT_EMAIL_TO", "")
    ERROR_REPORT_SMS_TO = os.getenv("ERROR_REPORT_SMS_TO", "")