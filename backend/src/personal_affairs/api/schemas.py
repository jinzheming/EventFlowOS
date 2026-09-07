from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_affairs.application.external_profiles import (
    normalize_external_binding,
    normalize_external_profile,
)
from personal_affairs.application.llm_profiles import normalize_llm_binding, normalize_llm_profile
from personal_affairs.application.write_targets import normalize_write_target
from personal_affairs.domain.enums import (
    ActorType,
    AgentProposalAction,
    AgentProposalRiskTier,
    AgentProposalSourceType,
    AgentProposalState,
    DeliveryChannel,
    DeliveryStatus,
    ItemScope,
    ItemStatus,
    MilestoneStatus,
    Priority,
    ProgressMode,
    ProjectHealth,
    ProjectStatus,
    ReminderTiming,
)


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    instance: str | None = None
    retryable: bool = False


class SessionOut(BaseModel):
    user_id: UUID
    username: str
    csrf_token: str
    timezone: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[Literal["read", "write"]] = Field(default=["read", "write"])
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class TokenOut(BaseModel):
    id: UUID
    name: str
    scopes: list[str]
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class TokenCreated(TokenOut):
    token: str


WebhookEventType = Literal[
    "item.created",
    "item.completed",
    "reminder.fired",
    "reminder.acked",
    "reminder.snoozed",
    "delivery.failed",
]


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2000)
    events: list[WebhookEventType] = Field(min_length=1)


class WebhookOut(BaseModel):
    id: UUID
    name: str
    url: str
    events: list[str]
    active: bool
    created_at: datetime
    updated_at: datetime


class WebhookCreated(WebhookOut):
    secret: str


class WebhookEventOut(BaseModel):
    id: UUID
    event_type: str
    aggregate: str
    aggregate_id: UUID
    payload: dict[str, Any] = {}
    created_at: datetime
    attempt_count: int = 0
    status: str
    last_error_code: str | None = None
    last_error_message: str | None = None


WriteTargetType = Literal["feishu_bitable", "custom"]


class WriteTargetPresetOut(BaseModel):
    target_type: WriteTargetType
    label: str
    format_key: str
    field_mapping: dict[str, str]
    description: str


class WriteTargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_type: WriteTargetType = "feishu_bitable"
    target_url: str = Field(min_length=1, max_length=2000)
    format_key: str | None = Field(default=None, max_length=120)
    field_mapping: dict[str, Any] = Field(default_factory=dict)
    instructions: str | None = Field(default=None, max_length=2000)
    active: bool = True

    @model_validator(mode="after")
    def normalize_mapping(self) -> "WriteTargetCreate":
        self.format_key, self.field_mapping = normalize_write_target(
            self.target_type,
            self.format_key,
            self.field_mapping,
        )
        return self


class WriteTargetPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    target_type: WriteTargetType | None = None
    target_url: str | None = Field(default=None, min_length=1, max_length=2000)
    format_key: str | None = Field(default=None, max_length=120)
    field_mapping: dict[str, Any] | None = None
    instructions: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class WriteTargetOut(BaseModel):
    id: UUID
    name: str
    target_type: WriteTargetType
    target_url: str
    format_key: str
    field_mapping: dict[str, str]
    instructions: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


ExternalProviderKey = Literal["feishu", "webhook", "notion", "calendar", "custom_http"]
ExternalCapability = Literal["write", "read", "sync", "notify", "lookup", "export"]
ExternalScopeType = Literal["global", "project", "item_type", "source_type", "person", "tag"]
ExternalConflictPolicy = Literal["append", "update", "skip", "ask"]


class ExternalProfilePresetOut(BaseModel):
    preset_key: str
    label: str
    provider_key: ExternalProviderKey
    capability: ExternalCapability
    auth_ref: str | None = None
    default_format_key: str
    default_field_mapping: dict[str, Any]
    description: str


class ExternalPurposePresetOut(BaseModel):
    purpose_key: str
    label: str
    capabilities: list[ExternalCapability]
    description: str


class ExternalProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_key: ExternalProviderKey = "feishu"
    preset_key: str | None = Field(default=None, max_length=120)
    capability: ExternalCapability = "write"
    auth_ref: str | None = Field(default=None, max_length=240)
    active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)

    @model_validator(mode="after")
    def normalize_profile(self) -> "ExternalProfileCreate":
        normalized = normalize_external_profile(
            self.provider_key,
            self.capability,
            preset_key=self.preset_key,
            auth_ref=self.auth_ref,
        )
        self.provider_key = normalized["provider_key"]
        self.capability = normalized["capability"]
        self.preset_key = normalized["preset_key"]
        self.auth_ref = normalized["auth_ref"]
        return self


class ExternalProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_key: ExternalProviderKey | None = None
    preset_key: str | None = Field(default=None, max_length=120)
    capability: ExternalCapability | None = None
    auth_ref: str | None = Field(default=None, max_length=240)
    active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)


class ExternalProfileOut(BaseModel):
    id: UUID
    name: str
    provider_key: ExternalProviderKey
    preset_key: str | None = None
    capability: ExternalCapability
    auth_ref: str | None = None
    active: bool
    priority: int
    created_at: datetime
    updated_at: datetime


class ExternalBindingCreate(BaseModel):
    profile_id: UUID
    purpose_key: str = Field(min_length=1, max_length=120)
    scope_type: ExternalScopeType = "global"
    scope_value: str | None = Field(default=None, max_length=240)
    target_ref: str = Field(min_length=1, max_length=2000)
    format_key: str = Field(min_length=1, max_length=120)
    field_mapping: dict[str, Any] = Field(default_factory=dict)
    value_mapping: dict[str, Any] = Field(default_factory=dict)
    instructions: str | None = Field(default=None, max_length=2000)
    conflict_policy: ExternalConflictPolicy = "ask"
    dry_run: bool = False
    active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)

    @model_validator(mode="after")
    def normalize_binding(self) -> "ExternalBindingCreate":
        normalized = normalize_external_binding(
            self.purpose_key,
            self.scope_type,
            self.target_ref,
            self.format_key,
            scope_value=self.scope_value,
            field_mapping=self.field_mapping,
            value_mapping=self.value_mapping,
            instructions=self.instructions,
            conflict_policy=self.conflict_policy,
        )
        self.purpose_key = normalized["purpose_key"]
        self.scope_type = normalized["scope_type"]
        self.scope_value = normalized["scope_value"]
        self.target_ref = normalized["target_ref"]
        self.format_key = normalized["format_key"]
        self.field_mapping = normalized["field_mapping"]
        self.value_mapping = normalized["value_mapping"]
        self.instructions = normalized["instructions"]
        self.conflict_policy = normalized["conflict_policy"]
        return self


class ExternalBindingPatch(BaseModel):
    profile_id: UUID | None = None
    purpose_key: str | None = Field(default=None, min_length=1, max_length=120)
    scope_type: ExternalScopeType | None = None
    scope_value: str | None = Field(default=None, max_length=240)
    target_ref: str | None = Field(default=None, min_length=1, max_length=2000)
    format_key: str | None = Field(default=None, min_length=1, max_length=120)
    field_mapping: dict[str, Any] | None = None
    value_mapping: dict[str, Any] | None = None
    instructions: str | None = Field(default=None, max_length=2000)
    conflict_policy: ExternalConflictPolicy | None = None
    dry_run: bool | None = None
    active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)


class ExternalBindingOut(BaseModel):
    id: UUID
    profile_id: UUID
    purpose_key: str
    scope_type: ExternalScopeType
    scope_value: str | None = None
    target_ref: str
    format_key: str
    field_mapping: dict[str, Any]
    value_mapping: dict[str, Any]
    instructions: str | None = None
    conflict_policy: ExternalConflictPolicy
    dry_run: bool
    active: bool
    priority: int
    last_used_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    profile_name: str
    provider_key: ExternalProviderKey
    preset_key: str | None = None
    capability: ExternalCapability
    auth_ref: str | None = None


