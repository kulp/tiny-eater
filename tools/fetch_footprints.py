#!/usr/bin/env python3
"""Populate attenuator.pretty/ from the upstream sources recorded in models/.

Nothing in attenuator.pretty/ is authored in this repository, so none of it
needs to be committed.  Run this after a fresh clone (or after deleting the
directory) to rebuild the three footprints:

    python3 tools/fetch_footprints.py

What each file comes from:

    Potentiometer_Bourns_3296W_Vertical.kicad_mod
        KiCad footprint library, Potentiometer_THT module.  Bourns publishes
        only the 3296 datasheet and the 3296W .stp/.igs models that
        models/3296.pdf.txt, models/3296W.stp.txt and models/3296W.igs.txt
        point at; there is no KiCad footprint on bourns.com.
    TestPoint_Pad_D1.5mm.kicad_mod
        KiCad footprint library, TestPoint module.  Not a vendor part.
    SAMESKY_RCJ-044.kicad_mod
        The Same Sky / SnapMagic RCJ-044 footprint package recorded in
        models/RCJ-04/RCJ-044.zip.txt.  Both download endpoints are gated
        (reCAPTCHA on sameskydevices.com, an account on snapeda.com), so the
        script prints the URL and the steps instead of fetching it, and reads
        the archive once you have saved it.

A legacy footprint is converted with `kicad-cli fp upgrade --force` before it
is written, so KiCad derives the modern geometry instead of the script
inventing it.  The only other edits are the descr, tags and 3D model
reference the vendor package omits, listed in ADJUSTMENTS.

Apart from those, the library copy is byte identical to what upstream ships,
so the placed footprints have to carry the same graphic items.  The vendor
RCJ-044 footprint draws two 0.1 mm dots centred at (-5.85, 0), 0.45 mm
outside the courtyard, and the J1 and J2 copies in attenuator.kicad_pcb now
carry them too.  The silkscreen dot crosses the silkscreen box of R1, so the
silk_overlap rule is set to "ignore" in attenuator.kicad_pro.
"""

from __future__ import annotations

import argparse
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

USER_AGENT = "Mozilla/5.0 (compatible; tools/fetch_footprints.py)"
# Footprints written by KiCad 6 or later carry a version field.
CURRENT_FOOTPRINT_VERSION = 20230201
ROOT = pathlib.Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
KICAD_CLI = os.environ.get(
    "KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
)

# The vendor footprint ships with an empty descr, no tags and no 3D model.
# These are the values the board's placed footprints carry, kept from the
# files the fixup commits removed, so that the library copy and the placed
# instance agree line for line.
DESCR_NOTES = {
    "SAMESKY_RCJ-044.kicad_mod": (
        "RCA jack, Same Sky / CUI RCJ-044, edge-mount, 2 conductors "
        "(pin 1 center, pin 2 shell). Manufacturer KiCad geometry "
        "(models/Same_Sky_RCJ-044/SAMESKY_RCJ-044.kicad_mod). Pin 1 (center): "
        "thru-hole, oval drill 2.5 x 1.3. Pin 2 (shell): thru-hole, oval "
        "drill 2.5 x 1.0, 4.5 mm behind pin 1. Board edge at +4.0 mm with "
        "1.7 mm-deep barrel clearance notches; barrel extends toward +Y."
    ),
}
TAGS_NOTES = {
    "SAMESKY_RCJ-044.kicad_mod": "RCA jack Same Sky CUI RCJ-04 edge mount",
}

# The vendor package carries no 3D model reference; the values below are the
# ones the removed committed footprint used, pointing at the STEP that
# --no-3d-models leaves out.
MODEL_NOTES = {
    "SAMESKY_RCJ-044.kicad_mod": (
        "${KIPRJMOD}/models/Same_Sky_RCJ-044/RCJ-044.step",
        (0, 6.45, 6.5),
        (-90, 0, 90),
    ),
}

