from personal_affairs.application.item_service import _apply_people_status


def test_waiting_person_sets_item_status_to_waiting() -> None:
    payload = {"status": "planned"}
    _apply_people_status(payload, [{"person_id": "p1", "role": "waiting"}], "planned")
    assert payload["status"] == "waiting"


def test_removing_waiting_people_returns_waiting_item_to_planned() -> None:
    payload = {}
    _apply_people_status(payload, [], "waiting")
    assert payload["status"] == "planned"


def test_terminal_status_is_not_overridden_by_waiting_person() -> None:
    payload = {"status": "done"}
    _apply_people_status(payload, [{"person_id": "p1", "role": "waiting"}], "planned")
    assert payload["status"] == "done"
