from django.db import models
from django.conf import settings
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_communities.models import Community
from openbook_terms.models import Skill


class Task(ModelWithUUID):
    pass
