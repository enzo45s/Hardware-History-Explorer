"""Offline archive-integrity and file-rollback tests; no local database touched."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import transfer_archive as backup


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.uploads = self.root / "uploads"
        self.uploads.mkdir()
        (self.work / "database.dump").write_bytes(b"PGDMP\x00binary\xff\x00")
        (self.work / "metadata.json").write_text(json.dumps({
            "project": "test", "postgres_major": 16, "git_commit": "a" * 40,
            "OPENAI_API_KEY": "not-for-the-backup", "password": "never-export",
        }))

    def prepare(self):
        backup.pack(self.work, self.uploads)
        (self.work / "archive.hhe-backup.tar.gz").rename(self.work / "input.hhe-backup.tar.gz")

    def custom_archive(self, entries, modify=None):
        files = {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                 for name, data, kind in entries if kind == "file"}
        manifest = {"format": backup.FORMAT, "version": 1, "postgres_major": 16, "files": files}
        if modify:
            modify(manifest)
        with tarfile.open(self.work / "input.hhe-backup.tar.gz", "w:gz") as archive:
            raw = json.dumps(manifest).encode()
            item = tarfile.TarInfo("manifest.json")
            item.size = len(raw)
            archive.addfile(item, io.BytesIO(raw))
            for name, data, kind in entries:
                item = tarfile.TarInfo(name)
                if kind == "link":
                    item.type = tarfile.SYMTYPE
                    item.linkname = "/tmp/escape"
                    archive.addfile(item)
                else:
                    item.size = len(data)
                    archive.addfile(item, io.BytesIO(data))

    def test_binary_roundtrip_replaces_photos_and_excludes_secrets(self):
        picture = bytes(range(256)) * 4
        (self.uploads / "photo.webp").write_bytes(picture)
        self.prepare()
        (self.uploads / "photo.webp").write_bytes(b"changed")
        (self.uploads / "extra.webp").write_bytes(b"remove-on-restore")
        backup.unpack(self.work)
        backup.install(self.work, self.uploads)
        self.assertEqual((self.uploads / "photo.webp").read_bytes(), picture)
        self.assertEqual([p.name for p in self.uploads.iterdir()], ["photo.webp"])
        manifest = (self.work / "verified-manifest.json").read_text()
        self.assertNotIn("not-for-the-backup", manifest)
        self.assertNotIn("never-export", manifest)
        self.assertEqual((self.work / "validated/database.dump").read_bytes(), b"PGDMP\x00binary\xff\x00")

    def test_empty_photos_roundtrip(self):
        self.prepare()
        backup.unpack(self.work)
        (self.uploads / "old.webp").write_bytes(b"old")
        backup.install(self.work, self.uploads)
        self.assertEqual(list(self.uploads.iterdir()), [])

    def test_hash_mismatch_never_installs(self):
        self.custom_archive([("database.dump", b"PGDMPwrong", "file")],
                            lambda m: m["files"]["database.dump"].update(sha256="0" * 64))
        (self.uploads / "keep.webp").write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "Hash"):
            backup.unpack(self.work)
        self.assertFalse((self.work / "validated").exists())
        self.assertEqual((self.uploads / "keep.webp").read_bytes(), b"keep")

    def test_rejects_unsafe_paths_and_windows_collisions(self):
        for names in (["../escape"], ["uploads/../../escape"], ["uploads/a:b"],
                      ["uploads/CON.webp"], ["uploads/a\\b"], ["uploads/a "],
                      ["uploads/A.webp", "uploads/a.webp"]):
            with self.subTest(names=names):
                entries = [("database.dump", b"PGDMP", "file")]
                entries.extend((name, b"x", "file") for name in names)
                self.custom_archive(entries)
                with self.assertRaises(ValueError):
                    backup.unpack(self.work)

    def test_rejects_links_duplicate_members_and_missing_files(self):
        for entries in (
            [("database.dump", b"PGDMP", "file"), ("uploads/a.webp", b"", "link")],
            [("database.dump", b"PGDMP", "file"), ("database.dump", b"PGDMP", "file")],
        ):
            self.custom_archive(entries)
            with self.assertRaises(ValueError):
                backup.unpack(self.work)
        self.custom_archive([("database.dump", b"PGDMP", "file")],
            lambda m: m["files"].update({"uploads/missing.webp": {"size": 0, "sha256": "0" * 64}}))
        with self.assertRaisesRegex(ValueError, "incompleto"):
            backup.unpack(self.work)

    def test_rollback_on_photo_move_failure(self):
        (self.uploads / "photo.webp").write_bytes(b"incoming")
        self.prepare()
        backup.unpack(self.work)
        (self.uploads / "photo.webp").write_bytes(b"original")
        (self.uploads / "extra.webp").write_bytes(b"extra")
        original_rename = Path.rename

        def fail_new(path, destination):
            if path.parent.name == "new":
                raise OSError("injected write error")
            return original_rename(path, destination)

        with patch.object(Path, "rename", fail_new), self.assertRaises(OSError):
            backup.install(self.work, self.uploads)
        self.assertEqual((self.uploads / "photo.webp").read_bytes(), b"original")
        self.assertEqual((self.uploads / "extra.webp").read_bytes(), b"extra")
        self.assertEqual(len(list(self.uploads.iterdir())), 2)

    def test_pack_rejects_symlinks_and_subfolders(self):
        (self.uploads / "subfolder").mkdir()
        with self.assertRaises(ValueError):
            backup.pack(self.work, self.uploads)
        (self.uploads / "subfolder").rmdir()
        (self.uploads / "link.webp").symlink_to(self.work / "database.dump")
        with self.assertRaises(ValueError):
            backup.pack(self.work, self.uploads)

    def test_disk_full_preflight_keeps_existing_photos(self):
        self.prepare()
        with patch.object(backup.shutil, "disk_usage", return_value=type("Disk", (), {"free": 0})()):
            with self.assertRaisesRegex(ValueError, "Spazio"):
                backup.unpack(self.work)
        self.assertFalse((self.work / "validated").exists())


if __name__ == "__main__":
    unittest.main()
