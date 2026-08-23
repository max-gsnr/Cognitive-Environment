import os
import tempfile

# Point the app at a throwaway database before app.config is imported anywhere.
_TMP = tempfile.mkdtemp(prefix="orbit-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/orbit-test.db")
os.environ.setdefault("GAMES_ROOT", f"{_TMP}/games")
