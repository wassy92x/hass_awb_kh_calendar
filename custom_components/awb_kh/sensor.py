from datetime import datetime, timedelta
import logging
import requests
import pytz

from homeassistant.const import (
    CONF_NAME,
    STATE_OFF,
    STATE_ON
)
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import (
    generate_entity_id,
    Entity,
)
from homeassistant.util import Throttle, dt

_LOGGER = logging.getLogger(__name__)

CONF_CITY = "city"
CONF_STREET = "street"
CONF_OFFSET = "offset"

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STREET): cv.string,
        vol.Optional(CONF_OFFSET, default="12:00:00"): cv.time_period_str,
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
    waste_sensors.append(WasteSensor("Restmüll", black_entity_id, data, "black", config[CONF_OFFSET]))
    waste_sensors.append(WasteSensor("Biomüll", brown_entity_id, data, "brown", config[CONF_OFFSET]))
    waste_sensors.append(WasteSensor("Kunstoffmüll", yellow_entity_id, data, "yellow", config[CONF_OFFSET]))
    waste_sensors.append(WasteSensor("Papiermüll", blue_entity_id, data, "blue", config[CONF_OFFSET]))
    add_entities(waste_sensors, True)


class WasteSensor(Entity):
    """A device for getting the next waste date."""

    def __init__(self, name, entity_id, data, trash_type, offset):
        """Create the Waste Sensor."""
        self.data = data
        self.entity_id = entity_id
        self._trash_type = trash_type
        self._next_date = None
        self._state = None
        self._name = name
        self._offset = offset

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {"next_date": self._next_date.isoformat()}

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:delete"

    @property
    def state(self):
        """Return the state"""
        return self._state

    @property
    def device_class(self):
        """Return the device class"""
        return "ISO8601"

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def update(self):
        """Update event data."""
        self.data.update()
        current_date_time = datetime.now(tz=pytz.timezone('Europe/Berlin'))
        current_date = current_date_time.date()
        self._state = STATE_OFF
        for event in self.data.events:
            if event[self._trash_type] is True and event["date"] >= current_date:
                self._next_date = event["date"]
                if current_date_time >= (event["date"] - self._offset) and current_date_time <= (event["date"] + timedelta(days=1)):
                    self._state = STATE_ON
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
        d = {"ort": self._city, "strasse": self._street}
        response = requests.post("https://app.awb-bad-kreuznach.de/index.php?option=com_iab_start&controller=iab_start&task=loadTermine", data=d)
        body = response.json()
        events = map(lambda k: {
            "id": k["id"],
            "date": datetime.strptime(k["termin"], "%Y-%m-%d").replace(tzinfo=pytz.timezone('Europe/Berlin')),
            "black": k["restmuell"] != "0",
            "brown": k["bio"] != "0",
            "yellow": k["wert"] != "0",
            "blue": k["papier"] != "0",
        }, body["termine"])
        self.events = sorted(events, key=lambda k: k["date"])
