import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

output_dir = r"c:\Users\ssubh\OneDrive\mini\Traffic_management\reports\report_figures"
os.makedirs(output_dir, exist_ok=True)

# -------------------------------------------------------------
# Figure 1.1: Fixed-Time vs Adaptive Comparison
# -------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), dpi=300)

ax1.set_title("Conventional Fixed-Time Signal System", fontsize=11, fontweight='bold', pad=12, color='#8B0000')
ax1.pie([25, 25, 25, 25], labels=['Lane 1 (North)\nFixed 30s', 'Lane 2 (East)\nFixed 30s', 'Lane 3 (South)\nFixed 30s', 'Lane 4 (West)\nFixed 30s'],
        colors=['#FF9999', '#66B2FF', '#99FF99', '#FFCC99'], autopct='%1.0f%%', startangle=90,
        wedgeprops=dict(width=0.45, edgecolor='black', linewidth=1.2))
ax1.text(0, 0, "Rigid Cycle\n120s Total\nBlind to Traffic", ha='center', va='center', fontsize=10, fontweight='bold', color='#555555')

ax2.set_title("Proposed Vision & IoT Adaptive System", fontsize=11, fontweight='bold', pad=12, color='#006400')
ax2.pie([40, 15, 35, 10], labels=['Lane 1 (Heavy)\nDynamic 38s', 'Lane 2 (Low)\nDynamic 12s', 'Lane 3 (Med)\nDynamic 26s', 'Lane 4 (Empty)\nQuick Clear 5s'],
        colors=['#2ECC71', '#3498DB', '#F1C40F', '#E67E22'], autopct='%1.0f%%', startangle=90,
        wedgeprops=dict(width=0.45, edgecolor='black', linewidth=1.2))
ax2.text(0, 0, "Dynamic Green\nEmergency\nPreemption", ha='center', va='center', fontsize=10, fontweight='bold', color='#1B4F72')

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig1_fixed_vs_adaptive.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 1.1 generated")


# -------------------------------------------------------------
# Figure 3.1: Block Diagram of Overall System Architecture
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 7.5), dpi=300)
ax.set_xlim(0, 12)
ax.set_ylim(0, 8.5)
ax.axis('off')

# Layer Backgrounds
def draw_box(x, y, w, h, title, bg_color, border_color):
    rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.15",
                                  facecolor=bg_color, edgecolor=border_color, linewidth=1.8)
    ax.add_patch(rect)
    ax.text(x + w/2, y + h - 0.35, title, ha='center', va='center', fontsize=10, fontweight='bold', color=border_color)

# Boxes
# 1. Perception Layer (Left)
draw_box(0.5, 4.8, 3.2, 3.2, "PERCEPTION & SENSING LAYER", "#EBF5FB", "#2874A6")
ax.text(2.1, 7.0, "• Lab Overhead Webcam (USB)\n• RC522 RFID Reader (SPI)\n  (Emergency Ambulance Tag)\n• VL53L0X Time-of-Flight (ToF)\n  (Blind Spot / Occluded Distance)\n• 4-Way Traffic ROI Partitioning",
        ha='center', va='center', fontsize=8.5, color='#1A252F', linespacing=1.3)

# 2. Dual-Laptop Processing Layer (Middle-Top)
draw_box(4.4, 4.8, 3.6, 3.2, "DISTRIBUTED PROCESSING LAYER", "#FEF9E7", "#B7950B")
ax.text(6.2, 7.0, "• Laptop 1: Primary Vision Unit\n  - OpenCV Frame Ingestion\n  - YOLO Density & Vehicle Counting\n  - FastAPI Backend & WebSocket Telemetry\n• Laptop 2: Emergency Coordinator\n  - Priority Engine & Fail-Safe State Machine\n  - Serial Telemetry Synchronization",
        ha='center', va='center', fontsize=8.5, color='#1A252F', linespacing=1.3)

# 3. Dual-ESP32 Embedded Control Layer (Right-Top)
draw_box(8.6, 4.8, 3.0, 3.2, "EMBEDDED CONTROLLER LAYER", "#EAFAF1", "#1E8449")
ax.text(10.1, 7.0, "• ESP32 Node 1 (Master):\n  - 4-Lane Signal Phase Switching\n  - 7-Segment Countdown Driver\n• ESP32 Node 2 (Dedicated):\n  - Ambulance Lane Priority\n  - ToF Distance Ranging\n  - Instant Trigger Interrupts",
        ha='center', va='center', fontsize=8.5, color='#1A252F', linespacing=1.3)

# 4. Actuation & Display Layer (Right-Bottom)
draw_box(8.6, 0.8, 3.0, 3.3, "ACTUATION & INDICATION", "#FDEDEC", "#B03A2E")
ax.text(10.1, 2.4, "• 4-Way Traffic Signal LEDs:\n  (Red, Yellow, Green per Lane)\n  (12 High-Brightness LEDs)\n• TM1637 4-Digit 7-Segment\n  Dynamic Countdown Timer\n• Emergency Clearance Alarm / Buzzer",
        ha='center', va='center', fontsize=8.5, color='#1A252F', linespacing=1.4)

