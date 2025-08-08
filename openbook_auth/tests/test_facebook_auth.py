from unittest.mock import patch, Mock
from django.test import TestCase
from openbook_auth.services import FacebookAuthService


class TestFacebookAuthService(TestCase):
    @patch("openbook_auth.services.requests.get")
    @patch("openbook_auth.services.requests.post")
    def test_authenticate_with_facebook_new_user_success(self, mock_post, mock_get):
        # Mock Facebook API response
        mock_fb_response = Mock()
        mock_fb_response.status_code = 200
        mock_fb_response.json.return_value = {"id": "123456789", "name": "John Doe", "email": "john@example.com"}

        # Mock Ory API response (user not found)
        mock_ory_get_response = Mock()
        mock_ory_get_response.status_code = 200
        mock_ory_get_response.json.return_value = []

        # Mock Ory API response (user creation)
        mock_ory_create_response = Mock()
        mock_ory_create_response.status_code = 201
        mock_ory_create_response.json.return_value = {
            "id": "new-ory-user-id",
            "traits": {"email": "john@example.com", "name": "John Doe"},
        }

        # Mock Ory API response (session creation)
        mock_ory_session_response = Mock()
        mock_ory_session_response.status_code = 201
        mock_ory_session_response.json.return_value = {
            "id": "session-id",
            "token": "ory-session-token",
            "identity_id": "new-ory-user-id",
        }

        mock_get.side_effect = [mock_fb_response, mock_ory_get_response]
        mock_post.side_effect = [mock_ory_create_response, mock_ory_session_response]

        result = FacebookAuthService.authenticate_with_facebook("fake_access_token", "facebook-123")

        self.assertIsNotNone(result)
        self.assertEqual(result["session_token"], "ory-session-token")
        self.assertEqual(result["user_id"], "new-ory-user-id")
        self.assertEqual(result["email"], "john@example.com")
        self.assertEqual(result["name"], "John Doe")

    @patch("openbook_auth.services.requests.get")
    @patch("openbook_auth.services.requests.post")
    def test_authenticate_with_facebook_existing_user_success(self, mock_post, mock_get):
        # Mock Facebook API response
        mock_fb_response = Mock()
        mock_fb_response.status_code = 200
        mock_fb_response.json.return_value = {"id": "123456789", "name": "John Doe", "email": "john@example.com"}

        # Mock Ory API response (user found)
        mock_ory_get_response = Mock()
        mock_ory_get_response.status_code = 200
        mock_ory_get_response.json.return_value = [
            {
                "id": "existing-ory-user-id",
                "credentials": {"oidc": {"identifiers": ["facebook-123:123456789"]}},
                "traits": {"email": "john@example.com", "name": "John Doe"},
            }
        ]

        # Mock Ory API response (session creation)
        mock_ory_session_response = Mock()
        mock_ory_session_response.status_code = 201
        mock_ory_session_response.json.return_value = {
            "id": "session-id",
            "token": "ory-session-token",
            "identity_id": "existing-ory-user-id",
        }

        mock_get.side_effect = [mock_fb_response, mock_ory_get_response]
        mock_post.return_value = mock_ory_session_response

        result = FacebookAuthService.authenticate_with_facebook("fake_access_token", "facebook-123")

        self.assertIsNotNone(result)
        self.assertEqual(result["session_token"], "ory-session-token")
        self.assertEqual(result["user_id"], "existing-ory-user-id")
        self.assertEqual(result["email"], "john@example.com")
        self.assertEqual(result["name"], "John Doe")

    @patch("openbook_auth.services.requests.get")
    def test_authenticate_with_facebook_invalid_token(self, mock_get):
        # Mock Facebook API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid token"
        mock_get.return_value = mock_response

        result = FacebookAuthService.authenticate_with_facebook("invalid_token", "facebook-123")

        self.assertIsNone(result)

    @patch("openbook_auth.services.requests.get")
    def test_authenticate_with_facebook_no_email(self, mock_get):
        # Mock Facebook API response without email
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123456789", "name": "John Doe"}

        mock_get.return_value = mock_response

        result = FacebookAuthService.authenticate_with_facebook("fake_access_token", "facebook-123")

        self.assertIsNone(result)

    @patch("openbook_auth.services.requests.get")
    def test_verify_facebook_token_success(self, mock_get):
        # Mock Facebook API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123456789", "name": "John Doe", "email": "john@example.com"}

        mock_get.return_value = mock_response

        result = FacebookAuthService.verify_facebook_token("fake_access_token", "facebook-123")

        self.assertIsNotNone(result)
        self.assertEqual(result["facebook_id"], "123456789")
        self.assertEqual(result["email"], "john@example.com")
        self.assertEqual(result["name"], "John Doe")

    @patch("openbook_auth.services.requests.get")
    def test_verify_facebook_token_invalid_token(self, mock_get):
        # Mock Facebook API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid token"
        mock_get.return_value = mock_response

        result = FacebookAuthService.verify_facebook_token("invalid_token", "facebook-123")

        self.assertIsNone(result)

    @patch("openbook_auth.services.requests.get")
    def test_find_ory_user_by_facebook_id_found(self, mock_get):
        # Mock Ory API response (user found)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "ory-user-id",
                "credentials": {"oidc": {"identifiers": ["facebook-123:123456789"]}},
                "traits": {"email": "john@example.com"},
            }
        ]

        mock_get.return_value = mock_response

        result = FacebookAuthService._find_ory_user_by_facebook_id("123456789", "facebook-123")

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "ory-user-id")

    @patch("openbook_auth.services.requests.get")
    def test_find_ory_user_by_facebook_id_not_found(self, mock_get):
        # Mock Ory API response (user not found)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_get.return_value = mock_response

        result = FacebookAuthService._find_ory_user_by_facebook_id("123456789", "facebook-123")

        self.assertIsNone(result)

    @patch("openbook_auth.services.requests.post")
    def test_create_ory_session_success(self, mock_post):
        # Mock Ory API response (session creation)
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "session-id",
            "token": "ory-session-token",
            "identity_id": "user-id",
        }

        mock_post.return_value = mock_response

        result = FacebookAuthService.create_ory_session("user-id")

        self.assertIsNotNone(result)
        self.assertEqual(result["token"], "ory-session-token")
        self.assertEqual(result["identity_id"], "user-id")
