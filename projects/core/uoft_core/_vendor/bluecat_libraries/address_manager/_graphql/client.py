# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Module for the GraphQL client
For internal BlueCat use only!
"""
from __future__ import annotations

import json
from string import Template
from typing import Any, Optional

import requests
from .exceptions import GraphQLException
from ...http_client.exceptions import ClientError


class Client:
    """
    BAM GraphQL client
    """

    def __init__(self, url: str, *, verify: bool | str = True) -> None:
        """
        ``verify`` has the same meaning as arguments of the same name commonly found in
        ``requests`` functions.
        """
        self.url = url

        self._verify = verify
        self._session: Optional[requests.Session] = None

    @property
    def is_authenticated(self) -> bool:
        """Whether or not this client is currently authenticated with a session."""
        return bool(self._session)

    def invalidate(self) -> None:
        """
        Log out of session and release any allocated session resources. If the client was not
        authenticated, this is a no-op.
        """
        if not self.is_authenticated:
            return
        # TDB: make logout request
        self._session.close()
        self._session = None

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args) -> None:
        self.invalidate()

    def get_tokens(self) -> dict[str, str]:
        """
        Return authentication tokens for the client's current session. These can be used to
        authenticate another ``Client`` object without having to make an authentication request.
        """
        if not self.is_authenticated:
            raise ClientError("Client is not authenticated")
        return {
            "jsession_id": self._session.cookies["JSESSIONID"],
            "nonce": self._session.headers["X-NONCE"],
        }

    def set_tokens(self, *, jsession_id: str, nonce: str) -> Client:
        """
        If the client is not authenticated, create a new session that's authenticated by the given
        tokens. Otherwise, replace tokens on the existing session. Return the client afterwards.
        """
        if not self._session:
            self._session = requests.Session()
        self._session.cookies["JSESSIONID"] = jsession_id
        self._session.headers["X-NONCE"] = nonce
        return self

    @staticmethod
    def __raise_if_errors(response: requests.Response) -> dict[str, Any]:
        """
        Check for errors in the GraphQL response and raise an exception if any exist. Otherwise,
        return the response body.
        """
        if not response.ok:
            raise GraphQLException(
                "Response with HTTP status code " + str(response.status_code), response, None
            )
        body = response.json()
        if "errors" in body:
            message = json.dumps([e["message"] for e in body["errors"]], indent=2)
            raise GraphQLException(message, response, body["errors"])
        return body

    def authenticate(self, username: str, password: str) -> Client:
        """Authenticate with a session, then return the client."""
        graph_query = Template(
            """
            mutation {
                basicAuth(
                    input: {
                        username: "$username",
                        password: "$password",
                        startSession: true
                    }
                ) {
                    session { nonce }
                }
            }
            """
        ).substitute(username=username, password=password)
        response = requests.post(self.url, json={"query": graph_query}, verify=self._verify)
        body = Client.__raise_if_errors(response)
        return self.set_tokens(
            jsession_id=response.cookies["JSESSIONID"],
            nonce=body["data"]["basicAuth"]["session"]["nonce"],
        )

    def execute(self, query: str, variables: Optional[dict] = None) -> dict:
        """
        Execute the given query (or mutation). If the query requires authentication, this client
        must first be authenticated with a session using the ``authenticate()`` method.

        :param query: GraphQL API query
        :type query: str
        :param variables: Arguments for the GraphQL API query
        :type variables: dict
        :return: A dictionary containing the GraphQL query response.
        :rtype: dict
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        response = (self._session or requests).post(self.url, json=payload, verify=self._verify)
        return Client.__raise_if_errors(response)
