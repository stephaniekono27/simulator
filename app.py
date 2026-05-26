import streamlit as st
import requests
import uuid
from datetime import datetime, timezone
import os
import math
import plotly.graph_objects as go

API_URL = "https://api.voloridgehealth.com/health-score"
API_KEY = st.secrets.get("VOLORIDGE_API_KEY") or os.environ.get("VOLORIDGE_API_KEY")

# Set to False once your API key is working
MOCK_MODE = True

# Ordered list of the 12 biomarkers to display
BIOMARKER_ORDER = [
    "29463-7",  # Weight
    "8480-6",   # Systolic BP
    "4548-4",   # HbA1c
    "2085-9",   # HDL
    "13457-7",  # LDL
    "1884-6",   # ApoB
    "718-7",    # Hemoglobin
    "788-0",    # RDW
    "6690-2",   # WBC
    "2160-0",   # Creatinine
    "33863-2",  # Cystatin C
    "1988-5",   # CRP
]

# Per-biomarker display config.
# to_display: multiply API value (in api_unit) to get display value
# to_api:     multiply display value to get API value
BIOMARKER_CONFIG = {
    "29463-7": {"name": "Weight",       "unit": "lbs",      "api_unit": "kg",        "to_display": 2.20462, "to_api": 0.453592, "min": 50.0,  "max": 600.0, "step": 1.0,  "default": 170.0},
    "8480-6":  {"name": "Systolic BP",  "unit": "mmHg",     "api_unit": "mmHg",      "to_display": 1.0,     "to_api": 1.0,      "min": 80.0,  "max": 200.0, "step": 1.0,  "default": 120.0},
    "4548-4":  {"name": "HbA1c",        "unit": "%",        "api_unit": "%",         "to_display": 1.0,     "to_api": 1.0,      "min": 4.0,   "max": 15.0,  "step": 0.1,  "default": 5.4},
    "2085-9":  {"name": "HDL",          "unit": "mg/dL",    "api_unit": "mg/dL",     "to_display": 1.0,     "to_api": 1.0,      "min": 20.0,  "max": 100.0, "step": 1.0,  "default": 52.0},
    "13457-7": {"name": "LDL",          "unit": "mg/dL",    "api_unit": "mg/dL",     "to_display": 1.0,     "to_api": 1.0,      "min": 30.0,  "max": 300.0, "step": 1.0,  "default": 118.0},
    "1884-6":  {"name": "ApoB",         "unit": "mg/dL",    "api_unit": "mg/dL",     "to_display": 1.0,     "to_api": 1.0,      "min": 40.0,  "max": 200.0, "step": 1.0,  "default": 85.0},
    "718-7":   {"name": "Hemoglobin",   "unit": "g/dL",     "api_unit": "g/dL",      "to_display": 1.0,     "to_api": 1.0,      "min": 8.0,   "max": 20.0,  "step": 0.1,  "default": 14.5},
    "788-0":   {"name": "RDW",          "unit": "%",        "api_unit": "%",         "to_display": 1.0,     "to_api": 1.0,      "min": 10.0,  "max": 25.0,  "step": 0.1,  "default": 13.2},
    "6690-2":  {"name": "WBC",          "unit": "10³/µL",   "api_unit": "10^3/uL",   "to_display": 1.0,     "to_api": 1.0,      "min": 2.0,   "max": 20.0,  "step": 0.1,  "default": 6.5},
    "2160-0":  {"name": "Creatinine",   "unit": "mg/dL",    "api_unit": "mg/dL",     "to_display": 1.0,     "to_api": 1.0,      "min": 0.4,   "max": 3.0,   "step": 0.01, "default": 0.9},
    "33863-2": {"name": "Cystatin C",   "unit": "mg/L",     "api_unit": "mg/L",      "to_display": 1.0,     "to_api": 1.0,      "min": 0.5,   "max": 3.0,   "step": 0.01, "default": 0.9},
    "1988-5":  {"name": "CRP",          "unit": "mg/L",     "api_unit": "mg/L",      "to_display": 1.0,     "to_api": 1.0,      "min": 0.1,   "max": 20.0,  "step": 0.1,  "default": 1.2},
}

