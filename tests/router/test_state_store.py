from src.router.state_store import StateStore, Whisper


def test_initializes_with_empty_context():
    store = StateStore()
    state = store.get_state()
    assert state.project_map == []
    assert state.goals == []
    assert state.history == []
    assert state.whispers == []


def test_update_goals():
    store = StateStore()
    store.update_goals(["Reduce Overwhelm", "Ship v1"])
    assert store.get_state().goals == ["Reduce Overwhelm", "Ship v1"]


def test_update_goals_replaces_not_appends():
    store = StateStore()
    store.update_goals(["Goal A"])
    store.update_goals(["Goal B"])
    assert store.get_state().goals == ["Goal B"]


def test_add_to_history():
    store = StateStore()
    store.add_to_history("User: Hello")
    store.add_to_history("Router: Hi there")
    assert store.get_state().history == ["User: Hello", "Router: Hi there"]


def test_inject_whisper():
    store = StateStore()
    store.inject_whisper("ProjectManager", "We already have a task for this.")
    whispers = store.get_state().whispers
    assert len(whispers) == 1
    assert whispers[0] == Whisper(source="ProjectManager", message="We already have a task for this.")


def test_inject_multiple_whispers():
    store = StateStore()
    store.inject_whisper("ProjectManager", "Task already exists.")
    store.inject_whisper("Architect", "Consider the existing API.")
    assert len(store.get_state().whispers) == 2


def test_clear_whispers():
    store = StateStore()
    store.inject_whisper("PM", "Note one.")
    store.inject_whisper("PM", "Note two.")
    store.clear_whispers()
    assert store.get_state().whispers == []
