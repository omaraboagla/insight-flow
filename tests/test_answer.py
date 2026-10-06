import pytest
from app.answer import verify_numbers, template_answer

@pytest.mark.parametrize('sentence,expected', [
 ('Revenue was 92,650.61.',True),
 ('Revenue was $92,650.61.',True),
 ('The discount was 5%.',True),
 ('We sold 999 units.',False),
 ('Revenue was 92,650.61 across 4 channels.',False),
 ('There were no numeric claims.',True),
])
def test_number_verifier_accepts_only_result_numbers(sentence,expected):
 result={'columns':['revenue','discount'],'rows':[[92650.61,0.05]]}
 assert verify_numbers(sentence,result) is expected

def test_template_answer_uses_result_cells():
 assert template_answer({'columns':['revenue'],'rows':[[12.5]]})=='revenue: 12.5.'
 assert template_answer({'columns':['revenue'],'rows':[]})=='No matching records were found in the data.'


def test_scientific_notation_and_spelled_scales_match_exact_result_magnitude():
 assert verify_numbers('The figure is 1e9.',{'rows':[[1_000_000_000]]})
 assert not verify_numbers('The figure is 1e9.',{'rows':[[1]]})
 assert verify_numbers('The figure is one billion.',{'rows':[[1_000_000_000]]})
 assert not verify_numbers('The figure is one billion.',{'rows':[[1]]})

def test_alias_digits_trigger_number_free_template_fallback():
 from app.answer import compose_answer
 class NeverCall:
  def generate(self,*args,**kwargs):raise AssertionError('template-only mode must not call the model')
 result={'columns':['revenue_2026'],'rows':[[42]],'row_count':1,'capped':False}
 answer,verified=compose_answer('How much?',result,NeverCall(),None,dont_send_result_rows=True)
 assert verified
 assert answer=='The computed results are shown in the table below.'
 from app.answer import _verified_template
 raw=template_answer(result)
 assert not verify_numbers(raw,result)  # The generated alias includes unsupported year digits.
 assert verify_numbers(answer,result)  # The fallback itself is number-free and safe.
 assert answer==_verified_template(result)[0]


def test_iso_and_natural_date_mentions_must_appear_in_result_dates():
 result={'rows':[['2026-05',2000000]]}
 assert verify_numbers('Revenue rose in 2026-05 to 2M.',result)
 assert verify_numbers('Revenue rose in May 2026 to two million.',result)
 assert not verify_numbers('Revenue rose in 2026-06 to 2M.',result)
 assert not verify_numbers('Revenue rose in June 2026 to two million.',result)

def test_compact_numeric_suffix_checks_full_magnitude():
 assert verify_numbers('Revenue reached 2M.',{'rows':[[2000000]]})
 assert not verify_numbers('Revenue reached 2M.',{'rows':[[2]]})

@pytest.mark.parametrize('claim,value',[
 ('2bn',2_000_000_000),('2mn',2_000_000),('2tn',2_000_000_000_000),
])
def test_compact_long_suffixes_check_full_magnitude(claim,value):
 assert verify_numbers(f'Revenue reached {claim}.',{'rows':[[value]]})
 assert not verify_numbers(f'Revenue reached {claim}.',{'rows':[[2]]})

@pytest.mark.parametrize('claim', ['negative one', '−1'])
def test_negative_written_and_unicode_sign_match_only_negative_result(claim):
 assert verify_numbers(f'Change was {claim}.',{'rows':[[-1]]})
 assert not verify_numbers(f'Change was {claim}.',{'rows':[[1]]})