SCORE_CATEGORIES = {
    "cardiovascular": ["cardiovascular", "cardiac", "heart", "coronary", "stroke", "vascular", "atrial", "arterial"],
    "metabolic": ["metabolic", "diabetes", "glucose", "insulin", "kidney", "renal", "liver", "thyroid", "obesity"],
    "longevity": ["longevity", "mortality", "life", "aging", "overall", "all-cause"],
}

st.set_page_config(page_title="VOLO Score Simulator", page_icon="🏥", layout="wide")
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    hr { margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)


# ── Mock data ─────────────────────────────────────────────────────────────────
def get_mock_response(weight_lbs=170.0):
    return {
        "scoring_results": [{
            "uid_ext": "simulator_user",
            "data": [{
                "scoring_predictors": [
                    {"predictor_code": "29463-7", "predictor_name": "Weight",      "value": str(round(weight_lbs * 0.453592, 1)), "unit": "kg",       "imputation_code": "GIVEN"},
                    {"predictor_code": "8480-6",  "predictor_name": "Systolic BP", "value": "122.0", "unit": "mmHg",     "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "4548-4",  "predictor_name": "HbA1c",       "value": "5.4",   "unit": "%",        "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "2085-9",  "predictor_name": "HDL",         "value": "52.0",  "unit": "mg/dL",    "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "13457-7", "predictor_name": "LDL",         "value": "118.0", "unit": "mg/dL",    "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "1884-6",  "predictor_name": "ApoB",        "value": "85.0",  "unit": "mg/dL",    "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "718-7",   "predictor_name": "Hemoglobin",  "value": "14.5",  "unit": "g/dL",     "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "788-0",   "predictor_name": "RDW",         "value": "13.2",  "unit": "%",        "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "6690-2",  "predictor_name": "WBC",         "value": "6.5",   "unit": "10^3/uL",  "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "2160-0",  "predictor_name": "Creatinine",  "value": "0.9",   "unit": "mg/dL",    "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "33863-2", "predictor_name": "Cystatin C",  "value": "0.9",   "unit": "mg/L",     "imputation_code": "SIDEWAYS"},
                    {"predictor_code": "1988-5",  "predictor_name": "CRP",         "value": "1.2",   "unit": "mg/L",     "imputation_code": "SIDEWAYS"},
                ],
                "disease_scores": [
                    {
                        "disease_name": "Cardiovascular Disease",
                        "health_score": {"health_score": 75.0, "min_score": 0.0, "max_score": 100.0},
                        "risk_ratios": {"your_risk_frac": 0.08, "peer_risk_frac": 0.10, "risk_ratio": 0.85},
                        "disease_age": {"disease_age": 43.5, "disease_age_delta": -1.5},
                        "score_percentile": 65.0,
                    },
                    {
                        "disease_name": "Metabolic Disease",
                        "health_score": {"health_score": 68.0, "min_score": 0.0, "max_score": 100.0},
                        "risk_ratios": {"your_risk_frac": 0.12, "peer_risk_frac": 0.10, "risk_ratio": 1.10},
                        "disease_age": {"disease_age": 46.8, "disease_age_delta": 1.8},
                        "score_percentile": 48.0,
                    },
                    {
                        "disease_name": "Longevity",
                        "health_score": {"health_score": 80.0, "min_score": 0.0, "max_score": 100.0},
                        "risk_ratios": {"your_risk_frac": 0.06, "peer_risk_frac": 0.09, "risk_ratio": 0.75},
                        "disease_age": {"disease_age": 42.0, "disease_age_delta": -3.0},
                        "score_percentile": 72.0,
                    },
                ],
            }],
        }],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────
def inches_to_cm(total_inches):
    return total_inches * 2.54


def lbs_to_kg(lbs):
    return lbs * 0.453592


def build_biomarker_list(scoring_predictors, weight_lbs):
    predictor_map = {p["predictor_code"]: p for p in scoring_predictors}
    biomarkers = []
    for code in BIOMARKER_ORDER:
        cfg = BIOMARKER_CONFIG[code]
        p = predictor_map.get(code)
        if p:
            try:
                api_val = float(p["value"])
            except (ValueError, TypeError):
                api_val = cfg["default"] * cfg["to_api"]
            display_val = round(api_val * cfg["to_display"], 4)
        else:
            display_val = cfg["default"]
        # For weight, use the actual input value (already in lbs)
        if code == "29463-7":
            display_val = round(weight_lbs, 1)
        biomarkers.append({
            "code": code,
            "name": cfg["name"],
            "value": display_val,
            "adjusted_value": display_val,
            "unit": cfg["unit"],
            "api_unit": cfg["api_unit"],
            "to_api": cfg["to_api"],
            "is_real": False,
            "min": cfg["min"],
            "max": cfg["max"],
            "step": cfg["step"],
        })
    return biomarkers


def build_request(age, sex, height_cm, weight_kg, pack_years, extra_predictors=None):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    predictors = [
        {"id": str(uuid.uuid4()), "observation_code": "30525-0", "value": str(age), "unit": "a"},
        {"id": str(uuid.uuid4()), "observation_code": "8302-2",  "value": str(round(height_cm, 1)), "unit": "cm"},
        {"id": str(uuid.uuid4()), "observation_code": "29463-7", "value": str(round(weight_kg, 1)), "unit": "kg"},
        {"id": str(uuid.uuid4()), "observation_code": "46098-0", "value": sex.lower(), "unit": ""},
        {"id": str(uuid.uuid4()), "observation_code": "64219-9", "value": str(round(pack_years, 2)), "unit": "pack/years"},
    ]
    if extra_predictors:
        predictors.extend(extra_predictors)
    return {
        "scoring_event_metadata": {
            "event_id": f"sim_{uuid.uuid4().hex[:8]}",
            "event_asof_dtutc": now,
            "mode": "score",
        },
        "user_data": [{"uid_ext": "simulator_user", "predictors": predictors}],
    }


def call_api(payload, weight_lbs=170.0):
    if MOCK_MODE:
        return get_mock_response(weight_lbs=weight_lbs)
    headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
    return requests.post(API_URL, json=payload, headers=headers, timeout=30)


def find_score(disease_scores, category):
    keywords = SCORE_CATEGORIES[category]
    for ds in disease_scores:
        if any(kw in ds.get("disease_name", "").lower() for kw in keywords):
            return ds
    return None


def make_gauge(title, score, min_score, max_score, bio_age=None, age_delta=None):
    span = max_score - min_score or 1
    p1 = min_score + span * 0.20
    p2 = min_score + span * 0.40
    p3 = min_score + span * 0.60
    p4 = min_score + span * 0.80

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={
            "text": (
                "<span style='font-weight:300;font-size:1em'>volo</span>"
                "<span style='font-weight:700;text-decoration:underline;font-size:1em'>SCORES</span>"
                f"<br><span style='font-size:0.72em;color:#555;font-weight:400'>{title}</span>"
            ),
            "font": {"family": "Arial", "size": 16},
        },
        number={"font": {"size": 44, "color": "#212121", "family": "Arial"}, "valueformat": ".0f"},
        gauge={
            "axis": {
                "range": [min_score, max_score],
                "tickvals": [min_score, max_score],
                "ticktext": [f"{int(min_score)}", f"{int(max_score)}"],
                "tickfont": {"size": 10, "color": "#555"},
                "tickwidth": 1,
                "tickcolor": "#555",
            },
            "bar": {"color": "#111111", "thickness": 0.04},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [min_score, p1], "color": "#b71c1c"},
                {"range": [p1,         p2], "color": "#ef5350"},
                {"range": [p2,         p3], "color": "#bdbdbd"},
                {"range": [p3,         p4], "color": "#66bb6a"},
                {"range": [p4, max_score],  "color": "#1b5e20"},
            ],
        },
    ))

    # Zone labels positioned along the arc
    cx, cy, r = 0.5, 0.21, 0.35
    zone_labels = [
        (162, "Poor",      "white"),
        (126, "Marginal",  "white"),
        (90,  "Average",   "#333333"),
        (54,  "Good",      "white"),
        (18,  "Excellent", "white"),
    ]
    for angle_deg, label, color in zone_labels:
        rad = math.radians(angle_deg)
        fig.add_annotation(
            x=cx + r * math.cos(rad),
            y=cy + r * math.sin(rad),
            text=label,
            showarrow=False,
            font={"size": 8, "color": color, "family": "Arial"},
            xref="paper", yref="paper",
        )

    # VoloAge below the score number
    if bio_age is not None and age_delta is not None:
        sign = "+" if age_delta > 0 else ""
        fig.add_annotation(
            x=0.5, y=0.06,
            text=f"VoloAge™: {bio_age:.0f} | {sign}{age_delta:.0f}",
            showarrow=False,
            font={"size": 11, "color": "#555555", "family": "Arial"},
            xref="paper", yref="paper",
        )

    fig.update_layout(
        height=270,
        margin=dict(l=30, r=30, t=80, b=50),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return fig


def on_slider_change(idx):
    val = st.session_state[f"slider_{idx}"]
    st.session_state[f"input_{idx}"] = val
    st.session_state.biomarkers[idx]["adjusted_value"] = val


def on_input_change(idx):
    val = st.session_state[f"input_{idx}"]
    st.session_state[f"slider_{idx}"] = val
    st.session_state.biomarkers[idx]["adjusted_value"] = val


# ── Page 1: Input ─────────────────────────────────────────────────────────────
def show_input_page():
    st.image("logo.png", width=280)
    if MOCK_MODE:
        st.info("Demo mode — showing sample data. No API connection required.")
    st.markdown("## VOLO Score Simulator")
    st.markdown("Enter your basic information below to receive your personalized VOLO Scores.")

    with st.form("health_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("About You")
            age = st.number_input("Age", min_value=18, max_value=100, value=45)
            sex = st.selectbox("Sex", ["Male", "Female"])
            feet = st.number_input("Height — feet", min_value=3, max_value=8, value=5)
            extra_inches = st.number_input("Height — inches", min_value=0, max_value=11, value=10)
            weight_lbs = st.number_input("Weight (lbs)", min_value=50, max_value=600, value=170)

        with col2:
            st.subheader("Smoking History")
            smoker = st.selectbox(
                "Have you ever smoked cigarettes?",
                ["Never smoked", "Current smoker", "Former smoker"],
            )
            packs_per_day = 0.0
            years_smoked = 0
            if smoker != "Never smoked":
                packs_per_day = st.number_input(
                    "Packs per day (on average)", min_value=0.1, max_value=10.0, value=1.0, step=0.1
                )
                years_smoked = st.number_input(
                    "Number of years smoked", min_value=1, max_value=80, value=10
                )

        submitted = st.form_submit_button(
            "Calculate My VOLO Scores", use_container_width=True, type="primary"
        )

    if submitted:
        height_cm = inches_to_cm(feet * 12 + extra_inches)
        weight_kg = lbs_to_kg(weight_lbs)
        pack_years = round(packs_per_day * years_smoked, 2) if smoker != "Never smoked" else 0.0
        payload = build_request(age, sex, height_cm, weight_kg, pack_years)

        with st.spinner("Calculating your VOLO Scores..."):
            try:
                response = call_api(payload, weight_lbs=float(weight_lbs))
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")
                st.stop()

        if MOCK_MODE:
            data = response
        elif response.status_code == 200:
            data = response.json()
        else:
            st.error(f"API returned an error ({response.status_code}):")
            st.code(response.text)
            st.stop()

        results = data.get("scoring_results", [])
        if not results or not results[0].get("data"):
            st.warning("No scores were returned. Please check your inputs.")
            st.stop()

        scoring_predictors = results[0]["data"][0].get("scoring_predictors", [])
        biomarkers = build_biomarker_list(scoring_predictors, float(weight_lbs))

        st.session_state.api_response = data
        st.session_state.input_data = {
            "age": age, "sex": sex,
            "height_cm": height_cm, "weight_kg": weight_kg,
            "weight_lbs": float(weight_lbs), "pack_years": pack_years,
        }
        st.session_state.biomarkers = biomarkers
        for i, bm in enumerate(biomarkers):
            st.session_state[f"slider_{i}"] = bm["value"]
            st.session_state[f"input_{i}"] = bm["value"]

        st.session_state.page = "results"
        st.rerun()


# ── Page 2: Results ───────────────────────────────────────────────────────────
def show_results_page():
    st.image("logo.png", width=280)

    if st.button("← Start Over"):
        for key in ["api_response", "input_data", "biomarkers"]:
            st.session_state.pop(key, None)
        st.session_state.page = "input"
        st.rerun()

    results = st.session_state.api_response.get("scoring_results", [])
    disease_scores = results[0]["data"][0].get("disease_scores", [])

    # ── Gauges ─────────────────────────────────────────────────────────────
    st.markdown("### Your VOLO Scores")
    for col, (cat_key, cat_label) in zip(
        st.columns(3),
        [
            ("cardiovascular", "Cardiovascular VOLO Score"),
            ("metabolic", "Metabolic VOLO Score"),
            ("longevity", "Longevity VOLO Score"),
        ],
    ):
        ds = find_score(disease_scores, cat_key)
        with col:
            if ds:
                hs = ds.get("health_score", {})
                da = ds.get("disease_age", {})
                st.plotly_chart(
                    make_gauge(
                        cat_label,
                        hs.get("health_score", 0),
                        hs.get("min_score", 0),
                        hs.get("max_score", 100),
                        bio_age=da.get("disease_age"),
                        age_delta=da.get("disease_age_delta"),
                    ),
                    use_container_width=True,
                    key=f"gauge_{cat_key}",
                )
            else:
                st.markdown(f"**{cat_label}**")
                st.info("Score not available")

    # ── Biomarker sliders ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Your Biomarkers")
    st.caption(
        "These values were estimated from your basic information. "
        "Slide or type to adjust, then mark as **Real** when you have an actual measurement."
    )

    biomarkers = st.session_state.biomarkers
    h0, h1, h2, h3, h4 = st.columns([2.2, 3.8, 1.2, 1.0, 1.5])
    h0.markdown("**Biomarker**")
    h1.markdown("**Adjust**")
    h2.markdown("**Value**")
    h3.markdown("**Unit**")
    h4.markdown("**Status**")
    st.markdown("<hr style='margin:2px 0 10px 0'>", unsafe_allow_html=True)

    for i, bm in enumerate(biomarkers):
        is_real = bm.get("is_real", False)
        c0, c1, c2, c3, c4 = st.columns([2.2, 3.8, 1.2, 1.0, 1.5])

        with c0:
            icon = "🔵" if is_real else "⚪"
            st.markdown(f"{icon} **{bm['name']}**")

        with c1:
            st.slider(
                f"s{i}",
                min_value=float(bm["min"]),
                max_value=float(bm["max"]),
                value=float(st.session_state.get(f"slider_{i}", bm["adjusted_value"])),
                step=float(bm["step"]),
                label_visibility="collapsed",
                key=f"slider_{i}",
                on_change=on_slider_change,
                args=(i,),
            )

        with c2:
            st.number_input(
                f"n{i}",
                min_value=float(bm["min"]),
                max_value=float(bm["max"]),
                value=float(st.session_state.get(f"input_{i}", bm["adjusted_value"])),
                step=float(bm["step"]),
                label_visibility="collapsed",
                key=f"input_{i}",
                on_change=on_input_change,
                args=(i,),
            )

        with c3:
            st.markdown(f"<div style='padding-top:8px'><small>{bm['unit']}</small></div>", unsafe_allow_html=True)

        with c4:
            if is_real:
                if st.button("✅ Real", key=f"real_{i}", type="primary"):
                    st.session_state.biomarkers[i]["is_real"] = False
                    st.rerun()
            else:
                if st.button("Set as Real", key=f"real_{i}"):
                    st.session_state.biomarkers[i]["is_real"] = True
                    st.rerun()

    # ── Recalculate ────────────────────────────────────────────────────────
    st.markdown("---")
    real_count = sum(1 for bm in biomarkers if bm.get("is_real"))
    if real_count:
        st.caption(f"{real_count} biomarker(s) marked as Real will be used to recalculate your scores.")

    if st.button("Recalculate VOLO Scores", type="primary", use_container_width=True):
        d = st.session_state.input_data
        extra = [
            {
                "id": str(uuid.uuid4()),
                "observation_code": bm["code"],
                "value": str(round(bm["adjusted_value"] * bm["to_api"], 4)),
                "unit": bm["api_unit"],
            }
            for bm in biomarkers if bm.get("is_real")
        ]
        payload = build_request(
            d["age"], d["sex"], d["height_cm"], d["weight_kg"], d["pack_years"],
            extra_predictors=extra,
        )
        with st.spinner("Recalculating..."):
            try:
                resp = call_api(payload, weight_lbs=d.get("weight_lbs", 170.0))
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")
                st.stop()

        if MOCK_MODE:
            st.session_state.api_response = resp
            st.rerun()
        elif resp.status_code == 200:
            st.session_state.api_response = resp.json()
            st.rerun()
        else:
            st.error(f"API error ({resp.status_code}): {resp.text}")


# ── Main ───────────────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "input"

if st.session_state.page == "input":
    show_input_page()
else:
    show_results_page()
