from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str


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


class RLModelRecord(BaseModel):
    id: int
    algorithm: str
    name: str | None = None
    checkpoint_path: str | None = None
    training_date: str | None = None
    best_evaluation_score: float | None = None


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


class LoginResponse(BaseModel):
    user: CurrentUser
    landing_path: str | None = None


class Scenario(BaseModel):
    id: int
    name: str
    description: str | None = ""
    traffic_density: str
    pedestrian_density: str
    emergency_mode: str
    road_constraint: str
    intersection_id: str
    engine_config: dict[str, Any] = Field(default_factory=dict)
    lane_closure_config: dict[str, Any] = Field(default_factory=dict)
    construction_config: dict[str, Any] = Field(default_factory=dict)
    accident_config: dict[str, Any] = Field(default_factory=dict)
    flooding_config: dict[str, Any] = Field(default_factory=dict)
    created_by: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    is_official: bool
    is_archived: bool


class ScenarioListResponse(BaseModel):
    scenarios: list[Scenario]


class ScenarioWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default="", max_length=2000)
    traffic_density: str = Field(default="Medium", min_length=1, max_length=40)
    pedestrian_density: str = Field(default="Medium", min_length=1, max_length=40)
    emergency_mode: str = Field(default="Disabled", min_length=1, max_length=80)
    road_constraint: str = Field(default="None", min_length=1, max_length=120)
    intersection_id: str = Field(default="tagum_1", min_length=1, max_length=80)
    engine_config: dict[str, Any] = Field(default_factory=dict)
    lane_closure_config: dict[str, Any] = Field(default_factory=dict)
    construction_config: dict[str, Any] = Field(default_factory=dict)
    accident_config: dict[str, Any] = Field(default_factory=dict)
    flooding_config: dict[str, Any] = Field(default_factory=dict)


class SimulationConfigureRequest(BaseModel):
    engine_config: dict[str, Any] | None = None
    scenario_id: int | None = Field(default=None, ge=1)
    intersection_id: str | None = Field(default=None, min_length=1, max_length=80)
    traffic_density: str | None = Field(default=None, min_length=1, max_length=40)
    pedestrian_density: str | None = Field(default=None, min_length=1, max_length=40)
    emergency_mode: str | None = Field(default=None, min_length=1, max_length=80)
    road_constraint: str | None = Field(default=None, min_length=1, max_length=120)
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


class CompareRunBundle(BaseModel):
    option: CompareRunOption
    frames: list[CompareTimelineFrame] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ComparePairResponse(BaseModel):
    left: CompareRunBundle
    right: CompareRunBundle
    frame_count: int
    warnings: list[str] = Field(default_factory=list)


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
    selected_scenario_id: int | None = None
    selected_scenario_name: str | None = None
    duration_seconds: int
    seed: int
    control_mode: str
    state: dict[str, Any]


class SimulationActionResponse(BaseModel):
    ok: bool = True
    message: str
    simulation: SimulationStateResponse
