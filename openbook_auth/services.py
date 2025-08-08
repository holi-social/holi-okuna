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
    def verify_facebook_token(access_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify Facebook access token using Ory Kratos admin API
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

            # Check if user exists in Ory with this Facebook ID
            ory_user = FacebookAuthService._find_ory_user_by_facebook_id(facebook_user_id)

            if ory_user:
                # User exists, return their info
                return {
                    "user_id": ory_user["id"],
                    "email": email or ory_user.get("traits", {}).get("email"),
                    "name": name,
                    "facebook_id": facebook_user_id,
                    "exists": True,
                }
            else:
                # User doesn't exist, we'll need to create them
                return {"email": email, "name": name, "facebook_id": facebook_user_id, "exists": False}

        except requests.RequestException as e:
            logger.error(f"Request error during Facebook token verification: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Facebook token verification: {e}")
            return None

    @staticmethod
    def _find_ory_user_by_facebook_id(facebook_id: str) -> Optional[Dict[str, Any]]:
        """
        Find Ory user by Facebook ID using direct identifier search
        """
        try:
            params = {"credentials_identifier": f"facebook-{facebook_id}", "include_credential": "oidc"}
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
    def create_ory_user_from_facebook(facebook_id: str, email: str, name: str) -> Optional[Dict[str, Any]]:
        """
        Create a new Ory user from Facebook data
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
                    "oidc": {"identifiers": [f"facebook-{facebook_id}"], "config": {"providers": ["facebook"]}}
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
    def generate_id_token(user_id: str, email: str) -> str:
        """
        Generate a JWT ID token for the mobile app
        """
        import jwt
        from datetime import datetime, timedelta

        payload = {
            "sub": user_id,
            "email": email,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=24),  # 24 hour expiry
            "iss": "okuna-auth",
            "aud": "okuna-mobile",
        }

        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
