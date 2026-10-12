from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[4]


def load_settings():
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from config.settings import SETTINGS

    return SETTINGS
