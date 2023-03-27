import uuid
from typing import List, Optional

import strawberry
from strawberry.file_uploads import Upload
from strawberry_django_plus import gql

from openbook_auth.schema.types import UpdateConnectionAction


@gql.input
class UpdateAuthenticatedUserInput:
    avatar: Optional[Upload] = strawberry.UNSET
    first_name: Optional[str] = strawberry.UNSET
    last_name: Optional[str] = strawberry.UNSET
    about_me: Optional[str] = strawberry.UNSET
    pronouns: Optional[str] = strawberry.UNSET
    location: Optional[str] = strawberry.UNSET
    engagement_level: Optional[str] = strawberry.UNSET
    interests: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    sdgs: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET
    skills: Optional[List[Optional[uuid.UUID]]] = strawberry.UNSET


@gql.input
class UpdateConnectionWithUserInput:
    user_id: Optional[str] = strawberry.UNSET
    action: UpdateConnectionAction
