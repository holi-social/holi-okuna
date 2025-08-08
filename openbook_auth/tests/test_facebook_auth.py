from unittest.mock import patch, Mock
from django.test import TestCase, SimpleTestCase
from openbook_auth.services import FacebookAuthService


class TestFacebookAuthService(TestCase):
    @patch("openbook_auth.services.requests.get")
    def test_verify_facebook_token_success(self, mock_get):
        # Mock Facebook API response
        mock_fb_response = Mock()
        mock_fb_response.status_code = 200
        mock_fb_response.json.return_value = {"id": "123456789", "name": "John Doe", "email": "john@example.com"}

        # Mock Ory API response (user not found)
        mock_ory_response = Mock()
        mock_ory_response.status_code = 200
        mock_ory_response.json.return_value = []

        mock_get.side_effect = [mock_fb_response, mock_ory_response]

        result = FacebookAuthService.verify_facebook_token("fake_access_token")

        self.assertIsNotNone(result)
        self.assertEqual(result["facebook_id"], "123456789")
        self.assertEqual(result["email"], "john@example.com")
        self.assertEqual(result["name"], "John Doe")
        self.assertFalse(result["exists"])

    @patch("openbook_auth.services.requests.get")
    def test_verify_facebook_token_invalid_token(self, mock_get):
        # Mock Facebook API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid token"
        mock_get.return_value = mock_response

        result = FacebookAuthService.verify_facebook_token("invalid_token")

        self.assertIsNone(result)

    @patch("openbook_auth.services.requests.get")
    def test_verify_facebook_token_existing_user(self, mock_get):
        # Mock Facebook API response
        mock_fb_response = Mock()
        mock_fb_response.status_code = 200
        mock_fb_response.json.return_value = {"id": "123456789", "name": "John Doe", "email": "john@example.com"}

        # Mock Ory API response (user found)
        mock_ory_response = Mock()
        mock_ory_response.status_code = 200
        mock_ory_response.json.return_value = [
            {
                "id": "ory-user-id",
                "credentials": {"oidc": {"identifiers": ["facebook-123456789"]}},
                "traits": {"email": "john@example.com"},
            }
        ]

        mock_get.side_effect = [mock_fb_response, mock_ory_response]

        result = FacebookAuthService.verify_facebook_token("fake_access_token")

        self.assertIsNotNone(result)
        self.assertEqual(result["user_id"], "ory-user-id")
        self.assertEqual(result["email"], "john@example.com")
        self.assertTrue(result["exists"])


class TestFacebookAuthServiceNoDB(SimpleTestCase):
    """Test class for FacebookAuthService methods that don't require database access"""

    def test_generate_id_token(self):
        user_id = "test-user-id"
        email = "test@example.com"

        token = FacebookAuthService.generate_id_token(user_id, email)

        self.assertIsInstance(token, str)

        # Decode the JWT token to verify its contents
        import jwt
        from django.conf import settings

        decoded_payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], audience="okuna-mobile"
        )

        self.assertEqual(decoded_payload["sub"], user_id)
        self.assertEqual(decoded_payload["email"], email)
        self.assertEqual(decoded_payload["iss"], "okuna-auth")
        self.assertEqual(decoded_payload["aud"], "okuna-mobile")
