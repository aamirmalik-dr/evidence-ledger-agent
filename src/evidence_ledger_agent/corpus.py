"""Immutable, normalized text store with per-document hashes and a manifest."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

from .schemas import Document

FICTIONAL_MARK = "FICTIONAL EXAMPLE DOCUMENT."
MANIFEST = "manifest.json"


class CorpusIntegrityError(ValueError):
    """A document does not match its manifest hash or fictional marking."""


def normalize_text(text: str) -> str:
    """Normalize text so that offsets and hashes are stable.

    NFC Unicode normalization, Unix newlines, tabs to spaces, no trailing
    whitespace on lines, at most one blank line in a row, no leading or
    trailing whitespace. The function is idempotent.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sha256_text(text: str) -> str:
    """SHA-256 hex digest of UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Corpus:
    """Read-only mapping from document id to normalized ``Document``."""

    def __init__(self, documents: list[Document], name: str = "corpus") -> None:
        self.name = name
        self._docs = MappingProxyType({d.doc_id: d for d in documents})

    @classmethod
    def load(cls, directory: Path, verify: bool = True) -> Corpus:
        """Load documents listed in ``manifest.json``.

        Args:
            directory: Folder holding ``manifest.json`` and the text files.
            verify: Check each normalized text against the manifest hash.

        Raises:
            CorpusIntegrityError: On a hash mismatch or a missing fictional mark.
        """
        directory = Path(directory)
        manifest = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
        docs = []
        for entry in manifest["documents"]:
            text = normalize_text((directory / entry["file"]).read_text(encoding="utf-8"))
            digest = sha256_text(text)
            if verify and entry.get("sha256") != digest:
                raise CorpusIntegrityError(f"{entry['doc_id']}: hash does not match manifest")
            if entry.get("fictional", True) and not text.startswith(FICTIONAL_MARK):
                raise CorpusIntegrityError(f"{entry['doc_id']}: missing fictional marking")
            docs.append(
                Document(
                    doc_id=entry["doc_id"],
                    title=entry["title"],
                    text=text,
                    sha256=digest,
                    kind=entry["kind"],
                    date=entry["date"],
                    conditions=entry.get("conditions", {}),
                    supersedes=entry.get("supersedes"),
                    fictional=entry.get("fictional", True),
                )
            )
        return cls(docs, name=manifest.get("family", directory.name))

    def get(self, doc_id: str) -> Document | None:
        """Return a document or None for an unknown id."""
        return self._docs.get(doc_id)

    @property
    def ids(self) -> list[str]:
        """Sorted document ids."""
        return sorted(self._docs)

    def __iter__(self) -> Iterator[Document]:
        return (self._docs[k] for k in self.ids)

    def __len__(self) -> int:
        return len(self._docs)

    def fingerprint(self) -> str:
        """Hash over all document ids and content hashes."""
        return sha256_text("\n".join(f"{d.doc_id}:{d.sha256}" for d in self))


def freeze_manifest(directory: Path) -> dict[str, str]:
    """Write current normalized-text hashes into ``manifest.json``.

    Returns:
        Mapping of document id to hash.
    """
    path = Path(directory) / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    hashes = {}
    for entry in manifest["documents"]:
        text = normalize_text((Path(directory) / entry["file"]).read_text(encoding="utf-8"))
        entry["sha256"] = hashes[entry["doc_id"]] = sha256_text(text)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return hashes
