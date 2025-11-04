# Starlink Status Tray App
# This Python script creates a system tray icon that monitors Starlink connection status.
# It displays a cellular-like signal bars icon in the tray, with bars indicating signal strength (based on SNR).
# The title is "Starlink Connected" or "Starlink Disconnected".
# On hover (tooltip), it shows "Connected/Disconnected - Down: XX Mbps" plus more details like uptime, latency, SNR, alerts, time to next handover, approximate current satellite, visible satellites, data usage.
# Requires Python 3.7+ and the following packages:
# pip install starlink-grpc-core pystray pillow speedtest-cli requests skyfield
#
# Run this script to start the app. It will run in the background.
# Right-click the tray icon for menu options: Details, Run Speed Test, Stow Dish, Unstow Dish, Reboot Dish, Connect to Starlink, Disconnect WiFi, Quit.
#
# Note: This assumes you're connected to the Starlink network. The gRPC endpoint is at 192.168.100.1:9200.
# If using a custom router, ensure 192.168.100.1 is reachable.
# Tested on Linux (Ubuntu); should work cross-platform.
# New feature: If not connected, attempts to auto-connect to visible "STARLINK" WiFi (prompts for password if needed, with 5-min cooldown).
# Added: Approximate current satellite ID using math (highest elevation satellite above min angle) and time to next handover (fixed intervals).
# Added: Menu options to stow/unstow/reboot the dish.
# Added: Display number of visible Starlink satellites (above horizon).
# Added: Data usage stats from history (total down/up in GB for recent history).
# Added: Popup notifications for new alerts (e.g., obstruction).
# Added: Log status to 'starlink_log.txt' every update.
# Updated: Icon simplified to just cellphone bars.
# Added: Menu item 'Connect to Starlink' to manually attempt connection to the nearest Starlink dish via WiFi.
# Added: Menu item 'Disconnect WiFi' to disconnect from current WiFi if connected via WiFi.
# Added: Remembers connected Starlink dishes (by BSSID) and passwords in a SQLite DB ('starlink_connections.db'). Prefers previously connected dishes for auto-connect.

import sys
import time
import threading
import grpc
import tkinter as tk
from tkinter import messagebox, simpledialog
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import starlink_grpc
import speedtest
import subprocess
import requests
from skyfield.api import load, EarthSatellite, wgs84
import os
import sqlite3

# Global variables
last_attempt = 0
tried_bssids = set()  # Changed to BSSIDs
location = None
tle_data = None
last_tle_fetch = 0
handover_secs = [12, 27, 42, 57]
prev_alerts = []
log_file = 'starlink_log.txt'
db_file = 'starlink_connections.db'

