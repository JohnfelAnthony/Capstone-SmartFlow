"""Apply the same serialized size bound to imports and saved scenarios."""
import config


def validate_scenario_json_size(field_name: str, raw_json: str) -> None:
    payload_bytes = len(raw_json.encode("utf-8"))
    if payload_bytes > config.SCENARIO_CONFIG_MAX_BYTES:
        raise ValueError(
            f"JSON configuration for '{field_name}' exceeds the "
            f"{config.SCENARIO_CONFIG_MAX_BYTES}-byte limit (expanded size: {payload_bytes} bytes). "
            "Split demand into smaller periods or increase SMARTFLOW_SCENARIO_CONFIG_MAX_BYTES."
        )
