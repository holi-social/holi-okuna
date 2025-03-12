from typing import Optional, Literal

# keys are the V2 skill slugs, values is a combined list of V1 and V2 skill slugs (for backwards-compatibility)
skill_v2_slugs = {
    "administration": ["administration", "organizational-skills"],
    "animal-care": ["animal-care"],
    "arts-crafts": ["arts-crafts", "arts-music-culture"],
    "building-handicraft": ["building-handicraft"],
    "childcare": ["childcare"],
    "community-organizing": ["community-organizing"],
    "creativity-design": ["creativity-design", "creativity", "design", "development-concept"],
    "driving": ["driving", "drive-transport"],
    "emergency-care": ["emergency-care"],
    "event-planning": ["event-planning"],
    "finances-taxes": ["finances-taxes"],
    "food-service": ["food-service", "cooking-baking"],
    "fundraising": ["fundraising"],
    "gardening-conservation": ["gardening-conservation"],
    "intercultural-competence": ["intercultural-competence", "inclusive-mindset-intercultural-competence"],
    "it-technology": ["it-technology"],
    "legal-assistance": ["legal-assistance", "law-regulations"],
    "management-strategy": ["management-strategy"],
    "marketing-communications": [
        "marketing-communications",
        "marketing-social-media",
        "communication-skills",
        "public-relations",
    ],
    "moderation-facilitation": ["moderation-facilitation"],
    "music-performance": ["music-performance"],
    "nursing-caregiving": ["nursing-caregiving", "caring-nursing"],
    "other": [
        "other",
        "environmental-awareness",
        "commitment",
        "conflict-management",
        "discipline",
        "empathy",
        "hands-on-support",
        "holistic-thinking",
        "humour",
        "independence",
        "initiative-and-energy",
        "mindfulness",
        "motivation",
        "negotiation-skills",
        "openness",
        "relationship-skills",
        "resilience",
        "self-confident",
        "solution-orientedness",
        "willingness-to-learn",
        "adaptability",
        "visionary-thinking",
        "assertiveness",
    ],
    "religious-spiritual-care": ["religious-spiritual-care"],
    "research-analysis": ["research-analysis", "critical-thinking", "analytical-thinking", "knowledge-management"],
    "sales-distribution": ["sales-distribution"],
    "team-leadership": ["team-leadership", "coordination-coordination-of-volunteers", "leadership", "teamwork"],
    "translation": ["translation", "writing-translation"],
    "tutoring-coaching": ["tutoring-coaching", "teaching-education", "coaching & mentoring"],
}

SkillV2 = Literal[
    "administration",
    "animal-care",
    "arts-crafts",
    "building-handicraft",
    "childcare",
    "community-organizing",
    "creativity-design",
    "driving",
    "emergency-care",
    "event-planning",
    "finances-taxes",
    "food-service",
    "fundraising",
    "gardening-conservation",
    "intercultural-competence",
    "it-technology",
    "legal-assistance",
    "management-strategy",
    "marketing-communications",
    "moderation-facilitation",
    "music-performance",
    "nursing-caregiving",
    "other",
    "religious-spiritual-care",
    "research-analysis",
    "sales-distribution",
    "team-leadership",
    "translation",
    "tutoring-coaching",
]


def slug_to_skill_v2(slug: str) -> Optional[str]:
    """
    Convert a slug to its corresponding V2 skill.
    Returns None if no match is found.
    """
    if slug in skill_v2_slugs:
        return slug

    for skill, slugs in skill_v2_slugs.items():
        if slug in slugs:
            return skill

    return None


def slugs_to_skill_v2_slugs(slugs: [str]) -> [str]:
    return list(set(filter(None, map(slug_to_skill_v2, slugs))))
