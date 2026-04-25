def test_project_runs():
    assert True


from tests.fixtures.transcripts import EXAMPLE_TRANSCRIPTS, REQUIRED_BEHAVIORS


def test_example_transcripts_define_required_behaviors():
    all_validated = {
        tag
        for transcript in EXAMPLE_TRANSCRIPTS
        for turn in transcript["turns"]
        for tag in turn.get("validates", [])
    }
    for behavior in REQUIRED_BEHAVIORS:
        assert behavior in all_validated, f"No transcript validates behavior: {behavior}"