# 5. Presentation & Monitoring Layer (Left-Bottom)
draw_box(0.5, 0.8, 7.5, 3.3, "PRESENTATION & MISSION-CONTROL DASHBOARD", "#F4ECF7", "#6C3483")
ax.text(4.25, 2.4, "• Real-Time Web Mission-Control Interface (React 19 + Vite)\n• Live OpenCV Annotated Video Stream with Dynamic Bounding Boxes\n• 4-Approach Traffic Signal State & Real-Time Countdown Telemetry\n• Density Tier Indicators (Low / Medium / High) & Starvation Prevention Monitor\n• Emergency Vehicle Alert Banner & Manual Officer Preemption Override Panel\n• Historical Session Logs, SQLite Persistence, and Automated PDF/CSV Reports",
        ha='center', va='center', fontsize=8.5, color='#1A252F', linespacing=1.3)

# Arrows
def draw_arrow(x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(facecolor='#2C3E50', edgecolor='#2C3E50', arrowstyle="->", lw=2.0))
    if label:
        ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, label, ha='center', va='center', fontsize=8, fontweight='bold', color='#2C3E50')

draw_arrow(3.7, 6.4, 4.4, 6.4, "Video / Tags")
draw_arrow(8.0, 6.4, 8.6, 6.4, "Serial / WiFi")
draw_arrow(10.1, 4.8, 10.1, 4.1, "GPIO Driving")
draw_arrow(8.6, 2.4, 8.0, 2.4, "Phase Status")
draw_arrow(6.2, 4.8, 6.2, 4.1, "WebSocket /ws")

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig3_1_system_architecture.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 3.1 generated")


# -------------------------------------------------------------
# Figure 3.2: Dual-Laptop & Dual-ESP32 Interconnection
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
ax.set_xlim(0, 11)
ax.set_ylim(0, 6)
ax.axis('off')

# Box Laptop 1
draw_box(0.8, 3.2, 4.2, 2.4, "LAPTOP 1: VISION & SERVER UNIT", "#EBF5FB", "#1B4F72")
ax.text(2.9, 4.3, "• Lab Overhead Webcam\n• OpenCV Vehicle Density Counting\n• FastAPI Engine (Port 8000)\n• React Dashboard (Port 5173)", ha='center', va='center', fontsize=9)

# Box Laptop 2
draw_box(6.0, 3.2, 4.2, 2.4, "LAPTOP 2: DEDICATED PRIORITY UNIT", "#FEF9E7", "#7D6608")
ax.text(8.1, 4.3, "• Dedicated Emergency Coordinator\n• Priority Decision & Preemption Logic\n• Starvation & Wait-Time Engine\n• Hardware Telemetry Sync", ha='center', va='center', fontsize=9)

# Box ESP32 Node 1
draw_box(0.8, 0.4, 4.2, 2.2, "ESP32 NODE 1: MASTER JUNCTION", "#EAFAF1", "#145A32")
ax.text(2.9, 1.4, "• 4-Lane Traffic LEDs (12 GPIOs)\n• TM1637 4-Digit Display (CLK, DIO)\n• Green / Yellow / Red Phasing", ha='center', va='center', fontsize=9)

# Box ESP32 Node 2
draw_box(6.0, 0.4, 4.2, 2.2, "ESP32 NODE 2: EMERGENCY & TOF", "#FDEDEC", "#78281F")
ax.text(8.1, 1.4, "• RC522 RFID Reader (Ambulance Tag)\n• VL53L0X ToF Distance Sensor\n• Blind Spot Occlusion Detection", ha='center', va='center', fontsize=9)

# Arrows between units
draw_arrow(5.0, 4.4, 6.0, 4.4, "TCP / WebSocket LAN")
draw_arrow(6.0, 4.2, 5.0, 4.2, "Sync Ack")
draw_arrow(2.9, 3.2, 2.9, 2.6, "USB-UART COM Port")
draw_arrow(8.1, 3.2, 8.1, 2.6, "USB-UART COM Port")
draw_arrow(6.0, 1.5, 5.0, 1.5, "ESP-NOW / Hardware Trigger")

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig3_2_dual_laptop_esp32.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 3.2 generated")


# -------------------------------------------------------------
# Figure 3.3: Conceptual Workflow Flowchart
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 8.5), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(0, 11)
ax.axis('off')

def draw_oval(x, y, w, h, text, bg, border):
    e = patches.Ellipse((x, y), w, h, facecolor=bg, edgecolor=border, lw=2)
    ax.add_patch(e)
    ax.text(x, y, text, ha='center', va='center', fontsize=9, fontweight='bold', color=border)

