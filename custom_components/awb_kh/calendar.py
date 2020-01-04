from datetime import datetime, timedelta
import logging
import requests

import voluptuous as vol

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    CalendarEventDevice,
    get_date,
)
from homeassistant.const import (
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.util import Throttle, dt

_LOGGER = logging.getLogger(__name__)

CONF_CITY = "city"
CONF_STREET = "street"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STREET): cv.string
    }
)

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=24)


def setup_platform(hass, config, add_entities, disc_info=None):
    """Set up the AWB KH Calendar platform."""
    data = AWBCalendarData(config[CONF_CITY], config[CONF_STREET])

    black_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "black_waste", hass=hass)
    brown_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "brown_waste", hass=hass)
    yellow_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "yellow_waste", hass=hass)
    blue_entity_id = generate_entity_id(ENTITY_ID_FORMAT, "blue_waste", hass=hass)
    trash_devices = [
        TrashDevice("Restmüll", restmuell_entity_id, data, "black")
        TrashDevice("Biomüll", biomuell_entity_id, data, "brown")
        TrashDevice("Kunstoffmüll", gelbermuell_entity_id, data, "yellow")
        TrashDevice("Papiermüll", papiermuell_entity_id, data, "blue")
    ]
    add_entities(trash_devices, True)


class TrashDevice(CalendarEventDevice):
    """A device for getting the next trash date."""

    def __init__(self, name, entity_id, data, trash_type):
        """Create the WebDav Calendar Event Device."""
        self.data = data
        self.entity_id = entity_id
        self._trash_type = trash_type
        self._event = None
        self._name = name

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return None

    @property
    def event(self):
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        events = filter(lambda k: k["date"] >= start_date and k["date"] <= end_date and k[self._trash_type] is True, self.data.events)
        return map(lambda k: {
            "uid": k["id"],
            "title": self.name,
            "start": self.get_hass_date(k["date"]),
            "end": self.get_hass_date(k["date"] + timedelta(days=1)),
            "location": "",
            "description": "",
        }, events)

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def update(self):
        """Update event data."""
        self.data.update()
        current_date = datetime.date(datetime.now())
        self._event = None
        for event in self.data.events:
            if event[self._trash_type] is True and event["date"] >= current_date:
                self._event = {
                    "summary": self.name,
                    "start": self.get_hass_date(event["date"]),
                    "end": self.get_hass_date(event["date"] + timedelta(days=1)),
                    "location": "",
                    "description": "",
                }
                return

    @staticmethod
    def get_hass_date(obj):
        """Return if the event matches."""
        return {"date": obj.isoformat()}


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
            "date": datetime.strptime(k["termin"], "%Y-%m-%d").date(),
            "black": k["restmuell"] != "0",
            "brown": k["bio"] != "0",
            "yellow": k["wert"] != "0",
            "blue": k["papier"] != "0",
        }, body["termine"])
        self.events = sorted(events, key=lambda k: k["date"])
