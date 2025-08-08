import http
import logging
import requests
from typing import Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

ORY_HEADERS = {"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"}


class FacebookAuthService:
    """
    Service to handle Facebook authentication using Ory Kratos
    """

    @staticmethod
    def verify_facebook_token(access_token: str, provider: str) -> Optional[Dict[str, Any]]:
        """
        Verify Facebook access token and get user information
        """
        try:
            # Verify the token with Facebook to get user info
            fb_response = requests.get(
                "https://graph.facebook.com/me",
                params={"access_token": access_token, "fields": "id,name,email"},
                timeout=10,
            )

            if fb_response.status_code != http.HTTPStatus.OK:
                logger.error(f"Facebook API error: {fb_response.status_code} - {fb_response.text}")
                return None

            fb_user_data = fb_response.json()
            facebook_user_id = fb_user_data.get("id")
            email = fb_user_data.get("email")
            name = fb_user_data.get("name")

            if not facebook_user_id:
                logger.error("No Facebook user ID in response")
                return None

            return {
                "email": email,
                "name": name,
                "facebook_id": facebook_user_id,
            }

        except requests.RequestException as e:
            logger.error(f"Request error during Facebook token verification: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Facebook token verification: {e}")
            return None

    @staticmethod
    def find_or_create_ory_identity(
        facebook_id: str, email: str, name: str, provider: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find existing Ory identity by Facebook ID or create a new one
        """
        try:
            # Find existing identity by Facebook ID
            ory_user = FacebookAuthService._find_ory_user_by_facebook_id(facebook_id, provider)

            if ory_user:
                logger.info(f"Found existing Ory user with Facebook ID: {facebook_id}")
                return ory_user

            # If not found, create new identity
            logger.info(f"Creating new Ory user for Facebook ID: {facebook_id}")
            return FacebookAuthService._create_ory_identity(facebook_id, email, name, provider)

        except Exception as e:
            logger.error(f"Error finding or creating Ory identity: {e}")
            return None

    @staticmethod
    def _find_ory_user_by_facebook_id(facebook_id: str, provider: str) -> Optional[Dict[str, Any]]:
        """
        Find Ory user by Facebook ID using direct identifier search
        """
        try:
            params = {"credentials_identifier": f"{provider}:{facebook_id}", "include_credential": "oidc"}
            response = requests.get(
                f"{settings.ORY_BASE_URL}/admin/identities/", params=params, headers=ORY_HEADERS, timeout=30
            )

            if response.status_code != http.HTTPStatus.OK:
                logger.error(f"Ory API error: {response.status_code} - {response.text}")
                return None

            users = response.json()

            if users and len(users) > 0:
                return users[0]

            return None

        except requests.RequestException as e:
            logger.error(f"Request error finding Ory user: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error finding Ory user: {e}")
            return None

    @staticmethod
    def _create_ory_identity(facebook_id: str, email: str, name: str, provider: str) -> Optional[Dict[str, Any]]:
        """
        Create a new Ory identity from Facebook data
        """
        try:
            name_parts = name.split(" ", 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Create user data for Ory
            user_data = {
                "schema_id": "default",
                "traits": {"email": email, "given_name": first_name, "family_name": last_name, "name": name},
                "credentials": {
                    "oidc": {
                        "config": {
                            "providers": [{"provider": provider, "subject": facebook_id, "use_auto_link": True}]
                        }
                    }
                },
                "verifiable_addresses": [{"value": email, "verified": True, "status": "completed"}],
            }

            # Create user in Ory
            response = requests.post(
                f"{settings.ORY_BASE_URL}/admin/identities/", headers=ORY_HEADERS, json=user_data, timeout=30
            )

            if response.status_code != http.HTTPStatus.CREATED:
                logger.error(f"Failed to create Ory user: {response.status_code} - {response.text}")
                return None

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Request error creating Ory user: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating Ory user: {e}")
            return None

    @staticmethod
    def create_ory_session(identity_id: str) -> Optional[Dict[str, Any]]:
        """
        Create a Kratos session for the given identity using Admin API
        """
        try:
            response = requests.post(
                f"{settings.ORY_BASE_URL}/admin/identities/{identity_id}/sessions", headers=ORY_HEADERS, timeout=30
            )

            if response.status_code != http.HTTPStatus.CREATED:
                logger.error(f"Failed to create Ory session: {response.status_code} - {response.text}")
                return None

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Request error creating Ory session: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating Ory session: {e}")
            return None

    @staticmethod
    def authenticate_with_facebook(access_token: str, provider: str) -> Optional[Dict[str, Any]]:
        """
        Complete Facebook authentication flow:
        1. Verify Facebook access token
        2. Find or create Kratos identity
        3. Create Kratos session
        4. Return session token
        """
        try:
            # Verify Facebook access token
            fb_user_data = FacebookAuthService.verify_facebook_token(access_token, provider)
            if not fb_user_data:
                logger.error("Failed to verify Facebook access token")
                return None

            facebook_id = fb_user_data["facebook_id"]
            email = fb_user_data["email"]
            name = fb_user_data["name"]

            if not email:
                logger.error("Facebook user does not have an email address")
                return None

            # Find or create Kratos identity
            ory_identity = FacebookAuthService.find_or_create_ory_identity(facebook_id, email, name, provider)
            if not ory_identity:
                logger.error("Failed to find or create Ory identity")
                return None

            # Create Kratos session
            ory_session = FacebookAuthService.create_ory_session(ory_identity["id"])
            if not ory_session:
                logger.error("Failed to create Ory session")
                return None

            return {
                "session_token": ory_session["token"],
                "user_id": ory_identity["id"],
                "email": email,
                "name": name,
            }

        except Exception as e:
            logger.error(f"Unexpected error in Facebook authentication flow: {e}")
            return None