def draw_rect(x, y, w, h, text, bg, border):
    r = patches.FancyBboxPatch((x-w/2, y-h/2), w, h, boxstyle="round,pad=0.08,rounding_size=0.1",
                               facecolor=bg, edgecolor=border, lw=1.8)
    ax.add_patch(r)
    ax.text(x, y, text, ha='center', va='center', fontsize=8.5, fontweight='bold', color='#1A252F', linespacing=1.2)

def draw_diamond(x, y, w, h, text, bg, border):
    pts = [[x, y+h/2], [x+w/2, y], [x, y-h/2], [x-w/2, y]]
    poly = patches.Polygon(pts, closed=True, facecolor=bg, edgecolor=border, lw=1.8)
    ax.add_patch(poly)
    ax.text(x, y, text, ha='center', va='center', fontsize=8, fontweight='bold', color='#1A252F', linespacing=1.1)

# Flowchart elements
draw_oval(5.0, 10.4, 2.6, 0.7, "SYSTEM START", "#EBF5FB", "#1B4F72")
draw_rect(5.0, 9.3, 5.8, 0.8, "Initialize Dual ESP32 Nodes, OpenCV Lab Webcam,\nRC522 RFID SPI & VL53L0X ToF I2C Bus", "#F4F6F6", "#34495E")
draw_rect(5.0, 8.2, 5.8, 0.8, "Continuous Acquisition: OpenCV 4-Lane ROI Frames,\nRFID Tag Polling & ToF Blind Spot Distance Ranging", "#FEF9E7", "#B7950B")
draw_diamond(5.0, 6.8, 4.4, 1.2, "Emergency Ambulance\nDetected via RFID?", "#FADBD8", "#922B21")

# Left branch: Emergency Preemption
draw_rect(1.8, 5.4, 2.8, 0.8, "Safe Preemption Sequence:\nConflicting Lane -> YELLOW (3s)", "#FDEDEC", "#C0392B")
draw_rect(1.8, 4.2, 2.8, 0.8, "ALL-RED Clearance (1s)\n(Zero Collision Invariant)", "#FDEDEC", "#C0392B")
draw_rect(1.8, 3.0, 2.8, 0.8, "Ambulance Lane -> GREEN (15s)\nDisplay Countdown on TM1637", "#EAFAF1", "#27AE60")
draw_rect(1.8, 1.8, 2.8, 0.8, "Verify Clearance via RFID/ToF\nResume Normal Adaptive Mode", "#EBF5FB", "#2980B9")

# Right branch: Normal Adaptive Decision
draw_diamond(6.8, 5.4, 3.4, 1.0, "Vehicle in Blind Spot?\n(ToF Distance < 25 cm)", "#FCF3CF", "#D4AC0D")
draw_rect(8.4, 4.2, 2.6, 0.7, "Increment Lane Count\n(+1 Virtual Detection)", "#FCF3CF", "#B7950B")
draw_rect(5.5, 4.2, 2.6, 0.7, "Standard OpenCV Density\n(Contour / YOLO Counts)", "#EAFAF1", "#1E8449")
draw_rect(6.8, 3.0, 5.2, 0.8, "Calculate Multi-Criteria Priority Score:\nScore(d) = 0.6*Density + 0.4*WaitTime + StarvationBoost", "#E8F8F5", "#117864")
draw_rect(6.8, 1.8, 5.2, 0.8, "Compute Dynamic Green Duration:\nDuration = clamp(2.5s + 2.2s*Vehicles, 5s, 40s)", "#E8F8F5", "#117864")

# Rejoin and update
draw_rect(5.0, 0.7, 6.8, 0.7, "Transmit Phase & Timer to ESP32 Master -> Update 4-Lane LEDs & 7-Segment", "#D6EAF8", "#1B4F72")

# Flow lines
draw_arrow(5.0, 10.05, 5.0, 9.7)
draw_arrow(5.0, 8.9, 5.0, 8.6)
draw_arrow(5.0, 7.8, 5.0, 7.4)

# Emergency YES
ax.annotate("", xy=(1.8, 5.8), xytext=(2.8, 6.8),
            arrowprops=dict(facecolor='#922B21', edgecolor='#922B21', arrowstyle="->", lw=1.8))
ax.text(2.1, 6.5, "YES (RFID Tag Read)", fontsize=8, fontweight='bold', color='#922B21')
draw_arrow(1.8, 5.0, 1.8, 4.6)
draw_arrow(1.8, 3.8, 1.8, 3.4)
draw_arrow(1.8, 2.6, 1.8, 2.2)
ax.annotate("", xy=(3.5, 0.9), xytext=(1.8, 1.4),
            arrowprops=dict(facecolor='#1B4F72', edgecolor='#1B4F72', arrowstyle="->", lw=1.8))

# Emergency NO
ax.annotate("", xy=(6.8, 5.9), xytext=(6.5, 6.8),
            arrowprops=dict(facecolor='#1E8449', edgecolor='#1E8449', arrowstyle="->", lw=1.8))
