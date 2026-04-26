from src.router.behavioral_contract import BEHAVIORAL_CONTRACT


def test_behavioral_contract_is_a_non_empty_string():
    assert isinstance(BEHAVIORAL_CONTRACT, str)
    assert len(BEHAVIORAL_CONTRACT) > 100


def test_behavioral_contract_includes_core_role():
    assert "facilitation router" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_includes_whisper_clause():
    assert "WHISPER from" in BEHAVIORAL_CONTRACT


def test_facilitator_prompt_embeds_behavioral_contract():
    from src.router.facilitator import _SYSTEM_PROMPT
    assert "facilitation router" in _SYSTEM_PROMPT
    assert "WHISPER from" in _SYSTEM_PROMPT
    assert "{goals}" in _SYSTEM_PROMPT
