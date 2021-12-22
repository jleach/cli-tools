from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Dict
from typing import NamedTuple
from typing import Optional
from typing import Union

import jwt

from codemagic.mixins import StringConverterMixin
from codemagic.utilities import log

from .type_declarations import ApiKey
from .type_declarations import KeyIdentifier

Seconds = int
JwtPayload = Dict[str, Union[int, str]]


class JWT(NamedTuple):
    key_id: KeyIdentifier
    token: str
    payload: JwtPayload
    expires_at: datetime


class JsonWebTokenManager(StringConverterMixin):
    """
    Helper class to generate JSON web tokens for App Store Connect API as per
    https://developer.apple.com/documentation/appstoreconnectapi/generating_tokens_for_api_requests
    """

    def __init__(
        self,
        api_key: ApiKey,
        token_duration: Seconds = 19*60,
        token_duration_error_margin: Seconds = 30,
        audience='appstoreconnect-v1',
        algorithm='ES256',
    ):
        self._logger = log.get_logger(self.__class__)
        # Authentication and expiration information used to generate JWT
        self._token_duration = token_duration
        self._token_duration_error_margin = token_duration_error_margin
        self._key = api_key
        # JWT properties
        self._algorithm = algorithm
        self._audience = audience
        # Internal cache
        self._jwt: Optional[JWT] = None

    @property
    def cache_path(self):
        return Path.home() / '.codemagic-cli-tools' / 'cache' / 'app_store_connect_jwt' / self._key.identifier

    def revoke(self):
        self._jwt = None
        self._revoke_disk_cache()

    def _revoke_disk_cache(self):
        try:
            self.cache_path.unlink()
        except FileNotFoundError:
            pass

    def _write_disk_cache(self, token: str):
        self.cache_path.parent.mkdir(exist_ok=True, parents=True)
        self.cache_path.write_text(token)
        self._logger.debug('Cached App Store Connect JWT')

    def _encode_token(self, jwt_payload: JwtPayload):
        return jwt.encode(
            jwt_payload,
            self._key.private_key,
            algorithm=self._algorithm,
            headers={'kid': self._key.identifier},
        )

    def _decode_payload(self, token: str) -> JwtPayload:
        return jwt.decode(
            token,
            self._key.private_key,
            algorithms=[self._algorithm],
            audience=self._audience,
        )

    def _load_jwt_from_disk(self) -> JWT:
        self._logger.debug('Load JWT for App Store Connect from disk cache')
        try:
            token = self.cache_path.read_text().strip()
        except FileNotFoundError:
            raise ValueError('Token is not cached', self._key.identifier)

        try:
            payload = self._decode_payload(token)
            expiration_timestamp: int = payload['exp']  # type: ignore
            expires_at = datetime.fromtimestamp(expiration_timestamp)
            issuer_id = payload['iss']
        except (TypeError, KeyError, jwt.InvalidTokenError):
            self._revoke_disk_cache()
            raise ValueError('Cached token is invalid', self._key.identifier)

        if issuer_id != self._key.issuer_id:
            self._revoke_disk_cache()
            raise ValueError('Cached token is invalid', self._key.identifier)
        elif self._is_expired(expires_at):
            self._revoke_disk_cache()
            raise ValueError('Cached token is expired', expires_at)

        self._logger.debug('Loaded JWT for App Store Connect from disk cache')
        return JWT(self._key.identifier, token, payload, expires_at)

    def _generate_jwt(self) -> JWT:
        self._logger.debug('Generate new App Store Connect JWT')
        expires_at = datetime.now() + timedelta(seconds=self._token_duration)
        payload = {
            'iss': self._key.issuer_id,
            'exp': int(expires_at.timestamp()),
            'aud': self._audience,
        }
        token = self._encode_token(payload)
        return JWT(self._key.identifier, self._str(token), payload, expires_at)

    def _is_expired(self, expires_at: datetime) -> bool:
        delta = timedelta(seconds=self._token_duration_error_margin)
        return datetime.now() - delta > expires_at

    def get_jwt(self) -> JWT:
        if self._jwt and not self._is_expired(self._jwt.expires_at):
            return self._jwt

        try:
            self._jwt = self._load_jwt_from_disk()
        except ValueError as ve:
            self._logger.debug('Failed to load App Store Connect JWT from disk cache: %s', ve.args[0])
            self._jwt = self._generate_jwt()
            self._write_disk_cache(self._jwt.token)
        return self._jwt