ax.text(6.8, 6.5, "NO (Normal Traffic)", fontsize=8, fontweight='bold', color='#1E8449')

# ToF diamond
draw_arrow(8.0, 5.4, 8.4, 4.55, "YES")
draw_arrow(5.6, 5.4, 5.5, 4.55, "NO")
draw_arrow(8.4, 3.85, 7.8, 3.4)
draw_arrow(5.5, 3.85, 6.0, 3.4)
draw_arrow(6.8, 2.6, 6.8, 2.2)
ax.annotate("", xy=(6.0, 1.05), xytext=(6.8, 1.4),
            arrowprops=dict(facecolor='#1B4F72', edgecolor='#1B4F72', arrowstyle="->", lw=1.8))

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig3_3_conceptual_workflow.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 3.3 generated")


# -------------------------------------------------------------
# Figure 4.1: Hardware Experimental Setup Diagram
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6.5), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# Intersection roads
road_bg = '#BDC3C7'
# Horizontal Road
ax.add_patch(patches.Rectangle((0, 3.5), 10, 3.0, facecolor=road_bg, edgecolor='none'))
# Vertical Road
ax.add_patch(patches.Rectangle((3.5, 0), 3.0, 10, facecolor=road_bg, edgecolor='none'))

# Center junction box
ax.add_patch(patches.Rectangle((3.5, 3.5), 3.0, 3.0, facecolor='#95A5A6', edgecolor='#7F8C8D', lw=1.5))
# Road center lines (dashed)
ax.plot([0, 3.5], [5.0, 5.0], color='#F4D03F', linestyle='--', lw=2)
ax.plot([6.5, 10], [5.0, 5.0], color='#F4D03F', linestyle='--', lw=2)
ax.plot([5.0, 5.0], [0, 3.5], color='#F4D03F', linestyle='--', lw=2)
ax.plot([5.0, 5.0], [6.5, 10], color='#F4D03F', linestyle='--', lw=2)

# Stop lines
ax.plot([3.5, 3.5], [3.5, 5.0], color='white', lw=3)
ax.plot([6.5, 6.5], [5.0, 6.5], color='white', lw=3)
ax.plot([5.0, 6.5], [3.5, 3.5], color='white', lw=3)
ax.plot([3.5, 5.0], [6.5, 6.5], color='white', lw=3)

# Overhead Webcam
ax.add_patch(patches.Circle((5.0, 5.0), 0.55, facecolor='#2C3E50', edgecolor='cyan', lw=2))
ax.text(5.0, 5.0, "OVERHEAD\nWEBCAM", ha='center', va='center', fontsize=6.5, fontweight='bold', color='white')

# Traffic Light Modules (R, Y, G)
def draw_traffic_light(x, y, label, active='red'):
    ax.add_patch(patches.Rectangle((x-0.3, y-0.6), 0.6, 1.2, facecolor='#17202A', edgecolor='gold', lw=1.2, zorder=5))
    ax.add_patch(patches.Circle((x, y+0.35), 0.12, facecolor='red' if active=='red' else '#550000', zorder=6))
    ax.add_patch(patches.Circle((x, y), 0.12, facecolor='yellow' if active=='yellow' else '#555500', zorder=6))
    ax.add_patch(patches.Circle((x, y-0.35), 0.12, facecolor='#00FF00' if active=='green' else '#004400', zorder=6))
    ax.text(x, y-0.8, label, ha='center', va='top', fontsize=7.5, fontweight='bold', color='#17202A')

draw_traffic_light(3.0, 6.8, "Lane 1 (North)", 'green')
draw_traffic_light(6.8, 7.0, "Lane 2 (East)", 'red')
draw_traffic_light(7.0, 3.2, "Lane 3 (South)", 'red')
draw_traffic_light(3.0, 3.0, "Lane 4 (West)\n[Ambulance Lane]", 'red')

# RFID Reader & Ambulance on Lane 4
ax.add_patch(patches.Rectangle((0.8, 4.0), 1.6, 0.8, facecolor='white', edgecolor='red', lw=2))
ax.text(1.6, 4.4, "AMBULANCE\n(RFID TAG)", ha='center', va='center', fontsize=7.5, fontweight='bold', color='red')

ax.add_patch(patches.Rectangle((2.6, 4.2), 0.5, 0.6, facecolor='#2980B9', edgecolor='white', lw=1.5))
ax.text(2.85, 4.5, "RC522\nRFID", ha='center', va='center', fontsize=6, fontweight='bold', color='white')

# ToF Sensor placed in Blind Spot (Corner / Underpass)
ax.add_patch(patches.Rectangle((2.6, 5.2), 0.5, 0.5, facecolor='#8E44AD', edgecolor='white', lw=1.5))
ax.text(2.85, 5.45, "ToF\nSensor", ha='center', va='center', fontsize=6, fontweight='bold', color='white')
ax.text(1.5, 5.5, "[Blind Spot Detection]", fontsize=7, color='#5B2C6F', style='italic')

