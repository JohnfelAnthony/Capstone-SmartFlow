from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str


class NetworkRevisionPreviewRequest(BaseModel):
    network: dict[str, Any]


class NetworkRevisionApplyRequest(NetworkRevisionPreviewRequest):
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    username: str = Field(min_length=3, max_length=80)
    email: str | None = Field(default=None, max_length=160)
    password: str = Field(min_length=1, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)


class RegisterResponse(BaseModel):
    message: str
    account_status: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)
    confirm_password: str = Field(min_length=1, max_length=256)


class MessageResponse(BaseModel):
    message: str


class Permission(BaseModel):
    page: str
    action: str


class AdminUser(BaseModel):
    id: int
    full_name: str
    username: str
    email: str | None = None
    role: str
    role_id: int
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    last_login_at: str | None = None
    must_change_password: bool
    run_count: int = 0
    audit_count: int = 0
    is_self: bool = False


class AdminUserListResponse(BaseModel):
    users: list[AdminUser]


class AdminUserCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    username: str = Field(min_length=3, max_length=80)
    email: str | None = Field(default=None, max_length=160)
    role_id: int = Field(default=2, ge=1)
    status: str = Field(default="active", min_length=1, max_length=40)
    must_change_password: bool = True


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    username: str | None = Field(default=None, min_length=3, max_length=80)
    email: str | None = Field(default=None, max_length=160)
    role_id: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, min_length=1, max_length=40)
    must_change_password: bool | None = None


class AdminUserCreateResponse(BaseModel):
    user: AdminUser
    temporary_password: str
    message: str


class AdminPasswordResetResponse(BaseModel):
    temporary_password: str
    message: str
    user: AdminUser


class AdminRole(BaseModel):
    id: int
    name: str
    description: str | None = None
    permissions: list[Permission] = Field(default_factory=list)
    locked: bool = False


class AdminRoleListResponse(BaseModel):
    roles: list[AdminRole]


class RolePermissionUpdate(BaseModel):
    page: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=80)
    enabled: bool


class RolePermissionUpdateRequest(BaseModel):
    updates: list[RolePermissionUpdate] = Field(default_factory=list)


class AuditLogRecord(BaseModel):
    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    target: str
    details: str | None = None
    timestamp: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogRecord]


class BackupRecord(BaseModel):
    id: int
    filename: str
    created_by: int | None = None
    username: str | None = None
    created_at: str | None = None
    size_bytes: int = 0


class BackupListResponse(BaseModel):
    backups: list[BackupRecord]


class BackupActionResponse(BaseModel):
    message: str
    backup: BackupRecord | None = None
    restore_path: str | None = None


class RLModelRecord(BaseModel):
    id: int
    algorithm: str
    name: str | None = None
    checkpoint_path: str | None = None
    training_date: str | None = None
    best_evaluation_score: float | None = None
    compatible: bool = False
    compatibility_message: str = ""
    controlled_junction: str | None = None
    network_id: str | None = None
    decision_interval_seconds: float = 5
    minimum_green_hold_seconds: float = 10
    training_status: str | None = None
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)


class RLModelListResponse(BaseModel):
    models: list[RLModelRecord]


class RLTrainingJobItem(BaseModel):
    id: int
    job_id: int
    algorithm: str
    sequence_index: int
    status: str
    progress_percent: float = 0
    latest_episode: int = 0
    latest_reward: float | None = None
    latest_epsilon: float | None = None
    latest_timesteps: int = 0
    artifact_path: str | None = None
    metadata_path: str | None = None
    rl_model_id: int | None = None
    evaluation_path: str | None = None
    message: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    created_at: str | None = None


class RLTrainingJob(BaseModel):
    id: int
    user_id: int | None = None
    status: str
    selected_algorithms: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    progress_percent: float = 0
    current_algorithm: str | None = None
    current_item_id: int | None = None
    log_path: str | None = None
    message: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    created_at: str | None = None


