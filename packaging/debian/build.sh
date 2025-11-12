#!/bin/bash

# Debian Package Build Script for SOFL
# Usage: ./build.sh [version]

set -e

VERSION=${1:-"0.0.3"}
PACKAGE_NAME="sofl"
BUILD_DIR="deb-build"
DEBIAN_DIR="packaging/debian"
# OUTPUT_DIR is normalized to absolute path later; default is project dist directory
OUTPUT_DIR=${2:-"dist"}

echo "Building Debian package for $PACKAGE_NAME version $VERSION..."

# Optionally skip dependency installation (useful for CI where deps are pre-installed)
if [ "${SKIP_DEP_INSTALL:-0}" != "1" ] && [ "${CI:-}" != "true" ]; then
    echo "Installing required dependencies..."
    sudo apt update

    # Check and install required tools
    REQUIRED_TOOLS="dpkg-deb meson ninja"
    for tool in $REQUIRED_TOOLS; do
        if ! command -v "$tool" &> /dev/null; then
            echo "Installing $tool..."
            pkg="$tool"
            [ "$tool" = "ninja" ] && pkg="ninja-build"
            sudo apt install -y "$pkg"
        fi
    done

    # Install build dependencies
    BUILD_DEPS="python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests python3-pillow python3-cairo python3-psutil python3-xdg libgtk-4-dev libadwaita-1-dev"
    echo "Installing build dependencies..."
    sudo apt install -y $BUILD_DEPS
else
    echo "Skipping dependency installation (CI environment or SKIP_DEP_INSTALL=1)."
fi

# Get project root directory (parent of packaging directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Normalize OUTPUT_DIR to absolute path
if [[ "$OUTPUT_DIR" != /* ]]; then
    OUTPUT_DIR="$PROJECT_ROOT/$OUTPUT_DIR"
fi
OUTPUT_DIR="$(mkdir -p "$OUTPUT_DIR" && cd "$OUTPUT_DIR" && pwd)"

DESTDIR_PATH="$PROJECT_ROOT/$BUILD_DIR"

rm -rf "${DESTDIR_PATH:?}"
rm -f "${OUTPUT_DIR:?}"/*.deb

# Build the application using meson
echo "Building application with Meson..."
cd "$PROJECT_ROOT"

rm -rf build-dir
meson setup build-dir --prefix=/usr --buildtype=release -Dprofile=release -Dtiff_compression=webp
meson compile -C build-dir
meson install --destdir="$DESTDIR_PATH" -C build-dir

# Ensure desktop file exists (fallback for environments where i18n merge fails)
DESKTOP_TARGET="$DESTDIR_PATH/usr/share/applications/org.badkiko.sofl.desktop"
if [ ! -f "$DESKTOP_TARGET" ]; then
    echo "Desktop entry missing after install; generating fallback copy..."
    DESKTOP_SOURCE="$PROJECT_ROOT/data/org.badkiko.sofl.desktop.in"
    install -Dm644 "$DESKTOP_SOURCE" "$DESKTOP_TARGET"
    sed -i "s/@APP_ID@/org.badkiko.sofl/g" "$DESKTOP_TARGET"
fi

# Copy debian control files
mkdir -p "$DESTDIR_PATH/DEBIAN"
cp "$DEBIAN_DIR/DEBIAN/control" "$DESTDIR_PATH/DEBIAN/"

# Update version in control file
sed -i "s/Version: .*/Version: $VERSION/" "$DESTDIR_PATH/DEBIAN/control"

# Create postinst script for desktop database update
cat > "$DESTDIR_PATH/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

if [ "$1" = "configure" ]; then
    # Update desktop database
    update-desktop-database /usr/share/applications 2>/dev/null || true

    # Update icon cache
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true

    # Compile glib schemas
    glib-compile-schemas /usr/share/glib-2.0/schemas 2>/dev/null || true
fi

exit 0
EOF

chmod 755 "$DESTDIR_PATH/DEBIAN/postinst"

# Create prerm script for cleanup
cat > "$DESTDIR_PATH/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e

if [ "$1" = "remove" ] || [ "$1" = "upgrade" ]; then
    # Update desktop database
    update-desktop-database /usr/share/applications 2>/dev/null || true

    # Update icon cache
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

exit 0
EOF

chmod 755 "$DESTDIR_PATH/DEBIAN/prerm"

# Build the package
echo "Building Debian package..."
if command -v fakeroot &> /dev/null; then
    fakeroot dpkg-deb --build "$DESTDIR_PATH" "${PACKAGE_NAME}_${VERSION}_all.deb"
else
    echo "Warning: fakeroot not found, building package without owner normalization."
    dpkg-deb --build "$DESTDIR_PATH" "${PACKAGE_NAME}_${VERSION}_all.deb"
fi

echo "Debian package created: $(pwd)/${PACKAGE_NAME}_${VERSION}_all.deb"

# Move package to absolute OUTPUT_DIR (already absolute)
mv "${PACKAGE_NAME}_${VERSION}_all.deb" "$OUTPUT_DIR/"
echo "Package moved to: $OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}_all.deb"

# Optional: Check package with lintian
if command -v lintian &> /dev/null; then
    PACKAGE_PATH="${OUTPUT_DIR}/${PACKAGE_NAME}_${VERSION}_all.deb"
    echo "Checking package with lintian..."
    lintian "$PACKAGE_PATH" || true
fi

echo "Build completed successfully!"
