from typing import Iterable, List, Protocol
from openbook_common.topics import slugs_to_topic_v2_slugs
from openbook_common.skills import slugs_to_skill_v2_slugs


class _Topic(Protocol):
    slug: str


class _Skill(Protocol):
    slug: str


def topics_to_topic_v2_slugs(topics: Iterable[_Topic]) -> List[str]:
    return slugs_to_topic_v2_slugs([topic.slug for topic in topics])


def skills_to_skill_v2_slugs(skills: Iterable[_Skill]) -> List[str]:
    return slugs_to_skill_v2_slugs([skill.slug for skill in skills])
