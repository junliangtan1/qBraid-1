# Copyright 2023 qBraid
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Module for making requests to the qBraid API.

"""
import configparser
import logging
import os
from typing import Any, Optional

from requests import RequestException, Response, Session
from requests.adapters import HTTPAdapter

from .exceptions import AuthError, ConfigError, RequestsApiError
from .retry import STATUS_FORCELIST, PostForcelistRetry

DEFAULT_ENDPOINT_URL = "https://api-staging-1.qbraid.com/api"
DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".qbraid", "qbraidrc")
DEFAULT_CONFIG_SECTION = "default"

logger = logging.getLogger(__name__)


class QbraidSession(Session):
    """Custom session with handling of request urls and authentication.

    This is a child class of :py:class:`requests.Session`. It handles qbraid
    authentication with custom headers, has SSL verification disabled
    for compatibility with lab, and returns all responses as jsons for
    convenience in the sdk.

    Args:
        base_url: Base URL for the session's requests.
        user_email: JupyterHub User.
        refresh_token: Authenticated qBraid refresh-token.
        retries_total: Number of total retries for the requests.
        retries_connect: Number of connect retries for the requests.
        backoff_factor: Backoff factor between retry attempts.

    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        base_url: Optional[str] = None,
        user_email: Optional[str] = None,
        refresh_token: Optional[str] = None,
        retries_total: int = 5,
        retries_connect: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        super().__init__()

        self.base_url = base_url
        self.user_email = user_email
        self.refresh_token = refresh_token
        self.verify = False

        self._initialize_retry(retries_total, retries_connect, backoff_factor)

    def __del__(self) -> None:
        """qbraid session destructor. Closes the session."""
        self.close()

    @property
    def base_url(self) -> Optional[str]:
        """Return the qbraid api url."""
        return self._base_url

    @base_url.setter
    def base_url(self, value: Optional[str]) -> None:
        """Set the qbraid api url."""
        url = value if value else self.get_config_variable("url")
        self._base_url = url if url else DEFAULT_ENDPOINT_URL

    @property
    def user_email(self) -> Optional[str]:
        """Return the session user email."""
        return self._user_email

    @user_email.setter
    def user_email(self, value: Optional[str]) -> None:
        """Set the session user email."""
        user_email = value if value else self.get_config_variable("email")
        self._user_email = user_email if user_email else os.getenv("JUPYTERHUB_USER")
        if user_email:
            self.headers.update({"email": user_email})  # type: ignore[attr-defined]

    @property
    def refresh_token(self) -> Optional[str]:
        """Return the session refresh token."""
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]) -> None:
        """Set the session refresh token."""
        refresh_token = value if value else self.get_config_variable("refresh-token")
        self._refresh_token = refresh_token
        if refresh_token:
            self.headers.update({"refresh-token": refresh_token})  # type: ignore[attr-defined]

    def get_config_variable(self, config_name: str) -> Optional[str]:
        """Returns the config value of specified config.

        Args:
            config_name: The name of the config
        """
        filepath = DEFAULT_CONFIG_PATH
        if os.path.isfile(filepath):
            config = configparser.ConfigParser()
            config.read(filepath)
            section = DEFAULT_CONFIG_SECTION
            if section in config.sections():
                if config_name in config[section]:
                    return config[section][config_name]
        return None

    def save_config(
        self,
        user_email: Optional[str] = None,
        refresh_token: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Create qbraidrc file. In qBraid Lab, qbraidrc is automatically present in filesystem.

        Args:
            user_email:  JupyterHub User.
            refresh_token: Authenticated qBraid refresh-token.
            base_url: Base URL for the session's requests.
        """
        self.user_email = user_email if user_email else self.user_email
        self.refresh_token = refresh_token if refresh_token else self.refresh_token
        self.base_url = base_url if base_url else self.base_url

        res = self.get("/identity")

        if res.status_code != 200 or self.user_email != res.json()["email"]:
            raise AuthError("Invalid qBraid API credentials")

        try:
            filepath = DEFAULT_CONFIG_PATH
            if not os.path.isfile(filepath):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
            config = configparser.ConfigParser()
            config.read(filepath)
            section = DEFAULT_CONFIG_SECTION
            if section not in config.sections():
                config.add_section(section)
            config.set(section, "email", self.user_email)
            config.set(section, "refresh-token", self.refresh_token)
            config.set(section, "url", self.base_url)
            with open(filepath, "w", encoding="utf-8") as cfgfile:
                config.write(cfgfile)
        except Exception as err:
            raise ConfigError from err

    def _email_converter(self) -> Optional[str]:
        """Convert email to compatible string format"""
        if not self.user_email:
            return None
        return (
            self.user_email.replace("-", "-2d")
            .replace(".", "-2e")
            .replace("@", "-40")
            .replace("_", "-5f")
        )

    def _initialize_retry(
        self, retries_total: int, retries_connect: int, backoff_factor: float
    ) -> None:
        """Set the session retry policy.

        Args:
            retries_total: Number of total retries for the requests.
            retries_connect: Number of connect retries for the requests.
            backoff_factor: Backoff factor between retry attempts.
        """
        retry = PostForcelistRetry(
            total=retries_total,
            connect=retries_connect,
            backoff_factor=backoff_factor,
            status_forcelist=STATUS_FORCELIST,
        )

        retry_adapter = HTTPAdapter(max_retries=retry)
        self.mount("http://", retry_adapter)
        self.mount("https://", retry_adapter)

    def request(self, method: str, url: str, **kwargs: Any) -> Response:  # type: ignore[override]
        """Construct, prepare, and send a ``Request``.

        Args:
            method: Method for the new request (e.g. ``POST``).
            url: URL for the new request.
            **kwargs: Additional arguments for the request.
        Returns:
            Response object.
        Raises:
            RequestsApiError: If the request failed.
        """
        # pylint: disable=arguments-differ
        final_url = self.base_url + url

        headers = self.headers.copy()
        headers.update(kwargs.pop("headers", {}))

        try:
            response = super().request(method, final_url, headers=headers, **kwargs)
            response.raise_for_status()
        except RequestException as ex:
            # Wrap requests exceptions for compatibility.
            message = str(ex)
            if ex.response is not None:
                try:
                    error_json = ex.response.json()["error"]
                    msg = error_json["message"]
                    code = error_json["code"]
                    message += f". {msg}, Error code: {code}."
                    logger.debug("Response uber-trace-id: %s", ex.response.headers["uber-trace-id"])
                except Exception:  # pylint: disable=broad-except
                    # the response did not contain the expected json.
                    message += f". {ex.response.text}"

            if self.refresh_token:
                message = message.replace(self.refresh_token, "...")

            raise RequestsApiError(message) from ex

        return response
