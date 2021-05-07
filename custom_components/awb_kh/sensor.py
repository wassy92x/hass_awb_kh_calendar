from datetime import datetime, timedelta
import pytz
import logging
import requests

from homeassistant.const import (
    CONF_NAME,
)
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import (
    generate_entity_id,
    Entity,
)
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_CITY = "city"
CONF_STREET = "street"

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STREET): cv.string,
    }
)
ENTITY_ID_FORMAT = "sensor.{}"
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=24)


def setup_platform(hass, config, add_entities, disc_info=None):
    """Set up the AWB KH Sensor platform."""
    data = AWBCalendarData(config[CONF_CITY], config[CONF_STREET])
    black_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "black_waste", hass=hass)
    brown_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "brown_waste", hass=hass)
    yellow_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "yellow_waste", hass=hass)
    blue_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "blue_waste", hass=hass)
    waste_sensors = []
    waste_sensors.append(WasteSensor("Restmüll", black_entity_id, data, "black"))
    waste_sensors.append(WasteSensor("Biomüll", brown_entity_id, data, "brown"))
    waste_sensors.append(WasteSensor("Kunstoffmüll", yellow_entity_id, data, "yellow"))
    waste_sensors.append(WasteSensor("Papiermüll", blue_entity_id, data, "blue"))
    add_entities(waste_sensors, True)


class WasteSensor(Entity):
    """A device for getting the next waste date."""

    def __init__(self, name, entity_id, data, trash_type):
        """Create the Waste Sensor."""
        self.data = data
        self.entity_id = entity_id
        self._trash_type = trash_type
        self._next_date = None
        self._name = name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return None

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:delete"

    @property
    def state(self):
        """Return the state"""
        return self._next_date

    @property
    def device_class(self):
        """Return the device class"""
        return "timestamp"

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def update(self):
        """Update event data."""
        self.data.update()
        current_date = datetime.now().date()
        self._next_date = None;
        for event in self.data.events:
            if event[self._trash_type] is True and event["date"] >= current_date:
                self._next_date = event["date"]
                return

class AWBCalendarData:
    """Class to utilize the AWB KH Calendar device to get the events."""

    def __init__(self, city, street):
        """Set up how we are going to search the WebDav calendar."""
        self._city = city
        self._street = street
        self.events = []

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        d = {"ort": self._city, "strasse": self._street, "mode": "false"}
        response = requests.post(" https://app.awb-bad-kreuznach.de/api/loadDates.php", data=d)
        body = response.json()
        timezone = pytz.timezone("Europe/Berlin")
        events = map(lambda k: {
            "id": k["id"],
            "date": timezone.localize(datetime.strptime(k["termin"], "%Y-%m-%d")).date(),
            "black": k["restmuell"] != "0",
            "brown": k["bio"] != "0",
            "yellow": k["wert"] != "0",
            "blue": k["papier"] != "0",
        }, body)
        self.events = sorted(events, key=lambda k: k["date"])
