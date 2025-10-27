import unittest
from rest_framework.exceptions import NotFound

from openbook_common.topics import topic_v2_slug_aliases
from openbook_common.skills import skill_v2_slug_aliases
from openbook_common.validators import topic_v2_exists, skill_v2_exists


class TestTopicV2Validation(unittest.TestCase):
    def test_validation_succeeds_for_existing_slugs(self):
        all_v2_slugs = topic_v2_slug_aliases.keys()

        for slug in all_v2_slugs:
            topic_v2_exists(slug)

    def test_validation_fails_for_v1_slugs(self):
        all_v2_slugs = topic_v2_slug_aliases.keys()
        all_v1_slugs = filter(
            lambda slug: slug not in all_v2_slugs, [slug for slugs in topic_v2_slug_aliases.values() for slug in slugs]
        )

        for slug in all_v1_slugs:
            with self.assertRaises(NotFound):
                topic_v2_exists(slug)

    def test_validation_fails_for_unknown_slug(self):
        with self.assertRaises(NotFound):
            topic_v2_exists("unknown")

    def test_validation_fails_for_empty_slug(self):
        with self.assertRaises(NotFound):
            topic_v2_exists("")


class TestSkillV2Validation(unittest.TestCase):
    def test_validation_succeeds_for_existing_slugs(self):
        all_v2_slugs = skill_v2_slug_aliases.keys()

        for slug in all_v2_slugs:
            skill_v2_exists(slug)

    def test_validation_fails_for_v1_slugs(self):
        all_v2_slugs = skill_v2_slug_aliases.keys()
        all_v1_slugs = filter(
            lambda slug: slug not in all_v2_slugs, [slug for slugs in skill_v2_slug_aliases.values() for slug in slugs]
        )

        for slug in all_v1_slugs:
            with self.assertRaises(NotFound):
                skill_v2_exists(slug)

    def test_validation_fails_for_unknown_slug(self):
        with self.assertRaises(NotFound):
            skill_v2_exists("unknown")

    def test_validation_fails_for_empty_slug(self):
        with self.assertRaises(NotFound):
            skill_v2_exists("")
