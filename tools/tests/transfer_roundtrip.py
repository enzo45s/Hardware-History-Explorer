"""Docker/PowerShell integration test, exclusively on two new disposable projects.

Requires already built HHE images (default: images from `docker compose up`).
Never exports, resets or restores the developer's existing Compose database.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import uuid

ROOT = Path(__file__).resolve().parents[2]


def run(args, **kwargs):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Command failed: {args}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def image(service):
    container = run(["docker", "compose", "ps", "-a", "-q", service])
    return run(["docker", "inspect", "--format={{.Config.Image}}", container])


FIXTURE = '''
from app.main import SessionLocal, UPLOAD_DIR
from app.models import Computer, ComputerImage, Release, Source
from app.import_models import ImportJob, ImportRow, ImportClaim
from app.photo_jobs import PhotoJob
from app.importing.bulk1000bit import BulkJob
from app.catalog_store import refresh_pending
from app.catalog_cleanup import prepare as cleanup_preview, apply as cleanup_apply
from PIL import Image
with SessionLocal() as db:
    # Cover a physically cleaned source and a legacy/cache-mode destination,
    # including restoration of the destination's safety backup.
    cleanup_apply(db, cleanup_preview(db))
    computer = db.query(Computer).first()
    source = Source(title="Synthetic backup test: prezzo, citta, 日本", url="https://example.org/backup-test")
    db.add(source)
    release = db.query(Release).first()
    release.price = 123.45
    release.sources.append(source)
    job = ImportJob(provider="canonical", filename="synthetic.json", format="json", checksum="a" * 64,
        raw_payload='{"original":"日本, 123.45, binary encoded: /wA="}', status="applied")
    db.add(job)
    db.flush()
    row = ImportRow(job_id=job.id, position=0, raw={"test": True}, normalized={"price": 123.45},
        status="updated", computer_id=computer.id)
    db.add(row)
    db.flush()
    db.add(ImportClaim(row_id=row.id, computer_id=computer.id, source_id=source.id,
        entity="release", target_id=release.id, field="price", value={"value": 123.45},
        previous={"value": None}, status="pending"))
    db.add(PhotoJob(active_key="active", status="paused", error="Synthetic paused queue"))
    db.add(BulkJob(active_key="active", status="paused", requests=12, robots={"synthetic": True}))
    db.add(ComputerImage(computer_id=computer.id, local_filename="transfer-fixture.webp",
        caption="Synthetic uploaded photograph", is_primary=True))
    db.commit()
    # The fixture writes through a separate CLI process. Settle its derived
    # catalog before taking the byte-for-byte reference; normal API startup
    # also drains this queue after an offline import/restore.
    refresh_pending(db)
Image.new("RGB", (23, 17), (11, 88, 22)).save(UPLOAD_DIR / "transfer-fixture.webp", format="WEBP")
'''

SNAPSHOT = '''
import hashlib, json
from sqlalchemy import inspect, text
from app.main import engine, UPLOAD_DIR
report = {}
with engine.connect() as connection:
    for name in sorted(inspect(connection).get_table_names()):
        rows = connection.execute(text('SELECT * FROM "' + name + '"')).mappings().all()
        values = sorted(json.dumps(dict(row), sort_keys=True, default=str, ensure_ascii=False) for row in rows)
        report[name] = {"rows": len(rows), "sha256": hashlib.sha256("\\n".join(values).encode()).hexdigest()}
    report["sequences"] = dict(connection.execute(text("SELECT sequencename, last_value FROM pg_sequences WHERE schemaname='public'")).all())
report["uploads"] = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in UPLOAD_DIR.iterdir()}
print(json.dumps(report, sort_keys=True))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--powershell", default=shutil.which("pwsh"))
    parser.add_argument("--image-api")
    parser.add_argument("--image-web")
    args = parser.parse_args()
    if not args.powershell:
        parser.error("PowerShell 7 (pwsh) is required for this integration test.")
    api_image = args.image_api or image("api")
    web_image = args.image_web or image("web")
    projects = ["hhe-transfer-test-" + uuid.uuid4().hex[:12] for _ in range(2)]
    with TemporaryDirectory(prefix="hhe transfer test ") as folder:
        work = Path(folder)
        override = work / "compose.yml"
        override.write_text(f"""services:
  api:
    image: {api_image}
    pull_policy: never
    ports: !reset []
  web:
    image: {web_image}
    pull_policy: never
    ports: !reset []