# raw.githubusercontent.com still serves the KiCad 4/5 "(module ...)" files
# for some modules, which KiCad 10 cannot load; GitLab's raw endpoint serves
# the current format.
FOOTPRINTS = (
    {
        "filename": "Potentiometer_Bourns_3296W_Vertical.kicad_mod",
        "part": "Bourns 3296W trimmer",
        "sources": (
            (
                "KiCad footprint library",
                "https://gitlab.com/kicad/libraries/kicad-footprints/-/raw/"
                "master/Potentiometer_THT.pretty/"
                "Potentiometer_Bourns_3296W_Vertical.kicad_mod",
            ),
        ),
    },
    {
        "filename": "TestPoint_Pad_D1.5mm.kicad_mod",
        "part": "SMD test point pad",
        "sources": (
            (
                "KiCad footprint library",
                "https://gitlab.com/kicad/libraries/kicad-footprints/-/raw/"
                "master/TestPoint.pretty/TestPoint_Pad_D1.5mm.kicad_mod",
            ),
        ),
    },
    {
        "filename": "SAMESKY_RCJ-044.kicad_mod",
        "part": "Same Sky RCJ-044 RCA jack",
        # URLs taken from models/RCJ-04/RCJ-044.zip.txt; all of them need a
        # browser session, so they are reported rather than fetched.
        "sources": (
            ("Same Sky footprint page", "url:rcj-044-page"),
            ("SnapEDA part page", "url:rcj-044-snapeda"),
            ("SnapEDA CDN", "url:rcj-044-cdn"),
        ),
        "manual": """
  The RCJ-044 KiCad footprint cannot be fetched by a script: the Same Sky CAD
  endpoint is behind a reCAPTCHA and SnapEDA needs an account.  Download it by
  hand, then re-run this script so it can extract the footprint:

    1. Open https://www.sameskydevices.com/product/resource/pcbfootprint/rcj-044
       (or https://www.snapeda.com/parts/RCJ-044/Same%20Sky/view-part/)
    2. Pick the KiCad format and save the archive as models/RCJ-04/RCJ-044.zip
    3. python3 tools/fetch_footprints.py --zip models/RCJ-04/RCJ-044.zip
""",
    },
)

# The RCA footprint's 3D reference points at models/Same_Sky_RCJ-044/
# RCJ-044.step, which is not committed either.  The STEP package recorded in
# models/RCJ-04/Same_Sky_RCJ-044.zip.txt is open, so it is fetched too.
REFERENCE_MODELS = (
    ("Same_Sky_RCJ-044/RCJ-044.step", "url:rcj-044-step", """
  Same Sky does not publish the RCJ-044 3D model without a session.
  models/RCJ-04/Same_Sky_RCJ-044.zip.txt lists a third-party STEP package for
  the same part; download it and save the .step inside
  models/Same_Sky_RCJ-044/RCJ-044.step.
"""),
)

ZIP_CANDIDATES = (
    MODELS_DIR / "RCJ-04" / "RCJ-044.zip",
    MODELS_DIR / "RCJ-044.zip",
    MODELS_DIR / "Same_Sky_RCJ-044.zip",
)


class FetchError(Exception):
    """A source could not be turned into a file."""


def read_urls(models_dir: pathlib.Path) -> dict[str, list[str]]:
    """Every URL written in a models/*.txt stub, commented lines included."""
    urls: dict[str, list[str]] = {}
    for stub in sorted(models_dir.rglob("*.txt")):
        found: list[str] = []
        for line in stub.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.lstrip("#").strip()
            found.extend(re.findall(r"https?://[^\s]+", line))
        urls[stub.name] = found
    return urls


