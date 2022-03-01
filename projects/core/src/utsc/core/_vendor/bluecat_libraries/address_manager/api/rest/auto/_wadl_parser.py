# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Tools for processing a BlueCat Address Manager REST API service specification
and generating functions for calling discovered endpoints.
"""
import re
from typing import Optional
from xml.etree import ElementTree

from ....api._version import Version
from .....http_client import ClientError, ErrorResponse


class ServiceBase:
    """
    A base (and empty) service representation that can be used as subject of
    extension with methods for calling Address Manager endpoints.
    The instance(s) of this class are not expected to be used as a
    client directly, but as holders of the generated wrappers.

    :param url: Base URL for the target service's endpoints. Defaults to `None`.
    :type url: str, optional
    :param version: Version of the target service. Defaults to `None`.
    :type version: str, optional
    """

    def __init__(self, url=None, version: Optional[Version] = None) -> None:
        self.url = url
        self.version = version

    def __getattr__(self, item):
        """
        User tries to make a REST call that wasn't generated. Probably means it
        doesn't exist.

        :param item: The method attribute being called.
        :raise: ClientError
        """
        raise ClientError("REST API method not found: {}".format(item))


def get_element_namespace(element):
    """
    Gets the namespace of an element.

    :param element: Element to get the namespace of.
    :return: Namespace of given element.
    """
    result = re.match("{.+}", element.tag)
    return result.group(0) if result else ""


def process_rest_response(response):
    """
    Processes response from Address Manager REST API.

    :param response:
    :return: object
    """
    if not response.ok:
        message = response.text
        if not message:
            message = "Response with HTTP status code {}".format(response.status_code)
        raise ErrorResponse(message, response)
    try:
        return response.json()
    except (AttributeError, ValueError):
        return response.text


class WADLParser:
    """
    Generator of a service for calling endpoints defined in a WADL.
    """

    def __init__(self, url, wadl, namespace=None):
        if isinstance(wadl, str):
            wadl = ElementTree.fromstring(wadl)
        if not namespace:
            namespace = get_element_namespace(wadl)

        self.endpoint_base_url = url
        self.wadl = wadl
        self.xpath_method = ".//{0}method".format(namespace)
        self.xpath_request_param = "./{0}request/{0}param".format(namespace)
        self.xpath_request_representation = "./{0}request/{0}representation".format(namespace)

    def generate_service(self):
        """
        Process the provided WADL and construct an object with generated methods for the described
        endpoints.

        :return: An object with generated methods for the endpoints of the service described in the
            provided WADL.
        :rtype: ServiceBase
        """
        target = ServiceBase(self.endpoint_base_url)
        self.generate_all_methods(target)
        return target

    def generate_all_methods(self, target):
        """
        Iterates through all REST methods defined in the WADL file and attaches
        the generated Python methods to the target instance.

        :param target: Service object to attach the generated methods to.
        :type target: object
        """
        rest_methods = self.wadl.findall(self.xpath_method)
        for method in rest_methods:
            self.generate_method(target, method)

    def generate_method(self, target, rest_method):
        """
        Generate Python method based on a WADL specification and attach it to
        the target instance.

        :param target: Service object to attach a generated method to.
        :type target: object
        :param rest_method: XML element from the WADL file, describing a REST
            method.
        """
        rest_params = rest_method.findall(self.xpath_request_param)
        rest_call_type = rest_method.attrib["name"].lower()
        rest_method_name = rest_method.attrib["id"]
        representation_param = rest_method.findall(self.xpath_request_representation)
        extra_data_type = ""
        if representation_param:
            extra_data_type = representation_param[0].attrib["mediaType"]

        endpoint_url = "{url}/{rest_call}".format(
            url=self.endpoint_base_url, rest_call=rest_method_name
        )

        def generic_rest_call(session, *args, **kwargs):
            """
            Generates a REST API call to BlueCat Address Manager based on the item the user specified.

            :param session: requests session used to make the REST call with.
            :param args: positional arguments for the REST call.
            :param kwargs: keyword arguments for the REST call.
            :return: Response for the REST call.
            """
            parameters = {}
            index = -1
            extra_arg = None
            try:
                for index, param in enumerate(rest_params):
                    parameters[param.attrib["name"]] = args[index]
            except IndexError:
                pass
            finally:
                if len(parameters) < len(rest_params) + len(representation_param):
                    for key, value in kwargs.items():
                        if any(
                            rest_params[i].attrib["name"] == key for i in range(0, len(rest_params))
                        ):
                            parameters[key] = value
                        else:
                            extra_arg = {key: value}
            http_method = getattr(session, rest_call_type)

            # NOTE: The expectation that the value of `verify` of the session will be honoured
            # inside the HTTP methods below is not satisfied. In the test pipeline / environment
            # that does not happen. Until test environment is updated we have to be explicit.
            # NOTE: Passing `verify` explicitly in the method calls as a temporary workaround.

            # Checks if you need to send json over with the request
            if extra_data_type in ["application/json", "multipart/form-data"] and len(args) + len(
                kwargs
            ) > len(rest_params):
                if extra_data_type == "multipart/form-data":
                    if not extra_arg:
                        extra_arg = {"data": args[index + 1]}
                    response = http_method(
                        endpoint_url, params=parameters, files=extra_arg, verify=session.verify
                    )
                else:
                    if not extra_arg:
                        extra_arg = args[index + 1]
                    response = http_method(
                        endpoint_url, params=parameters, json=extra_arg, verify=session.verify
                    )
            else:
                response = http_method(endpoint_url, params=parameters, verify=session.verify)
            return process_rest_response(response)

        setattr(target, rest_method.attrib["id"], generic_rest_call)
        return generic_rest_call
