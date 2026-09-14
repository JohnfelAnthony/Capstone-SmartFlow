from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from sumolib import checkBinary
except ImportError:  # pragma: no cover - handled at runtime
    checkBinary = None


ROOT = Path(__file__).resolve().parents[1]
SUMO_ROOT = ROOT / "sumo"
VISUAL_NETWORK_ROOT = ROOT / "data" / "generated" / "visual_networks"
DEFAULT_INTERSECTION_ID = "tagum_1"


@dataclass(frozen=True)
class IntersectionAssets:
    intersection_id: str
    label: str
    viewport_label: str
    sumo_dir: Path
    sumo_config_path: Path
    sumo_net_path: Path
    sumo_route_path: Path
    sumo_scope_path: Path
    visual_network_path: Path
    controlled_tls_ids: tuple[str, ...]
    major_tls_ids: tuple[str, ...]
    minor_tls_ids: tuple[str, ...]
    phase_sequence: tuple[tuple[str, float], ...]
    tls_state_map: dict[str, str]
    approach_lanes: dict[str, tuple[str, ...]]
    pedestrian_route_templates: tuple[dict[str, str], ...]
    default_scenario_name: str

    @property
    def expected_asset_paths(self) -> dict[str, Path]:
        return {
            "sumo_dir": self.sumo_dir,
            "sumocfg": self.sumo_config_path,
            "net": self.sumo_net_path,
            "route": self.sumo_route_path,
            "scope": self.sumo_scope_path,
            "visual_network": self.visual_network_path,
        }


SUMO_STEP_LENGTH = 0.1

PHASE_SEQUENCE = (
    ("WEST_GREEN", 35.0),
    ("WEST_YELLOW", 7.0),
    ("EAST_GREEN", 35.0),
    ("EAST_YELLOW", 7.0),
    ("NORTH_GREEN", 20.0),
    ("NORTH_YELLOW", 7.0),
    ("SOUTH_GREEN", 20.0),
    ("SOUTH_YELLOW", 7.0),
    ("PED_GREEN", 20.0),
    ("ALL_RED", 7.0),
)

TLS_STATE_MAP = {
    "WEST_GREEN": "rrrrrrrrrrGGGGrrrr",
    "WEST_YELLOW": "rrrrrrrrrryyyyrrrr",
    "EAST_GREEN": "rrrGGGGrrrrrrrrrrr",
    "EAST_YELLOW": "rrryyyyrrrrrrrrrrr",
    "NORTH_GREEN": "GGGrrrrrrrrrrrrrrr",
    "NORTH_YELLOW": "yyyrrrrrrrrrrrrrrr",
    "SOUTH_GREEN": "rrrrrrrGGGrrrrrrrr",
    "SOUTH_YELLOW": "rrrrrrryyyrrrrrrrr",
    "PED_GREEN": "rrrrrrrrrrrrrrGGGG",
    "ALL_RED": "rrrrrrrrrrrrrrrrrr",
}

APPROACH_LANES = {
    "north": ("-E2_1",),
    "south": ("E3_1",),
    "east": ("-E1_1", "-E1_2"),
    "west": ("E0_1", "E0_2"),
}

PEDESTRIAN_ROUTE_TEMPLATES = (
    {
        "name": "west_to_south",
        "from_edge": "E0",
        "to_edge": "-E3",
    },
    {
        "name": "west_to_east",
        "from_edge": "E0",
        "to_edge": "E1",
    },
    {
        "name": "north_to_south",
        "from_edge": "-E2",
        "to_edge": "-E3",
    },
    {
        "name": "east_to_west",
        "from_edge": "-E1",
        "to_edge": "-E0",
    },
    {
        "name": "south_to_north",
        "from_edge": "E3",
        "to_edge": "E2",
    },
)

TAGUM_2_PHASE_SEQUENCE = (
    ("NORTH_GREEN", 30.0),
    ("NORTH_YELLOW", 7.0),
    ("EAST_GREEN", 30.0),
    ("EAST_YELLOW", 7.0),
    ("SOUTH_GREEN", 30.0),
    ("SOUTH_YELLOW", 7.0),
    ("WEST_GREEN", 30.0),
    ("WEST_YELLOW", 7.0),
    ("PED_GREEN", 20.0),
    ("ALL_RED", 7.0),
)