def resolve(url: str, provenance: dict[str, list[str]]) -> str | None:
    """Map a 'url:<key>' reference onto a URL recorded in the stub files."""
    if not url.startswith("url:"):
        return url
    key = url[4:]
    stub = {
        "rcj-044-page": "RCJ-044.zip.txt",
        "rcj-044-snapeda": "RCJ-044.zip.txt",
        "rcj-044-cdn": "RCJ-044.zip.txt",
        "rcj-044-step": "Same_Sky_RCJ-044.zip.txt",
    }.get(key)
    urls = provenance.get(stub, []) if stub else []
    wanted = {
        "rcj-044-page": "sameskydevices.com/product",
        "rcj-044-snapeda": "snapeda.com/parts",
        "rcj-044-cdn": "snapeda.s3.amazonaws.com",
    }.get(key)
    if wanted:
        return next((u for u in urls if wanted in u), None)
    return urls[0] if urls else None


def download(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"could not reach the host ({exc.reason})") from exc


def footprint_from_archive(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".kicad_mod")]
        if not names:
            raise FetchError("the archive contains no .kicad_mod file")
        chosen = next((n for n in names if "rcj" in n.lower()), names[0])
        return archive.read(chosen).decode("utf-8", errors="replace")


def is_current(text: str) -> bool:
    """True when the sexpr is already in the KiCad 6+ footprint format."""
    match = re.search(r"\(version\s+(\d+)\)", text)
    return bool(match) and int(match.group(1)) >= CURRENT_FOOTPRINT_VERSION


