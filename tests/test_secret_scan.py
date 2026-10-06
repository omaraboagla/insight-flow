import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('eval_harness',ROOT/'tests'/'eval_harness.py')
harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)

def test_secret_scan_excludes_only_dotenv_and_returns_paths_not_values(tmp_path):
    marker='fixture-secret-do-not-print'
    (tmp_path/'.env').write_text(marker)
    (tmp_path/'safe.txt').write_text('no marker')
    assert harness.scan_tree(marker,tmp_path)==[]
    (tmp_path/'leak.log').write_text('oops '+marker)
    hits=harness.scan_tree(marker,tmp_path)
    assert hits==['leak.log']
    assert marker not in repr(hits)
