#!/bin/sh
# Build Gary on the Raspberry Pi itself, under QNX.
#   sh qnx/build_qnx.sh
#
# Needs the packages that QNX's AI workshop installs. If this fails with a
# missing header or library, run the workshop's installer once:
#   cd ~/QNX-AI-workshop && sudo ./configure.sh
set -e
cd "$(dirname "$0")"

WORKSHOP_DIR="${WORKSHOP_DIR:-$HOME/QNX-AI-workshop}"
if [ ! -f "$WORKSHOP_DIR/rpi_cam.cpp" ]; then
  echo "Cloning QNX-AI-workshop into $WORKSHOP_DIR"
  git clone --depth 1 https://github.com/qnx/QNX-AI-workshop "$WORKSHOP_DIR"
fi

cmake -S . -B build -DWORKSHOP_DIR="$WORKSHOP_DIR"
cmake --build build

echo
echo "Built qnx/build/gary. Run it from the project folder:"
echo "  cd $(cd .. && pwd) && ./qnx/build/gary"