TAGUM_2_TLS_STATE_MAP = {
    "NORTH_GREEN": "rrrrrrrrrGGGGrrrr",
    "NORTH_YELLOW": "rrrrrrrrryyyyrrrr",
    "EAST_GREEN": "GGrrrrrrrrrrrrrrr",
    "EAST_YELLOW": "yyrrrrrrrrrrrrrrr",
    "SOUTH_GREEN": "rrGGGGrrrrrrrrrrr",
    "SOUTH_YELLOW": "rryyyyrrrrrrrrrrr",
    "WEST_GREEN": "rrrrrrGGGrrrrrrrr",
    "WEST_YELLOW": "rrrrrryyyrrrrrrrr",
    "PED_GREEN": "rrrrrrrrrrrrrGGGG",
    "ALL_RED": "rrrrrrrrrrrrrrrrr",
}

TAGUM_2_APPROACH_LANES = {
    "north": ("E2_0", "E2_1", "E2_2"),
    "south": ("-E3_0", "-E3_1", "-E3_2"),
    "east": ("-E4_0", "-E4_1"),
    "west": ("E5_0", "E5_1", "E5_2"),
}

TAGUM_2_PEDESTRIAN_ROUTE_TEMPLATES = (
    {
        "name": "west_to_east",
        "from_edge": "E5",
        "to_edge": "E4",
    },
    {
        "name": "west_to_south",
        "from_edge": "E5",
        "to_edge": "E3",
    },
    {
        "name": "north_to_south",
        "from_edge": "E2",
        "to_edge": "E3",
    },
    {
        "name": "east_to_west",
        "from_edge": "-E4",
        "to_edge": "-E5",
    },
    {
        "name": "south_to_north",
        "from_edge": "-E3",
        "to_edge": "-E2",
    },
)

DENSITY_SCALE = {
    "none": 0.0,
    "low": 0.08,
    "medium": 1.0,
    "high": 1.5,
    "heavy": 1.5,
}

VEHICLE_SAMPLE_LIMIT = 160
PEDESTRIAN_SAMPLE_LIMIT = 64
EVENT_LIMIT = 100
CHART_HISTORY_LIMIT = 30

PEDESTRIAN_SPAWN_INTERVALS = {
    "none": None,
    "low": 12.0,
    "medium": 8.0,
    "high": 5.0,
    "heavy": 4.0,
}


def _visual_network_path(intersection_id: str) -> Path:
    return VISUAL_NETWORK_ROOT / f"{intersection_id}.json"


def _build_assets(
    *,
    intersection_id: str,
    label: str,
    viewport_label: str,
    folder_name: str,
    sumocfg_name: str,
    net_name: str,
    route_name: str,
    scope_name: str,
    controlled_tls_ids: tuple[str, ...],
    phase_sequence: tuple[tuple[str, float], ...],
    tls_state_map: dict[str, str],
    approach_lanes: dict[str, tuple[str, ...]],
    pedestrian_route_templates: tuple[dict[str, str], ...],
    default_scenario_name: str,
    major_tls_ids: tuple[str, ...] | None = None,
    minor_tls_ids: tuple[str, ...] = (),
) -> IntersectionAssets:
    sumo_dir = SUMO_ROOT / folder_name
    resolved_major_tls_ids = major_tls_ids if major_tls_ids is not None else controlled_tls_ids
    return IntersectionAssets(
        intersection_id=intersection_id,
        label=label,
        viewport_label=viewport_label,
        sumo_dir=sumo_dir,
        sumo_config_path=sumo_dir / sumocfg_name,
        sumo_net_path=sumo_dir / net_name,
        sumo_route_path=sumo_dir / route_name,
        sumo_scope_path=sumo_dir / scope_name,
        visual_network_path=_visual_network_path(intersection_id),
        controlled_tls_ids=controlled_tls_ids,
        major_tls_ids=resolved_major_tls_ids,
        minor_tls_ids=minor_tls_ids,
        phase_sequence=phase_sequence,
        tls_state_map=tls_state_map,
        approach_lanes=approach_lanes,
        pedestrian_route_templates=pedestrian_route_templates,
        default_scenario_name=default_scenario_name,
    )