# Initialize DB
def init_db():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS connections
                 (bssid TEXT PRIMARY KEY, ssid TEXT, password TEXT, last_connected INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# Function to save or update connection in DB
def save_connection(bssid, ssid, password):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    current_time = int(time.time())
    c.execute('''INSERT OR REPLACE INTO connections (bssid, ssid, password, last_connected)
                 VALUES (?, ?, ?, ?)''', (bssid.upper(), ssid, password, current_time))
    conn.commit()
    conn.close()

# Function to update last_connected
def update_last_connected(bssid):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    current_time = int(time.time())
    c.execute('''UPDATE connections SET last_connected = ? WHERE bssid = ?''', (current_time, bssid.upper()))
    conn.commit()
    conn.close()

# Function to get known connections sorted by last_connected desc
def get_known_connections():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''SELECT bssid, ssid, password, last_connected FROM connections ORDER BY last_connected DESC''')
    rows = c.fetchall()
    conn.close()
    return rows

# Function to get password for bssid
def get_password(bssid):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''SELECT password FROM connections WHERE bssid = ?''', (bssid.upper(),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# Function to fetch TLE data (once per day)
def fetch_tle():
    global tle_data, last_tle_fetch
    if time.time() - last_tle_fetch < 86400:  # 24 hours
        return
    try:
        url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle'
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        tle_data = []
        i = 0
        while i < len(lines):
            if lines[i].strip():  # Name
                name = lines[i].strip()
                i += 1
                if i < len(lines):
                    line1 = lines[i].strip()
                    i += 1
                    if i < len(lines):
                        line2 = lines[i].strip()
                        tle_data.append((name, line1, line2))
            i += 1
        last_tle_fetch = time.time()
    except Exception as e:
        print(f"TLE fetch error: {e}", file=sys.stderr)

# Function to get approximate current satellite and visible count
def get_satellite_info(lat, lon, alt=0):
    if tle_data is None:
        return "Unknown (TLE not fetched)", 0
    try:
        observer = wgs84.latlon(lat, lon, alt)
        ts = load.timescale()
        t = ts.now()
        max_elev = 0
        current_sat = "Unknown"
        visible_count = 0
        for name, l1, l2 in tle_data:
            sat = EarthSatellite(l1, l2, name)
            diff = sat - observer
            topocentric = diff.at(t)
            elev, _, _ = topocentric.altaz()
            if elev.degrees > 0:
                visible_count += 1
            if elev.degrees > max_elev and elev.degrees > 25:
                max_elev = elev.degrees
                current_sat = name
        return current_sat, visible_count
    except Exception as e:
        print(f"Satellite calc error: {e}", file=sys.stderr)
        return "Calculation Error", 0

# Function to calculate time to next handover
def time_to_next_handover():
    current_sec = int(time.time() % 60)
    next_hs = min((hs for hs in handover_secs if hs > current_sec), default=handover_secs[0] + 60)
    time_remaining = next_hs - current_sec if next_hs > current_sec else (next_hs - current_sec) % 60
    return time_remaining

# Function to create a cellular signal bars icon based on strength (0-4 bars)
def create_signal_icon(bars=0, connected=True):
    width, height = 32, 32  # Smaller size for tray icon
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))  # Transparent background
    draw = ImageDraw.Draw(image)
    
    bar_width = 5
    bar_gap = 2
    max_bars = 4
    bar_heights = [8, 12, 16, 20]  # Increasing heights for bars
    
    start_x = (width - (bar_width * max_bars + bar_gap * (max_bars - 1))) // 2
    start_y = height - max(bar_heights)
    
    color = (0, 255, 0) if connected else (128, 128, 128)  # Green if connected, gray if not
    
    for i in range(max_bars):
        x0 = start_x + i * (bar_width + bar_gap)
        y0 = height - bar_heights[i]
        x1 = x0 + bar_width
        y1 = height
        if i < bars:
            draw.rectangle((x0, y0, x1, y1), fill=color)
        else:
            draw.rectangle((x0, y0, x1, y1), outline=color, width=1)  # Outline for empty bars
    
    # If disconnected, add a red X
    if not connected:
        draw.line((0, 0, width, height), fill=(255, 0, 0), width=2)
        draw.line((0, height, width, 0), fill=(255, 0, 0), width=2)
    
    return image

# Function to get connection type (ethernet or wifi)
def get_connection_type():
    try:
        output = subprocess.check_output(["nmcli", "-t", "-f", "TYPE,STATE", "con", "show", "--active"]).decode("utf-8")
        lines = output.strip().split("\n")
        for line in lines:
            if line:
                typ, state = line.split(":")
                if state == "activated":
                    if typ == "802-3-ethernet":
                        return "ethernet"
                    elif typ == "802-11-wireless":
                        return "wifi"
        return None
    except Exception:
        return None

