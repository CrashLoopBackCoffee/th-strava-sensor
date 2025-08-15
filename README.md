# Strava Sensor

A Python tool that extracts device battery information from sports activity FIT files and publishes them as Home Assistant sensors via MQTT. Monitor the battery status of your cycling computers, power meters, heart rate monitors, and other fitness devices through Home Assistant.

## Features

- **Multi-source support**: Read FIT files from local filesystem, Garmin Connect, or find activities via Strava API
- **Device battery monitoring**: Extract battery voltage, status, and level from multiple devices in a single activity
- **Home Assistant integration**: Auto-discovery MQTT sensors with proper device classes
- **Robust parsing**: Handle corrupted files and various FIT file formats gracefully
- **Modern Python**: Built with Python 3.13, Pydantic v2, and comprehensive type hints

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/CrashLoopBackCoffee/th-strava-sensor.git
cd th-strava-sensor

# Install dependencies using uv
pip install uv
uv sync
```

### Basic Usage

```bash
# Parse a local FIT file
uv run parse-activity file:///path/to/activity.fit

# Download and parse from Garmin Connect
uv run parse-activity garmin://123456789

# Find activity via Strava and download from Garmin
uv run parse-activity https://www.strava.com/activities/123456789

# Publish to MQTT and Home Assistant
uv run parse-activity --publish file:///path/to/activity.fit
```

## Configuration

### Environment Setup

The project uses direnv for automatic environment configuration. Set up your local environment:

1. **Copy the environment template:**
   ```bash
   cp .env.local.example .env.local
   ```

2. **Configure credentials** in `.env.local` using one of these approaches:

   **Option A: 1Password CLI Integration (Recommended)**
   - Uncomment and configure the 1Password section
   - Update vault/item references to match your 1Password setup
   - Requires `op` CLI tool and appropriate vault access

   **Option B: Direct Environment Variables**
   - Uncomment and fill in the direct credential section
   - Less secure but simpler for development

3. **Configure MQTT broker URL** to match your setup

The `.env.local` file is excluded from git for security. The direnv configuration will automatically source this file when entering the project directory.

### Environment Variables

```bash
# Required for Garmin Connect integration
export GARMIN_USERNAME="your_username"
export GARMIN_PASSWORD="your_password"

# Required for Strava integration
export STRAVA_REFRESH_TOKEN="your_refresh_token"

# Required for MQTT publishing
export MQTT_BROKER_URL="mqtt://your-broker:1883"
export MQTT_USERNAME="your_username"
export MQTT_PASSWORD="your_password"
```

### Strava API Setup

To use Strava integration, you need to set up API access:

1. Create a Strava application at https://www.strava.com/settings/api
2. Get your refresh token following this guide: https://medium.com/@lejczak.learn/get-your-strava-activity-data-using-python-2023-%EF%B8%8F-b03b176965d0
3. Set the `STRAVA_REFRESH_TOKEN` environment variable

## How It Works

The tool uses a modular architecture with pluggable sources:

1. **Source Selection**: Automatically determines the appropriate source based on URI scheme
2. **Activity Retrieval**: Downloads or reads the FIT file data
3. **FIT Parsing**: Extracts device information and battery status using the Garmin FIT SDK
4. **Data Processing**: Normalizes device information with manufacturer-specific overrides
5. **MQTT Publishing**: Publishes device status and Home Assistant auto-discovery configuration

### Supported Sources

- **File Source** (`file://`): Local FIT files
- **Garmin Source** (`garmin://` or Garmin Connect URLs): Downloads from Garmin Connect
- **Strava Source** (Strava URLs): Uses Strava API to find activities, then downloads from other sources

### Device Information Extracted

- Battery voltage, status (new/good/ok/low/critical), and level percentage
- Device type, manufacturer, serial number, product name
- Software and hardware versions
- Custom device name mappings for better identification

## Home Assistant Integration

When using `--publish`, the tool creates Home Assistant sensors via MQTT auto-discovery:

- **Battery Level**: Percentage sensors with battery device class
- **Battery Status**: Enum sensors showing battery condition
- **Battery Voltage**: Voltage sensors for technical monitoring

Each device appears as a separate entity in Home Assistant with proper naming and device information.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical documentation.

## License

This project is open source. See the repository for license details.
