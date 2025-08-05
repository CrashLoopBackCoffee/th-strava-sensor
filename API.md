# API Documentation

This document provides reference documentation for the Strava Sensor public APIs.

## Command Line Interface

### Basic Usage

```bash
uv run parse-activity [OPTIONS] SOURCE_URI
```

### Options

- `--publish`: Enable MQTT publishing to Home Assistant
- `--help`: Show help message and exit

### Supported URI Schemes

#### Local Files
```bash
# Absolute path
parse-activity file:///path/to/activity.fit

# Relative path
parse-activity file://./activity.fit
```

#### Garmin Connect
```bash
# Activity ID
parse-activity garmin://123456789

# Full URL
parse-activity https://connect.garmin.com/modern/activity/123456789
```

#### Strava
```bash
# Activity ID
parse-activity strava://123456789

# Full URL
parse-activity https://www.strava.com/activities/123456789
```

## Environment Configuration

### Required Variables

#### Garmin Connect Integration
```bash
export GARMIN_USERNAME="your_garmin_username"
export GARMIN_PASSWORD="your_garmin_password"

# Optional: Token storage location (default: ~/.garminconnect)
export GARMINTOKENS="/path/to/token/storage"
```

#### Strava Integration
```bash
export STRAVA_REFRESH_TOKEN="your_strava_refresh_token"
```

#### MQTT Publishing
```bash
export MQTT_BROKER_URL="mqtt://broker-hostname:1883"
export MQTT_USERNAME="mqtt_username"
export MQTT_PASSWORD="mqtt_password"

# For TLS/SSL connections
export MQTT_BROKER_URL="mqtts://broker-hostname:8883"
```

## Python API

### Source Classes

#### BaseSource

Abstract base class for all data sources.

```python
from strava_sensor.source.base import BaseSource

class BaseSource(metaclass=abc.ABCMeta):
    uri_scheme: str | None = None
    http_hosts: list[str] = []

    def matches_uri(self, uri: str) -> bool
    def read_activity(self, uri: str) -> bytearray
    def find_activity(self, date: datetime.date, elapsed_time_in_s: int, distance_in_m: int) -> str | None
```

#### FileSource

```python
from strava_sensor.source.file import FileSource

source = FileSource()
data = source.read_activity("file:///path/to/activity.fit")
```

#### GarminSource

```python
from strava_sensor.source.garmin import GarminSource

source = GarminSource("username", "password")
data = source.read_activity("garmin://123456789")

# Find activity by metadata
uri = source.find_activity(
    date=datetime.date(2024, 1, 15),
    elapsed_time_in_s=3600,
    distance_in_m=50000
)
```

#### StravaSource

```python
from strava_sensor.source.strava import StravaSource
import stravalib

client = stravalib.Client(refresh_token="your_token")
downstream_sources = [FileSource(), GarminSource("user", "pass")]
source = StravaSource(client, downstream_sources)

data = source.read_activity("strava://123456789")
```

### FIT File Processing

#### FitFile

```python
from strava_sensor.fitfile.fitfile import FitFile, NotAFitFileError, CorruptedFitFileError

try:
    fitfile = FitFile(activity_data)

    # Basic activity info
    activity_id = fitfile.activity_id
    start_time = fitfile.start_time

    # Device information
    devices = fitfile.get_devices_status()
    for device in devices:
        print(f"Device: {device.product}")
        print(f"Battery: {device.battery_level}%")

except NotAFitFileError:
    print("File is not a valid FIT file")
except CorruptedFitFileError:
    print("FIT file is corrupted")
```

#### DeviceStatus Model

```python
from strava_sensor.fitfile.model import DeviceStatus, BatteryStatus

device = DeviceStatus(
    device_index=1,
    device_type="bike_power",
    serial_number="123456",
    product="Favero Assioma",
    battery_voltage=3.2,
    battery_status=BatteryStatus.GOOD,
    battery_level=85,
    manufacturer="favero_electronics",
    source_type="ant_plus"
)

# Publish to MQTT
device.publish_on_mqtt(mqtt_client)
```

### MQTT Integration

#### MQTTClient

```python
from strava_sensor.mqtt.mqtt import MQTTClient
import time

client = MQTTClient()
client.connect("mqtt://broker:1883", "username", "password")

# Wait for connection
while not client.connected:
    time.sleep(0.1)

# Publish data
client.publish("topic/path", "message payload")

# Cleanup
client.disconnect()
```