class RLLogLine(BaseModel):
    ts: str | None = None
    type: str | None = None
    algorithm: str | None = None
    text: str


class RLTrainingStatusResponse(BaseModel):
    active_job_id: int | None = None
    job: RLTrainingJob | None = None
    items: list[RLTrainingJobItem] = Field(default_factory=list)
    log_lines: list[RLLogLine] = Field(default_factory=list)
    models: list[RLModelRecord] = Field(default_factory=list)


class RLTrainingJobListResponse(BaseModel):
    jobs: list[RLTrainingJob]


class RLTrainingStartRequest(BaseModel):
    algorithms: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    advanced: dict[str, Any] = Field(default_factory=dict)


class RLEvaluateModelRequest(BaseModel):
    model_id: int = Field(ge=1)
    settings: dict[str, Any] = Field(default_factory=dict)


class RLJobActionResponse(BaseModel):
    message: str
    job_id: int | None = None


class CurrentUser(BaseModel):
    id: int
    username: str
    full_name: str
    email: str | None = None
    role: str
    role_id: int
    status: str
    must_change_password: bool
    permissions: list[Permission] = Field(default_factory=list)
    created_at: str | None = None


class LoginResponse(BaseModel):
    user: CurrentUser
    landing_path: str | None = None


class Scenario(BaseModel):
    id: int
    name: str
    description: str | None = ""
    network_id: str | None
    migration_error: str | None = None
    engine_config: dict[str, Any] = Field(default_factory=dict)
    created_by: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    is_official: bool
    is_archived: bool


class ScenarioListResponse(BaseModel):
    scenarios: list[Scenario]


class ScenarioWriteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default="", max_length=2000)
    network_id: str | None = Field(default=None, min_length=1, max_length=80)
    engine_config: dict[str, Any] = Field(default_factory=dict)


class ObservationImportRequest(BaseModel):
    kind: str
    source_kind: str = "synthetic"
    csv_text: str
    source_description: str
    collected_on: str
    collection_start: str | None = None
    collection_end: str | None = None
    engine_config: dict[str, Any] = Field(default_factory=dict)
    network_id: str | None = None


class ClosureCheckRequest(BaseModel):
    closed_lanes: list[str] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


RouteId = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")]
RouteVehicleClass = Literal["car", "motorcycle", "tricycle", "bus", "truck"]
RouteResponseChoice = Literal["side_street", "side_street_adaptive", "share", "nearest_exit", "wait"]
RouteBasis = Literal["initial_arrangement_zero_queue"]


class RoutePlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RouteScenarioSource(RoutePlannerInput):
    kind: Literal["scenario"]
    scenario_id: int = Field(strict=True, ge=1, le=2**63-1)


class RouteNetworkSource(RoutePlannerInput):
    kind: Literal["network"]
    network_id: RouteId


RouteSource = Annotated[RouteScenarioSource | RouteNetworkSource, Field(discriminator="kind")]


class RouteClosureOverride(RoutePlannerInput):
    closed_lanes: list[RouteId] = Field(max_length=1024)
    closure_responses: dict[RouteId, RouteResponseChoice] = Field(max_length=1024)


class RouteContextRequest(RoutePlannerInput):
    source: RouteSource
    vehicle_type: RouteVehicleClass


class RoutePreviewRequest(RouteContextRequest):
    expected_network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    entry_id: RouteId
    destination_id: RouteId
    closure_override: RouteClosureOverride = Field(
        default_factory=lambda: RouteClosureOverride(closed_lanes=[], closure_responses={}),
    )


class RouteNotice(BaseModel):
    code: str
    message: str


class RouteBoundary(BaseModel):
    id: str
    label: str


class RouteEntry(RouteBoundary):
    lane_ids: list[str]


class RoutePair(BaseModel):
    entry_id: str
    destination_id: str


class RouteRoad(BaseModel):
    lane_id: str
    road_id: str
    label: str
    direction: str