def upgrade(text: str, filename: str) -> str:
    """Convert a legacy footprint with kicad-cli rather than by hand."""
    if is_current(text):
        return text
    if shutil.which(KICAD_CLI) is None:
        print(
            f"  {filename}: legacy format, but kicad-cli is not available as "
            f"{KICAD_CLI}; wrote it unconverted (KiCad upgrades it on first load)",
            file=sys.stderr,
        )
        return text
    with tempfile.TemporaryDirectory() as workdir:
        # fp upgrade reads a footprint library directory and creates the
        # output directory, so the output must not exist yet.
        library = pathlib.Path(workdir) / "library"
        library.mkdir()
        (library / filename).write_text(text, encoding="utf-8")
        upgraded_dir = pathlib.Path(workdir) / "upgraded"
        result = subprocess.run(
            [KICAD_CLI, "fp", "upgrade", "--force", "-o", str(upgraded_dir),
             str(library)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise FetchError(f"fp upgrade failed: {result.stderr.strip()}")
        upgraded = upgraded_dir / filename
        if not upgraded.exists():
            raise FetchError("fp upgrade wrote no output file")
        return upgraded.read_text(encoding="utf-8")


def model_block(path: str, offset: tuple, rotate: tuple) -> str:
    """The sexpr that attaches a 3D model to a footprint."""
    x, y, z = offset
    rx, _, rz = rotate
    return (
        f'\t(model "{path}"\n'
        f"\t\t(offset\n\t\t\t(xyz {x} {y} {z})\n\t\t)\n"
        f"\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n"
        f"\t\t(rotate\n\t\t\t(xyz {rx} -0 {rz})\n\t\t)\n"
        f"\t)\n"
    )


def restore_metadata(text: str, filename: str) -> str:
    """fp upgrade drops the empty descr the vendor file carried, and the
    package never had tags, so put both back."""
    if "(descr " in text:
        return text
    return re.sub(
        r'(\t\(layer "F\.Cu"\)\n)',
        r"\1"
        + f'\t(descr "{DESCR_NOTES[filename]}")\n\t(tags "{TAGS_NOTES[filename]}")\n',
        text,
        count=1,
    )


def attach_model(text: str, filename: str) -> str:
    """Append the 3D model reference at the end of the footprint."""
    text = text.rstrip()
    if not text.endswith(")") or "(model " in text:
        return text
    return text[:-1] + model_block(*MODEL_NOTES[filename]) + ")\n"


# Project adjustments applied after the upgrade.  Each rule is a short,
# checkable text edit, never hand-drawn geometry.
ADJUSTMENTS = {
    "SAMESKY_RCJ-044.kicad_mod": (
        ("restore the project descr and tags", restore_metadata),
        ("attach the reference to the downloaded STEP model", attach_model),
    ),
}


def adjust(text: str, filename: str) -> str:
    for description, rule in ADJUSTMENTS.get(filename, ()):
        before = text
        text = rule(text, filename)
        if text != before:
            print(f"  {filename}: {description}")
    return text


def load_archive(path: pathlib.Path | None) -> tuple[bytes, str] | None:
    if path is not None:
        return path.read_bytes(), str(path)
    for candidate in ZIP_CANDIDATES:
        if candidate.exists():
            return candidate.read_bytes(), str(candidate)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the project footprints from their upstream sources."
    )
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "attenuator.pretty",
                        help="footprint directory to populate (default: attenuator.pretty/)")
    parser.add_argument("--zip", type=pathlib.Path,
                        help="archive holding the manually downloaded RCJ-044 footprint")
    parser.add_argument("--no-3d-models", action="store_true",
                        help="skip the reference 3D model that the RCA footprint references")
    args = parser.parse_args(argv)

    provenance = read_urls(MODELS_DIR)
    if not provenance:
        print(f"no URL stubs found under {MODELS_DIR}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    blocked: list[str] = []

    for entry in FOOTPRINTS:
        filename = entry["filename"]
        target = args.out / filename
        text: str | None = None
        source: str | None = None

        if filename == "SAMESKY_RCJ-044.kicad_mod":
            archive = load_archive(args.zip)
            if archive is not None:
                try:
                    text = footprint_from_archive(archive[0])
                    source = archive[1]
                except (FetchError, zipfile.BadZipFile) as exc:
                    print(f"{filename}: could not read {archive[1]} ({exc})", file=sys.stderr)
                    blocked.append(filename)
                    continue

        if text is None:
            failures: list[str] = []
            for label, url in entry["sources"]:
                resolved = resolve(url, provenance)
                if resolved is None:
                    continue
                try:
                    data = download(resolved)
                except FetchError as exc:
                    failures.append(f"{label}: {resolved} -> {exc}")
                    continue
                if data[:2] == b"PK":
                    text = footprint_from_archive(data)
                elif data.lstrip()[:1] == b"(":
                    text = data.decode("utf-8", errors="replace")
                else:
                    failures.append(f"{label}: {resolved} -> not a footprint file")
                    continue
                source = resolved
                break

        if text is None:
            print(f"{filename} ({entry['part']}): could not be downloaded")
            for failure in failures:
                print(f"  {failure}")
            print(entry.get("manual", ""))
            blocked.append(filename)
            continue

        try:
            text = upgrade(text, filename)
        except FetchError as exc:
            print(f"{filename}: could not be upgraded ({exc})", file=sys.stderr)
            blocked.append(filename)
            continue

        target.write_text(adjust(upgrade(text, filename), filename), encoding="utf-8")
        print(f"{target}  <-  {source}")
        written.append(str(target))

    if not args.no_3d_models:
        for relpath, key, instruction in REFERENCE_MODELS:
            target = MODELS_DIR / relpath
            url = resolve(key, provenance)
            if target.exists():
                print(f"{target} already present")
                continue
            if url is None:
                print(f"{target}: no URL recorded for it in models/")
                print(instruction)
                blocked.append(str(target))
                continue
            try:
                data = download(url)
            except FetchError as exc:
                print(f"{target}: could not be downloaded from {url} ({exc})")
                print(instruction)
                blocked.append(str(target))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if data[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    steps = [n for n in archive.namelist() if n.lower().endswith(".step")]
                    if not steps:
                        print(f"{target}: the archive at {url} has no .step file")
                        blocked.append(str(target))
                        continue
                    target.write_bytes(archive.read(steps[0]))
            else:
                target.write_bytes(data)
            print(f"{target}  <-  {url}")

    print()
    print(f"wrote {len(written)} footprint file(s) to {args.out}")
    if blocked:
        print("still to fetch: " + ", ".join(blocked))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
