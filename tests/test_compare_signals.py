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
