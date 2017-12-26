"""
Telstra API platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.telstra/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    BaseNotificationService, ATTR_TITLE, PLATFORM_SCHEMA)
from homeassistant.const import CONTENT_TYPE_JSON
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_CONSUMER_KEY = 'consumer_key'
CONF_CONSUMER_SECRET = 'consumer_secret'
CONF_PHONE_NUMBER = 'phone_number'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CONSUMER_KEY): cv.string,
    vol.Required(CONF_CONSUMER_SECRET): cv.string,
    vol.Required(CONF_PHONE_NUMBER): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Telstra SMS API notification service."""
    consumer_key = config.get(CONF_CONSUMER_KEY)
    consumer_secret = config.get(CONF_CONSUMER_SECRET)
    phone_number = config.get(CONF_PHONE_NUMBER)

    if _authenticate(consumer_key, consumer_secret) is False:
        _LOGGER.exception("Error obtaining authorization from Telstra API")
        return None

    return TelstraNotificationService(
        consumer_key, consumer_secret, phone_number)


class TelstraNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Telstra SMS API."""

    def __init__(self, consumer_key, consumer_secret, phone_number):
        """Initialize the service."""
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._phone_number = phone_number

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE)

        # Retrieve authorization first
        token_response = _authenticate(
            self._consumer_key, self._consumer_secret)
        if token_response is False:
            _LOGGER.exception("Error obtaining authorization from Telstra API")
            return

        provision_response = _provision(token_response)
        if provision_response is False:
            _LOGGER.exception("Error provisioning number from Telstra API")
            return

        # Send the SMS
        if title:
            text = '{} {}'.format(title, message)
        else:
            text = message

        message_data = {
            'to': self._phone_number,
            'body': text,
            'replyRequest':"False",
        }
        message_resource = 'https://tapi.telstra.com/v2/messages/sms'
        message_headers = {
            'Content-Type': CONTENT_TYPE_JSON,
            'Authorization': 'Bearer ' + token_response['access_token'],
        }
        message_response = requests.post(
            message_resource, headers=message_headers, json=message_data,
            timeout=10)

        if message_response.status_code != 201:
            _LOGGER.exception("Failed to send SMS. Status code: %d",
                              message_response.status_code)


def _authenticate(consumer_key, consumer_secret):
    """Authenticate with the Telstra API."""
    token_data = {
        'client_id': consumer_key,
        'client_secret': consumer_secret,
        'grant_type': 'client_credentials',
        'scope': 'NSMS'
    }
    token_resource = 'https://sapi.telstra.com/v1/oauth/token'
    token_response = requests.get(
        token_resource, params=token_data, timeout=10).json()

    if 'error' in token_response:
        return False

    return token_response


def _provision(token_response):
    """Provision a number with the Telstra API."""
    provision_data = {
        'Authorization': 'Bearer ' + token_response['access_token'],
        'cache-control':'no-cache',
        'Content-Type':'application/json',
        'activedays':"30",
        'notifyurl':"",
        'callbackdata':""
    }

    provision_resource = 'https://tapi.telstra.com/v2/messages/provisioning/subscriptions'
    provision_response = requests.get(
        provision_resource, params=provision_data, timeout=10).json()

    if 'error' in provision_response:
        return False

    return provision_response

