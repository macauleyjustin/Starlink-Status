#!/bin/bash
set -e

echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential cmake qt6-base-dev qt6-base-dev-tools protobuf-compiler libprotobuf-dev libgrpc++-dev libgrpc-dev

echo "Dependencies installed."
