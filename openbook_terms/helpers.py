from typing import Iterable, List
from openbook_terms.models import Topic, Skill
from openbook_common.topics import slugs_to_topic_v2_slugs
from openbook_common.skills import slugs_to_skill_v2_slugs


def topics_to_topic_v2_slugs(topics: Iterable[Topic]) -> List[str]:
    return slugs_to_topic_v2_slugs([topic.slug for topic in topics])


def skills_to_skill_v2_slugs(skills: Iterable[Skill]) -> List[str]:
    return slugs_to_skill_v2_slugs([skill.slug for skill in skills])
