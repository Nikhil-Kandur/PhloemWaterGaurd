import streamlit as st
import time
import yaml
import pandas as pd
from datetime import datetime, timedelta
from modules.data_source import DataSource
from modules.notifier import TelegramNotifier
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Phloem WaterGuard Dashboard", layout="wide", page_icon="💧")

# --- LOAD CONFIG & STATE ---
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    st.error("❌ config.yaml not found!")
    st.stop()

# Initialize Global Modules
if 'source' not in st.session_state:
    st.session_state.source = DataSource(mode=config['system']['mode'])
if 'notifier' not in st.session_state:
    st.session_state.notifier = TelegramNotifier()

# Initialize State Variables
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'Flow', 'Level'])
if 'event_log' not in st.session_state:
    st.session_state.event_log = pd.DataFrame(columns=['Timestamp', 'Event', 'Flow Rate', 'Total Waste'])
if 'total_leak_vol' not in st.session_state: st.session_state.total_leak_vol = 0.0
if 'night_violation_count' not in st.session_state: st.session_state.night_violation_count = 0
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'last_security_state' not in st.session_state: st.session_state.last_security_state = "ARMED"

# --- SIDEBAR CONTROLS ---
st.sidebar.title("🔧 Controls")

# 1. Start/Stop Monitoring
if not st.session_state.is_running:
    if st.sidebar.button("▶️ START MONITORING", type="primary"):
        st.session_state.is_running = True
        st.rerun()
else:
    if st.sidebar.button("⏹️ STOP MONITORING", type="secondary"):
        st.session_state.is_running = False
        st.rerun()

st.sidebar.markdown("---")

# 2. System Security (ARMED / DISARMED)
st.sidebar.subheader("🛡️ Security & Reset")
security_state = st.sidebar.radio("Mode", ["ARMED", "DISARMED"], index=0)
is_armed = (security_state == "ARMED")

# STATE CHANGE LOGIC
if security_state != st.session_state.last_security_state:
    st.session_state.last_security_state = security_state
    if not is_armed:
        st.session_state.source.send_command("STOP_ALL")
        st.toast("System DISARMED: Pump Stopped, Valve Closed.", icon="🔒")
    else:
        st.session_state.source.send_command("AUTO_MODE")
        st.toast("System ARMED: Auto-Logic Active.", icon="🛡️")

# 3. MANUAL OVERRIDES
st.sidebar.markdown("---")
st.sidebar.subheader("🔧 Valve Control")

c1, c2 = st.sidebar.columns(2)
if c1.button("OPEN VALVE", disabled=is_armed):
    st.session_state.source.send_command("OPEN_VALVE")
    st.toast("Manual Command: Valve OPEN", icon="🚰")

if c2.button("CLOSE VALVE", disabled=is_armed):
    st.session_state.source.send_command("CLOSE_VALVE")
    st.toast("Manual Command: Valve CLOSED", icon="🚫")

if is_armed:
    st.sidebar.caption("⚠️ Disarm system to enable manual control.")

st.sidebar.markdown("---")

# 4. Night Mode Rules
st.sidebar.subheader("🌙 Night Mode Rules")
night_start = st.sidebar.slider("Night Mode Start (Hr)", 0, 23, config['thresholds']['night_start'])
night_end = st.sidebar.slider("Night Mode End (Hr)", 0, 23, config['thresholds']['night_end'])


st.sidebar.markdown("---")

# 5. Simulation Speed
st.sidebar.subheader("⏩ Simulation Speed")
time_speed = st.sidebar.slider("Speed Factor (x)", 1, 3600, 1)
sim_hour_start = st.sidebar.slider("Set Clock Start Hour", 0, 23, datetime.now().hour)


st.sidebar.markdown("---")
if st.sidebar.button("❌ SHUTDOWN SYSTEM", type="primary"):
    st.toast("System Shutting Down...", icon="🔌")
    time.sleep(1)
    os._exit(0)
# --- MAIN DASHBOARD LAYOUT ---

# HEADER ROW
col_head_1, col_head_2 = st.columns([3, 1])
with col_head_1:
    st.title("💧 Phloem System")
with col_head_2:
    clock_metric = st.empty()

# METRICS ROW
kpi_tank, kpi_flow, kpi_waste, kpi_status = st.columns(4)
tank_metric = kpi_tank.empty()
flow_metric = kpi_flow.empty()
waste_metric = kpi_waste.empty()
status_metric = kpi_status.empty()

# ALERT BANNER
alert_banner = st.empty()

# GRAPHS
st.subheader("🌊 Real-Time Flow Rate")
flow_chart_place = st.empty()

st.subheader("🛢️ Reservoir Level")
level_chart_place = st.empty()

