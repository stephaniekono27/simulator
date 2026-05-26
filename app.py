import streamlit as st
import requests
import uuid
from datetime import datetime, timezone
import os
import plotly.graph_objects as go

API_URL = "https://api.voloridgehealth.com/health-score"
API_KEY = st.secrets.get("VOLORIDGE_API_KEY") or os.environ.get("VOLORIDGE_API_KEY")

SCORE_CATEGORIES = {
    "cardiovascular": ["cardiovascular", "cardiac", "heart", "coronary", "stroke", "vascular", "atrial", "arterial"],
    "metabolic": ["metabolic", "diabetes", "glucose", "insulin", "kidney", "renal", "liver", "thyroid", "obesity"],
    "longevity": ["longevity", "mortality", "life", "aging", "overall", "all-cause"],
}

UNIT_RANGES = {
    "mg/dL": (0.0, 500.0),
    "mmHg": (40.0, 200.0),
    "%": (0.0, 100.0),
    "mg/L": (0.0, 50.0),
    "IU/L": (0.0, 500.0),
    "g/dL": (0.0, 20.0),
    "umol/L": (0.0, 1000.0),
    "nmol/L": (0.0, 100.0),
    "mIU/L": (0.0, 100.0),
    "kg/m2": (10.0, 60.0),
    "mmol/L": (0.0, 30.0),
}

st.set_page_config(page_title="VOLO Score Simulator", page_icon="🏥", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    hr { margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)


def get_slider_range(value_str, unit):
    try:
        v = float(value_str)
    except (ValueError, TypeError):
        v = 0.0
    base_min, base_max = UNIT_RANGES.get(unit, (0.0, max(v * 3.0, 100.0)))
    actual_min = min(base_min, v * 0.5) if v > 0 else base_min
    actual_max = max(base_max, v * 2.0)
    if actual_min >= actual_max:
        actual_max = actual_min + 100.0
    return round(actual_min, 4), round(actual_max, 4)


def inches_to_cm(total_inches):
    return total_inches * 2.54


def lbs_to_kg(lbs):
    return lbs * 0.453592


def build_request(age, sex, height_cm, weight_kg, pack_years, extra_predictors=None):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    predictors = [
        {"id": str(uuid.uuid4()), "observation_code": "30525-0", "value": str(age), "unit": "a"},
        {"id": str(uuid.uuid4()), "observation_code": "8302-2", "value": str(round(height_cm, 1)), "unit": "cm"},
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


def call_api(payload):
    headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
    return requests.post(API_URL, json=payload, headers=headers, timeout=30)


def find_score(disease_scores, category):
    keywords = SCORE_CATEGORIES[category]
    for ds in disease_scores:
        name = ds.get("disease_name", "").lower()
        if any(kw in name for kw in keywords):
            return ds
    return None


def make_gauge(title, score, min_score, max_score):
    span = max_score - min_score or 1
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": title, "font": {"size": 15, "color": "#1f4e79"}},
        number={"font": {"size": 32, "color": "#1f4e79"}},
        gauge={
            "axis": {"range": [min_score, max_score], "tickwidth": 1},
            "bar": {"color": "#1f4e79", "thickness": 0.28},
            "bgcolor": "white",
            "steps": [
                {"range": [min_score, min_score + span * 0.33], "color": "#ffe0e0"},
                {"range": [min_score + span * 0.33, min_score + span * 0.66], "color": "#fff3cd"},
                {"range": [min_score + span * 0.66, max_score], "color": "#d4edda"},
            ],
        },
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10), paper_bgcolor="white")
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
                response = call_api(payload)
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")
                st.stop()

        if response.status_code == 200:
            data = response.json()
            results = data.get("scoring_results", [])
            if not results or not results[0].get("data"):
                st.warning("No scores were returned. Please check your inputs.")
                st.stop()

            scoring_predictors = results[0]["data"][0].get("scoring_predictors", [])
            biomarkers = []
            for p in scoring_predictors:
                if p.get("imputation_code", "GIVEN") != "GIVEN":
                    try:
                        v = float(p.get("value", 0))
                    except (ValueError, TypeError):
                        continue
                    unit = p.get("unit", "")
                    rng = get_slider_range(p.get("value", 0), unit)
                    biomarkers.append({
                        "code": p.get("predictor_code", ""),
                        "name": p.get("predictor_name") or p.get("predictor_code", "Unknown"),
                        "value": v,
                        "adjusted_value": v,
                        "unit": unit,
                        "is_real": False,
                        "min": rng[0],
                        "max": rng[1],
                    })

            st.session_state.api_response = data
            st.session_state.input_data = {
                "age": age, "sex": sex,
                "height_cm": height_cm, "weight_kg": weight_kg, "pack_years": pack_years,
            }
            st.session_state.biomarkers = biomarkers[:12]
            for i, bm in enumerate(biomarkers[:12]):
                st.session_state[f"slider_{i}"] = bm["value"]
                st.session_state[f"input_{i}"] = bm["value"]

            st.session_state.page = "results"
            st.rerun()
        else:
            st.error(f"API returned an error ({response.status_code}):")
            st.code(response.text)


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
                st.plotly_chart(
                    make_gauge(cat_label, hs.get("health_score", 0), hs.get("min_score", 0), hs.get("max_score", 100)),
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
        "Slide or type to adjust a value, then mark it as **Real** when you have an actual measurement."
    )

    biomarkers = st.session_state.biomarkers
    if not biomarkers:
        st.info("No imputed biomarkers were returned by the API.")
    else:
        h0, h1, h2, h3, h4 = st.columns([2.5, 3.5, 1.2, 1.0, 1.5])
        h0.markdown("**Biomarker**")
        h1.markdown("**Adjust**")
        h2.markdown("**Value**")
        h3.markdown("**Unit**")
        h4.markdown("**Status**")
        st.markdown("<hr style='margin:2px 0 10px 0'>", unsafe_allow_html=True)

        for i, bm in enumerate(biomarkers):
            is_real = bm.get("is_real", False)
            c0, c1, c2, c3, c4 = st.columns([2.5, 3.5, 1.2, 1.0, 1.5])

            with c0:
                icon = "🔵" if is_real else "⚪"
                st.markdown(f"{icon} **{bm['name']}**")

            with c1:
                st.slider(
                    f"s{i}",
                    min_value=float(bm["min"]),
                    max_value=float(bm["max"]),
                    value=float(st.session_state.get(f"slider_{i}", bm["adjusted_value"])),
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
                "value": str(round(bm["adjusted_value"], 4)),
                "unit": bm["unit"],
            }
            for bm in biomarkers if bm.get("is_real")
        ]
        payload = build_request(
            d["age"], d["sex"], d["height_cm"], d["weight_kg"], d["pack_years"],
            extra_predictors=extra,
        )
        with st.spinner("Recalculating..."):
            try:
                resp = call_api(payload)
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")
                st.stop()
        if resp.status_code == 200:
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
