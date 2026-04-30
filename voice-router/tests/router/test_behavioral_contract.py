from src.router.behavioral_contract import BEHAVIORAL_CONTRACT


def test_behavioral_contract_is_a_non_empty_string():
    assert isinstance(BEHAVIORAL_CONTRACT, str)
    assert len(BEHAVIORAL_CONTRACT) > 100


def test_behavioral_contract_includes_core_role():
    assert "facilitation partner" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_includes_whisper_clause():
    assert "WHISPER from" in BEHAVIORAL_CONTRACT


def test_facilitator_prompt_embeds_behavioral_contract():
    from src.router.facilitator import _SYSTEM_PROMPT
    assert "facilitation partner" in _SYSTEM_PROMPT
    assert "WHISPER from" in _SYSTEM_PROMPT
    assert "{goals}" in _SYSTEM_PROMPT


def test_behavioral_contract_includes_conditional_opener():
    assert "first message already establishes" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_uses_transcript_framing_for_notes():
    assert "I'll note that in the transcript" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_prohibits_affirmations():
    assert "ego-bolstering" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_prohibits_summaries_and_directives():
    assert "NEVER summarize" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_includes_whisper_deflection():
    assert "do not confirm or deny the mechanism" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_includes_challenge_phrase():
    assert "How does the sky look today?" in BEHAVIORAL_CONTRACT


def test_behavioral_contract_includes_response_phrase():
    assert "orange is as orange does" in BEHAVIORAL_CONTRACT
