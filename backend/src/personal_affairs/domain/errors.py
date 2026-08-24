class DomainError(Exception):
    """Domain-level error carried to the API boundary.

    A plain Exception subclass (not a frozen dataclass) so Python can freely
    set ``__traceback__`` when the error propagates through generator-based
    context managers such as the ``db_conn`` dependency; a frozen dataclass
    turns that into FrozenInstanceError and masks the intended 4xx with a 500.
    """

    def __init__(self, code: str, message: str, http_status: int = 400, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable


def validation_error(code: str, message: str) -> DomainError:
    return DomainError(code=code, message=message, http_status=422)


def conflict_error(code: str, message: str) -> DomainError:
    return DomainError(code=code, message=message, http_status=409)


class ErrorCode:
    AUTH_REQUIRED = "AUTH_REQUIRED"
    BAD_CREDENTIALS = "BAD_CREDENTIALS"
    CSRF_REQUIRED = "CSRF_REQUIRED"
    PAT_SCOPE_FORBIDDEN = "PAT_SCOPE_FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PERSONAL_ITEM_PROJECT_FORBIDDEN = "PERSONAL_ITEM_PROJECT_FORBIDDEN"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    INVALID_SCHEDULE = "INVALID_SCHEDULE"
    REMINDER_TARGET_MISSING = "REMINDER_TARGET_MISSING"
    NOTIFICATION_UNAVAILABLE = "NOTIFICATION_UNAVAILABLE"
    TAG_NOT_FOUND = "TAG_NOT_FOUND"
    TAG_NAME_CONFLICT = "TAG_NAME_CONFLICT"
    TAG_DEPTH_EXCEEDED = "TAG_DEPTH_EXCEEDED"
    TAG_INVALID_PARENT = "TAG_INVALID_PARENT"
    TAG_ITEM_FORBIDDEN = "TAG_ITEM_FORBIDDEN"
    PERSON_NAME_CONFLICT = "PERSON_NAME_CONFLICT"
    GROUP_NAME_CONFLICT = "GROUP_NAME_CONFLICT"
    VIEW_NAME_CONFLICT = "VIEW_NAME_CONFLICT"
    PERSON_IN_USE = "PERSON_IN_USE"
    PERSON_ITEM_FORBIDDEN = "PERSON_ITEM_FORBIDDEN"
    PROPOSAL_ALREADY_DECIDED = "PROPOSAL_ALREADY_DECIDED"
    PROPOSAL_ACTION_UNSUPPORTED = "PROPOSAL_ACTION_UNSUPPORTED"
