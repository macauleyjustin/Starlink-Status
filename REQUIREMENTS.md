Starlink Status Tray App
Overview
This Python application provides a system tray icon for monitoring and managing Starlink internet connections on Linux (tested on Ubuntu). It displays real-time status, including connection state, speeds, signal strength (as cellular bars), satellite info, and more. Key features include auto-reconnection to known Starlink dishes, dish controls, and logging.
The icon shows dynamic signal bars (green for connected, gray with red X for disconnected). Hover for a tooltip with details; right-click for a menu.
Screenshots

Tray Icon (Connected): Failed to load imageView link (Green bars)
Tray Icon (Disconnected): Failed to load imageView link (Gray bars with red X)
Tooltip Example: Detailed stats on hover.
Menu: Options like "Details", "Stow Dish", etc.

Features

Real-Time Monitoring:

Connection status (Connected/Disconnected).
Download/Upload speeds (Mbps), latency (ms), uptime (hours).
Signal strength (SNR) visualized as 0-4 bars.
Alerts (e.g., obstructed, motors stuck, thermal throttle) with popup notifications for new ones.


Satellite Tracking:

Approximate current satellite (highest elevation >25° using orbital math).
Number of visible satellites (above horizon).
Time to next handover (based on fixed intervals: 12, 27, 42, 57 seconds).


Data Usage:

Recent download/upload totals (GB) from history.


Connectivity:

Auto-connects to previously connected Starlink dishes (remembers BSSID and password via SQLite DB).
Manual "Connect to Starlink" for nearest dish (strongest signal).
"Disconnect WiFi" option.
Detects Ethernet vs. WiFi and updates tooltip.


Dish Controls (via gRPC):

Stow/Unstow/Reboot the dish.


Utilities:

Integrated speed test (via speedtest-cli).
Status logging to starlink_log.txt.
DB: starlink_connections.db for saved connections.


Icon: Simple cellular bars for familiarity.

Prerequisites

Python 3.7+.
Access to Starlink dish (WiFi or Ethernet at 192.168.100.1:9200).
NetworkManager (for WiFi controls on Linux).
System tray support (e.g., via GNOME/Plasma extensions).

Installation

Install Dependencies:
See requirements.md for the full list. Install via pip:
text