LLMProviderKey = Literal["litellm", "openai_compatible", "ollama", "custom"]
LLMScopeType = Literal["global", "project", "source_type", "item_type", "risk_tier"]
LLMPrivacyTier = Literal["standard", "private", "sensitive"]


class LLMProfilePresetOut(BaseModel):
    preset_key: str
    label: str
    provider_key: LLMProviderKey
    base_url: str | None = None
    model_name: str
    auth_ref: str | None = None
    capabilities: dict[str, Any]
    default_params: dict[str, Any]
    privacy_tier: LLMPrivacyTier
    description: str


class LLMPurposePresetOut(BaseModel):
    purpose_key: str
    label: str
    required_capabilities: list[str]
    description: str


class LLMProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_key: LLMProviderKey = "litellm"
    preset_key: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=2000)
    model_name: str = Field(min_length=1, max_length=240)
    auth_ref: str | None = Field(default=None, max_length=240)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    default_params: dict[str, Any] = Field(default_factory=dict)
    privacy_tier: LLMPrivacyTier = "standard"
    active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)

    @model_validator(mode="after")
    def normalize_profile(self) -> "LLMProfileCreate":
        normalized = normalize_llm_profile(
            self.provider_key,
            self.model_name,
            preset_key=self.preset_key,
            base_url=self.base_url,
            auth_ref=self.auth_ref,
            capabilities=self.capabilities,
            default_params=self.default_params,
            privacy_tier=self.privacy_tier,
        )
        self.provider_key = normalized["provider_key"]
        self.preset_key = normalized["preset_key"]
        self.base_url = normalized["base_url"]
        self.model_name = normalized["model_name"]
        self.auth_ref = normalized["auth_ref"]
        self.capabilities = normalized["capabilities"]
        self.default_params = normalized["default_params"]
        self.privacy_tier = normalized["privacy_tier"]
        return self


class LLMProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider_key: LLMProviderKey | None = None
    preset_key: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=2000)
    model_name: str | None = Field(default=None, min_length=1, max_length=240)
    auth_ref: str | None = Field(default=None, max_length=240)
    capabilities: dict[str, Any] | None = None
    default_params: dict[str, Any] | None = None
    privacy_tier: LLMPrivacyTier | None = None
    active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)


class LLMProfileOut(BaseModel):
    id: UUID
    name: str
    provider_key: LLMProviderKey
    preset_key: str | None = None
    base_url: str | None = None
    model_name: str
    auth_ref: str | None = None
    capabilities: dict[str, Any]
    default_params: dict[str, Any]
    privacy_tier: LLMPrivacyTier
    active: bool
    priority: int
    created_at: datetime
    updated_at: datetime


class LLMBindingCreate(BaseModel):
    purpose_key: str = Field(min_length=1, max_length=120)
    scope_type: LLMScopeType = "global"
    scope_value: str | None = Field(default=None, max_length=240)
    profile_id: UUID
    override_params: dict[str, Any] = Field(default_factory=dict)
    instructions: str | None = Field(default=None, max_length=2000)
    active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)

    @model_validator(mode="after")
    def normalize_binding(self) -> "LLMBindingCreate":
        normalized = normalize_llm_binding(
            self.purpose_key,
            self.scope_type,
            scope_value=self.scope_value,
            override_params=self.override_params,
            instructions=self.instructions,
        )
        self.purpose_key = normalized["purpose_key"]
        self.scope_type = normalized["scope_type"]
        self.scope_value = normalized["scope_value"]
        self.override_params = normalized["override_params"]
        self.instructions = normalized["instructions"]
        return self


class LLMBindingPatch(BaseModel):
    purpose_key: str | None = Field(default=None, min_length=1, max_length=120)
    scope_type: LLMScopeType | None = None
    scope_value: str | None = Field(default=None, max_length=240)
    profile_id: UUID | None = None
    override_params: dict[str, Any] | None = None
    instructions: str | None = Field(default=None, max_length=2000)
    active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)


class LLMBindingOut(BaseModel):
    id: UUID
    purpose_key: str
    scope_type: LLMScopeType
    scope_value: str | None = None
    profile_id: UUID
    override_params: dict[str, Any]
    instructions: str | None = None
    active: bool
    priority: int
    created_at: datetime
    updated_at: datetime
    profile_name: str
    provider_key: LLMProviderKey
    model_name: str


