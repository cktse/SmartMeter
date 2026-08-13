import ujson
import utime

#
# ECHONET Appendix Revision F
#
class BRouteMQTTClient:

    SENSORS = [
        {
            "id": "power",
            "name": "Instantaneous Power",
            "unit": "W",
            "device_class": "power",
            "state_class": "measurement"
        },
        {
            "id": "current_r",
            "name": "Instantaneous Current (R phase)",
            "unit": "A",
            "device_class": "current",
            "state_class": "measurement"
        },
        {
            "id": "current_t",
            "name": "Instantaneous Current (T phase)",
            "unit": "A",
            "device_class": "current",
            "state_class": "measurement"
        },
        {
            "id": "cumulative_energy",
            "name": "Cumulative Energy",
            "unit": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing"
        },
        {
            "id": "cumulative_energy_r",
            "name": "Cumulative Energy (Reverse)",
            "unit": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing"
        },
        {
            "id": "monthly_energy",
            "name": "Monthly Energy",
            "unit": "kWh",
            "device_class": "energy",
            "state_class": "total"
        },
        {
            "id": "monthly_charge",
            "name": "Monthly Charge",
            "device_class": "monetary",
            "unit": "JPY",
            "state_class": "total"
        },
    ]

    # TODO: defined by ECHONET consortium; include only common ones to save memory
    MANUFACTURERS = {
        "000016": "Toshiba",
        "00004E": "Fujitsu",
        "000041": "ENEGATE",
    }

    def __init__(
            self,
            mqtt,
            manufacturer_code,
            production_number,
            version='F',
            location='Garden/perimeter',
            discovery_prefix="homeassistant"):

        self.mqtt = mqtt
        self.discovery_prefix = discovery_prefix
        self.device_id = f'smartmeter_{manufacturer_code}_{production_number}'  # must be immutable
        self.production_number = production_number

        if manufacturer_code in self.MANUFACTURERS:
            self.manufacturer = self.MANUFACTURERS[manufacturer_code]
            self.device_name = f'{self.manufacturer} Smart Meter ({self.production_number})'
        else:
            self.manufacturer = manufacturer_code
            self.device_name = f'Smart Meter ({self.manufacturer} {self.production_number})'

        self.device = {
            "identifiers": [self.device_id],
            "name": self.device_name,
            "manufacturer": self.manufacturer,
            "serial_number": self.production_number
        }

        self.sensors = self.SENSORS

    def _config_topic(self, sensor_id):

        return "%s/sensor/%s/%s/config" % (
            self.discovery_prefix,
            self.device_id,
            sensor_id
        )

    def _state_topic(self, sensor_id):

        return "echonet/%s/%s/state" % (
            self.device_id,
            sensor_id
        )

    def publish_discovery(self):

        # Clear any stale retained configs (publish empty payload)
        for sensor in self.sensors:
            self.mqtt.publish(
                self._config_topic(sensor["id"]),
                b"",
                retain=True
            )
        utime.sleep(1)

        # Publish fresh discovery for all entities
        for sensor in self.sensors:

            payload = {
                "name": sensor["name"],
                "unique_id": self.device_id + "_" + sensor["id"],
                "state_topic": self._state_topic(sensor["id"]),
                "unit_of_measurement": sensor["unit"],
                "state_class": sensor["state_class"],
                "device": self.device,
                "device_class": sensor["device_class"]
            }

            print('publish_discovery:', ujson.dumps(payload))  # TODO: use logging
            self.mqtt.publish(
                self._config_topic(sensor["id"]),
                ujson.dumps(payload),
                retain=True
            )

            print("Discovery:", sensor["name"])
            utime.sleep(0.2)

    def publish(self, sensor_id, value):

        print('publish:', sensor_id, value)
        self.mqtt.publish(
            self._state_topic(sensor_id),
            str(value),
            retain=True
        )

    def publish_many(self, values):
        """
        values = {
            "power":1234,
            "voltage":101.7
        }
        """

        for k in values:
            self.publish(
                k,
                values[k]
            )


#
# Testing
#
if __name__ == "__main__":

    from umqtt.simple import MQTTClient
    from machine import unique_id
    from ubinascii import hexlify

    client_id = "bp35a1_" + hexlify(unique_id()).decode()

    mqtt = MQTTClient(
        client_id=client_id,
        server="homeassistant.local",
        port="1883",
        user="ckmqtt",
        password="wIdhym-5timqu-vadquk"
    )

    mqtt.connect()

    print(mqtt.client_id, mqtt.server, mqtt.port, mqtt.user)

    ha = BRouteMQTTClient(
        mqtt=mqtt,
        manufacturer_code="000016",
        production_number="F24G366505"
    )

    ha.publish_discovery()

    ha.publish_many({
        "power":1450,
        "current_r":6,
        "current_t":3,
        "monthly_energy":284,
        "monthly_charge":8610

    })
