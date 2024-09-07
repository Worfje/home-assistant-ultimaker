"""Platform for sensor integration.

configuration.yaml
sensor:
  - platform: ultimaker
    name: PRINTER_NAME
    host: IP_ADDRESS
    scan_interval: 10 (optional, default 10)
    decimal: 2 (optional, default = 2)
    resources:
      - status (optional)
      - state (optional)
      - progress (optional)
      - bed_temperature (optional)
      - bed_temperature_target (optional)
      - bed_type (optional)
      - hotend_1_temperature (optional)
      - hotend_1_temperature_target (optional)
      - hotend_1_id (optional)
      - hotend_2_temperature (optional)
      - hotend_2_temperature_target (optional)
      - hotend_2_id (optional)
      - active_material_1_guid (optional)
      - active_material_1_length_remaining (optional)
      - active_material_2_guid (optional)
      - active_material_2_length_remaining (optional)
      
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    TEMP_CELSIUS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType, StateType
from homeassistant.util import Throttle

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "status": ["Printer status", "", "mdi:printer-3d"],
    "state": ["Print job state", "", "mdi:printer-3d-nozzle"],
    "progress": ["Print job progress", "%", "mdi:progress-clock"],
    "bed_temperature": ["Bed temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "bed_temperature_target": [
        "Bed temperature target",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "bed_type": ["Bed type", "", "mdi:layers"],
    "hotend_1_temperature": ["Hotend 1 temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "hotend_1_temperature_target": [
        "Hotend 1 temperature target",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "hotend_1_id": ["Hotend 1 id", "", "mdi:printer-3d-nozzle-outline"],
    "hotend_2_temperature": ["Hotend 2 temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "hotend_2_temperature_target": [
        "Hotend 2 temperature target",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "hotend_2_id": ["Hotend 2 id", "", "mdi:printer-3d-nozzle-outline"],
    "active_material_1_guid": ["Filament 1 type", "", "mdi:tape-drive"],
    "active_material_2_guid": ["Filament 2 type", "", "mdi:tape-drive"],
    "active_material_1_length_remaining": ["Filament 1 length remaining", "m", "mdi:tape-drive"],
    "active_material_2_length_remaining": ["Filament 2 length remaining", "m", "mdi:tape-drive"],
}

CONF_DECIMAL = "decimal"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_DECIMAL, default=2): cv.positive_int,
        vol.Required(CONF_SENSORS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)

MATERIAL_LIST = [
  {
    "guid": "7cbdb9ca-081a-456f-a6ba-f73e4e9cb856",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Pearl Gold",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "60636bb4-518f-42e7-8237-fe77b194ebe0",
    "brand": "Generic",
    "material": "ABS",
    "color": "Generic",
    "version": 25,
    "density": 1.1
  },
  {
    "guid": "7e6207c4-22ff-441a-b261-ff89f166d6a0",
    "brand": "Generic",
    "material": "Breakaway",
    "color": "Generic",
    "version": 25,
    "density": 1.22
  },
  {
    "guid": "12f41353-1a33-415e-8b4f-a775a6c70cc6",
    "brand": "Generic",
    "material": "CPE",
    "color": "Generic",
    "version": 28,
    "density": 1.27
  },
  {
    "guid": "e2409626-b5a0-4025-b73e-b58070219259",
    "brand": "Generic",
    "material": "CPE+",
    "color": "Generic",
    "version": 27,
    "density": 1.18
  },
  {
    "guid": "28fb4162-db74-49e1-9008-d05f1e8bef5c",
    "brand": "Generic",
    "material": "Nylon",
    "color": "Generic",
    "version": 24,
    "density": 1.14
  },
  {
    "guid": "98c05714-bf4e-4455-ba27-57d74fe331e4",
    "brand": "Generic",
    "material": "PC",
    "color": "Generic",
    "version": 26,
    "density": 1.19
  },
  {
    "guid": "1cbfaeb3-1906-4b26-b2e7-6f777a8c197a",
    "brand": "Generic",
    "material": "PETG",
    "color": "Generic",
    "version": 13,
    "density": 1.27
  },
  {
    "guid": "506c9f0d-e3aa-4bd4-b2d2-23e2425b1aa9",
    "brand": "Generic",
    "material": "PLA",
    "color": "Generic",
    "version": 25,
    "density": 1.24
  },
  {
    "guid": "aa22e9c7-421f-4745-afc2-81851694394a",
    "brand": "Generic",
    "material": "PP",
    "color": "Generic",
    "version": 27,
    "density": 0.89
  },
  {
    "guid": "86a89ceb-4159-47f6-ab97-e9953803d70f",
    "brand": "Generic",
    "material": "PVA",
    "color": "Generic",
    "version": 26,
    "density": 1.23
  },
  {
    "guid": "9d5d2d7c-4e77-441c-85a0-e9eefd4aa68c",
    "brand": "Generic",
    "material": "Tough PLA",
    "color": "Generic",
    "version": 19,
    "density": 1.24
  },
  {
    "guid": "1d52b2be-a3a2-41de-a8b1-3bcdb5618695",
    "brand": "Generic",
    "material": "TPU 95A",
    "color": "Generic",
    "version": 27,
    "density": 1.22
  },
  {
    "guid": "2f9d2279-9b0e-4765-bf9b-d1e1e13f3c49",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Black",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "7c9575a6-c8d6-40ec-b3dd-18d7956bfaae",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Blue",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "3400c0d1-a4e3-47de-a444-7b704f287171",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Green",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "8b75b775-d3f2-4d0f-8fb2-2a3dd53cf673",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Grey",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "0b4ca6ef-eac8-4b23-b3ca-5f21af00e54f",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Orange",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "763c926e-a5f7-4ba0-927d-b4e038ea2735",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Silver Metallic",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "5df7afa6-48bd-4c19-b314-839fe9f08f1f",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Red",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "173a7bae-5e14-470e-817e-08609c61e12b",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Light Grey",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "5253a75a-27dc-4043-910f-753ae11bc417",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "White",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "e873341d-d9b8-45f9-9a6f-5609e1bcff68",
    "brand": "Ultimaker",
    "material": "ABS",
    "color": "Yellow",
    "version": 28,
    "density": 1.1
  },
  {
    "guid": "7e6207c4-22ff-441a-b261-ff89f166d5f9",
    "brand": "Ultimaker",
    "material": "Breakaway",
    "color": "White",
    "version": 29,
    "density": 1.22
  },
  {
    "guid": "a8955dc3-9d7e-404d-8c03-0fd6fee7f22d",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Black",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "4d816290-ce2e-40e0-8dc8-3f702243131e",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Blue",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "10961c00-3caf-48e9-a598-fa805ada1e8d",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Dark Grey",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "7ff6d2c8-d626-48cd-8012-7725fa537cc9",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Green",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "1f3c3be1-2e60-4343-b35d-cb383958d992",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Green Translucent",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "1aca047a-42df-497c-abfb-0e9cb85ead52",
    "brand": "Ultimaker",
    "material": "CPE+",
    "color": "Black",
    "version": 29,
    "density": 1.18
  },
  {
    "guid": "a9c340fe-255f-4914-87f5-ec4fcb0c11ef",
    "brand": "Ultimaker",
    "material": "CPE+",
    "color": "Transparent",
    "version": 29,
    "density": 1.18
  },
  {
    "guid": "6df69b13-2d96-4a69-a297-aedba667e710",
    "brand": "Ultimaker",
    "material": "CPE+",
    "color": "White",
    "version": 29,
    "density": 1.18
  },
  {
    "guid": "00181d6c-7024-479a-8eb7-8a2e38a2619a",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Red",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "bd0d9eb3-a920-4632-84e8-dcd6086746c5",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Transparent",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "881c888e-24fb-4a64-a4ac-d5c95b096cd7",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "White",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "b9176a2a-7a0f-4821-9f29-76d882a88682",
    "brand": "Ultimaker",
    "material": "CPE",
    "color": "Yellow",
    "version": 31,
    "density": 1.27
  },
  {
    "guid": "c64c2dbe-5691-4363-a7d9-66b2dc12837f",
    "brand": "Ultimaker",
    "material": "Nylon",
    "color": "Black",
    "version": 27,
    "density": 1.14
  },
  {
    "guid": "e256615d-a04e-4f53-b311-114b90560af9",
    "brand": "Ultimaker",
    "material": "Nylon",
    "color": "Transparent",
    "version": 27,
    "density": 1.14
  },
  {
    "guid": "e92b1f0b-a069-4969-86b4-30127cfb6f7b",
    "brand": "Ultimaker",
    "material": "PC",
    "color": "Black",
    "version": 29,
    "density": 1.19
  },
  {
    "guid": "8a38a3e9-ecf7-4a7d-a6a9-e7ac35102968",
    "brand": "Ultimaker",
    "material": "PC",
    "color": "Transparent",
    "version": 29,
    "density": 1.19
  },
  {
    "guid": "5e786b05-a620-4a87-92d0-f02becc1ff98",
    "brand": "Ultimaker",
    "material": "PC",
    "color": "White",
    "version": 29,
    "density": 1.19
  },
  {
    "guid": "3ee70a86-77d8-4b87-8005-e4a1bc57d2ce",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Black",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "44a029e6-e31b-4c9e-a12f-9282e29a92ff",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Blue",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "2433b8fb-dcd6-4e36-9cd5-9f4ee551c04c",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Green",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "fe3982c8-58f4-4d86-9ac0-9ff7a3ab9cbc",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Magenta",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "d9549dba-b9df-45b9-80a5-f7140a9a2f34",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Orange",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "d9fc79db-82c3-41b5-8c99-33b3747b8fb3",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Pearl-White",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "9cfe5bf1-bdc5-4beb-871a-52c70777842d",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Red",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "e509f649-9fe6-4b14-ac45-d441438cb4ef",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "White",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "0e01be8c-e425-4fb1-b4a3-b79f255f1db9",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Silver Metallic",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "532e8b3d-5fd4-4149-b936-53ada9bd6b85",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Transparent",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "fe15ed8a-33c3-4f57-a2a7-b4b78a38c3cb",
    "brand": "Ultimaker",
    "material": "PVA",
    "color": "Natural",
    "version": 30,
    "density": 1.23
  },
  {
    "guid": "03f24266-0291-43c2-a6da-5211892a2699",
    "brand": "Ultimaker",
    "material": "Tough PLA",
    "color": "Black",
    "version": 22,
    "density": 1.22
  },
  {
    "guid": "07a4547f-d21f-41a0-8eee-bc92125221b3",
    "brand": "Ultimaker",
    "material": "TPU 95A",
    "color": "Red",
    "version": 30,
    "density": 1.22
  },
  {
    "guid": "c8e4a85e-b256-4468-8516-0aa98c69c7d7",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Green",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "c8394116-30ba-4112-b4d9-8b2394278cb3",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Grey",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "a02a3978-eb33-47ca-b32b-d08b92b58638",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Orange",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "9680dff6-7aa5-400b-982c-40a0de06a718",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Red",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "40a273c6-0e15-4db5-a278-8eb0b4a9e293",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Silver",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "61eb5c6c-0110-49de-9756-13b8c7cc2ff1",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "White",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "d67a3ccb-6b51-4013-bdac-4c59e952aaf4",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Yellow Fluorescent",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "9c1959d0-f597-46ec-9131-34020c7a54fc",
    "brand": "Ultimaker",
    "material": "PLA",
    "color": "Yellow",
    "version": 26,
    "density": 1.24
  },
  {
    "guid": "c7005925-2a41-4280-8cdd-4029e3fe5253",
    "brand": "Ultimaker",
    "material": "PP",
    "color": "Transparent",
    "version": 30,
    "density": 0.89
  },
  {
    "guid": "6d71f4ad-29ab-4b50-8f65-22d99af294dd",
    "brand": "Ultimaker",
    "material": "Tough PLA",
    "color": "Green",
    "version": 22,
    "density": 1.22
  },
  {
    "guid": "2db25566-9a91-4145-84a5-46c90ed22bdf",
    "brand": "Ultimaker",
    "material": "Tough PLA",
    "color": "Red",
    "version": 22,
    "density": 1.24
  },
  {
    "guid": "851427a0-0c9a-4d7c-a9a8-5cc92f84af1f",
    "brand": "Ultimaker",
    "material": "Tough PLA",
    "color": "White",
    "version": 22,
    "density": 1.24
  },
  {
    "guid": "eff40bcf-588d-420d-a3bc-a5ffd8c7f4b3",
    "brand": "Ultimaker",
    "material": "TPU 95A",
    "color": "Black",
    "version": 30,
    "density": 1.22
  },
  {
    "guid": "5f4a826c-7bfe-460f-8650-a9178b180d34",
    "brand": "Ultimaker",
    "material": "TPU 95A",
    "color": "Blue",
    "version": 30,
    "density": 1.22
  },
  {
    "guid": "6a2573e6-c8ee-4c66-8029-3ebb3d5adc5b",
    "brand": "Ultimaker",
    "material": "TPU 95A",
    "color": "White",
    "version": 30,
    "density": 1.22
  },
  {
    "guid": "5f9f3de0-045b-48d9-84ec-19db92be7603",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Black",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "2257ab94-fb27-42e6-865c-05aa6717504b",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Blue",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "e0af2080-29fc-4b18-a5c0-42ca112f507f",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Blue Translucent",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "218379df-4a67-4668-b5f8-2a14c92bce96",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Yellow",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "c8639119-5cae-4f56-9bcf-3bb00e8225fd",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Red Translucent",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "7418eca4-e2c4-45b1-a022-37180861fd39",
    "brand": "Ultimaker",
    "material": "PETG",
    "color": "Transparent",
    "version": 30,
    "density": 1.27
  },
  {
    "guid": "55317359-2538-4b89-855d-e74d3c3d5916",
    "brand": "DSM",
    "material": "Novamid ID 1030 CF",
    "color": "Generic",
    "version": 1,
    "density": 1
  },
  {
    "guid": "efbc209c-14ec-4671-acca-93eef5a207f8",
    "brand": "Owens Corning",
    "material": "XSTRAND GF30-PA6",
    "color": "Generic",
    "version": 2,
    "density": 1.17
  },
  {
    "guid": "6660eb2e-aa40-49ad-ac9b-ada979f3de9b",
    "brand": "Ultimaker",
    "material": "Tough PLA",
    "color": "Gray",
    "version": 12,
    "density": 1.24
  },
  {
    "guid": "4b049931-6ee9-408c-8588-ddd4673467d1",
    "brand": "Ultimaker",
    "material": "Tough PLA",
    "color": "Blue",
    "version": 12,
    "density": 1.24
  },
  {
    "guid": "bfdb0787-032d-4cf5-9975-964132bd641c",
    "brand": "Ultimaker",
    "material": "Tough PLA",
    "color": "Yellow",
    "version": 12,
    "density": 1.24
  }
]


MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
BASE_URL = "http://{0}/api/v1"
MATERIAL_URL = "http://{0}/cluster-api/v1/materials"


async def async_setup_platform(
    hass: HomeAssistantType, config, async_add_entities, discovery_info=None
):
    """Setup the Ultimaker printer sensors"""
    session = async_get_clientsession(hass)
    data = UltimakerStatusData(session, config.get(CONF_HOST))
    await data.async_update()

    entities = []
    if CONF_SENSORS in config:
        for sensor in config[CONF_SENSORS]:
            sensor_type = sensor.lower()
            name = f"{config.get(CONF_NAME)} {SENSOR_TYPES[sensor][0]}"
            unit = SENSOR_TYPES[sensor][1]
            icon = SENSOR_TYPES[sensor][2]

            _LOGGER.debug(
                f"Adding Ultimaker printer sensor: {name}, {sensor_type}, {unit}, {icon}"
            )
            entities.append(
                UltimakerStatusSensor(
                    data, name, sensor_type, unit, icon, config.get(CONF_DECIMAL)
                )
            )

    async_add_entities(entities, True)


class UltimakerStatusData(object):
    """Handle Ultimaker object and limit updates"""

    def __init__(self, session, host):
        if host:
            self._url_printer = BASE_URL.format(host) + "/printer"
            self._url_print_job = BASE_URL.format(host) + "/print_job"
            self._url_system = BASE_URL.format(host) + "/system"
        self._host = host
        self._session = session
        self._data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Download and update data from the Ultimaker Printer"""
        if self._host:
            try:
                printer_data = await self.fetch_data(self._url_printer)
                print_job_data = await self.fetch_data(self._url_print_job)
                system_data = await self.fetch_data(self._url_system)
                self._data = printer_data.copy()
                self._data.update(print_job_data)
                self._data.update(system_data)
            except aiohttp.ClientError:
                self._data = {"status": "not connected"}
            self._data["sampleTime"] = datetime.now()

    async def fetch_data(self, url):
        try:
            with async_timeout.timeout(5):
                response = await self._session.get(url)
        except aiohttp.ClientError as err:
            _LOGGER.warning(f"Printer {self._host} is offline")
            raise err
        except asyncio.TimeoutError:
            _LOGGER.error(
                f" Timeout error occurred while polling ultimaker printer using url {url}"
            )
        except Exception as err:
            _LOGGER.error(
                f"Unknown error occurred while polling Ultimaker printer using {url} -> error: {err}"
            )
            return {}

        try:
            ret = await response.json()
        except Exception as err:
            _LOGGER.error(f"Cannot parse data received from Ultimaker printer {err}")
            return {}
        return ret

    @property
    def latest_data(self):
        return self._data