# Function to get active WiFi connection name
def get_active_wifi_con():
    try:
        output = subprocess.check_output(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show", "--active"]).decode("utf-8")
        lines = output.strip().split("\n")
        for line in lines:
            if line:
                name, typ = line.split(":")
                if typ == "802-11-wireless":
                    return name
        return None
    except Exception:
        return None

# Function to get Starlink status and history
def get_starlink_status():
    global location, prev_alerts
    try:
        ctx = starlink_grpc.ChannelContext(target="192.168.100.1:9200")
        status = starlink_grpc.get_status(ctx)
        state = status.get('state', 'UNKNOWN')
        connected = (state == 'CONNECTED')
        if not connected:
            return False, state, 0, 0, 0, 0, 0, [], 0, "N/A", "N/A", 0, 0, 0

        # Get location if not cached
        if location is None:
            loc = starlink_grpc.get_location(ctx)
            location = (loc.get('latitude', 0), loc.get('longitude', 0), loc.get('altitude', 0))

        uptime_hours = status.get('uptime_s', 0) / 3600
        down_speed = status.get('downlink_throughput_bps', 0) / 1e6
        up_speed = status.get('uplink_throughput_bps', 0) / 1e6
        latency = status.get('pop_ping_latency_ms', 0)
        snr = status.get('snr', 0)

        # Map SNR to bars
        if snr < 0:
            bars = 0
        elif snr < 3:
            bars = 1
        elif snr < 6:
            bars = 2
        elif snr < 9:
            bars = 3
        else:
            bars = 4

        alerts = []
        if status.get('alert_obstructed', False):
            alerts.append("Obstructed")
        if status.get('alert_motors_stuck', False):
            alerts.append("Motors Stuck")
        if status.get('alert_thermal_throttle', False):
            alerts.append("Thermal Throttle")

        # Check for new alerts and notify
        new_alerts = [a for a in alerts if a not in prev_alerts]
        if new_alerts:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning("Starlink Alert", f"New alerts: {', '.join(new_alerts)}")
        prev_alerts = alerts[:]

        # Get satellite info
        lat, lon, alt = location
        current_sat, visible_count = get_satellite_info(lat, lon, alt)

        # Time to next handover
        time_remaining = time_to_next_handover()

        # Get history for usage
        history = starlink_grpc.get_history(ctx)
        total_down_gb = sum(history.download_bytes) / 1e9 if hasattr(history, 'download_bytes') else 0
        total_up_gb = sum(history.upload_bytes) / 1e9 if hasattr(history, 'upload_bytes') else 0

        return connected, state, down_speed, up_speed, latency, uptime_hours, snr, alerts, bars, current_sat, time_remaining, visible_count, total_down_gb, total_up_gb
    except grpc.RpcError:
        prev_alerts = []
        return False, "Disconnected (Unable to reach dish)", 0, 0, 0, 0, 0, [], 0, "N/A", "N/A", 0, 0, 0
    except AttributeError:
        # Fallback if history fields not present
        return connected, state, down_speed, up_speed, latency, uptime_hours, snr, alerts, bars, current_sat, time_remaining, visible_count, 0, 0

# Function to prompt for WiFi password
def prompt_password(ssid):
    root = tk.Tk()
    root.withdraw()
    password = simpledialog.askstring("Connect to Starlink", f"Enter password for {ssid}:", show='*')
    return password

# Function to scan for Starlink networks
def scan_starlink_networks():
    try:
        output = subprocess.check_output(["nmcli", "-t", "-f", "BSSID,SSID,SIGNAL", "device", "wifi", "list", "--rescan", "yes"]).decode("utf-8")
        lines = output.strip().split("\n")
        networks = []
        for line in lines:
            if line:
                parts = line.split(":", 2)
                if len(parts) == 3:
                    bssid, ssid, signal = parts
                    if ssid.upper() in ["STARLINK", "STINKY"]:  # Common defaults
                        networks.append({"bssid": bssid, "ssid": ssid, "signal": int(signal)})
        return networks
    except Exception as e:
        print(f"Scan error: {e}", file=sys.stderr)
        return []

# Function to attempt connect to a specific BSSID/SSID with password
def attempt_connect(bssid, ssid, password):
    try:
        result = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password, "bssid", bssid], capture_output=True, text=True, check=True)
        if result.returncode == 0:
            save_connection(bssid, ssid, password)  # Save or update
            update_last_connected(bssid)
            return True
        else:
            return False
    except subprocess.CalledProcessError:
        return False

# Function to connect to Starlink (manual or auto logic)
def connect_to_starlink(icon, auto=False):
    networks = scan_starlink_networks()
    if not networks:
        if not auto:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Connect to Starlink", "No Starlink dish detected nearby.")
        return

    # Get known connections
    known = get_known_connections()  # List of (bssid, ssid, password, last_connected)

    # Match visible with known
    visible_known = []
    for net in networks:
        for k in known:
            if net['bssid'] == k[0]:
                visible_known.append({**net, 'password': k[2], 'last_connected': k[3]})

    # Sort visible known by last_connected desc, then signal desc
    visible_known.sort(key=lambda x: (-x['last_connected'], -x['signal']))

    connected = False
    if visible_known:
        # Try known, starting from most recent
        for net in visible_known:
            # First try con up (if profile exists)
            result = subprocess.run(["nmcli", "con", "up", net['ssid']], capture_output=True, text=True)
            if result.returncode == 0:
                update_last_connected(net['bssid'])
                connected = True
                break
            # Else, use saved password
            if attempt_connect(net['bssid'], net['ssid'], net['password']):
                connected = True
                break

    if not connected:
        # No known or failed, pick strongest new
        networks.sort(key=lambda x: -x['signal'])
        for net in networks:
            if net['bssid'] in tried_bssids:
                continue
            # Try con up first
            result = subprocess.run(["nmcli", "con", "up", net['ssid']], capture_output=True, text=True)
            if result.returncode == 0:
                update_last_connected(net['bssid'])  # Assume saved, but password not known, but if up, ok
                connected = True
                break
            # Prompt for password
            password = prompt_password(net['ssid']) if not auto else None
            if password:
                if attempt_connect(net['bssid'], net['ssid'], password):
                    connected = True
                    break
            tried_bssids.add(net['bssid'])

    if connected and not auto:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Connect to Starlink", "Connected to Starlink.")
    elif not connected and not auto:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Connect to Starlink", "Failed to connect.")