# --- ANALYTICS LOG SETUP (OUTSIDE LOOP TO PREVENT CRASH) ---
st.markdown("---")
st.subheader("📋 Event Analytics Log")

# Create the Expander ONCE
with st.expander("View Event Log Details", expanded=False):
    # Create a placeholder INSIDE the expander
    log_table_placeholder = st.empty()

    # Download Button (Safe here because it's outside the loop)
    if 'event_log' in st.session_state and not st.session_state.event_log.empty:
        csv = st.session_state.event_log.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Report (CSV)", csv, "leak_report.csv", "text/csv")

# --- MAIN EXECUTION LOOP ---
if st.session_state.is_running:
    if 'virtual_time' not in st.session_state:
        st.session_state.virtual_time = datetime.now().replace(hour=sim_hour_start, minute=0, second=0)

    while st.session_state.is_running:
        # A. Advance Time
        st.session_state.virtual_time += timedelta(seconds=time_speed)
        curr_time_str = st.session_state.virtual_time.strftime("%H:%M:%S")
        curr_hour = st.session_state.virtual_time.hour

        # B. Get Sensor Data
        flow, leak_flag, level = st.session_state.source.get_reading()

        # C. Logic
        violation_type = "NONE"

        if is_armed:
            is_night = False
            if night_start == night_end:
                is_night = True
            elif night_start > night_end:
                if curr_hour >= night_start or curr_hour < night_end: is_night = True
            else:
                if night_start <= curr_hour < night_end: is_night = True

            if leak_flag == 1:
                violation_type = "CRITICAL"
            elif is_night and flow > 0.5:
                violation_type = "NIGHT_LEAK"
                st.session_state.night_violation_count += 1
                waste_added = (flow / 60.0) * time_speed
                st.session_state.total_leak_vol += waste_added

        # D. Update UI Metrics
        clock_metric.metric("Time", curr_time_str)
        tank_metric.metric("Tank Level", f"{level}%")
        flow_metric.metric("Flow Rate", f"{flow:.2f} L/m")
        waste_metric.metric("Water Wasted", f"{st.session_state.total_leak_vol:.1f} L")

        if not is_armed:
            status_metric.info("DISARMED")
            alert_banner.info("🔧 SYSTEM DISARMED: Manual Control Enabled")
        elif violation_type == "CRITICAL":
            status_metric.error("LEAK DETECTED")
            alert_banner.error(f"🚨 CRITICAL PIPE FAILURE! Flow: {flow} L/m")
        elif violation_type == "NIGHT_LEAK":
            status_metric.warning("NIGHT USAGE")
            alert_banner.warning(f"🌙 UNAUTHORIZED NIGHT USAGE! ({curr_time_str})")
        else:
            status_metric.success("ARMED")
            alert_banner.empty()

        # E. Notifications
        if violation_type != "NONE" and is_armed:
            now = time.time()
            if 'last_alert' not in st.session_state or (now - st.session_state.last_alert > 60):
                msg = f"⚠️ ALERT: {violation_type} | Time: {curr_time_str} | Flow: {flow:.1f} L/m"
                st.session_state.notifier.send_alert(msg)
                st.session_state.last_alert = now
                st.toast("Notification Sent!", icon="📱")

        # F. Update Graphs
        new_row = pd.DataFrame({'Time': [curr_time_str], 'Flow': [flow], 'Level': [level]})
        st.session_state.history = pd.concat([st.session_state.history, new_row], ignore_index=True).tail(50)

        flow_chart_place.line_chart(st.session_state.history['Flow'])
        level_chart_place.area_chart(st.session_state.history['Level'])

        # --- UPDATE ANALYTICS LOG (Inside Loop) ---
        if violation_type != "NONE" and is_armed:
            # Check for duplicates or cooldown
            if st.session_state.event_log.empty or \
                    st.session_state.event_log.iloc[0]['Event'] != violation_type or \
                    (datetime.strptime(curr_time_str, "%H:%M:%S") - datetime.strptime(
                        st.session_state.event_log.iloc[0]['Timestamp'], "%H:%M:%S")).seconds > 60:
                new_event = pd.DataFrame([{
                    'Timestamp': curr_time_str,
                    'Event': violation_type,
                    'Flow Rate': f"{flow} L/m",
                    'Total Waste': f"{st.session_state.total_leak_vol:.2f} L"
                }])
                st.session_state.event_log = pd.concat([new_event, st.session_state.event_log], ignore_index=True)

        # Update the Table Visuals (Using the placeholder created outside)
        log_table_placeholder.dataframe(st.session_state.event_log, use_container_width=True)

        time.sleep(1.0)

        if not st.session_state.is_running:
            break
else:
    st.info("System is STOPPED. Click 'START MONITORING' to begin.")