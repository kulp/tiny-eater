#!/usr/bin/env python3
"""Download the RCJ-044 STEP model that the RCA footprints reference.

attenuator.pretty/ is committed, so the only thing left to fetch is the 3D
model the two RCA footprints point at, models/Same_Sky_RCJ-044/RCJ-044.step.
Same Sky only serves its CAD package to a browser session, so
models/RCJ-04/Same_Sky_RCJ-044.zip.txt records a third-party STEP package for
the same part, which is open:

    python3 tools/fetch_models.py

The fetch is idempotent: an existing model is left alone unless --force is
given.  The 3D PCB renders are the only consumers.  DRC, ERC, the connectivity
check and the enclosure check all work without the model, because KiCad only
needs the .step for the picture and the footprint's geometry is in the
.kicad_pcb itself.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import sys
import urllib.error
import urllib.request
import zipfile

USER_AGENT = "Mozilla/5.0 (compatible; tools/fetch_models.py)"
ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
PROVENANCE_STUB = MODELS_DIR / "RCJ-04" / "Same_Sky_RCJ-044.zip.txt"
TARGET = MODELS_DIR / "Same_Sky_RCJ-044" / "RCJ-044.step"


class FetchError(Exception):
    """A source could not be turned into a file."""


def source_url() -> str | None:
    """The first URL written in the provenance stub."""
    if not PROVENANCE_STUB.exists():
        return None
    for line in PROVENANCE_STUB.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.search(r"https?://[^\s]+", line.lstrip("#"))
        if match:
            return match.group(0)
    return None


def download(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"could not reach the host ({exc.reason})") from exc


def step_from_package(data: bytes) -> bytes:
    """Return the STEP body, unwrapping the archive if the URL is a zip."""
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            steps = [n for n in archive.namelist() if n.lower().endswith(".step")]
            if not steps:
                raise FetchError("the archive contains no .step file")
            chosen = next((n for n in steps if "rcj" in n.lower()), steps[0])
            return archive.read(chosen)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the RCJ-044 3D model referenced by the RCA footprints."
    )
    parser.add_argument("--force", action="store_true",
                        help="re-download even when the model is already present")
    args = parser.parse_args(argv)

    if TARGET.exists() and not args.force:
        print(f"{TARGET} already present")
        return 0

    url = source_url()
    if url is None:
        print(f"no URL recorded in {PROVENANCE_STUB}", file=sys.stderr)
        return 1

    try:
        data = download(url)
    except FetchError as exc:
        print(f"{TARGET}: could not be downloaded from {url} ({exc})", file=sys.stderr)
        return 1

    try:
        step = step_from_package(data)
    except (FetchError, zipfile.BadZipFile) as exc:
        print(f"{TARGET}: {url} is not a usable STEP package ({exc})", file=sys.stderr)
        return 1

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(step)
    print(f"{TARGET}  <-  {url} ({len(step)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
