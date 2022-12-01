from unittest import mock

import requests
from django.test import TestCase
from django.utils import timezone

from openbook_common.models import LinkPreview


class MockResponse:
    def __init__(self, text):
        self.text = text


class LinkPreviewTestCase(TestCase):
    @mock.patch("requests.get")
    def test_page_without_opengraph_gives_empty_preview(self, mock_get):
        mock_get.return_value = MockResponse("<html>no opengraph</html>")
        preview = LinkPreview.from_url("www.abcd.de")
        preview2 = LinkPreview.from_url("www.abcd.de")
        self.assertIn(mock.call(url="http://www.abcd.de/"), mock_get.call_args_list)
        self.assertEqual(1, len(mock_get.call_args_list))
        self.assertEqual(preview, preview2)
        self.assertEqual(preview.has_data(), False)
        self.assertEqual(preview.requested_url, "www.abcd.de")
        self.assertEqual(preview.url, "")
        self.assertEqual(preview.title, "")
        self.assertEqual(preview.description, "")
        self.assertEqual(preview.type, "")
        self.assertEqual(preview.image, "")
        self.assertTrue(
            timezone.now() - timezone.timedelta(seconds=3)
            <= preview.fetched_at
            <= timezone.now()
        )

    @mock.patch("requests.get")
    def test_preview_without_data_is_note_returned(self, mock_get):
        mock_get.return_value = MockResponse("<html>no opengraph</html>")
        previews = LinkPreview.parse_text("www.abcd.de")
        previews2 = LinkPreview.parse_text("www.abcd.de")
        self.assertIn(mock.call(url="http://www.abcd.de/"), mock_get.call_args_list)
        self.assertEqual(1, len(mock_get.call_args_list))
        self.assertEqual(previews, previews2)
        self.assertEqual(previews, [])

    @mock.patch("requests.get")
    def test_page_with_opengraph_gives_preview(self, mock_get):
        mock_get.return_value = MockResponse(
            """
            <html><head>
            <meta property="og:url" content="https://my.url/xyz" />
            <meta property="og:type" content="website" />
            <meta property="og:title" content="MyTitle" />
            <meta property="og:description" content="MyDescription" />
            <meta property="og:image" content="https://www.my.url/image.jpg" />
            </head></html>
            """
        )
        previews = LinkPreview.parse_text("www.my.de")
        self.assertIn(mock.call(url="http://www.my.de/"), mock_get.call_args_list)
        self.assertEqual(1, len(previews))
        preview = previews[0]
        self.assertEqual(preview.has_data(), True)
        self.assertEqual(preview.requested_url, "www.my.de")
        self.assertEqual(preview.url, "https://my.url/xyz")
        self.assertEqual(preview.title, "MyTitle")
        self.assertEqual(preview.description, "MyDescription")
        self.assertEqual(preview.type, "website")
        self.assertEqual(preview.image, "https://www.my.url/image.jpg")
        self.assertTrue(
            timezone.now() - timezone.timedelta(seconds=3)
            <= preview.fetched_at
            <= timezone.now()
        )

    @mock.patch("requests.get")
    def test_multiple_urls_are_parsed(self, mock_get):
        mock_get.side_effect = (
            MockResponse(
                """
                <html><head>
                <meta property="og:url" content="https://my.url/xyz" />
                <meta property="og:type" content="website" />
                <meta property="og:title" content="MyTitle" />
                <meta property="og:description" content="MyDescription" />
                <meta property="og:image" content="https://www.my.url/image.jpg" />
                </head></html>
                """
            ),
            MockResponse(
                """
                <html><head>
                <meta property="og:url" content="https://mysecond.url/xyz" />
                <meta property="og:type" content="other" />
                <meta property="og:title" content="MySecondTitle" />
                <meta property="og:description" content="MySecondDescription" />
                <meta property="og:image" content="/secondimage.jpg" />
                </head></html>
                """
            ),
        )
        previews = LinkPreview.parse_text(
            "Two URLs: www.my.de and www.mysecond.de are in this text"
        )
        self.assertIn(mock.call(url="http://www.my.de/"), mock_get.call_args_list)
        self.assertIn(mock.call(url="http://www.mysecond.de/"), mock_get.call_args_list)
        self.assertEqual(2, len(previews))

        preview = previews[0]
        self.assertEqual(preview.has_data(), True)
        self.assertEqual(preview.requested_url, "www.my.de")
        self.assertEqual(preview.url, "https://my.url/xyz")
        self.assertEqual(preview.title, "MyTitle")
        self.assertEqual(preview.description, "MyDescription")
        self.assertEqual(preview.type, "website")
        self.assertEqual(preview.image, "https://www.my.url/image.jpg")

        preview2 = previews[1]
        self.assertEqual(preview2.has_data(), True)
        self.assertEqual(preview2.requested_url, "www.mysecond.de")
        self.assertEqual(preview2.url, "https://mysecond.url/xyz")
        self.assertEqual(preview2.title, "MySecondTitle")
        self.assertEqual(preview2.description, "MySecondDescription")
        self.assertEqual(preview2.type, "other")
        self.assertEqual(preview2.image, "https://mysecond.url/secondimage.jpg")
