import os
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