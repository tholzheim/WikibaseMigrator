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
    def get_authorize_url(cls, consumer_key: str, mediawiki_rest_url: HttpUrl, callback_url: str):
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
        code_verfier = cls.get_user_code_verfier()
        print(code_verfier)
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
        print(response.json())

    @classmethod
    def _get_code_challenge(cls):
        code_verifier = cls.get_user_code_verfier()
        if code_verifier is None:
            code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
            code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
            app.storage.user["code_verifier"] = code_verifier
        print(code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge

    @classmethod
    def get_user_code_verfier(cls):
        return app.storage.user.get("code_verifier")
