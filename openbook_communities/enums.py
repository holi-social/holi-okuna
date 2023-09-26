from enum import Enum

import strawberry


@strawberry.enum
class UpdateConnectionAction(Enum):
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    GRANT_ADMIN_ACCESS = "GRANT_ADMIN_ACCESS"
    LEAVE_SPACE = "LEAVE_SPACE"
    REMOVE_MEMBER = "REMOVE_MEMBER"
    REVOKE_ADMIN_ACCESS = "REVOKE_ADMIN_ACCESS"