class RouteContextResponse(BaseModel):
    source: RouteSource
    source_label: str
    network_id: str
    network_sha256: str
    network_binding: Literal["saved_fingerprint", "current_unpinned", "current_network"]
    geometry: dict[str, Any]
    entries: list[RouteEntry]
    destinations: list[RouteEntry]
    eligible_pairs: list[RoutePair]
    initial_closures: RouteClosureOverride
    roads: list[RouteRoad]
    basis: RouteBasis
    has_later_closure_changes: bool
    notices: list[RouteNotice]


class RoutePoint(BaseModel):
    x: float
    y: float


class RouteLaneSegment(BaseModel):
    kind: Literal["lane"]
    lane_id: str
    points: list[RoutePoint]


class RouteConnectorSegment(BaseModel):
    kind: Literal["connector"]
    from_lane_id: str
    to_lane_id: str
    points: list[RoutePoint]


RouteSegment = Annotated[RouteLaneSegment | RouteConnectorSegment, Field(discriminator="kind")]


class RoutePath(BaseModel):
    lane_ids: list[str]
    destination_id: str
    destination_label: str
    segments: list[RouteSegment]


class RouteResponseOption(BaseModel):
    value: RouteResponseChoice
    enabled: bool
    reason: str | None


class RouteSharedRoad(BaseModel):
    road_id: str
    shared_lane: str
    kept_lane: str
    width: float
    lanes: dict[str, list[tuple[float, float]]]


class RoutePreviewResponse(BaseModel):
    network_id: str
    network_sha256: str
    basis: RouteBasis
    routing_mode: Literal["static", "adaptive"]
    arrangement_valid: bool
    effective_closures: RouteClosureOverride
    effective_closed_lanes: list[str]
    response_options: dict[str, list[RouteResponseOption]]
    original: RoutePath | None
    selected: RoutePath | None
    outcome: Literal["unchanged", "detour", "alternative_exit", "waiting_entry", "no_route", "invalid_arrangement"]
    reason: str
    intended_destination_id: str
    actual_destination_id: str | None
    shared_roads: list[RouteSharedRoad]
    uses_shared_pavement: bool
    notices: list[RouteNotice]


class MovementCountsRequest(BaseModel):
    csv_text: str
    network_id: str
    engine_config: dict[str, Any] = Field(default_factory=dict)


class FieldObserverCountsRequest(BaseModel):
    network_id: str
    engine_config: dict[str, Any] = Field(default_factory=dict)
    files: dict[str, str]


class ObservationImportResponse(BaseModel):
    engine_config: dict[str, Any]
    summary: dict[str, Any]


class SimulationConfigureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine_config: dict[str, Any] | None = None
    scenario_id: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=1, le=24 * 60 * 60)
    seed: int | None = Field(default=None, ge=0, le=2**32-1)
    control_mode: str | None = Field(default=None, min_length=1, max_length=80)


class SimulationStartRequest(BaseModel):
    scenario_id: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=1, le=24 * 60 * 60)
    seed: int | None = Field(default=None, ge=0, le=2**32-1)
    control_mode: str | None = Field(default=None, min_length=1, max_length=80)


class SimulationStepRequest(BaseModel):
    num_ticks: int = Field(default=1, ge=1, le=600)


class SimulationSpeedRequest(BaseModel):
    speed_multiplier: float = Field(ge=0.25, le=4)


class TimelineGenerateRequest(BaseModel):
    scenario_id: int = Field(ge=1)
    duration_seconds: int = Field(default=300, ge=1, le=24 * 60 * 60)
    seed: int | None = Field(default=None, ge=0, le=2**32-1)
    control_mode: str | None = Field(default="fixed-time", min_length=1, max_length=80)


class PlaybackLoadRequest(BaseModel):
    run_id: int = Field(ge=1)


class PlaybackSeekRequest(BaseModel):
    frame_index: int = Field(ge=0)