class LLMResolvedBindingOut(BaseModel):
    binding_id: UUID
    purpose_key: str
    scope_type: LLMScopeType
    scope_value: str | None = None
    override_params: dict[str, Any]
    binding_instructions: str | None = None
    binding_priority: int
    profile_id: UUID
    profile_name: str
    provider_key: LLMProviderKey
    preset_key: str | None = None
    base_url: str | None = None
    model_name: str
    auth_ref: str | None = None
    capabilities: dict[str, Any]
    default_params: dict[str, Any]
    privacy_tier: LLMPrivacyTier
    profile_priority: int


class ItemPersonInput(BaseModel):
    person_id: UUID
    role: Literal["together", "waiting"]


class ItemPersonOut(BaseModel):
    id: UUID
    name: str
    identity: str | None = None
    active: bool = True
    role: Literal["together", "waiting"]


class ItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    notes: str | None = None
    scope: ItemScope
    status: ItemStatus = ItemStatus.INBOX
    priority: Priority = Priority.NORMAL
    project_id: UUID | None = None
    all_day: bool = True
    start_at: datetime | None = None
    due_at: datetime | None = None
    start_date: date | None = None
    due_date: date | None = None
    waiting_on: str | None = Field(default=None, max_length=300)
    waiting_follow_up_date: date | None = None
    recurrence_freq: Literal["daily", "weekly", "monthly"] | None = None
    recurrence_interval: int | None = Field(default=None, ge=1, le=99)
    recurrence_until: date | None = None
    recurrence_count: int | None = Field(default=None, ge=1, le=999)
    estimated_minutes: int | None = Field(default=None, ge=1, le=10080)
    tag_ids: list[UUID] | None = None
    people: list[ItemPersonInput] | None = None


class ItemCreate(ItemBase):
    client_request_id: str | None = Field(default=None, max_length=120)
    intake_text: str | None = None
    intake_scope_source: str | None = None
    intake_origin: Literal["web", "agent", "api"] | None = None
    intake_normalization: Literal["none", "llm"] | None = None


class ItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = None
    status: ItemStatus | None = None
    priority: Priority | None = None
    project_id: UUID | None = None
    all_day: bool | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None
    start_date: date | None = None
    due_date: date | None = None
    waiting_on: str | None = Field(default=None, max_length=300)
    waiting_follow_up_date: date | None = None
    recurrence_freq: Literal["daily", "weekly", "monthly"] | None = None
    recurrence_interval: int | None = Field(default=None, ge=1, le=99)
    recurrence_until: date | None = None
    recurrence_count: int | None = Field(default=None, ge=1, le=999)
    estimated_minutes: int | None = Field(default=None, ge=1, le=10080)
    tag_ids: list[UUID] | None = None
    people: list[ItemPersonInput] | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope: ItemScope
    project_id: UUID | None
    project_name: str | None = None
    title: str
    notes: str | None
    status: ItemStatus
    priority: Priority
    all_day: bool
    start_at: datetime | None
    due_at: datetime | None
    start_date: date | None
    due_date: date | None
    waiting_on: str | None
    waiting_follow_up_date: date | None
    recurrence_freq: str | None
    recurrence_interval: int | None
    recurrence_until: date | None
    recurrence_count: int | None
    estimated_minutes: int | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    archived_at: datetime | None
    deleted_at: datetime | None = None
    created_by_actor: str = "human"
    updated_by_actor: str = "human"
    source_context: dict[str, Any] = {}
    execution_output: dict[str, Any] = {}
    version: int
    created_at: datetime
    updated_at: datetime
    tags: list["ItemTagOut"] = []
    people: list["ItemPersonOut"] = []


