# app.py
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests
from zones import zone_coords

# --------------------------------------
# CONFIG
st.set_page_config(layout="wide")

# --------------------------------------
# UI - SELECT ZONE
st.title("Bangkok Zone X Predictor")
zone = st.selectbox("เลือกเขตในกรุงเทพฯ", list(zone_coords.keys()))
lat, lon = zone_coords[zone]

# --------------------------------------
# API FETCH FUNCTIONS
@st.cache_data(ttl=1800)
def get_forecast(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,relative_humidity_2m_max,relative_humidity_2m_min"
        f"&timezone=auto&forecast_days=16"
    )
    res = requests.get(url)
    return res.json()

@st.cache_data(ttl=1800)
def get_historical(lat, lon, start_date, end_date):
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=temperature_2m_max,temperature_2m_min,relative_humidity_2m_max,relative_humidity_2m_min"
        f"&timezone=auto"
    )
    res = requests.get(url)
    return res.json()

# --------------------------------------
# X CALCULATION
@st.cache_data
def calc_x(t, rh):
    return 32.426272 - 0.622108 * t - 0.153707 * rh

def risk_level(x):
    if x >= 100: return "🛑 อันตรายมาก"
    elif x >= 80: return "⚠️ อันตราย"
    elif x >= 60: return "⚡️ ปานกลาง"
    elif x >= 40: return "🔹 ต่ำ"
    else: return "🟢 ปลอดภัย"

# --------------------------------------
# FETCH + PROCESS DATA

today = datetime.date.today()

# กำหนดช่วงย้อนหลัง -10 วันถึง -1 วัน
start_hist = today - datetime.timedelta(days=10)
end_hist = today - datetime.timedelta(days=1)

# ดึงข้อมูลย้อนหลัง
hist_data = get_historical(lat, lon, start_hist.isoformat(), end_hist.isoformat())

# ดึงข้อมูล forecast ล่วงหน้า (รวมวันนี้)
forecast_data = get_forecast(lat, lon)

# รวมข้อมูลย้อนหลังและข้อมูล forecast เข้าด้วยกัน
def merge_data(hist, forecast):
    combined = {
        "time": [],
        "temperature_2m_max": [],
        "temperature_2m_min": [],
        "relative_humidity_2m_max": [],
        "relative_humidity_2m_min": [],
    }

    for key in combined.keys():
        combined[key].extend(hist.get("daily", {}).get(key, []))
        combined[key].extend(forecast.get("daily", {}).get(key, []))
    return combined

combined_data = merge_data(hist_data, forecast_data)

if "time" in combined_data and len(combined_data["time"]) > 0:
    df = pd.DataFrame({
        "Date": pd.to_datetime(combined_data["time"]),
        "Temp (°C)": [(t1 + t2) / 2 for t1, t2 in zip(combined_data["temperature_2m_max"], combined_data["temperature_2m_min"])],
        "RH (%)": [(r1 + r2) / 2 for r1, r2 in zip(combined_data["relative_humidity_2m_max"], combined_data["relative_humidity_2m_min"])],
    })

    df["X Value"] = df.apply(lambda row: calc_x(row["Temp (°C)"], row["RH (%)"]), axis=1)
    df["Risk"] = df["X Value"].apply(risk_level)

    # กำหนดช่วงวันที่แสดง -10 ถึง +10 วัน จากวันนี้
    start_date = today - datetime.timedelta(days=10)
    end_date = today + datetime.timedelta(days=10)
    all_dates = pd.date_range(start=start_date, end=end_date)

    # รีindex dataframe ให้ตรงกับช่วงวันที่กำหนด (มี NaN สำหรับวันที่ไม่มีข้อมูล)
    df = df.set_index("Date").reindex(all_dates).reset_index().rename(columns={"index": "Date"})

    # สร้าง column header เป็น string วันที่
    df_cols = df.set_index("Date")["X Value"].T
    df_cols = df_cols.rename("X Value").to_frame().T
    df_cols.columns = [d.strftime("%d %b") for d in df_cols.columns]

    # แสดงค่า X ปัจจุบันเด่นๆ (ถ้ามีข้อมูล)
    if today in df["Date"].values:
        current_x = df[df["Date"] == today]["X Value"].values[0]
        st.markdown(f"""
        <div style='font-size:32px; font-weight:bold; margin-bottom:20px;'>
            ✨ วันที่ {today.strftime('%d %B %Y')} : ค่า X = {current_x:.2f} ({risk_level(current_x)})
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='font-size:32px; font-weight:bold; margin-bottom:20px;'>
            ✨ วันที่ {today.strftime('%d %B %Y')} : ไม่พบข้อมูล
        </div>
        """, unsafe_allow_html=True)

    # Render ตารางแนวนอนแบบเลื่อน
    st.markdown("""
    <style>
    .scroll-table {
        overflow-x: auto;
        background: #f9f9f9;
        border-radius: 12px;
        padding: 10px;
    }
    table.custom {
        border-collapse: separate;
        border-spacing: 0;
        font-size: 22px;
    }
    table.custom th, table.custom td {
        padding: 20px 30px;
        border: 1px solid #ccc;
        min-width: 100px;
        text-align: center;
    }
    table.custom th {
        background-color: #4a6c8b;
        color: white;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
    }
    table.custom td {
        background-color: white;
        color: black;
    }
    .cell-danger { background: #ffd6d6; }
    .cell-warning { background: #fff3cd; }
    .cell-safe { background: #d6f5d6; }
    .subtitle { font-size: 18px; color: gray; }
    </style>
    """, unsafe_allow_html=True)

    # ตกแต่งตามระดับความอันตราย
    html = "<div class='scroll-table'><table class='custom'><tr><th>Date</th>"
    for col in df_cols.columns:
        html += f"<th>{col}</th>"
    html += "</tr><tr><td><b>X value</b></td>"

    for val in df_cols.iloc[0]:
        label = risk_level(val)
        if "มาก" in label:
            style = "cell-danger"
        elif "อันตราย" in label:
            style = "cell-warning"
        elif "ปลอดภัย" in label:
            style = "cell-safe"
        else:
            style = ""
        if pd.isna(val):
            html += f"<td>—</td>"
        else:
            html += f"<td class='{style}'><div style='font-size:26px'>{val:.2f}</div><div class='subtitle'>{label}</div></td>"
    html += "</tr></table></div>"
    st.markdown(html, unsafe_allow_html=True)

else:
    st.error("ไม่สามารถดึงข้อมูลย้อนหลังหรือพยากรณ์จาก API ได้ กรุณาลองใหม่")