""")

        def compose(project, *command, **kwargs):
            return run(["docker", "compose", "-p", project, "-f", str(ROOT / "docker-compose.yml"),
                        "-f", str(override), *command], **kwargs)

        def python(project, code):
            return compose(project, "exec", "-T", "api", "python", "-", input=code)

        def transfer(project, mode, archive, confirmed=True, allow_mismatch=True):
            # Use a PS driver so array arguments behave the same under PS 5.1/7.
            settings = work / "arguments.json"
            settings.write_text(json.dumps({"Mode": mode, "ProjectName": project,
                "ArchivePath": str(archive), "BackupDirectory": str(work / "backups"),
                "ComposeFile": [str(ROOT / "docker-compose.yml"), str(override)]}))
            driver = work / "invoke.ps1"
            driver.write_text('''$v = Get-Content -Raw -LiteralPath $args[0] | ConvertFrom-Json
$p = @{}; $v.PSObject.Properties | ForEach-Object { $p[$_.Name] = $_.Value }
& $args[1] @p''' + (" -AllowVersionMismatch" if allow_mismatch else "") + (" -ConfirmRestore" if confirmed else ""))
            return run([args.powershell, "-NoProfile", "-File", str(driver), str(settings),
                        str(ROOT / "tools/Transfer-HheArchive.ps1")])

        def snapshot(project):
            return json.loads(python(project, SNAPSHOT))

        def assert_ready(project):
            assert compose(project, "exec", "-T", "api", "python", "-c",
                "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').status)") == "200"
            assert len(compose(project, "ps", "--status", "running", "-q").splitlines()) == 3

        try:
            for project in projects:
                compose(project, "up", "--no-build", "-d", "--wait")
            source, destination = projects
            python(source, FIXTURE)
            python(destination, "from app.main import UPLOAD_DIR; (UPLOAD_DIR / 'destination-only.webp').write_bytes(b'old')")
            before_source, before_destination = snapshot(source), snapshot(destination)
            archive = work / "transfer.hhe-backup.tar.gz"
            print(transfer(source, "Export", archive))
            assert snapshot(source) == before_source
            assert_ready(source)
            for confirmed in (False,):
                try:
                    transfer(destination, "Restore", archive, confirmed=confirmed)
                except RuntimeError as error:
                    assert "ConfirmRestore" in str(error)
                else:
                    raise AssertionError("Restore without confirmation was allowed")
            assert snapshot(destination) == before_destination
            print(transfer(destination, "Restore", archive))
            assert snapshot(destination) == before_source, "Full DB/sequence/photo roundtrip differs"
            assert_ready(destination)
            # Read the actual local media through FastAPI, not only from disk.
            assert python(destination, "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/media/transfer-fixture.webp').status)") == "200"
            safety = list((work / "backups").glob("prima-del-ripristino-*.hhe-backup.tar.gz"))
            assert len(safety) == 1
            print(transfer(destination, "Restore", safety[0]))
            assert snapshot(destination) == before_destination, "Safety backup did not restore the previous destination"

            # A valid archive envelope with an invalid pg_dump must fail before cutover.
            import importlib.util
            spec = importlib.util.spec_from_file_location("transfer_archive", ROOT / "tools/transfer_archive.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            invalid_work = work / "invalid"
            invalid_work.mkdir()
            (invalid_work / "database.dump").write_bytes(b"PGDMPcorrupt-but-checksummed")
            (invalid_work / "metadata.json").write_text(json.dumps({"project": source, "postgres_major": 16}))
            empty = invalid_work / "uploads"
            empty.mkdir()
            module.pack(invalid_work, empty)
            try:
                transfer(destination, "Restore", invalid_work / "archive.hhe-backup.tar.gz", allow_mismatch=False)
            except RuntimeError as error:
                assert "Versioni del codice" in str(error)
            else:
                raise AssertionError("Unknown code version was accepted without an override")
            assert snapshot(destination) == before_destination
            try:
                transfer(destination, "Restore", invalid_work / "archive.hhe-backup.tar.gz")
            except RuntimeError as error:
                assert "pg_restore" in str(error)
            else:
                raise AssertionError("Invalid pg_dump was restored")
            assert snapshot(destination) == before_destination
            assert_ready(destination)

            # Exact empty-archive state must survive startup (no demo reseeding).
            python(source, '''
from app.main import SessionLocal
from app.models import Computer
from app.import_models import ArchiveReset
with SessionLocal() as db:
    db.query(Computer).delete(synchronize_session=False)
    db.add(ArchiveReset(note="Synthetic empty-archive test", counts={}, snapshot={}, reconciliation_cutoff=0))
    db.commit()
''')
            empty_before = snapshot(source)
            assert empty_before["computers"]["rows"] == 0
            empty_archive = work / "empty.hhe-backup.tar.gz"
            transfer(source, "Export", empty_archive)
            transfer(destination, "Restore", empty_archive)
            assert snapshot(destination) == empty_before
            assert_ready(destination)
            print("PASS: complete DB, sequences, prices, sources, pending claims, original payload, paused queues and WebP roundtrip; safety recovery; failed restore leaves destination unchanged; empty archive does not reseed demos.")
        finally:
            # Only the two randomly named projects created by this test, never user volumes.
            for project in projects:
                compose(project, "down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
