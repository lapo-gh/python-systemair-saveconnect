import json
import logging
import typing
from json import JSONDecodeError

import httpx

from systemair.saveconnect.models import SaveConnectDevice
from systemair.saveconnect.registry import RegisterWrite

from .const import APIRoutes

_LOGGER = logging.getLogger(__name__)


class SaveConnectGraphQL:

    def __init__(self, api):
        self.api = api
        transport = httpx.AsyncHTTPTransport(retries=api.http_retries)
        self._http: httpx.AsyncClient = httpx.AsyncClient(timeout=300, transport=transport)
        self.headers = {
            "content-type": "application/json",
            "x-access-token": None
        }
        self.api_url = "https://homesolutions.systemair.com/gateway/api"

    def set_access_token(self, _oidc_token):
        self.headers["x-access-token"] = _oidc_token["access_token"]

    async def queryWriteDeviceValues(self, device_id, register_pair: RegisterWrite, is_import=False):
        """
        Runs the GQL query for writing to the device.
        @param device_id:
        @param register_pair:
        @param is_import:
        @return:
        """
        query = """
                mutation ($input: WriteDeviceValuesInputType!) {
                  WriteDeviceValues(input: $input)
                }
            """

        data = dict(
            input={
                "deviceId": device_id,
                "import": is_import,
                "registerValues": json.dumps([
                    register_pair.dict()
                ])
            }
        )

        response_data = await self.post_request(
            url=self.api_url,
            data=dict(query=query, variables=data),
            headers=self.headers
        )

        return self.api.data.update(device_id, response_data)

    async def queryDeviceView(self, device_id, route):

        query = """
            mutation ($input: GetDeviceViewInput!) {
              GetDeviceView(input: $input) {
                route
                elements
                dataItems
                title
                translationVariables
              }
            }
        """
        data = dict(
            input=dict(
                deviceId=device_id,
                route=route
            )
        )

        response_data = await self.post_request(
            url=self.api_url,
            data=dict(query=query, variables=data),
            headers=self.headers
        )

        return self.api.data.update(device_id, response_data)

    async def queryGetDeviceData(self, device_id, change_mode=False):
        success = await self.queryDeviceView(
            device_id=device_id,
            route=f"/device/home{'' if not change_mode else '/changeMode'}"
        )
        return success

    async def queryGetAccount(self) -> typing.List['SaveConnectDevice']:
        query = """
            {
              GetAccount {
                email
                firstName
                lastName
                city
                country
                locale
                phoneNumber
                street
                role
                zipCode
                permissions
                exists
                disabled
                devices {
                  name
                  identifier
                  connectionStatus
                  startupWizardRequired
                  updateInProgress
                  units {
                    temperature
                    pressure
                    flow
                  }
                  street
                  zipcode
                  city
                  country
                  serviceLocked
                  filterLocked
                  weekScheduleLocked
                  hasAlarms
                }
                notifications {
                  id
                  title
                  description
                  type
                  unread
                  email
                  properties
                  createdAt
                }
                company {
                  companyName
                  referenceEmail
                  referenceName
                  responsiblePerson
                  responsiblePersonPhoneNumber
                }
              }
            }
        """

        response_data = await self.post_request(
            url=self.api_url,
            data=dict(query=query, variables={}),
            headers=self.headers
        )

        if response_data is None:
            _LOGGER.error("No data from the API")
            return []

        for device_data in response_data["GetAccount"]["devices"]:
            self.api.data.update_device(device_data=device_data)

        return list(self.api.data.devices.values())

    async def queryDeviceInfo(self, device: SaveConnectDevice):
        statuses = []
        for route in [
            APIRoutes.VIEWS_UNIT_INFORMATION_COMPONENTS_DESC,
            APIRoutes.VIEWS_UNIT_INFORMATION_SENSORS_DESC,
            APIRoutes.VIEWS_UNIT_INFORMATION_UNIT_INPUT_STATUS_DESC,
            APIRoutes.VIEWS_UNIT_INFORMATION_UNIT_OUTPUT_STATUS_DESC,
            APIRoutes.VIEWS_UNIT_INFORMATION_UNIT_DATE_TIME_TITLE,
            APIRoutes.VIEWS_UNIT_INFORMATION_UNIT_VERSION_DESC,
        ]:
            status = await self.queryDeviceView(device.identifier, route)

            if not status:
                _LOGGER.error(f"queryDeviceInfo failed for route={route}")
            statuses.append(status)

        return all(statuses)

        async def post_request(self, query: str, variables: dict = None) -> dict:
            json_payload = {
            "query": query,
            "variables": variables,
        }

        async with self.session.post(self._url, json=json_payload) as response:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as e:
                _logger.warning(f"Request failed with status {response.status}: {response.text}")
                raise e

            response_json = await response.json()

            if "errors" in response_json:
                _logger.warning(f"GraphQL errors: {response_json['errors']}")
                raise GraphQLException(response_json["errors"])

            if "data" not in response_json:
                _logger.warning(f"Missing 'data' key in response: {response_json}")
                return {}

            return response_json["data"]