## Data Models

### DeviceStatus Fields

| Field | Type | Description |
|-------|------|-------------|
| `device_index` | `int` | Device index in activity |
| `device_type` | `str` | Type of device (e.g., "bike_power") |
| `serial_number` | `str` | Device serial number |
| `product` | `str` | Product name |
| `battery_voltage` | `float \| None` | Battery voltage in volts |
| `battery_status` | `BatteryStatus` | Battery condition enum |
| `battery_level` | `int \| None` | Battery percentage (0-100) |
| `manufacturer` | `str` | Manufacturer name |
| `source_type` | `str` | Connection type (e.g., "ant_plus") |
| `software_version` | `str \| None` | Device software version |
| `hardware_version` | `str \| None` | Device hardware version |

### BatteryStatus Enum

```python
class BatteryStatus(enum.StrEnum):
    NEW = 'new'
    GOOD = 'good'
    OK = 'ok'
    LOW = 'low'
    CRITICAL = 'critical'
    CHARGING = 'charging'
    UNKNOWN = 'unknown'
```

## MQTT Topics

### Device Status
```
strava/{serial_number}/status
```

Payload: JSON representation of DeviceStatus model

### Home Assistant Discovery
```
homeassistant/device/strava-{serial_number}/config
```

Payload: Home Assistant device discovery configuration

## Error Handling

### Exception Hierarchy

```python
# Base exceptions
ValueError
├── NotAFitFileError        # Invalid file format
├── CorruptedFitFileError   # Damaged file data
└── InvalidActivityFileError # Wrong activity type

# Usage
try:
    fitfile = FitFile(data)
except (NotAFitFileError, CorruptedFitFileError) as e:
    logger.error("Failed to parse FIT file: %s", e)
```

### Graceful Degradation

The system continues processing when possible:
- Missing battery data logged as warnings
- Corrupted devices skipped with error messages
- Network timeouts retried with exponential backoff

## Performance Considerations

### Memory Usage
- FIT files loaded entirely into memory
- Large activities (>10MB) may require streaming
- Device objects are lightweight

### API Rate Limits
- **Garmin Connect**: ~1000 requests/hour
- **Strava API**: 15 minutes, 100 daily
- **MQTT**: No inherent limits (broker dependent)

### Caching
- Garmin OAuth tokens cached to filesystem
- No automatic FIT file caching (implement if needed)

## Security Notes

### Credential Storage
- Environment variables for runtime secrets
- OAuth tokens encrypted at rest
- No credentials in source code or logs

### Network Security
- HTTPS for all API communications
- TLS support for MQTT connections
- Certificate validation enabled by default

## Integration Examples

### Home Assistant Automation

```yaml
# automation.yaml
automation:
  - alias: "Low Battery Alert"
    trigger:
      platform: state
      entity_id: sensor.strava_123456_battery_status
      to: "low"
    action:
      service: notify.mobile_app
      data:
        message: "Device {{ trigger.entity_id }} has low battery"
```

### Scheduled Processing

```bash
# crontab entry for daily processing
0 8 * * * cd /path/to/strava-sensor && uv run parse-activity --publish $(find ~/.garmin -name "*.fit" -mtime -1)
```

### Docker Integration

```dockerfile
FROM python:3.13-slim

RUN pip install uv
COPY . /app
WORKDIR /app
RUN uv sync

CMD ["uv", "run", "parse-activity", "--publish", "$ACTIVITY_URI"]
```

## Troubleshooting

### Common Issues

**Authentication Errors**
```bash
# Check environment variables
env | grep -E "(GARMIN|STRAVA|MQTT)"

# Test Garmin connection
uv run python -c "from garminconnect import Garmin; g = Garmin('user', 'pass'); g.login()"
```

**FIT File Errors**
```bash
# Validate FIT file integrity
uv run parse-activity file:///path/to/activity.fit

# Check file permissions
ls -la /path/to/activity.fit
```

**MQTT Connection Issues**
```bash
# Test MQTT connectivity
mosquitto_pub -h broker -u username -P password -t test -m "hello"

# Check network connectivity
telnet broker-hostname 1883
```

### Debug Logging

```python
import logging
import daiquiri

# Enable debug logging
daiquiri.setup(level=logging.DEBUG)

# Run with debug output
uv run parse-activity --debug file:///path/to/activity.fit
```

This API documentation provides the essential reference information for using Strava Sensor programmatically and via the command line interface.