INTERSECTION_ASSET_REGISTRY: dict[str, IntersectionAssets] = {
    "tagum_1": _build_assets(
        intersection_id="tagum_1",
        label="Tagum 1 (Main)",
        viewport_label="Tagum City — Pioneer Ave & Apokon Rd",
        folder_name="Tagum_1",
        sumocfg_name="tagum1.sumocfg",
        net_name="tagum1.net.xml",
        route_name="tagum1.rou.xml",
        scope_name="main_intersection_scope.json",
        controlled_tls_ids=("J1",),
        phase_sequence=PHASE_SEQUENCE,
        tls_state_map=TLS_STATE_MAP,
        approach_lanes=APPROACH_LANES,
        pedestrian_route_templates=PEDESTRIAN_ROUTE_TEMPLATES,
        default_scenario_name="Tagum City - J1 Main Intersection",
    ),
    "tagum_2": _build_assets(
        intersection_id="tagum_2",
        label="Tagum 2 (Secondary)",
        viewport_label="Tagum City — J6 Secondary Intersection",
        folder_name="Tagum_2",
        sumocfg_name="tagum2.sumocfg",
        net_name="tagum2.net.xml",
        route_name="tagum2.rou.xml",
        scope_name="main_intersection_scope.json",
        controlled_tls_ids=("J6",),
        phase_sequence=TAGUM_2_PHASE_SEQUENCE,
        tls_state_map=TAGUM_2_TLS_STATE_MAP,
        approach_lanes=TAGUM_2_APPROACH_LANES,
        pedestrian_route_templates=TAGUM_2_PEDESTRIAN_ROUTE_TEMPLATES,
        default_scenario_name="Tagum City - J6 Secondary Intersection",
    ),
    "tagum_3": _build_assets(
        intersection_id="tagum_3",
        label="Tagum 3 (Bypass)",
        viewport_label="Tagum City — J3 Bypass Intersection",
        folder_name="Tagum_3",
        sumocfg_name="tagum3.sumocfg",
        net_name="tagum3.net.xml",
        route_name="tagum3.rou.xml",
        scope_name="main_intersection_scope.json",
        controlled_tls_ids=("J3",),
        phase_sequence=PHASE_SEQUENCE,
        tls_state_map=TLS_STATE_MAP,
        approach_lanes=APPROACH_LANES,
        pedestrian_route_templates=PEDESTRIAN_ROUTE_TEMPLATES,
        default_scenario_name="Tagum City - J3 Bypass Intersection",
    ),
}


def get_intersection_assets(intersection_id: str | None) -> IntersectionAssets:
    normalized_intersection_id = str(intersection_id or DEFAULT_INTERSECTION_ID).strip().lower()
    return INTERSECTION_ASSET_REGISTRY.get(
        normalized_intersection_id,
        INTERSECTION_ASSET_REGISTRY[DEFAULT_INTERSECTION_ID],
    )


DEFAULT_INTERSECTION_ASSETS = get_intersection_assets(DEFAULT_INTERSECTION_ID)

# Backward-compatible defaults for code that still expects single-intersection
# constants while the rest of the stack is being migrated to the registry.
SUMO_DIR = DEFAULT_INTERSECTION_ASSETS.sumo_dir
SUMO_CONFIG_PATH = DEFAULT_INTERSECTION_ASSETS.sumo_config_path
SUMO_NET_PATH = DEFAULT_INTERSECTION_ASSETS.sumo_net_path
SUMO_ROUTE_PATH = DEFAULT_INTERSECTION_ASSETS.sumo_route_path
SUMO_SCOPE_PATH = DEFAULT_INTERSECTION_ASSETS.sumo_scope_path
CONTROLLED_TLS_IDS = DEFAULT_INTERSECTION_ASSETS.controlled_tls_ids
MAJOR_TLS_IDS = DEFAULT_INTERSECTION_ASSETS.major_tls_ids
MINOR_TLS_IDS = DEFAULT_INTERSECTION_ASSETS.minor_tls_ids
DEFAULT_SCENARIO_NAME = DEFAULT_INTERSECTION_ASSETS.default_scenario_name


def get_sumo_binary() -> str:
    if checkBinary is None:
        raise RuntimeError("sumolib is unavailable; cannot resolve the SUMO binary")
    return checkBinary("sumo")
