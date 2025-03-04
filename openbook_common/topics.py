from typing import Optional, Literal, List

# keys are the V2 topic slugs, values is a combined list of V1 and V2 topic slugs (for backwards-compatibility)
topic_v2_slugs = {
    "animal-welfare": ["animal-welfare", "biodiversity-animal-welfare"],
    "arts-culture": ["arts-culture", "culture-social-change"],
    "climate-environment": [
        "climate-environment",
        "climate-protection",
        "water-ocean",
        "energy-transition",
        "natural-resources",
    ],
    "democracy-politics": ["democracy-politics", "governance", "politics-society"],
    "disability-inclusion": ["disability-inclusion", "disabilities-inclusion"],
    "disaster-relief": ["disaster-relief", "natural-disaster-response"],
    "elderly-care": ["elderly-care", "elderly-people"],
    "family-kids": ["family-kids"],
    "food-hunger-relief": ["food-hunger-relief", "agriculture-food"],
    "gender-equality": ["gender-equality", "diversity-gender-equality"],
    "housing": ["housing", "building-housing"],
    "human-rights": ["human-rights", "democracy-human-rights"],
    "lgbtqia-plus": ["lgbtqia-plus"],
    "lifestyle-consumption": ["lifestyle-consumption", "consumption-lifestyle", "eco-tourism"],
    "literacy-education": ["literacy-education", "education-science"],
    "mental-physical-health": ["mental-physical-health", "physical-mental-health"],
    "migration-refugees": ["migration-refugees", "migration-integration"],
    "mobility-transport": ["mobility-transport", "mobility-infrastructure"],
    "other": ["other", "alternative-economy", "urban-rural-development"],
    "peace-security": ["peace-security"],
    "poverty-homelessness": ["poverty-homelessness", "poverty-homelesness"],
    "sports-recreation": ["sports-recreation"],
    "technology-innovation": ["technology-innovation", "technological-innovation"],
    "youth-development": ["youth-development", "children-youth"],
}

TopicV2 = Literal[
    "animal-welfare",
    "arts-culture",
    "climate-environment",
    "democracy-politics",
    "disability-inclusion",
    "disaster-relief",
    "elderly-care",
    "family-kids",
    "food-hunger-relief",
    "gender-equality",
    "housing",
    "human-rights",
    "lgbtqia-plus",
    "lifestyle-consumption",
    "literacy-education",
    "mental-physical-health",
    "migration-refugees",
    "mobility-transport",
    "other",
    "peace-security",
    "poverty-homelessness",
    "sports-recreation",
    "technology-innovation",
    "youth-development",
]


def slug_to_topic_v2(slug: str) -> Optional[str]:
    """
    Convert a slug to its corresponding V2 topic.
    Returns None if no match is found.
    """
    if slug in topic_v2_slugs:
        return slug

    for topic, slugs in topic_v2_slugs.items():
        if slug in slugs:
            return topic

    return None


def slugs_to_topic_v2_slugs(slugs: List[str]) -> List[str]:
    return list(set(filter(None, map(slug_to_topic_v2, slugs))))
