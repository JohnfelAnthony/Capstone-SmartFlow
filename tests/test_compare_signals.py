from services.compare_signals import summarize_signals


def frame(t, phase, stage="green", mode="signalized"):
    return {"time": t, "junction_controls": {"j": {"phase": phase, "stage": stage, "mode": mode, "selected_for_rl": True}}}


def test_green_durations_exclude_partial_edges_and_record_actual_variation():
    frames = [frame(0, "NORTH_GREEN"), frame(1, "ALL_RED", "red"),
              frame(2, "NORTH_GREEN"), frame(3, "NORTH_GREEN"), frame(4, "ALL_RED", "red"),
              frame(5, "NORTH_GREEN"), frame(6, "NORTH_GREEN"), frame(7, "NORTH_GREEN"), frame(8, "ALL_RED", "red"),
              frame(9, "NORTH_GREEN"), frame(10, "NORTH_GREEN")]
    result = summarize_signals(frames, step=1, start=0, end=10)
    phase = result["phases"][0]
    assert phase == {"phase": "NORTH_GREEN", "total_seconds": 7, "complete_count": 2, "mean_seconds": 2.5, "min_seconds": 2, "max_seconds": 3}
    assert result["junction_id"] == "j"


def test_gaps_are_not_counted_as_long_greens_and_unknown_control_is_unavailable():
    result = summarize_signals([frame(0, "NORTH_GREEN"), frame(1, "NORTH_GREEN"), frame(20, "NORTH_GREEN"), frame(21, "ALL_RED", "red")], step=1, start=0, end=25)
    assert result["unavailable_seconds"] == 23
    assert result["phases"][0]["mean_seconds"] is None
    assert result["phases"][0]["total_seconds"] == 2
    assert summarize_signals([{"time": 0}, {"time": 1}], step=1, start=0, end=1)["unavailable_seconds"] == 1


def test_unsignalized_junction_never_claims_green_duration():
    result = summarize_signals([frame(0, "NORTH_GREEN", mode="first_come"), frame(1, "NORTH_GREEN", mode="first_come")], step=1, start=0, end=1)
    assert result["phases"] == []
    assert result["segments"][0]["stage"] == "unsignalized"


def test_reading_only_time_and_signal_state_gives_the_full_frame_answer():
    import json
    from services.compare_signals import _signal_fields

    frames = [
        {"engine_version": "native-14", "time": 0.1, "visible_time": 0.0, "vehicles": [{"id": "car-1", "time": 99, "junction_controls": "no"}],
         "junction_controls": {"j": {"mode": "signalized", "phase": "N", "stage": "green", "nested": {"a": [1, {"b": 2}]}}}},
        {"time": 1e-05, "junction_controls": None},
        {"time": 2.5, "vehicles": []},
        {"note": "{braces before time}", "time": 3.0, "junction_controls": {}},
    ]
    for frame in frames:
        line = json.dumps(frame)
        fields = _signal_fields(line)
        assert fields.get("time") == frame.get("time")
        assert fields.get("junction_controls") == frame.get("junction_controls")
