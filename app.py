import streamlit as st
from google import genai
from google.genai import types
import time
import json
import pandas as pd
import io

# Page config
st.set_page_config(
    page_title="Civic Infrastructure Issue Reporter",
    page_icon="🏙️",
    layout="wide"
)

# Initialize GenAI Client securely from st.secrets
if "GEMINI_API_KEY" in st.secrets:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("GEMINI_API_KEY not found in Streamlit secrets. Please check your .streamlit/secrets.toml file.")
    st.stop()

# Initialize session state for reports if not already present
if "reports" not in st.session_state:
    st.session_state.reports = [
        {
            "id": 1,
            "category": "Pothole",
            "severity_score": 8,
            "summary": "Large deep pothole on main road causing hazard to two-wheelers.",
            "latitude": 28.5843,
            "longitude": 77.4411,
            "status": "Open",
            "image": None
        },
        {
            "id": 2,
            "category": "Streetlight",
            "severity_score": 6,
            "summary": "Non-functional street light leaving the corner dark at night.",
            "latitude": 28.5850,
            "longitude": 77.4420,
            "status": "Open",
            "image": None
        }
    ]

st.title("🏙️ Civic Infrastructure Issue Reporter")
st.markdown("Report street issues, potholes, and hazards for fast municipal response.")

# --- SIDEBAR ROLE ACCESS CONTROL ---
st.sidebar.title("Portal Access")
is_admin = st.sidebar.checkbox("🔒 Login as Administrator", value=False)

# Dynamically set tabs based on whether Admin Mode is active
if is_admin:
    tab_report, tab_map, tab_admin = st.tabs(["📝 Report Issue", "🗺️ Public Map", "🛡️ Admin Panel"])
else:
    tab_report, tab_map = st.tabs(["📝 Report Issue", "🗺️ Public Map"])

with tab_report:
    st.subheader("Submit a New Infrastructure Issue")
    
    uploaded_file = st.file_uploader("Upload image of the issue", type=["jpg", "jpeg", "png"])
    
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=28.5843, format="%.4f")
    with col2:
        lon = st.number_input("Longitude", value=77.4411, format="%.4f")
        
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Issue Photo", width=350)
        
    if st.button("Analyze & Submit Report"):
        if uploaded_file is not None:
            with st.spinner("AI is analyzing the infrastructure issue..."):
                
                models_to_try = [
                    'gemini-3.5-flash-lite',
                    'gemini-2.5-flash-lite',
                    'gemini-3.8-flash',
                    'gemini-4-hydrogen'
                ] 
                
                response = None
                for model_name in models_to_try:
                    for attempt in range(2):
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=[
                                    types.Part.from_bytes(
                                        data=uploaded_file.getvalue(),
                                        mime_type=uploaded_file.type,
                                    ),
                                    "Analyze this street infrastructure photo. Return ONLY valid JSON with keys: 'category' (Pothole, Streetlight, Water Leak, or Other), 'severity_score' (integer 1-10, where 10 is immediate hazard), and 'summary' (short 1-sentence description)."
                                ],
                                config=types.GenerateContentConfig(response_mime_type="application/json")
                            )
                            break
                        except Exception as e:
                            err = str(e)
                            if "503" in err:
                                time.sleep(2 * (attempt + 1))
                                continue
                            elif "404" in err or "429" in err:
                                break
                            else:
                                raise e
                    if response is not None:
                        break

                if response is None:
                    st.error("All models are currently overloaded (503). Wait 15 seconds and submit again.")
                    st.stop()
                
                try:
                    result_data = json.loads(response.text)
                except Exception:
                    text = response.text.strip()
                    if text.startswith("```json"):
                        text = text[7:]
                    if text.endswith("```"):
                        text = text[:-3]
                    result_data = json.loads(text.strip())
                
                new_report = {
                    "id": len(st.session_state.reports) + 1,
                    "category": result_data.get("category", "Other"),
                    "severity_score": int(result_data.get("severity_score", 5)),
                    "summary": result_data.get("summary", "No description provided."),
                    "latitude": lat,
                    "longitude": lon,
                    "status": "Open",
                    "image": uploaded_file.getvalue()
                }
                
                st.session_state.reports.append(new_report)
                st.success("Report successfully analyzed, saved, and submitted!")
                time.sleep(1)
                st.rerun()
        else:
            st.warning("Please upload an image first.")

with tab_map:
    st.subheader("Live Issue Map")
    if st.session_state.reports:
        df_map = pd.DataFrame(st.session_state.reports)
        if "image" in df_map.columns:
            df_map = df_map.drop(columns=["image"])
        st.map(df_map, latitude="latitude", longitude="longitude", size="severity_score")
    else:
        st.info("No reports available yet.")

# Admin Panel tab only exists when is_admin is True
if is_admin:
    with tab_admin:
        st.subheader("Admin Resolution Panel")
        if st.session_state.reports:
            df_admin = pd.DataFrame(st.session_state.reports)
            if "image" in df_admin.columns:
                df_admin = df_admin.drop(columns=["image"])
            df_admin = df_admin.sort_values(by="severity_score", ascending=False)
            st.dataframe(df_admin, use_container_width=True)
            
            report_ids = [r["id"] for r in st.session_state.reports if r["status"] == "Open"]
            if report_ids:
                selected_id = st.selectbox("Select Issue ID to Resolve", report_ids)
                
                selected_report = next((r for r in st.session_state.reports if r["id"] == selected_id), None)
                if selected_report and selected_report.get("image") is not None:
                    st.image(io.BytesIO(selected_report["image"]), caption=f"Issue #{selected_id} Evidence", width=350)
                else:
                    st.info("No photo attached to this report (Sample IDs 1 & 2 do not have images).")
                    
                if st.button("Mark as Resolved"):
                    for r in st.session_state.reports:
                        if r["id"] == selected_id:
                            r["status"] = "Resolved"
                    st.success(f"Issue #{selected_id} marked as Resolved!")
                    st.rerun()
            else:
                st.success("All reported issues have been resolved!")
        else:
            st.info("No records in the admin panel.")
