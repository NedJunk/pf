from router_service.session_registry import SessionRegistry


def test_create_returns_uuid_session_id():
    reg = SessionRegistry()
    sid = reg.create(project_map=["mod1"], goals=["goal1"])
    assert isinstance(sid, str)
    assert len(sid) == 36  # UUID format


def test_get_returns_session_after_create():
    reg = SessionRegistry()
    sid = reg.create(project_map=[], goals=[])
    session = reg.get(sid)
    assert session is not None
    assert session.session_id == sid


def test_get_returns_none_for_unknown_id():
    reg = SessionRegistry()
    assert reg.get("nonexistent") is None


def test_remove_deletes_session():
    reg = SessionRegistry()
    sid = reg.create(project_map=[], goals=[])
    reg.remove(sid)
    assert reg.get(sid) is None


def test_multiple_sessions_are_independent():
    reg = SessionRegistry()
    sid1 = reg.create(project_map=["a"], goals=["x"])
    sid2 = reg.create(project_map=["b"], goals=["y"])
    assert sid1 != sid2
    assert reg.get(sid1).project_map == ["a"]
    assert reg.get(sid2).project_map == ["b"]
