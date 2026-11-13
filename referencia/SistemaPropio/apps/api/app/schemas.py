from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

T = TypeVar("T")

IdentifierKind = Literal["DNI", "NIE", "PASAPORTE", "OTRO"]
AddressKind = Literal["postal", "empadronamiento", "otro"]
Materia = Literal["laboral", "extranjeria", "nacionalidad"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


# ---------------------------------------------------------------- identidad
class OrgRef(BaseModel):
    id: uuid.UUID
    name: str
    country: str


class MembershipOut(BaseModel):
    organization: OrgRef
    branch: str | None
    department: str | None
    role_code: str
    role_name: str


class MeOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    email: str
    memberships: list[MembershipOut]
    permissions: dict[str, list[str]]  # organization_id -> permisos efectivos
    auth_mode: str           # método de la sesión actual: demo | local_mfa | oidc
    environment: str
    has_password: bool = False


class DemoLoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)


class DemoUserOut(BaseModel):
    username: str
    full_name: str
    description: str


class BranchOut(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    kind: str


class OrganizationOut(OrgRef):
    branches: list[BranchOut]
    can_create_contacts: bool


# ---------------------------------------------------------------- contactos
class IdentifierIn(BaseModel):
    kind: IdentifierKind
    number: str = Field(min_length=3, max_length=40)
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    valid_until: date | None = None


class PhoneIn(BaseModel):
    number: str = Field(min_length=6, max_length=30)
    label: Literal["movil", "fijo", "whatsapp", "otro"] = "movil"
    is_primary: bool = False


class EmailIn(BaseModel):
    email: EmailStr
    is_primary: bool = False


class AddressIn(BaseModel):
    kind: AddressKind
    line1: str = Field(min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=12)
    municipality: str = Field(min_length=2, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    country: str = Field(default="ES", pattern=r"^[A-Z]{2}$")


class ConsentIn(BaseModel):
    purpose: Literal["gestion_expediente", "comunicaciones_servicio", "comunicaciones_comerciales"]
    granted: bool
    source: Literal["presencial", "telefono", "formulario_web", "documento_firmado"]


class ContactCreate(BaseModel):
    organization_id: uuid.UUID
    primary_branch_id: uuid.UUID | None = None
    given_name: str = Field(min_length=1, max_length=120)
    family_names: str = Field(min_length=1, max_length=200)
    birth_date: date | None = None
    nationality: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    preferred_language: Literal["es", "ca", "en", "fr", "ar", "ro", "pt"] = "es"
    origin: str | None = Field(default=None, max_length=60)
    identifiers: list[IdentifierIn] = Field(default_factory=list, max_length=5)
    phones: list[PhoneIn] = Field(default_factory=list, max_length=5)
    emails: list[EmailIn] = Field(default_factory=list, max_length=5)
    addresses: list[AddressIn] = Field(default_factory=list, max_length=5)
    consents: list[ConsentIn] = Field(default_factory=list, max_length=5)
    confirm_possible_duplicate: bool = False
    duplicate_justification: str | None = Field(default=None, max_length=500)

    @field_validator("given_name", "family_names")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Campo obligatorio")
        return v

    @field_validator("birth_date")
    @classmethod
    def _past(cls, v: date | None) -> date | None:
        if v and v >= date.today():
            raise ValueError("La fecha de nacimiento debe ser anterior a hoy")
        return v


class ContactUpdate(BaseModel):
    version: int = Field(ge=1, description="Versión leída; evita sobrescribir cambios ajenos")
    given_name: str | None = Field(default=None, min_length=1, max_length=120)
    family_names: str | None = Field(default=None, min_length=1, max_length=200)
    birth_date: date | None = None
    nationality: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    preferred_language: Literal["es", "ca", "en", "fr", "ar", "ro", "pt"] | None = None
    add_phones: list[PhoneIn] = Field(default_factory=list, max_length=5)
    add_emails: list[EmailIn] = Field(default_factory=list, max_length=5)
    add_identifiers: list[IdentifierIn] = Field(default_factory=list, max_length=5)
    reason: str = Field(min_length=3, max_length=300, description="Motivo del cambio (auditoría)")


class DuplicateCheckIn(BaseModel):
    organization_id: uuid.UUID
    identifiers: list[IdentifierIn] = Field(default_factory=list, max_length=5)
    phones: list[str] = Field(default_factory=list, max_length=5)


class ContactMinimal(BaseModel):
    """Ficha mínima: lo que Recepción necesita para identificar a la persona."""

    id: uuid.UUID
    access_level: Literal["minimal", "full"]
    organization_id: uuid.UUID
    display_name: str
    primary_branch: str | None
    phones_masked: list[str]
    identifiers_masked: list[str]
    possible_duplicate: bool


class IdentifierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    number_normalized: str
    country: str
    valid_until: date | None


class PointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    value_normalized: str
    label: str | None
    is_primary: bool


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    line1: str
    line2: str | None
    postal_code: str | None
    municipality: str
    province: str | None
    country: str


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    purpose: str
    granted: bool
    source: str
    recorded_at: datetime


class ContactFull(ContactMinimal):
    given_name: str
    family_names: str
    birth_date: date | None
    nationality: str | None
    preferred_language: str
    origin: str | None
    status: str
    is_synthetic: bool
    version: int
    created_at: datetime
    updated_at: datetime
    identifiers: list[IdentifierOut]
    points: list[PointOut]
    addresses: list[AddressOut]
    consents: list[ConsentOut]


class DuplicateCheckOut(BaseModel):
    identifier_matches: list[ContactMinimal]
    hidden_identifier_matches: int
    shared_phone_contacts: int


# ---------------------------------------------------------------- expedientes
class CaseMeta(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    access_level: Literal["metadata", "full"]
    code: str
    materia: str
    status: str
    branch: str
    department: str
    contact_id: uuid.UUID
    contact_name: str | None
    created_at: datetime
    # Solo con acceso completo (Q-6.4): días sin actividad registrada.
    last_activity_at: datetime | None = None
    inactive_days: int | None = None


class CaseFull(CaseMeta):
    title: str
    confidential_summary: str
    assignments: list[dict]


# ---------------------------------------------------------------- autorizaciones y auditoría
class GrantCreate(BaseModel):
    user_id: uuid.UUID
    case_id: uuid.UUID
    reason: str = Field(min_length=10, max_length=500)
    expires_at: datetime


class GrantOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    case_id: uuid.UUID
    case_code: str
    reason: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    actor_username: str | None = None
    organization_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    reason: str | None
    before: dict | None
    after: dict | None
    hash: str


# ---------------------------------------------------------------- F0.2 acceso y sesiones
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class LoginStep(BaseModel):
    stage: Literal["mfa", "enroll"]


class MfaIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class EnrollStartOut(BaseModel):
    username: str
    otpauth_uri: str
    secret: str
    qr_svg: str


class EnrollConfirmIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)
    new_password: str = Field(min_length=1, max_length=256)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class SessionOut(BaseModel):
    id: uuid.UUID
    auth_method: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    state: str
    ip: str | None
    user_agent: str | None
    revoke_reason: str | None
    current: bool = False


# ---------------------------------------------------------------- F0.2 administración
# Correo corporativo del usuario (formato básico; los dominios ficticios .invalid se admiten en desarrollo).
_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

class MembershipIn(BaseModel):
    organization_id: uuid.UUID
    role_code: str = Field(min_length=2, max_length=60)
    branch_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    valid_to: datetime | None = None


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]{2,79}$")
    full_name: str = Field(min_length=3, max_length=200)
    email: str = Field(max_length=200, pattern=_EMAIL)
    membership: MembershipIn
    reason: str = Field(min_length=5, max_length=500)


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=200)
    email: str | None = Field(default=None, max_length=200, pattern=_EMAIL)
    reason: str = Field(min_length=5, max_length=500)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class MembershipAddIn(MembershipIn):
    reason: str = Field(min_length=5, max_length=500)


class AdminMembershipOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization: str
    branch_id: uuid.UUID | None
    branch: str | None
    department_id: uuid.UUID | None
    department: str | None
    role_code: str
    role_name: str
    status: str
    valid_from: datetime
    valid_to: datetime | None
    manageable: bool


class AdminUserOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    email: str
    status: str
    is_demo: bool
    has_password: bool
    mfa_enrolled: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    memberships: list[AdminMembershipOut]
    active_sessions: int


class AdminUserDetail(AdminUserOut):
    sessions: list[SessionOut]


class TempPasswordOut(BaseModel):
    user: AdminUserOut
    temporary_password: str
    notice: str


class BackupRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    file_name: str
    size_bytes: int | None
    sha256: str | None
    schema_version: str | None
    restore_ok: bool
    audit_chain_ok: bool | None
    audit_events: int | None
    matches_live_chain: bool | None
    table_counts: dict | None
    detail: str | None
    triggered_by: str
