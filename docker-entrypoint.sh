#!/bin/bash
# Docker entrypoint script for Auto-Snap MCP Server
# Validates dependencies and starts the MCP server with proper configuration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" >&2
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
}

# Function to check system dependencies
check_dependencies() {
    log "Checking system dependencies..."
    
    local missing_deps=()
    
    # Check for required system tools
    if ! command -v wmctrl >/dev/null 2>&1; then
        missing_deps+=("wmctrl")
    fi
    
    if ! command -v xdotool >/dev/null 2>&1; then
        missing_deps+=("xdotool")
    fi
    
    if ! command -v tesseract >/dev/null 2>&1; then
        missing_deps+=("tesseract-ocr")
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        error "Missing system dependencies: ${missing_deps[*]}"
        error "These should have been installed during Docker build"
        return 1
    fi
    
    log "All system dependencies are available"
    return 0
}

# Function to validate Python environment
check_python_deps() {
    log "Checking Python dependencies..."
    
    python -c "
import sys
try:
    import mcp
    import PIL
    import pytesseract
    import img2pdf
    import pyscreenshot
    print('All Python dependencies are available', file=sys.stderr)
except ImportError as e:
    print(f'Missing Python dependency: {e}', file=sys.stderr)
    sys.exit(1)
"
}

# Function to setup directories
setup_directories() {
    log "Setting up directories..."
    
    # Ensure output and temp directories exist
    mkdir -p "${AUTO_SNAP_OUTPUT_DIR:-/app/captures}"
    mkdir -p "${AUTO_SNAP_TEMP_DIR:-/app/temp}"
    
    # Set permissions if running as root (shouldn't happen in MCP Hub)
    if [ "$(id -u)" -eq 0 ]; then
        warn "Running as root - this should not happen in Docker MCP Hub"
        chown -R mcp-user:mcp-user "${AUTO_SNAP_OUTPUT_DIR:-/app/captures}" "${AUTO_SNAP_TEMP_DIR:-/app/temp}" 2>/dev/null || true
    fi
}

# Function to check X11 environment
check_x11() {
    log "Checking X11 environment..."
    
    if [ -z "${DISPLAY:-}" ]; then
        warn "DISPLAY environment variable not set"
        warn "Screenshot functionality may not work without X11 forwarding"
        warn "See documentation for X11 setup with Docker"
    else
        log "DISPLAY set to: ${DISPLAY}"
        
        # Test X11 connection if possible
        if command -v xset >/dev/null 2>&1; then
            if xset q >/dev/null 2>&1; then
                log "X11 connection successful"
            else
                warn "X11 connection failed - check X11 forwarding setup"
            fi
        fi
    fi
}

# Function to validate configuration
validate_config() {
    log "Validating configuration..."
    
    # Check if output directory is writable
    if [ ! -w "${AUTO_SNAP_OUTPUT_DIR:-/app/captures}" ]; then
        error "Output directory ${AUTO_SNAP_OUTPUT_DIR:-/app/captures} is not writable"
        return 1
    fi
    
    # Check if temp directory is writable
    if [ ! -w "${AUTO_SNAP_TEMP_DIR:-/app/temp}" ]; then
        error "Temp directory ${AUTO_SNAP_TEMP_DIR:-/app/temp} is not writable"
        return 1
    fi
    
    log "Configuration validation complete"
}

# Function to print environment info
print_environment_info() {
    log "Auto-Snap MCP Server Environment Information:"
    echo "  Python version: $(python --version)" >&2
    echo "  Working directory: $(pwd)" >&2
    echo "  User: $(whoami)" >&2
    echo "  Output directory: ${AUTO_SNAP_OUTPUT_DIR:-/app/captures}" >&2
    echo "  Temp directory: ${AUTO_SNAP_TEMP_DIR:-/app/temp}" >&2
    echo "  DISPLAY: ${DISPLAY:-'not set'}" >&2
    echo "  Legacy mode: ${AUTO_SNAP_LEGACY_MODE:-true}" >&2
    echo "  Auto cleanup: ${AUTO_SNAP_AUTO_CLEANUP_TEMP:-true}" >&2
}

# Main entrypoint logic
main() {
    log "Starting Auto-Snap MCP Server container..."
    
    # Print environment information
    print_environment_info
    
    # Perform dependency checks
    if ! check_dependencies; then
        error "Dependency check failed"
        exit 1
    fi
    
    if ! check_python_deps; then
        error "Python dependency check failed"
        exit 1
    fi
    
    # Setup directories
    setup_directories
    
    # Check X11 (non-fatal)
    check_x11
    
    # Validate configuration
    if ! validate_config; then
        error "Configuration validation failed"
        exit 1
    fi
    
    log "Pre-flight checks complete - starting MCP server"
    
    # Execute the provided command
    exec "$@"
}

# Handle signals gracefully
trap 'log "Received signal, shutting down..."; exit 0' SIGTERM SIGINT

# Run main function with all arguments
main "$@"