class SimulationRunRecord(BaseModel):
    id: int
    scenario_id: int | None = None
    scenario_name: str | None = None
    user_id: int | None = None
    user_name: str | None = None
    run_mode: str
    control_mode: str
    status: str
    start_time: str | None = None
    end_time: str | None = None
    duration_seconds: float = 0
    seed: int | None = None
    rl_model_id: int | None = None
    notes: str | None = None
    timeline_path: str | None = None
    is_favorite: bool = False
    metrics: dict[str, Any] | None = None


class SimulationRunListResponse(BaseModel):
    runs: list[SimulationRunRecord]


class RunFavoriteRequest(BaseModel):
    is_favorite: bool


class ReportExportRequest(BaseModel):
    run_ids: list[int] = Field(default_factory=list)
    format: str = Field(default="csv", min_length=1, max_length=16)


class CompareTimelineMeta(BaseModel):
    intersection_id: str | None = None
    requested_duration_seconds: float = 0
    actual_duration_seconds: float = 0
    step_length_seconds: float = 0
    frame_count: int = 0


class CompareRunOption(BaseModel):
    run: SimulationRunRecord
    label: str
    timeline: CompareTimelineMeta
    compatibility_key: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class CompareRunListResponse(BaseModel):
    runs: list[CompareRunOption]


class CompareTimelineFrame(BaseModel):
    index: int
    time: float = 0
    phase: str = "UNKNOWN"
    phase_remaining: float = 0
    queues: dict[str, float] = Field(default_factory=dict)
    vehicle_count: int = 0
    pedestrian_count: int = 0
    avg_wait: float = 0
    avg_queue: float = 0
    max_queue: float = 0
    throughput: float = 0
    avg_ped_delay: float = 0
    interpreted_metrics: dict[str, float | None] = Field(default_factory=dict)


class CompareRunBundle(BaseModel):
    option: CompareRunOption
    frames: list[CompareTimelineFrame] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ComparePairFramesResponse(BaseModel):
    times: list[float]
    left: list[dict[str, Any]]
    right: list[dict[str, Any]]
    duration: float


class ComparePairResponse(BaseModel):
    left: CompareRunBundle
    right: CompareRunBundle
    frame_count: int
    comparison_type: str
    playback_times: list[float]
    geometry: dict[str, Any] | None = None
    opening_frames: ComparePairFramesResponse | None = None
    warnings: list[str] = Field(default_factory=list)


class ComparePairHistoryResponse(BaseModel):
    left: list[CompareTimelineFrame]
    right: list[CompareTimelineFrame]


class RunTimelineResponse(BaseModel):
    run: SimulationRunRecord
    timeline: CompareTimelineMeta
    frames: list[CompareTimelineFrame] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)


class TimelineGenerateResponse(BaseModel):
    message: str
    run: SimulationRunRecord


class SimulationStateResponse(BaseModel):
    status: str
    owner_user_id: int | None = None
    owner_name: str | None = None
    active_run_id: int | None = None
    run_mode: str = "live"
    speed_multiplier: float = 1
    selected_scenario_id: int | None = None
    selected_scenario_name: str | None = None
    duration_seconds: int
    seed: int
    control_mode: str
    state: dict[str, Any]
    render_frame: dict[str, Any] | None = None
    render_frame_error: str | None = None


class SimulationActionResponse(BaseModel):
    ok: bool = True
    message: str
    simulation: SimulationStateResponse


class SignalDesignRequest(BaseModel):
    """Inputs for a provisional Webster plan; see simulation/signal_design.py for the formulas and placeholders."""
    network_id: str | None = None
    junction: str | None = None
    phase_order: list[Any] = Field(min_length=1)
    # approach -> vehicle class -> vehicles per hour
    approach_counts: dict[str, dict[str, float]]
    base_plan: dict[str, Any] = Field(default_factory=dict)
    pedestrian_green_seconds: float | None = None
