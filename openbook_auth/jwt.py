import json
from django.conf import settings
import jwt
import requests
from django.core.cache import cache


JWKS_CACHE_KEY = 'jwks'
JWKS_CACHE_TIMEOUT_SECONDS = 5 * 60


def jwt_decode_token(token):
    jwks = _jwks()
    try:
        return _validate_token(jwks, token)
    except:
        # remove JWKS from cache, just in case the jwks changed and the token was signed with a newer cert
        jwks = _refresh_jwks()
        return _validate_token(jwks, token)


def _validate_token(jwks, token):
    header = jwt.get_unverified_header(token)
    public_key = None
    for jwk in jwks['keys']:
        if jwk['kid'] == header['kid']:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    if public_key is None:
        raise Exception('Public key not found.')

    issuer = settings.JWT_AUTH['JWT_ISSUER']
    audience = settings.JWT_AUTH['JWT_AUDIENCE']
    return jwt.decode(token, public_key, audience=audience, issuer=issuer, algorithms=['RS256'])


def _jwks():
    jwks = cache.get(JWKS_CACHE_KEY)

    if jwks is None:
        jwks_url = settings.JWT_AUTH['JWT_JWKS_URL']
        jwks = requests.get(jwks_url).json()
        cache.set(JWKS_CACHE_KEY, jwks, JWKS_CACHE_TIMEOUT_SECONDS)

    return jwks


def _refresh_jwks():
    cache.delete(JWKS_CACHE_KEY)
    return _jwks()