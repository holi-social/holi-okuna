import logging
import unittest

from openbook_common.skills import skill_v2_slugs, slug_to_skill_v2, slugs_to_skill_v2_slugs

logger = logging.getLogger(__name__)


class TestSlugToSkillV2(unittest.TestCase):
    # Define test cases as a list of tuples (input, expected)
    test_cases = [
        # Music Performance
        ("music-performance", "music-performance"),
        # Childcare
        ("childcare", "childcare"),
        # Sales & Distribution
        ("sales-distribution", "sales-distribution"),
        # Emergency Care
        ("emergency-care", "emergency-care"),
        # Animal Care
        ("animal-care", "animal-care"),
        # Religious & Spiritual Care
        ("religious-spiritual-care", "religious-spiritual-care"),
        # Gardening & Conservation
        ("gardening-conservation", "gardening-conservation"),
        # Community Organizing
        ("community-organizing", "community-organizing"),
        # Event Planning
        ("event-planning", "event-planning"),
        # Arts & Crafts
        ("arts-crafts", "arts-crafts"),
        ("arts-music-culture", "arts-crafts"),
        # Intercultural Competence
        ("intercultural-competence", "intercultural-competence"),
        ("inclusive-mindset-intercultural-competence", "intercultural-competence"),
        # Driving
        ("driving", "driving"),
        ("drive-transport", "driving"),
        # Legal Assistance
        ("legal-assistance", "legal-assistance"),
        ("law-regulations", "legal-assistance"),
        # Nursing & Caregiving
        ("nursing-caregiving", "nursing-caregiving"),
        ("caring-nursing", "nursing-caregiving"),
        # Food Service
        ("food-service", "food-service"),
        ("cooking-baking", "food-service"),
        # Translation
        ("translation", "translation"),
        ("writing-translation", "translation"),
        # Administration
        ("administration", "administration"),
        ("organizational-skills", "administration"),
        # Creativity & Design
        ("creativity-design", "creativity-design"),
        ("creativity", "creativity-design"),
        ("design", "creativity-design"),
        ("development-concept", "creativity-design"),
        # Tutoring & Coaching
        ("tutoring-coaching", "tutoring-coaching"),
        ("teaching-education", "tutoring-coaching"),
        ("coaching & mentoring", "tutoring-coaching"),
        # Marketing & Communications
        ("marketing-communications", "marketing-communications"),
        ("marketing-social-media", "marketing-communications"),
        ("communication-skills", "marketing-communications"),
        ("public-relations", "marketing-communications"),
        # Team Leadership
        ("team-leadership", "team-leadership"),
        ("coordination-coordination-of-volunteers", "team-leadership"),
        ("leadership", "team-leadership"),
        ("teamwork", "team-leadership"),
        # Research & Analysis
        ("research-analysis", "research-analysis"),
        ("critical-thinking", "research-analysis"),
        ("analytical-thinking", "research-analysis"),
        ("knowledge-management", "research-analysis"),
        # Other
        ("other", "other"),
        ("environmental-awareness", "other"),
        ("commitment", "other"),
        ("conflict-management", "other"),
        ("discipline", "other"),
        ("empathy", "other"),
        ("hands-on-support", "other"),
        ("holistic-thinking", "other"),
        ("humour", "other"),
        ("independence", "other"),
        ("initiative-and-energy", "other"),
        ("mindfulness", "other"),
        ("motivation", "other"),
        ("negotiation-skills", "other"),
        ("openness", "other"),
        ("relationship-skills", "other"),
        ("resilience", "other"),
        ("self-confident", "other"),
        ("solution-orientedness", "other"),
        ("willingness-to-learn", "other"),
        ("adaptability", "other"),
        ("visionary-thinking", "other"),
        ("assertiveness", "other"),
        # Fundraising
        ("fundraising", "fundraising"),
        # Moderation & Facilitation
        ("moderation-facilitation", "moderation-facilitation"),
        # Management & Strategy
        ("management-strategy", "management-strategy"),
        # IT & Technology
        ("it-technology", "it-technology"),
        # Finances & Taxes
        ("finances-taxes", "finances-taxes"),
        # Building & Handicraft
        ("building-handicraft", "building-handicraft"),
        # Edge cases
        ("", None),
        ("unknown-slug", None),
    ]

    def test_slug_to_skill_v2_mapping(self):
        """Test that each slug maps to its expected skill."""
        for input_slug, expected in self.test_cases:
            assert slug_to_skill_v2(input_slug) == expected

    def test_all_implemented_slugs_are_tested(self):
        """Test that all slugs in the implementation have a corresponding test case."""
        all_defined_slugs = [slug for slugs in skill_v2_slugs.values() for slug in slugs]
        tested_slugs = [test_case[0] for test_case in self.test_cases]

        for slug in all_defined_slugs:
            assert slug in tested_slugs, f"Slug '{slug}' is missing a test case"


class TestSlugsToSkillV2Slugs(unittest.TestCase):
    def test_skill_v1_slugs_mapping(self):
        """Test that a list of SkillV1 slugs is mapped to a list of SkillV2 slugs"""
        input_slugs = ["law-regulations", "empathy", "it-technology", "discipline"]
        expected = ["legal-assistance", "other", "it-technology"]

        actual = slugs_to_skill_v2_slugs(input_slugs)

        assert len(actual) == len(expected), "Invalid number of slugs"
        for slug in expected:
            assert slug in actual, f"Slug '{slug}' is missing"

    def test_skill_v2_slugs_mapping(self):
        """Test that a list of SkillV2 slugs is mapped to a distinct list of SkillV2 slugs"""
        input_slugs = ["animal-care", "other", "it-technology", "other"]
        expected = ["animal-care", "other", "it-technology"]

        actual = slugs_to_skill_v2_slugs(input_slugs)

        assert len(actual) == len(expected), "Invalid number of slugs"
        for slug in expected:
            assert slug in actual, f"Slug '{slug}' is missing"

    def test_mixed_version_slugs_mapping(self):
        """Test that a list of mixed version slugs is mapped to a list of SkillV2 slugs"""
        input_slugs = ["law-regulations", "empathy", "it-technology", "animal-care"]
        expected = ["legal-assistance", "other", "it-technology", "animal-care"]

        actual = slugs_to_skill_v2_slugs(input_slugs)

        assert len(actual) == len(expected), "Invalid number of slugs"
        for slug in expected:
            assert slug in actual, f"Slug '{slug}' is missing"

    def test_unknown_slug_mapping(self):
        """Test that unknown or empty slugs are ignored when mapping to a list of SkillV2 slugs"""
        input_slugs = ["law-regulations", "", "it-technology", "unknown"]
        expected = ["legal-assistance", "it-technology"]

        actual = slugs_to_skill_v2_slugs(input_slugs)

        assert len(actual) == len(expected), "Invalid number of slugs"
        for slug in expected:
            assert slug in actual, f"Slug '{slug}' is missing"
