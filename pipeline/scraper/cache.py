"""Raw response cache under data/raw/{source}/{season}/{name}.json.

Every fetch goes through get_or_fetch, so re-running the pipeline costs zero requests.
"""

import json
from pathlib import Path

# Repo root / data / raw (this file is pipeline/scraper/cache.py).
DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


def cache_path(source, season, name, root=DEFAULT_ROOT):
    return Path(root) / source / season / f"{name}.json"


def get_or_fetch(source, season, name, fetch, root=DEFAULT_ROOT):
    """Return the cached JSON if present; otherwise call fetch(), save its result, and return it."""
    path = cache_path(source, season, name, root)
    if path.exists():
        return json.loads(path.read_text())

    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file, then rename, so a crash never leaves a half-written cache entry.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)
    return data
