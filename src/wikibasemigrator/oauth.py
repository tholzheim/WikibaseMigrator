import base64
import hashlib
import os
import re

import requests
from nicegui import app
from pydantic import HttpUrl


class OAuth:
    """
    Provides functions to access the mediawiki oauth api
    """

    @classmethod
    def get_authorize_url(cls, consumer_key: str | None, mediawiki_rest_url: HttpUrl, callback_url: str) -> str:
        """
        Get authorization url that sends the user to the wiki to authorize
        :param consumer_key: consumer_key of the application if None link to homepage is returned
        :param mediawiki_rest_url: url of the mediawiki rest endpoint
        :param callback_url: callback url that is registered at the mediawiki
        :return: url of the authorization page
        """
        if consumer_key is None:
            return "/"
        params = {
            "response_type": "code",
            "client_id": consumer_key,
            "redirect_uri": "http://localhost:8009/oauth_callback",
            "code_challenge": cls._get_code_challenge(),
            "code_challenge_method": "S256",
        }
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{mediawiki_rest_url.unicode_string()}/oauth2/authorize?{query}"

    @classmethod
    def fetch_access_token(cls, code: str, consumer_key: str, mediawiki_rest_url: HttpUrl, callback_url: str):
        """
        Fetch access token with given code
        :param code:
        :param consumer_key:
        :param mediawiki_rest_url:
        :param callback_url:
        :return:
        """
        code_verfier = cls.get_user_code_verfier()
        params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_url,
            "code_verifier": code_verfier,
            "client_id": consumer_key,
            # "code_challenge_method": "S256",
        }
        url = f"{mediawiki_rest_url.unicode_string()}/oauth2/access_token"
        response = requests.post(url, data=params)
        # ToDo: Test the access token return
        print(response.json())

    @classmethod
    def _get_code_challenge(cls):
        """
        Get code challenge for the OAuth requests
        the challenge is store per user
        :return:
        """
        code_verifier = cls.get_user_code_verfier()
        if code_verifier is None:
            code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
            code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
            cls.set_user_code_verifier(code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge

    @classmethod
    def get_user_code_verfier(cls):
        """
        Get user code verifier
        :return:
        """
        return app.storage.user.get("code_verifier")

    @classmethod
    def set_user_code_verifier(cls, code_verifier: str):
        """
        Set user code verifier
        :param code_verifier:
        :return:
        """
        app.storage.user["code_verifier"] = code_verifier