# Function to disconnect WiFi
def disconnect_wifi(icon):
    connection_type = get_connection_type()
    if connection_type != "wifi":
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Disconnect WiFi", "Not connected via WiFi.")
        return

    active_con = get_active_wifi_con()
    if active_con:
        try:
            subprocess.run(["nmcli", "con", "down", active_con], check=True)
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Disconnect WiFi", "Disconnected from WiFi.")
        except Exception as e:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Disconnect WiFi", f"Failed to disconnect: {e}")
    else:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Disconnect WiFi", "No active WiFi connection found.")

# Function to attempt auto-connect to Starlink WiFi (only if not connected and not on ethernet)
def auto_connect(connection_type):
    global last_attempt
    if time.time() - last_attempt < 300:  # 5 minutes cooldown
        return
    if connection_type == "ethernet":  # No auto-connect for ethernet
        return
    last_attempt = time.time()
    connect_to_starlink(None, auto=True)

# Function to log status
def log_status(connected, state, down_speed, up_speed, latency, uptime_hours, snr, alerts, current_sat, time_remaining, visible_count, total_down_gb, total_up_gb):
    with open(log_file, 'a') as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        alert_str = ", ".join(alerts) if alerts else "None"
        f.write(f"{timestamp} | Connected: {connected} | State: {state} | Down: {down_speed:.2f} Mbps | Up: {up_speed:.2f} Mbps | Latency: {latency:.0f} ms | Uptime: {uptime_hours:.1f} h | SNR: {snr} | Alerts: {alert_str} | Current Sat: {current_sat} | Next Handover: {time_remaining} s | Visible Sats: {visible_count} | Down Usage: {total_down_gb:.2f} GB | Up Usage: {total_up_gb:.2f} GB\n")

# Update the icon title, tooltip, and image
def update_icon(icon):
    fetch_tle()  # Fetch TLE if needed
    connected, state, down_speed, up_speed, latency, uptime_hours, snr, alerts, bars, current_sat, time_remaining, visible_count, total_down_gb, total_up_gb = get_starlink_status()
    connection_type = get_connection_type()
    
    icon.title = "Starlink " + ("Connected" if connected else "Disconnected")
    
    alert_str = "\nAlerts: " + ", ".join(alerts) if alerts else ""
    tooltip = (
        f"{'Connected' if connected else 'Disconnected'} - Down: {down_speed:.2f} Mbps\n"
        f"Up: {up_speed:.2f} Mbps\n"
        f"Latency: {latency:.0f} ms\n"
        f"Uptime: {uptime_hours:.1f} hours\n"
        f"SNR (Signal Strength): {snr}{alert_str}\n"
        f"Connection Type: {connection_type if connection_type else 'Unknown'}\n"
        f"Approx Current Satellite: {current_sat}\n"
        f"Time to Next Handover: {time_remaining} s\n"
        f"Visible Satellites: {visible_count}\n"
        f"Recent Down Usage: {total_down_gb:.2f} GB\n"
        f"Recent Up Usage: {total_up_gb:.2f} GB"
    )
    icon.tooltip = tooltip
    
    # Update icon image to cellphone bars
    new_icon_image = create_signal_icon(bars, connected)
    icon.icon = new_icon_image

    # Log status
    log_status(connected, state, down_speed, up_speed, latency, uptime_hours, snr, alerts, current_sat, time_remaining, visible_count, total_down_gb, total_up_gb)

    # If not connected, attempt auto-connect (only for WiFi)
    if not connected:
        auto_connect(connection_type)

