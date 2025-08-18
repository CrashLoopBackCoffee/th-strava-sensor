#!/bin/bash

# Script to determine semantic version bump type based on git cliff changelog groups
# Outputs: major, minor, or patch to stdout
# Logs debug information to stderr

set -euo pipefail

# Function to log to stderr
log() {
    echo "$@" >&2
}

# Main logic
main() {
    log "Running git cliff to generate unreleased changelog..."

    # Get the unreleased changelog
    local changelog
    if ! changelog=$(git cliff --unreleased --strip all 2>/dev/null); then
        log "Error: Failed to run git cliff"
        exit 1
    fi

    # Check if there are any changes
    if [[ -z "$changelog" || "$changelog" =~ ^[[:space:]]*$ ]]; then
        log "No unreleased changes found"
        echo "patch"  # Default to patch if no changes
        exit 0
    fi

    log "Parsing changelog headers..."
    log "Changelog content:"
    log "$changelog"

    # Extract level 3 headers (### ...)
    local headers
    headers=$(echo "$changelog" | grep '^### ' || true)

    if [[ -z "$headers" ]]; then
        log "No level 3 headers found, defaulting to patch"
        echo "patch"
        exit 0
    fi

    log "Found headers:"
    log "$headers"

    # Determine bump type based on header content
    # Priority: Breaking > Enhancement > Everything else (patch)
    # Match on text content without relying on emojis for robustness

    if echo "$headers" | grep -q "Breaking Changes"; then
        log "Found breaking changes - bumping major version"
        echo "major"
    elif echo "$headers" | grep -q "Enhancements"; then
        log "Found enhancements - bumping minor version"
        echo "minor"
    else
        log "Found other changes (security, bug fixes, docs, etc.) - bumping patch version"
        echo "patch"
    fi
}

# Execute main function
main "$@"
