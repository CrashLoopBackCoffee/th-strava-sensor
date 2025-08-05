# Architecture Documentation

This document provides a detailed technical overview of the Strava Sensor project architecture.

## Overview

Strava Sensor follows a modular, plugin-based architecture that separates concerns between data sources, file processing, device modeling, and output publishing. The design emphasizes extensibility, type safety, and robust error handling.

## Core Components

### 1. Source System (`src/strava_sensor/source/`)

The source system provides an abstraction layer for reading activity data from different platforms.

#### Base Source (`base.py`)
- **Abstract base class** defining the interface for all data sources
- **URI matching** system using schemes and hostnames
- **Activity reading** abstract method for data retrieval
- **Activity finding** optional method for discovering activities by metadata

```python
class BaseSource(metaclass=abc.ABCMeta):
    uri_scheme = None  # URI scheme (e.g., 'file', 'garmin')
    http_hosts = []    # HTTP hostnames this source handles
    
    def matches_uri(self, uri: str) -> bool
    def read_activity(self, uri: str) -> bytearray
    def find_activity(self, date, elapsed_time, distance) -> str | None
```

#### Concrete Sources

**File Source (`file.py`)**
- Handles local filesystem FIT files
- URI scheme: `file://`
- Simple file reading with existence validation

**Garmin Source (`garmin.py`)**
- Integrates with Garmin Connect API
- URI schemes: `garmin://` and Garmin Connect URLs
- Features:
  - OAuth token persistence for authentication
  - Activity download in original FIT format
  - Activity discovery by date, time, and distance matching
  - Tolerance-based matching (±60s time, ±100m distance)

**Strava Source (`strava.py`)**
- Integrates with Strava API for activity discovery
- URI schemes: `strava://` and Strava URLs
- **Delegation pattern**: Uses downstream sources for actual FIT file retrieval
- Activity metadata matching with other sources

### 2. FIT File Processing (`src/strava_sensor/fitfile/`)

Handles parsing and extraction of device information from FIT files.

#### FIT File Parser (`fitfile.py`)
- **Garmin FIT SDK** integration for binary file parsing
- **Error handling** for corrupted and invalid files
- **Message type enumeration** for structured data access
- **Device status extraction** from multiple message types

Key features:
- Validates FIT file headers and structure
- Extracts activity metadata (ID, start time)
- Combines device info from multiple message sources
- Handles incomplete or missing device data gracefully

#### Device Model (`model.py`)
- **Pydantic v2** models for type-safe device representation
- **Battery status enumeration** with standardized states
- **Manufacturer overrides** for better device identification
- **MQTT publishing** with Home Assistant auto-discovery

```python
class DeviceStatus(pydantic.BaseModel):
    device_index: int
    device_type: str
    serial_number: str
    product: str
    battery_voltage: float | None
    battery_status: BatteryStatus
    battery_level: int | None
    manufacturer: str
    # ... additional fields
```

### 3. MQTT Integration (`src/strava_sensor/mqtt/`)

Handles communication with MQTT brokers and Home Assistant integration.

#### MQTT Client (`mqtt.py`)
- **Paho MQTT** client wrapper
- **Connection management** with automatic reconnection
- **Topic publishing** for both data and discovery
- **Home Assistant compatibility** with proper device classes

Features:
- TLS/SSL support for secure connections
- Quality of Service (QoS) configuration
- Connection state tracking
- Error handling and logging

### 4. CLI Interface (`src/strava_sensor/cli.py`)

Command-line interface providing the main entry point for the application.

#### Key Functions
- **Source initialization** with environment-based configuration
- **URI routing** to appropriate source handlers
- **Logging setup** with configurable levels
- **MQTT publishing** coordination
- **Error handling** with user-friendly messages

#### Source Initialization Strategy
1. Always include File source for local files
2. Add Garmin source if credentials are available
3. Add Strava source last with access to all downstream sources
4. This ordering enables Strava→Garmin→File delegation

## Design Patterns

### 1. Strategy Pattern
Sources implement a common interface but use different strategies for data retrieval.

### 2. Chain of Responsibility
Strava source delegates to downstream sources until one succeeds.

### 3. Factory Pattern
Source initialization creates appropriate source instances based on available configuration.

### 4. Adapter Pattern
Each source adapts its specific API to the common BaseSource interface.

## Data Flow

```
1. CLI receives URI
2. Source matching determines handler
3. Activity data retrieved (possibly via delegation)
4. FIT file parsed for device information
5. Device status models created and validated
6. MQTT publishing (optional) with Home Assistant discovery
7. Results logged and displayed
```

## Error Handling Strategy

### Graceful Degradation
- Continue processing other devices if one fails
- Log warnings for missing optional data
- Provide meaningful error messages for user issues

### Typed Exceptions
- `NotAFitFileError`: Invalid file format
- `CorruptedFitFileError`: Damaged file data
- `InvalidActivityFileError`: Wrong activity type

### Validation Layers
1. URI format validation
2. File existence/accessibility checks
3. FIT file structure validation
4. Device data completeness checks
5. MQTT connection validation

## Extension Points

### Adding New Sources
1. Inherit from `BaseSource`
2. Implement required abstract methods
3. Define URI scheme and/or HTTP hosts
4. Add to source initialization in CLI

### Adding New Device Types
1. Update `MODEL_OVERRIDE` dictionary in `model.py`
2. Add device-specific field mappings
3. Extend validation rules if needed

### Adding New Output Formats
1. Create new publisher classes similar to MQTT client
2. Add device status publishing methods
3. Integrate with CLI publishing logic

## Performance Considerations

### Caching
- Garmin OAuth tokens cached to filesystem
- FIT parsing results could be cached for repeated access

### Concurrency
- Current implementation is synchronous
- Could be extended with async/await for concurrent source queries

### Memory Usage
- FIT files loaded entirely into memory
- Streaming parser could be implemented for large files

## Security Considerations

### Credential Management
- Environment variables for sensitive data
- OAuth token encryption at rest
- No hardcoded credentials in source code

### Network Security
- HTTPS for all API communications
- TLS for MQTT connections
- Certificate validation enabled

### Input Validation
- URI parsing with security checks
- File path traversal prevention
- Malicious FIT file protection via SDK

## Testing Strategy

### Unit Tests
- Individual component testing with mocks
- Error condition coverage
- Data validation testing

### Integration Tests
- End-to-end workflow validation
- Real API integration (with test accounts)
- MQTT publishing verification

### Test Fixtures
- Sample FIT files for various device types
- Corrupted file test cases
- API response mocks

## Dependencies

### Core Dependencies
- **garmin-fit-sdk**: Binary FIT file parsing
- **stravalib**: Strava API integration
- **garminconnect**: Garmin Connect API
- **paho-mqtt**: MQTT communication
- **pydantic**: Data validation and serialization
- **requests**: HTTP client for API calls

### Development Dependencies
- **pytest**: Testing framework
- **ruff**: Linting and formatting
- **pyright**: Type checking
- **pre-commit**: Git hook management
- **uv**: Package management

## Future Enhancements

### Planned Features
- Configuration file support
- Scheduled activity processing
- Database storage for historical data
- Web dashboard for device monitoring
- Support for additional file formats (TCX, GPX)

### API Improvements
- REST API for programmatic access
- Webhook support for real-time processing
- GraphQL interface for flexible queries

### Scalability
- Distributed processing for multiple users
- Cloud deployment options
- Container orchestration support