# TM1637 7-Segment Timer Display
ax.add_patch(patches.Rectangle((7.5, 8.2), 2.2, 1.0, facecolor='#1C2833', edgecolor='cyan', lw=1.5))
ax.text(8.6, 8.7, "TM1637 DISPLAY", ha='center', va='center', fontsize=7, color='cyan')
ax.text(8.6, 8.45, "00:28", ha='center', va='center', fontsize=12, fontweight='bold', color='#2ECC71')

# Dual ESP32 Controller nodes
ax.add_patch(patches.Rectangle((0.3, 8.2), 2.8, 1.3, facecolor='#EAFAF1', edgecolor='#1E8449', lw=1.5))
ax.text(1.7, 9.2, "ESP32 MASTER NODE", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#145A32')
ax.text(1.7, 8.6, "• 12x Traffic Signal LEDs\n• TM1637 Countdown Display", ha='center', va='center', fontsize=6.5)

ax.add_patch(patches.Rectangle((0.3, 0.5), 2.8, 1.3, facecolor='#FDEDEC', edgecolor='#C0392B', lw=1.5))
ax.text(1.7, 1.5, "ESP32 DEDICATED NODE", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#78281F')
ax.text(1.7, 0.9, "• RC522 RFID Reader (SPI)\n• VL53L0X ToF Sensor (I2C)", ha='center', va='center', fontsize=6.5)

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig4_1_hardware_setup.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 4.1 generated")


# -------------------------------------------------------------
# Figure 4.2: ESP32 Pin Connections & Schematic Diagram
# -------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), dpi=300)

for ax in (ax1, ax2):
    ax.axis('off')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

# ESP32 Node 1 (Master)
ax1.set_title("ESP32 Master Node: Traffic LEDs & 7-Segment Display", fontsize=10, fontweight='bold', pad=10, color='#145A32')
ax1.add_patch(patches.Rectangle((3.0, 1.5), 4.0, 7.0, facecolor='#17202A', edgecolor='#27AE60', lw=2))
ax1.text(5.0, 8.0, "ESP32 DevKit V1\n(Master Controller)", ha='center', va='center', fontsize=9, fontweight='bold', color='white')

# Left Pins (Master)
master_left = [("GPIO 23", "North RED LED"), ("GPIO 22", "North YEL LED"), ("GPIO 21", "North GRN LED"),
               ("GPIO 19", "East RED LED"), ("GPIO 18", "East YEL LED"), ("GPIO 5", "East GRN LED")]
for i, (pin, desc) in enumerate(master_left):
    y = 7.0 - i * 0.9
    ax1.plot([2.0, 3.0], [y, y], color='#27AE60', lw=1.5)
    ax1.text(2.9, y, pin, ha='right', va='center', fontsize=7, color='yellow')
    ax1.text(1.9, y, desc, ha='right', va='center', fontsize=7.5, fontweight='bold')

# Right Pins (Master)
master_right = [("GPIO 17", "South RED LED"), ("GPIO 16", "South YEL LED"), ("GPIO 4", "South GRN LED"),
                ("GPIO 2", "West RED LED"), ("GPIO 15", "West YEL LED"), ("GPIO 13", "West GRN LED"),
                ("GPIO 25", "TM1637 CLK"), ("GPIO 26", "TM1637 DIO")]
for i, (pin, desc) in enumerate(master_right):
    y = 7.2 - i * 0.75
    ax1.plot([7.0, 8.0], [y, y], color='#27AE60', lw=1.5)
    ax1.text(7.1, y, pin, ha='left', va='center', fontsize=7, color='yellow')
    ax1.text(8.1, y, desc, ha='left', va='center', fontsize=7.5, fontweight='bold')

# ESP32 Node 2 (Dedicated Emergency & ToF)
ax2.set_title("ESP32 Dedicated Node: RFID Reader & ToF Distance Sensor", fontsize=10, fontweight='bold', pad=10, color='#922B21')
ax2.add_patch(patches.Rectangle((3.0, 1.5), 4.0, 7.0, facecolor='#17202A', edgecolor='#E74C3C', lw=2))
ax2.text(5.0, 8.0, "ESP32 DevKit V1\n(Dedicated Emergency)", ha='center', va='center', fontsize=9, fontweight='bold', color='white')

# Left Pins (RFID SPI)
rfid_pins = [("GPIO 18 (SCK)", "RC522 SCK"), ("GPIO 19 (MISO)", "RC522 MISO"), ("GPIO 23 (MOSI)", "RC522 MOSI"),
             ("GPIO 5 (SS/SDA)", "RC522 SDA"), ("GPIO 22 (RST)", "RC522 RST"), ("3.3V / GND", "RC522 Power")]
for i, (pin, desc) in enumerate(rfid_pins):
    y = 7.0 - i * 0.9
    ax2.plot([2.0, 3.0], [y, y], color='#E74C3C', lw=1.5)
    ax2.text(2.9, y, pin, ha='right', va='center', fontsize=7, color='yellow')
    ax2.text(1.9, y, desc, ha='right', va='center', fontsize=7.5, fontweight='bold')

# Right Pins (ToF I2C & Serial)
tof_pins = [("GPIO 21 (SDA)", "VL53L0X SDA (I2C)"), ("GPIO 22 (SCL)", "VL53L0X SCL (I2C)"),
            ("GPIO 16 (RX2)", "Laptop 2 Serial TX"), ("GPIO 17 (TX2)", "Laptop 2 Serial RX"),
            ("VIN (5V)", "External 5V Power"), ("GND", "Common Ground Bus")]
for i, (pin, desc) in enumerate(tof_pins):
    y = 7.0 - i * 0.9
    ax2.plot([7.0, 8.0], [y, y], color='#E74C3C', lw=1.5)
    ax2.text(7.1, y, pin, ha='left', va='center', fontsize=7, color='yellow')
    ax2.text(8.1, y, desc, ha='left', va='center', fontsize=7.5, fontweight='bold')

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig4_2_pin_connections.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 4.2 generated")


# -------------------------------------------------------------
# Figure 4.3: Mission Control Dashboard UI Mockup
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
ax.set_xlim(0, 11)
ax.set_ylim(0, 6)
ax.axis('off')

# Main frame
ax.add_patch(patches.Rectangle((0.2, 0.2), 10.6, 5.6, facecolor='#0B0F19', edgecolor='#2A3B5C', lw=2))

# Top App Header
ax.add_patch(patches.Rectangle((0.2, 5.0), 10.6, 0.8, facecolor='#111827', edgecolor='none'))
ax.text(0.5, 5.4, "AI ADAPTIVE TRAFFIC MANAGEMENT SYSTEM", fontsize=11, fontweight='bold', color='#60A5FA')
ax.add_patch(patches.FancyBboxPatch((8.0, 5.15), 2.5, 0.5, facecolor='#DC2626', edgecolor='none', boxstyle="round,pad=0.1"))
ax.text(9.25, 5.4, "EMERGENCY PREEMPTION ACTIVE", fontsize=7.5, fontweight='bold', color='white', ha='center', va='center')

# Left Panel: Live Camera Feed with YOLO / Lane Overlays
ax.add_patch(patches.Rectangle((0.5, 0.6), 5.5, 4.1, facecolor='#1F2937', edgecolor='#374151', lw=1.5))
ax.text(0.7, 4.45, "Live Vision Perception (Webcam Overlay)", fontsize=8.5, fontweight='bold', color='#9CA3AF')

# Video frame inside
ax.add_patch(patches.Rectangle((0.7, 0.8), 5.1, 3.4, facecolor='#111827', edgecolor='#4B5563', lw=1))
# Bounding boxes
ax.add_patch(patches.Rectangle((1.0, 1.8), 1.2, 1.5, facecolor='none', edgecolor='#3B82F6', lw=1.8))
ax.text(1.0, 3.4, "Car #12 [North] (0.89)", fontsize=7, color='#93C5FD')
ax.add_patch(patches.Rectangle((3.2, 2.0), 1.4, 1.8, facecolor='none', edgecolor='#EF4444', lw=2.2))
ax.text(3.2, 3.9, "AMBULANCE #07 [West] (0.94)", fontsize=7, fontweight='bold', color='#FCA5A5')

# Right Top Panel: Intersection Signal Status
ax.add_patch(patches.Rectangle((6.3, 2.8), 4.3, 1.9, facecolor='#1F2937', edgecolor='#374151', lw=1.5))
ax.text(6.5, 4.45, "Intersection Phase Telemetry", fontsize=8.5, fontweight='bold', color='#9CA3AF')
lanes_status = [("North Approach", "RED", "#EF4444"), ("East Approach", "RED", "#EF4444"),
                ("South Approach", "RED", "#EF4444"), ("West Approach", "GREEN (EMERGENCY)", "#10B981")]
for i, (lname, st, col) in enumerate(lanes_status):
    y = 4.0 - i * 0.35
    ax.text(6.6, y, lname, fontsize=7.5, color='#D1D5DB')
    ax.text(9.2, y, st, fontsize=7.5, fontweight='bold', color=col)

# Right Bottom Panel: Hardware Telemetry (ESP32, RFID, ToF)
ax.add_patch(patches.Rectangle((6.3, 0.6), 4.3, 2.0, facecolor='#1F2937', edgecolor='#374151', lw=1.5))
ax.text(6.5, 2.35, "Hardware Sensors & Node Telemetry", fontsize=8.5, fontweight='bold', color='#9CA3AF')
hw_status = [
    ("ESP32 Master Node:", "CONNECTED (COM3 @ 115200)", "#10B981"),
    ("ESP32 Dedicated Node:", "CONNECTED (COM4 @ 115200)", "#10B981"),
    ("RFID Tag Detected:", "ID: A3-89-F1-02 (AMBULANCE)", "#F87171"),
    ("ToF Distance Ranging:", "18.4 cm [Vehicle Present in Occlusion]", "#FBBF24"),
    ("Countdown Remaining:", "14.2 s (TM1637 Synced)", "#60A5FA")
]
for i, (k, v, col) in enumerate(hw_status):
    y = 2.0 - i * 0.3
    ax.text(6.5, y, k, fontsize=7, color='#9CA3AF')
    ax.text(8.3, y, v, fontsize=7, fontweight='bold', color=col)

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig4_3_dashboard_interface.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 4.3 generated")


# -------------------------------------------------------------
# Figure 4.4: Density vs Green Time Dynamic Curve
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
vehicles = np.arange(0, 22)
# Formula: clamp(2.5 + 2.2 * N, 5, 40), with 4.0s for 0 vehicles
green_times = [4.0 if n == 0 else min(40.0, max(5.0, 2.5 + 2.2 * n)) for n in vehicles]

ax.plot(vehicles, green_times, marker='o', color='#1F77B4', lw=2.2, label=r'Dynamic Green Duration: $T = \mathrm{clamp}(2.5 + 2.2N, 5, 40)$')
ax.axhline(5, color='#2CA02C', linestyle='--', lw=1.5, label='Min Green Clamp (5s)')
ax.axhline(40, color='#D62728', linestyle='--', lw=1.5, label='Max Green Safety Clamp (40s)')
ax.axhline(30, color='#7F7F7F', linestyle=':', lw=1.5, label='Conventional Fixed Timer (30s)')

ax.set_title("Dynamic Queue-Clearing Green Duration vs. Vehicle Density", fontsize=11, fontweight='bold')
ax.set_xlabel("Detected Vehicle Queue Count ($N$)", fontsize=9.5)
ax.set_ylabel("Allocated Green Signal Duration (Seconds)", fontsize=9.5)
ax.set_xlim(-0.5, 21.5)
ax.set_ylim(0, 45)
ax.grid(True, linestyle=':', alpha=0.6)
ax.legend(fontsize=8.5, loc='lower right')

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig4_4_density_vs_greentime.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 4.4 generated")


# -------------------------------------------------------------
# Figure 4.5: Emergency Vehicle RFID Preemption Timeline
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
ax.set_xlim(0, 35)
ax.set_ylim(-0.5, 3.5)
ax.axis('off')

ax.set_title("Fail-Safe Emergency Preemption State Transition Sequence", fontsize=11, fontweight='bold', pad=10)

# Phases
phases = [
    (0, 10, "Phase 1: Normal Adaptive Green\n(North Approach Active)", "#A9DFBF", "#1E8449"),
    (10, 13, "Phase 2: Yellow Transition\n(3.0s Safe Deceleration)", "#F9E79F", "#B7950B"),
    (13, 14, "Phase 3: All-Red\n(1.0s Clearance)", "#F5B7B1", "#C0392B"),
    (14, 29, "Phase 4: Emergency Green\n(15.0s Ambulance Lane Priority)", "#AED6F1", "#2874A6"),
    (29, 35, "Phase 5: Return to Adaptive\n(Next Highest Density Lane)", "#D2B4DE", "#7D3C98")
]

for x1, x2, desc, bg, border in phases:
    ax.add_patch(patches.Rectangle((x1, 1.2), x2-x1, 1.4, facecolor=bg, edgecolor=border, lw=2))
    ax.text((x1+x2)/2, 1.9, desc, ha='center', va='center', fontsize=8, fontweight='bold', color='#1A252F', linespacing=1.2)
    ax.text(x1, 0.8, f"{x1}s", ha='center', va='center', fontsize=8, color='#555555')

ax.text(35, 0.8, "35s", ha='center', va='center', fontsize=8, color='#555555')
ax.plot([0, 35], [1.0, 1.0], color='#2C3E50', lw=2)

# Trigger Annotation
ax.annotate("RFID Ambulance Tag Read\nat Lane 4 (t = 10s)", xy=(10, 2.6), xytext=(10, 3.3),
            arrowprops=dict(facecolor='red', edgecolor='red', arrowstyle="->", lw=2),
            ha='center', fontsize=8.5, fontweight='bold', color='red')

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig4_5_emergency_preemption_timeline.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 4.5 generated")


# -------------------------------------------------------------
# Figure 4.6: ToF Distance Sensor Response in Blind Spot
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=300)
distances = np.linspace(5, 50, 100)
# Detection threshold is 25 cm
detection_prob = 1 / (1 + np.exp((distances - 25) / 1.5))

ax.plot(distances, detection_prob * 100, color='#8E44AD', lw=2.5, label='Occluded Vehicle Detection Probability (%)')
ax.axvline(25, color='#E74C3C', linestyle='--', lw=1.8, label='Detection Cutoff Threshold (25.0 cm)')
ax.fill_between(distances, 0, detection_prob * 100, where=(distances <= 25), color='#D7BDE2', alpha=0.5, label='Vehicle Present Zone (Trigger Count)')
ax.fill_between(distances, 0, detection_prob * 100, where=(distances > 25), color='#EAEDED', alpha=0.5, label='Clear Lane Zone')

ax.set_title("VL53L0X Time-of-Flight (ToF) Blind Spot Detection Characteristic", fontsize=11, fontweight='bold')
ax.set_xlabel("Measured Target Distance (cm)", fontsize=9.5)
ax.set_ylabel("Vehicle Detection Confidence (%)", fontsize=9.5)
ax.set_xlim(5, 50)
ax.set_ylim(0, 105)
ax.grid(True, linestyle=':', alpha=0.6)
ax.legend(fontsize=8.5, loc='upper right')

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig4_6_tof_distance_response.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 4.6 generated")


# -------------------------------------------------------------
# Figure 4.7: Average Waiting Time Comparison
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.5, 4.5), dpi=300)

