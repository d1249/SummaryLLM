#!/bin/bash
# State rotation script for cleanup and archival
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default paths
STATE_DIR="${STATE_DIR:-/opt/digest/.state}"
OUT_DIR="${OUT_DIR:-/opt/digest/out}"
ARCHIVE_DIR="${ARCHIVE_DIR:-/opt/digest/archive}"

# Retention periods (in days)
DELETE_AFTER_DAYS="${DELETE_AFTER_DAYS:-30}"
ARCHIVE_AFTER_DAYS="${ARCHIVE_AFTER_DAYS:-14}"

echo "Rotating digest state and artifacts..."
echo "State directory: $STATE_DIR"
echo "Output directory: $OUT_DIR"
echo "Archive directory: $ARCHIVE_DIR"
echo "Delete after: $DELETE_AFTER_DAYS days"
echo "Archive after: $ARCHIVE_AFTER_DAYS days"

# Create archive directory if it doesn't exist
mkdir -p "$ARCHIVE_DIR"

# Function to process files by age
process_files() {
    local dir="$1"
    local pattern="$2"
    local action="$3"
    local days="$4"
    
    if [ -d "$dir" ]; then
        echo "Processing $dir with pattern $pattern..."
        find "$dir" -name "$pattern" -type f -mtime +$days -exec $action {} \;
    else
        echo "Directory $dir does not exist, skipping..."
    fi
}

# Archive old artifacts
echo "Archiving old artifacts..."
process_files "$OUT_DIR" "digest-*.json" "mv {} $ARCHIVE_DIR/" "$ARCHIVE_AFTER_DAYS"
process_files "$OUT_DIR" "digest-*.md" "mv {} $ARCHIVE_DIR/" "$ARCHIVE_AFTER_DAYS"

# Delete very old artifacts
echo "Deleting very old artifacts..."
process_files "$ARCHIVE_DIR" "digest-*.json" "rm -f" "$DELETE_AFTER_DAYS"
process_files "$ARCHIVE_DIR" "digest-*.md" "rm -f" "$DELETE_AFTER_DAYS"

# Clean up old state files
echo "Cleaning up old state files..."
process_files "$STATE_DIR" "*.state" "rm -f" "$DELETE_AFTER_DAYS"

# Clean up empty directories
echo "Cleaning up empty directories..."
find "$OUT_DIR" -type d -empty -delete 2>/dev/null || true
find "$STATE_DIR" -type d -empty -delete 2>/dev/null || true

echo "State rotation completed successfully!"
echo "Archived files: $(find "$ARCHIVE_DIR" -type f | wc -l)"
echo "Remaining output files: $(find "$OUT_DIR" -type f | wc -l)"
