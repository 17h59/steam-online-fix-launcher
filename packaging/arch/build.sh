#!/bin/bash

# Arch Linux Package Build Script for SOFL (CI-friendly)
# Usage: ./build.sh [version] [output_dir]

set -euo pipefail

VERSION=${1:-"0.0.3"}
PACKAGE_NAME="sofl"
OUTPUT_DIR=${2:-"../../dist"}

echo "Building Arch Linux package for $PACKAGE_NAME version $VERSION..."

# Ensure we are on Arch Linux with makepkg available
if ! command -v makepkg &>/dev/null; then
    echo "Error: Arch Linux package can only be built on Arch Linux systems"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$(cd "$PROJECT_DIR" && mkdir -p "$OUTPUT_DIR" && cd "$OUTPUT_DIR" && pwd)"

echo "Project directory: $PROJECT_DIR"
echo "Arch directory: $ARCH_DIR"
echo "Output directory: $OUTPUT_DIR"

cd "$PROJECT_DIR"

# Fix git safe directory issue
git config --global --add safe.directory "$PROJECT_DIR" || true

# Create source tarball from git repository
echo "Creating source tarball..."
git archive --format=tar.gz --prefix="$PACKAGE_NAME-$VERSION/" -o "$OUTPUT_DIR/$PACKAGE_NAME-$VERSION.tar.gz" HEAD

# Prepare working directory for PKGBUILD
BUILD_WORK_DIR="$OUTPUT_DIR/arch-build-$VERSION"
mkdir -p "$BUILD_WORK_DIR"
chmod u+rwx "$BUILD_WORK_DIR"

# Copy PKGBUILD and update version
echo "Preparing PKGBUILD in working directory: $BUILD_WORK_DIR"
cp "$ARCH_DIR/PKGBUILD" "$BUILD_WORK_DIR/PKGBUILD"
sed -i "s/pkgver=.*/pkgver=$VERSION/" "$BUILD_WORK_DIR/PKGBUILD"

# Clean legacy install lines
sed -i "/data\/org.badkiko\\.sofl\\.desktop/d" "$BUILD_WORK_DIR/PKGBUILD" || true
sed -i "/data\/org.badkiko\\.sofl\\.metainfo\\.xml/d" "$BUILD_WORK_DIR/PKGBUILD" || true

# Build the package
echo "Building package with makepkg..."
cd "$BUILD_WORK_DIR"

# Set output directories
export SRCDEST="$OUTPUT_DIR"
export PKGDEST="$OUTPUT_DIR"
export PACKAGER="CI Builder <ci@localhost>"

# Run makepkg as root (safe in CI) and skip PGP checks
makepkg -f --noconfirm --skippgpcheck

echo "Arch Linux package built successfully!"

# Move created packages if needed (fallback)
if ls *.pkg.tar.zst *.tar.gz 1>/dev/null 2>&1; then
    mv *.pkg.tar.zst *.tar.gz "$OUTPUT_DIR/" 2>/dev/null || true
    echo "Packages moved to: $OUTPUT_DIR"
fi

# List created packages
ls -la "$OUTPUT_DIR"/*.pkg.tar.zst "$OUTPUT_DIR"/*.tar.gz 2>/dev/null || echo "No packages found"

echo "Arch Linux package build completed!"