class UltimakerStatusSensor(Entity):
    """Representation of a Ultimaker status sensor"""

    def __init__(
        self, data: UltimakerStatusData, name, sensor_type, unit, icon, decimal
    ):
        """Initialize the sensor."""
        self._data = data
        self._name = name
        self._type = sensor_type
        self._unit = unit
        self._icon = icon
        self._decimal = decimal

        self._state = None
        self._last_updated = None

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def icon(self) -> Optional[str]:
        return self._icon

    @property
    def state(self) -> StateType:
        if isinstance(self._state, float):
            return round(self._state, self._decimal)
        else:
            return self._state

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._unit

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        attr = {}
        if self._last_updated is not None:
            attr["Last Updated"] = self._last_updated
        return attr
        
    def __translate(self, guid):
        # translate guid to filanment type
        return next(d for d in MATERIAL_LIST if d["guid"] == guid).get("material") + " - " + next(d for d in MATERIAL_LIST if d["guid"] == guid).get("color")

    async def async_update(self):

        await self._data.async_update()
        data = self._data.latest_data

        if data:
            self._last_updated = data.get("sampleTime", None)

            if self._type == "status":
                self._state = data.get("status", "not connected")

            elif self._type == "state":
                self._state = data.get("state", None)
                if self._state:
                    self._state = self._state.replace("_", " ")

            elif self._type == "progress":
                self._state = data.get("progress", 0)
                if self._state:
                    self._state *= 100
                self._state = self._state

            elif "bed" in self._type:
                bed = data.get("bed", None)
                if "temperature" in self._type and bed:
                    temperature = bed.get("temperature", None)
                    if temperature:
                        if "target" in self._type:
                            self._state = temperature.get("target", None)
                        else:
                            self._state = temperature.get("current", None)
                if "type" in self._type and bed:
                    self._state = bed.get("type", None)

            elif "hotend" in self._type:
                head = data.get("heads", [None])[0]
                if head:
                    idx = int(self._type.split("_")[1]) - 1
                    extruder = head["extruders"][idx]
                    hot_end = extruder["hotend"]
                    if "temperature" in self._type and hot_end:
                        temperature = hot_end["temperature"]
                        if "target" in self._type:
                            self._state = temperature.get("target", None)
                        else:
                            self._state = temperature.get("current", None)
                    if "id" in self._type and hot_end:
                        self._state = hot_end["id"]
                        
            elif "active_material" in self._type:
                head = data.get("heads", [None])[0]
                if head:
                    idx = int(self._type.split("_")[2]) - 1
                    extruder = head["extruders"][idx]
                    active_material = extruder["active_material"]
                    if "guid" in self._type and active_material:
                        self._state = self.__translate(active_material["guid"])
                    if "length_remaining" in self._type and active_material:
                        self._state = active_material["length_remaining"] / 1000

            _LOGGER.debug(f"Device: {self._type} State: {self._state}")
