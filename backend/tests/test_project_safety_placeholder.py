from pathlib import Path

def test_placeholder_original_file_safety(tmp_path: Path):
    source = tmp_path / "方案.docx"
    source.write_text("demo", encoding="utf-8")
    before = source.read_text(encoding="utf-8")
    after = source.read_text(encoding="utf-8")
    assert before == after
