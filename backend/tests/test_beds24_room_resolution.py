from app.services.beds24_sync_service import _resolve_room


class _FakeDb:
    def __init__(self):
        self.lookups = []

    def get(self, model, local_id):
        self.lookups.append((model, local_id))
        return {"local_id": local_id}


def test_present_unmapped_room_id_does_not_fall_back_to_unit_id():
    db = _FakeDb()
    settings = {
        "room_map_by_room_id": {"535687": 4},
        "room_map_by_unit_id": {"1": 99},
        "auto_link_room": False,
    }

    room, warnings = _resolve_room(
        db,
        settings,
        {"roomId": "555293", "unitId": "1"},
    )

    assert room is None
    assert db.lookups == []
    assert warnings == ["room mapping unresolved"]


def test_unit_id_mapping_is_allowed_when_room_id_is_absent():
    db = _FakeDb()
    settings = {
        "room_map_by_room_id": {},
        "room_map_by_unit_id": {"1": 99},
        "auto_link_room": False,
    }

    room, warnings = _resolve_room(db, settings, {"unitId": "1"})

    assert room == {"local_id": 99}
    assert len(db.lookups) == 1
    assert db.lookups[0][1] == 99
    assert warnings == []