class ItemPageOut(BaseModel):
    items: list[ItemOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class ItemTagOut(BaseModel):
    id: UUID
    name: str
    color: str
    parent_id: UUID | None = None


class AgentProposalCreate(BaseModel):
    source_type: AgentProposalSourceType = AgentProposalSourceType.AGENT
    source_ref: str | None = Field(default=None, max_length=500)
    risk_tier: AgentProposalRiskTier = AgentProposalRiskTier.L2
    confidence: float | None = Field(default=None, ge=0, le=1)
    proposed_action: AgentProposalAction = AgentProposalAction.CREATE_ITEM
    proposed_payload: dict[str, Any]
    evidence: dict[str, Any] = {}
    reason: str | None = Field(default=None, max_length=2000)
    target_item_id: UUID | None = None
    expires_at: datetime | None = None


class AgentProposalApprove(BaseModel):
    edited_payload: dict[str, Any] | None = None
    decision_note: str | None = Field(default=None, max_length=1000)


class AgentProposalReject(BaseModel):
    decision_note: str | None = Field(default=None, max_length=1000)


class AgentProposalOut(BaseModel):
    id: UUID
    source_type: AgentProposalSourceType
    source_ref: str | None = None
    risk_tier: AgentProposalRiskTier
    confidence: float | None = None
    state: AgentProposalState
    proposed_action: AgentProposalAction
    proposed_payload: dict[str, Any]
    evidence: dict[str, Any] = {}
    reason: str | None = None
    target_item_id: UUID | None = None
    applied_item_id: UUID | None = None
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by_actor: ActorType | None = None
    decision_note: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentProposalDecisionOut(BaseModel):
    proposal: AgentProposalOut
    item: ItemOut | None = None


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    identity: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)


class PersonPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    identity: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class PersonOut(BaseModel):
    id: UUID
    name: str
    identity: str | None = None
    note: str | None = None
    active: bool
    item_count: int = 0
    created_at: datetime
    updated_at: datetime


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(default="#64748B", pattern=r"^#[0-9A-Fa-f]{6}$")
    parent_id: UUID | None = None


class TagPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    parent_id: UUID | None = None
    pinned: bool | None = None


class TagOut(BaseModel):
    id: UUID
    name: str
    color: str
    parent_id: UUID | None = None
    pinned: bool = False
    item_count: int = 0
    children: list["TagOut"] = []


class ReminderPut(BaseModel):
    timing: ReminderTiming = ReminderTiming.BEFORE_DUE
    offset_minutes: int = Field(default=10, ge=0, le=10080)
    timezone: str = "Asia/Shanghai"
    external_enabled: bool = False


class ReminderOut(BaseModel):
    id: UUID
    item_id: UUID
    timing: ReminderTiming
    offset_minutes: int
    timezone: str
    external_enabled: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    goal: str | None = None
    status: ProjectStatus = ProjectStatus.PLANNED
    health: ProjectHealth = ProjectHealth.UNKNOWN
    progress_mode: ProgressMode = ProgressMode.MANUAL
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    risk_summary: str | None = None
    next_step: str | None = None
    next_review_at: datetime | None = None
    due_date: date | None = None
    color: str = "#2563EB"
    group_id: UUID | None = None
    client_request_id: str | None = Field(default=None, max_length=120)


class ProjectGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = "#1d4ed8"
    sort_order: int = 0


class ProjectGroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = None
    sort_order: int | None = None


class ProjectGroupOut(BaseModel):
    id: UUID
    name: str
    color: str
    sort_order: int
    archived_at: datetime | None
    project_count: int
    risk_count: int
    created_at: datetime
    updated_at: datetime


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    goal: str | None = None
    status: ProjectStatus | None = None
    health: ProjectHealth | None = None
    progress_mode: ProgressMode | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    risk_summary: str | None = None
    next_step: str | None = None
    next_review_at: datetime | None = None
    due_date: date | None = None
    color: str | None = None
    group_id: UUID | None = None


class ProjectOut(BaseModel):
    id: UUID
    name: str
    goal: str | None
    status: ProjectStatus
    health: ProjectHealth
    progress_mode: ProgressMode
    progress_percent: int | None
    risk_summary: str | None
    next_step: str | None
    next_review_at: datetime | None
    due_date: date | None
    color: str
    group_id: UUID | None
    group_name: str | None = None
    archived_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    status: MilestoneStatus = MilestoneStatus.PENDING
    due_date: date | None = None
    weight: int = Field(default=1, ge=0, le=1000)
    sort_order: int = 0


