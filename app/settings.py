"""Optional settings, such as API keys, read from a `.env` file in the project folder.

The app needs none of them; see .env.example for what can be set.
"""

import os
from pathlib import Path

from app.database import PROJECT_ROOT

ENV_FILE = PROJECT_ROOT / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Copy `NAME=value` lines into the environment. Blank lines and `#` comments are skipped.

    A variable that is already set (in the terminal or by the tests) is left as it is.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("\"'"))
