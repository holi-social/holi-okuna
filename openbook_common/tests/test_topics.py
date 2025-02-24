import pytest

from openbook_common.topics import topic_v2_slugs, slug_to_topic_v2


class TestSlugToTopicV2:
    # Define test cases as a list of tuples (input, expected)
    test_cases = [
        # ANIMAL_WELFARE
        ("animal-welfare", "animal-welfare"),
        ("biodiversity-animal-welfare", "animal-welfare"),
        # ARTS_CULTURE
        ("arts-culture", "arts-culture"),
        ("culture-social-change", "arts-culture"),
        # CLIMATE_ENVIRONMENT
        ("climate-environment", "climate-environment"),
        ("climate-protection", "climate-environment"),
        ("water-ocean", "climate-environment"),
        ("energy-transition", "climate-environment"),
        ("natural-resources", "climate-environment"),
        # DEMOCRACY_POLITICS
        ("democracy-politics", "democracy-politics"),
        ("governance", "democracy-politics"),
        ("politics-society", "democracy-politics"),
        # DISABILITY_INCLUSION
        ("disability-inclusion", "disability-inclusion"),
        ("disabilities-inclusion", "disability-inclusion"),
        # DISASTER_RELIEF
        ("disaster-relief", "disaster-relief"),
        ("natural-disaster-response", "disaster-relief"),
        # ELDERLY_CARE
        ("elderly-care", "elderly-care"),
        ("elderly-people", "elderly-care"),
        # FAMILY_KIDS
        ("family-kids", "family-kids"),
        # FOOD_HUNGER_RELIEF
        ("food-hunger-relief", "food-hunger-relief"),
        ("agriculture-food", "food-hunger-relief"),
        # GENDER_EQUALITY
        ("gender-equality", "gender-equality"),
        ("diversity-genderequality", "gender-equality"),
        # HOUSING
        ("housing", "housing"),
        ("building-housing", "housing"),
        # HUMAN_RIGHTS
        ("human-rights", "human-rights"),
        ("democracy-human-rights", "human-rights"),
        # LGBTQIA_PLUS
        ("lgbtqia-plus", "lgbtqia-plus"),
        # LIFESTYLE_CONSUMPTION
        ("lifestyle-consumption", "lifestyle-consumption"),
        ("consumption-lifestyle", "lifestyle-consumption"),
        ("eco-tourism", "lifestyle-consumption"),
        # LITERACY_EDUCATION
        ("literacy-education", "literacy-education"),
        ("education-science", "literacy-education"),
        # MENTAL_PHYSICAL_HEALTH
        ("mental-physical-health", "mental-physical-health"),
        ("physical-mental-health", "mental-physical-health"),
        # MIGRATION_REFUGEES
        ("migration-refugees", "migration-refugees"),
        ("migration-integration", "migration-refugees"),
        # MOBILITY_TRANSPORT
        ("mobility-transport", "mobility-transport"),
        ("mobility-infrastructure", "mobility-transport"),
        # OTHER
        ("other", "other"),
        ("alternative-economy", "other"),
        ("urban-rural-development", "other"),
        # PEACE_SECURITY
        ("peace-security", "peace-security"),
        # POVERTY_HOMELESSNESS
        ("poverty-homelessness", "poverty-homelessness"),
        ("poverty-homelesness", "poverty-homelessness"),
        # SPORTS_RECREATION
        ("sports-recreation", "sports-recreation"),
        # TECHNOLOGY_INNOVATION
        ("technology-innovation", "technology-innovation"),
        ("technological-innovation", "technology-innovation"),
        # YOUTH_DEVELOPMENT
        ("youth-development", "youth-development"),
        ("children-youth", "youth-development"),
        # Edge cases
        ("", None),
        ("unknown-slug", None),
    ]

    @pytest.mark.parametrize("input_slug,expected", test_cases)
    def test_slug_to_topic_v2_mapping(self, input_slug, expected):
        """Test that each slug maps to its expected topic."""
        assert slug_to_topic_v2(input_slug) == expected

    def test_all_implemented_slugs_are_tested(self):
        """Test that all slugs in the implementation have a corresponding test case."""
        all_slugs = [slug for slugs in topic_v2_slugs.values() for slug in slugs]
        tested_slugs = [test_case[0] for test_case in self.test_cases]

        for slug in all_slugs:
            assert slug in tested_slugs, f"Slug '{slug}' is missing a test case"
