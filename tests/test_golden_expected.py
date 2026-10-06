import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'/'golden'))
from calculate_expected import calculate

def test_expected_values_recompute_from_original_workbooks():
    expected=json.loads((ROOT/'tests'/'golden'/'expected_results.json').read_text())
    assert calculate()==expected

def test_questions_embed_all_computed_expected_values():
    questions=json.loads((ROOT/'tests'/'golden'/'questions.json').read_text())
    expected=json.loads((ROOT/'tests'/'golden'/'expected_results.json').read_text())
    mapped={q['id']:q['expected_result'] for q in questions if 'expected_result' in q}
    assert mapped==expected
    assert len(questions)>=40
