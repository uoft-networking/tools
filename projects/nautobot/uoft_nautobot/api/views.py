# pylint: disable=unused-argument,redefined-builtin
import re

from django.conf import settings
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from rest_framework import status, fields as f
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiExample

from uoft_aruba import Settings as ArubaSettings
from uoft_core import txt


class InputError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = txt(
        """
        DELETE requests on this endpoint must include a JSON payload with a 'mac-address' 
        key whose value matches the regex pattern '^(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})$'.
        Example: {"mac-address":"10:02:b5:27:bb:0e"}
    """
    )
    default_code = "invalid_input"


class ArubaBlocklistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        conf: ArubaSettings = settings.PLUGINS_CONFIG["uoft_nautobot"]["aruba"]
        self.controllers = conf.md_api_connections
        self.mobility_master = conf.mm_api_connection

    @extend_schema(
        operation_id="aruba_stm_blocklist_get",
        responses={
            200: inline_serializer(
                name="aruba_stm_blacklist_get",
                fields={
                    "STA": f.CharField(
                        help_text='The mac address which has been blocked (ex: "d2:9a:3d:db:a6:e8")'
                    ),
                    "block-time(sec)": f.CharField(
                        help_text="How many seconds ago the mac address was added to the block list"
                    ),
                    "reason": f.CharField(help_text="Why the mac address was blocked"),
                    "remaining time(sec)": f.CharField(
                        help_text="How many seconds until this mac address is removed from the block list"
                    ),
                },
                many=True,
            )
        },
        examples=[
            OpenApiExample(
                "ex1",
                {
                    "STA": "d2:9a:3d:db:a6:e8",
                    "block-time(sec)": "2840",
                    "reason": "auth-failure",
                    "remaining time(sec)": "760",
                },
            ),
            OpenApiExample(
                "ex2",
                {
                    "STA": "38:f9:d3:6b:12:55",
                    "block-time(sec)": "2700",
                    "reason": "CP-flood",
                    "remaining time(sec)": "900",
                },
            ),
            OpenApiExample(
                "ex3",
                {
                    "STA": "8a:e5:08:3b:83:31",
                    "block-time(sec)": "1665",
                    "reason": "ARP spoofing",
                    "remaining time(sec)": "1935",
                },
            ),
        ],
    )
    def get(self, request, format=None):
        """
        Get the current aggregated WiFi authentication block list (aka 'stm blocklist')
        from the aruba controllers

        Example:
        ```console
        $ curl -H "Authorization: Token $token" -H "Accept: application/json; indent=4" -s https://engine.netmgmt.utsc.utoronto.ca/api/plugins/uoft/aruba-blocklist/
        [
            {
                "STA": "1a:0c:05:39:87:80",
                "block-time(sec)": "2325",
                "reason": "auth-failure",
                "remaining time(sec)": "1275"
            },
            {
                "STA": "40:23:43:aa:7a:2f",
                "block-time(sec)": "1015",
                "reason": "ping-flood",
                "remaining time(sec)": "2585"
            },
            {
                "STA": "3e:d2:51:bd:2a:69",
                "block-time(sec)": "55",
                "reason": "CP-flood",
                "remaining time(sec)": "3545"
            },
            ...
        ]
        ```
        """
        res = {}
        for c in self.controllers:
            with c as conn:
                res.update(
                    {
                        entry["STA"]: entry
                        for entry in conn.wlan.get_ap_client_blocklist()
                    }
                )
        return Response(list(res.values()))

    @extend_schema(
        operation_id="aruba_stm_blocklist_remove",
        responses={
            202: inline_serializer(
                name="aruba_stm_blacklist_remove",
                fields={
                    "detail": f.CharField(
                        help_text="A message confirming the results of the operation"
                    ),
                },
            ),
        },
        examples=[
            OpenApiExample(
                "ex1",
                {
                    "detail": "mac address '10:02:b5:27:bb:0e' has been removed from the aruba stm blocklist"
                },
            )
        ],
    )
    def delete(self, request, format=None):
        """
        Remove a mac address from the WiFi authentication block list (aka 'stm blocklist')
        of the aruba controllers.
        Requests on this endpoint must include a JSON payload with a 'mac-address'
        key whose value matches the regex pattern '^(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})$'.

        Example:
        ```console
        $ curl -H "Authorization: Token $token" -H "Accept: application/json;" -H 'Content-Type: application/json' -X DELETE -d '{"mac-address":"10:02:b5:27:bb:0e"}' -s https://engine.netmgmt.utsc.utoronto.ca/api/plugins/uoft/aruba-blocklist/
        {"detail": "mac address '10:02:b5:27:bb:0e' has been removed from the aruba stm blocklist"}
        ```
        """
        try:
            assert request.data
            assert "mac-address" in request.data
            mac = request.data["mac-address"]
            assert re.match(r"^(([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})$", mac)
        except AssertionError as e:
            raise InputError() from e

        # Now we can go ahead and delete the mac-address
        with self.mobility_master as conn:
            conn.wlan.blmgr_blocklist_remove(mac)

        res = {
            "detail": f"mac address '{mac}' has been removed from the aruba stm blocklist"
        }
        return Response(res, status=status.HTTP_202_ACCEPTED)
