"""Write normalized-text SHA-256 hashes into each fixture corpus manifest.

Run once after editing a fixture document. Loading a corpus verifies these
hashes, so any later change to a document is detected.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from evidence_ledger_agent.corpus import freeze_manifest

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Freeze the dev and held-out manifests (or the folders given)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="*", type=Path)
    args = parser.parse_args()
    folders = args.folders or [
        ROOT / "tests/fixtures/corpus/dev",
        ROOT / "tests/fixtures/corpus/heldout",
    ]
    for folder in folders:
        hashes = freeze_manifest(folder)
        print(f"{folder.name}: {len(hashes)} documents hashed")


if __name__ == "__main__":
    main()