categories = ['Low Density\n(1-5 Veh)', 'Medium Density\n(6-10 Veh)', 'High Density\n(11-18 Veh)', 'Peak Congested\n(18+ Veh)']
fixed_times = [38.5, 52.0, 78.4, 112.5]
adaptive_times = [14.2, 24.6, 39.8, 56.2]

x = np.arange(len(categories))
width = 0.35

rects1 = ax.bar(x - width/2, fixed_times, width, label='Conventional Fixed-Time System', color='#E74C3C', edgecolor='black')
rects2 = ax.bar(x + width/2, adaptive_times, width, label='Proposed Adaptive Vision + IoT System', color='#2ECC71', edgecolor='black')

ax.set_ylabel('Average Vehicle Waiting Time (Seconds)', fontsize=9.5)
ax.set_title('Vehicle Waiting Time Reduction across Traffic Congestion Tiers', fontsize=11, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=9)
ax.legend(fontsize=9)
ax.grid(True, axis='y', linestyle=':', alpha=0.6)

# Labels on bars
for r in rects1:
    h = r.get_height()
    ax.annotate(f'{h:.1f}s', xy=(r.get_x() + r.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, fontweight='bold')
for r in rects2:
    h = r.get_height()
    ax.annotate(f'{h:.1f}s', xy=(r.get_x() + r.get_width()/2, h), xytext=(0, 3), textcoords="offset points", ha='center', fontsize=8, fontweight='bold', color='#145A32')

# Percentage reduction annotation
for i in range(len(categories)):
    diff = ((fixed_times[i] - adaptive_times[i]) / fixed_times[i]) * 100
    ax.text(x[i], max(fixed_times[i], adaptive_times[i]) + 10, f"-{diff:.1f}% Delays", ha='center', fontsize=8, fontweight='bold', color='#2E4053')

ax.set_ylim(0, 135)
plt.tight_layout()
fig.savefig(os.path.join(output_dir, "fig4_7_wait_time_comparison.png"), bbox_inches='tight')
plt.close(fig)
print("Figure 4.7 generated")


# -------------------------------------------------------------
# Figure SDG: Sustainable Development Goals
# -------------------------------------------------------------
fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10, 3.2), dpi=300)
for ax, (num, title, color, desc) in zip(
    [ax1, ax2, ax3],
    [
        ("9", "INDUSTRY, INNOVATION\n& INFRASTRUCTURE", "#F36D25", "Intelligent Vision &\nIoT Adaptive Junctions"),
        ("11", "SUSTAINABLE CITIES\n& COMMUNITIES", "#F99D26", "Reduced Congestion &\nEmergency Preemption"),
        ("13", "CLIMATE\nACTION", "#3F7E44", "Lower Idling Emissions &\nFuel Conservation")
    ]
):
    ax.axis('off')
    ax.add_patch(patches.Rectangle((0.05, 0.05), 0.9, 0.9, facecolor=color, edgecolor='none', transform=ax.transAxes))
    ax.text(0.15, 0.72, num, fontsize=24, fontweight='bold', color='white', transform=ax.transAxes)
    ax.text(0.15, 0.42, title, fontsize=8, fontweight='bold', color='white', transform=ax.transAxes, linespacing=1.1)
    ax.text(0.15, 0.18, desc, fontsize=7.5, color='white', transform=ax.transAxes, linespacing=1.1)

plt.tight_layout()
fig.savefig(os.path.join(output_dir, "sdg_goals_diagram.png"), bbox_inches='tight')
plt.close(fig)
print("SDG diagram generated")
