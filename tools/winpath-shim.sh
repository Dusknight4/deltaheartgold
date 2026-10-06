#!/bin/sh
# Discard a leading -w flag (winepath compat), then print the last argument unchanged.
shift_if_w() { [ "$1" = "-w" ] && shift; echo "$1"; }
shift_if_w "$@"