class MilestoneOut(MilestoneCreate):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime


class MilestonePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    status: MilestoneStatus | None = None
    due_date: date | None = None
    weight: int | None = Field(default=None, ge=0, le=1000)


class ProjectUpdateCreate(BaseModel):
    body: str = Field(min_length=1)
    health: ProjectHealth | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    risk_summary: str | None = None
    next_step: str | None = None
    corrects_update_id: UUID | None = None


class ProjectUpdateOut(ProjectUpdateCreate):
    id: UUID
    project_id: UUID
    created_at: datetime


class CalendarEventOut(BaseModel):
    id: str
    kind: Literal["work_item", "personal_item", "milestone"]
    title: str
    start: datetime | date
    end: datetime | date | None = None
    all_day: bool
    source_id: UUID
    project_id: UUID | None = None
    status: str
    color: str


class DeliveryOut(BaseModel):
    id: UUID
    reminder_id: UUID
    item_id: UUID
    channel: DeliveryChannel
    scheduled_for: datetime
    status: DeliveryStatus
    attempt_count: int
    last_error_code: str | None
    last_error_message: str | None
    delivered_at: datetime | None
    acknowledged_at: datetime | None = None
    snooze_until: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SnoozePut(BaseModel):
    snooze_until: datetime


class ChannelsOut(BaseModel):
    feishu_configured: bool
    ntfy_configured: bool


class ReminderHealthOut(BaseModel):
    worker_seen_recently: bool
    pending_count: int
    retry_count: int
    dead_count: int
    max_lag_seconds: int | None


class IdentityScopeRule(BaseModel):
    keyword: str = Field(min_length=1, max_length=20)
    scope: Literal["work", "personal"]


class PreferencesOut(BaseModel):
    timezone: str
    work_filters: dict[str, Any]
    personal_filters: dict[str, Any]
    calendar_filters: dict[str, Any]
    weekly_review_enabled: bool = False
    desktop_notifications: bool = False
    identity_scope_rules: list[IdentityScopeRule] = []
    digest_morning_enabled: bool = True
    digest_evening_enabled: bool = False
    digest_morning_time: str = "08:00"
    digest_evening_time: str = "21:00"
    ics_token: str | None = None


class PreferencesPatch(BaseModel):
    timezone: str | None = None
    work_filters: dict[str, Any] | None = None
    personal_filters: dict[str, Any] | None = None
    calendar_filters: dict[str, Any] | None = None
    weekly_review_enabled: bool | None = None
    desktop_notifications: bool | None = None
    identity_scope_rules: list[IdentityScopeRule] | None = None
    digest_morning_enabled: bool | None = None
    digest_evening_enabled: bool | None = None
    digest_morning_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    digest_evening_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class FocusSessionOut(BaseModel):
    id: UUID
    item_id: UUID
    item_title: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None


class FocusSummaryOut(BaseModel):
    total_seconds: int
    session_count: int


class CheckinPut(BaseModel):
    checkin_date: date | None = None


class HabitWeekOut(BaseModel):
    item_id: UUID
    title: str
    scope: str
    recurrence_freq: str
    week: list[bool]
    week_done: int
    week_target: int
    streak: int
    today_done: bool


class FocusCalibrationOut(BaseModel):
    session_count: int
    actual_seconds: int
    calibrated_count: int
    estimated_seconds: int
    calibrated_actual_seconds: int


class SavedViewSpec(BaseModel):
    page: Literal["work", "personal"]
    quickFilter: str = "all"
    highPriority: bool = False
    search: str = ""


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    spec: SavedViewSpec
    sort_order: int = 0


class SavedViewPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    spec: SavedViewSpec | None = None
    sort_order: int | None = None


class SavedViewOut(BaseModel):
    id: UUID
    name: str
    spec: SavedViewSpec
    sort_order: int
    created_at: datetime
    updated_at: datetime
