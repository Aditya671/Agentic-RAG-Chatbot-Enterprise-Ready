from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_repository_level_tests_do_not_depend_on_machine_specific_paths():
    """Top-level CI tests must be runnable from a fresh clone."""
    forbidden = ("/mnt/data/", "/workspace/", "C:\\Users\\")
    test_files = list((ROOT / "tests").rglob("test_*.py"))
    offenders = []
    for path in test_files:
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in forbidden):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, "Tests use machine-specific paths: " + ", ".join(offenders)