# Show details in a message box
def show_details(icon):
    _, _, down_speed, up_speed, latency, uptime_hours, snr, alerts, _, current_sat, time_remaining, visible_count, total_down_gb, total_up_gb = get_starlink_status()
    connection_type = get_connection_type()
    alert_str = "\nAlerts: " + ", ".join(alerts) if alerts else ""
    msg = (
        f"Down: {down_speed:.2f} Mbps\n"
        f"Up: {up_speed:.2f} Mbps\n"
        f"Latency: {latency:.0f} ms\n"
        f"Uptime: {uptime_hours:.1f} hours\n"
        f"SNR: {snr}{alert_str}\n"
        f"Connection Type: {connection_type if connection_type else 'Unknown'}\n"
        f"Approx Current Satellite: {current_sat}\n"
        f"Time to Next Handover: {time_remaining} s\n"
        f"Visible Satellites: {visible_count}\n"
        f"Recent Down Usage: {total_down_gb:.2f} GB\n"
        f"Recent Up Usage: {total_up_gb:.2f} GB"
    )
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Starlink Status Details", msg)

# Run a speed test using speedtest-cli
def run_speedtest(icon):
    try:
        st = speedtest.Speedtest()
        st.download(threads=None)
        st.upload(threads=None)
        results = st.results.dict()
        msg = (
            f"Download: {results['download'] / 1e6:.2f} Mbps\n"
            f"Upload: {results['upload'] / 1e6:.2f} Mbps\n"
            f"Ping: {results['ping']:.0f} ms\n"
            f"Server: {results['server']['sponsor']}"
        )
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Speed Test Results", msg)
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Speed Test Error", str(e))

# Stow the dish
def stow_dish(icon):
    try:
        ctx = starlink_grpc.ChannelContext(target="192.168.100.1:9200")
        starlink_grpc.dish_stow(ctx)
        messagebox.showinfo("Starlink Control", "Dish stowed successfully.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to stow dish: {e}")

# Unstow the dish
def unstow_dish(icon):
    try:
        ctx = starlink_grpc.ChannelContext(target="192.168.100.1:9200")
        starlink_grpc.dish_unstow(ctx)
        messagebox.showinfo("Starlink Control", "Dish unstowed successfully.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to unstow dish: {e}")

# Reboot the dish
def reboot_dish(icon):
    if messagebox.askyesno("Confirm Reboot", "Are you sure you want to reboot the dish?"):
        try:
            ctx = starlink_grpc.ChannelContext(target="192.168.100.1:9200")
            starlink_grpc.dish_reboot(ctx)
            messagebox.showinfo("Starlink Control", "Dish reboot initiated.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reboot dish: {e}")

# Quit the app
def quit_app(icon):
    icon.stop()
    sys.exit(0)

# Setup the tray icon with initial image
initial_image = create_signal_icon(0, False)
icon = Icon('starlink', initial_image, "Starlink Status")

# Menu items
icon.menu = Menu(
    MenuItem('Details', show_details),
    MenuItem('Run Speed Test', run_speedtest),
    MenuItem('Stow Dish', stow_dish),
    MenuItem('Unstow Dish', unstow_dish),
    MenuItem('Reboot Dish', reboot_dish),
    MenuItem('Connect to Starlink', lambda icon: connect_to_starlink(icon)),
    MenuItem('Disconnect WiFi', disconnect_wifi),
    MenuItem('Quit', quit_app)
)

# Update loop in a separate thread
def update_loop():
    while True:
        update_icon(icon)
        time.sleep(30)  # Update every 30 seconds

# Start the update thread
thread = threading.Thread(target=update_loop, daemon=True)
thread.start()

# Run the icon
icon.run()

# Additional features:
# - Simplified icon to cellphone bars.
# - Periodic updates every 30 seconds.
# - Alerts for obstructions, motor issues, thermal throttling with popup notifications for new alerts.
# - Integrated speed test via menu.
# - Latency and SNR in tooltip.
# - Auto-connect to previously connected Starlink dishes (by BSSID) if disconnected, using saved passwords from DB.
# - Approximate current satellite using orbital math (highest elevation satellite).
# - Time to next satellite handover based on fixed intervals.
# - Number of visible satellites (above horizon).
# - Recent data usage from history (summed in GB).
# - Menu options to stow/unstow/reboot the dish.
# - Logs status to 'starlink_log.txt' for historical monitoring.
# - Remembers connections in 'starlink_connections.db' for passwords and prefers recent connections.
# You can extend by adding graphs from history data or per-device usage if integrated with router API.
