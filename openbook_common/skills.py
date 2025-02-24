from typing import Optional, Literal

# keys are the V2 skill slugs, values is a combined list of V1 and V2 skill slugs (for backwards-compatibility)
skill_v2_slugs = {
    "music-performance": ["music-performance"],
    "childcare": ["childcare"],
    "sales-distribution": ["sales-distribution"],
    "emergency-care": ["emergency-care"],
    "animal-care": ["animal-care"],
    "religious-spiritual-care": ["religious-spiritual-care"],
    "gardening-conservation": ["gardening-conservation"],
    "community-organizing": ["community-organizing"],
    "event-planning": ["event-planning"],
    "arts-crafts": ["arts-crafts", "arts-music-culture"],
    "intercultural-competence": ["intercultural-competence", "inclusive-mindset-intercultural-competence"],
    "driving": ["driving", "drive-transport"],
    "legal-assistance": ["legal-assistance", "law-regulations"],
    "nursing-caregiving": ["nursing-caregiving", "caring-nursing"],
    "food-service": ["food-service", "cooking-baking"],
    "translation": ["translation", "writing-translation"],
    "administration": ["administration", "organizational-skills"],
    "creativity-design": ["creativity-design", "creativity", "design", "development-concept"],
    "tutoring-coaching": ["tutoring-coaching", "teaching-education", "coaching & mentoring"],
    "marketing-communications": [
        "marketing-communications",
        "marketing-social-media",
        "communication-skills",
        "public-relations",
    ],
    "team-leadership": ["team-leadership", "coordination-coordination-of-volunteers", "leadership", "teamwork"],
    "research-analysis": ["research-analysis", "critical-thinking", "analytical-thinking", "knowledge-management"],
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
    "fundraising": ["fundraising"],
    "moderation-facilitation": ["moderation-facilitation"],
    "management-strategy": ["management-strategy"],
    "it-technology": ["it-technology"],
    "finances-taxes": ["finances-taxes"],
    "building-handicraft": ["building-handicraft"],
}

SkillV2 = Literal[
    "music-performance",
    "childcare",
    "sales-distribution",
    "emergency-care",
    "animal-care",
    "religious-spiritual-care",
    "gardening-conservation",
    "community-organizing",
    "event-planning",
    "arts-crafts",
    "intercultural-competence",
    "driving",
    "legal-assistance",
    "nursing-caregiving",
    "food-service",
    "translation",
    "administration",
    "creativity-design",
    "tutoring-coaching",
    "marketing-communications",
    "team-leadership",
    "research-analysis",
    "other",
    "fundraising",
    "moderation-facilitation",
    "management-strategy",
    "it-technology",
    "finances-taxes",
    "building-handicraft",
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
