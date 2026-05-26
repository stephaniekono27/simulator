import streamlit as st
import requests
import uuid
from datetime import datetime, timezone
import os

API_URL = "https://api.voloridgehealth.com/health-score"
API_KEY = st.secrets.get("VOLORIDGE_API_KEY") or os.environ.get("VOLORIDGE_API_KEY")

st.set_page_config(
    page_title="VOLO Score Simulator",
    page_icon="🏥",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .score-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border-left: 5px solid #ccc;
    }
    .score-card.green { border-left-color: #28a745; }
    .score-card.yellow { border-left-color: #ffc107; }
    .score-card.red { border-left-color: #dc3545; }
    h1 { color: #1f4e79; }
</style>
""", unsafe_allow_html=True)


def inches_to_cm(total_inches):
    return total_inches * 2.54


def lbs_to_kg(lbs):
    return lbs * 0.453592


def score_tier(score, min_score, max_score):
    span = max_score - min_score
    if span == 0:
        return "yellow"
    normalized = (score - min_score) / span
    if normalized >= 0.66:
        return "green"
    elif normalized >= 0.33:
        return "yellow"
    return "red"


def tier_label(tier):
    return {"green": "✅ Good", "yellow": "⚠️ Fair", "red": "🔴 Needs Attention"}[tier]


def build_request(age, sex, height_cm, weight_kg, pack_years):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "scoring_event_metadata": {
            "event_id": f"sim_{uuid.uuid4().hex[:8]}",
            "event_asof_dtutc": now,
            "mode": "score",
        },
        "user_data": [
            {
                "uid_ext": "simulator_user",
                "predictors": [
                    {
                        "id": str(uuid.uuid4()),
                        "observation_code": "30525-0",
                        "value": str(age),
                        "unit": "a",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "observation_code": "8302-2",
                        "value": str(round(height_cm, 1)),
                        "unit": "cm",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "observation_code": "29463-7",
                        "value": str(round(weight_kg, 1)),
                        "unit": "kg",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "observation_code": "46098-0",
                        "value": sex.lower(),
                        "unit": "",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "observation_code": "64219-9",
                        "value": str(round(pack_years, 2)),
                        "unit": "pack/years",
                    },
                ],
            }
        ],
    }


def call_api(payload):
    headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
    return requests.post(API_URL, json=payload, headers=headers, timeout=30)


# ── UI ────────────────────────────────────────────────────────────────────────

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

    submitted = st.form_submit_button("Calculate My Health Scores", use_container_width=True, type="primary")


if submitted:
    height_cm = inches_to_cm(feet * 12 + extra_inches)
    weight_kg = lbs_to_kg(weight_lbs)
    pack_years = round(packs_per_day * years_smoked, 2) if smoker != "Never smoked" else 0.0

    payload = build_request(age, sex, height_cm, weight_kg, pack_years)

    with st.spinner("Calculating your health scores..."):
        try:
            response = call_api(payload)
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")
            st.stop()

    if response.status_code == 200:
        data = response.json()
        results = data.get("scoring_results", [])

        if not results or not results[0].get("data"):
            st.warning("No scores were returned. Please check your inputs and try again.")
            st.stop()

        disease_scores = results[0]["data"][0].get("disease_scores", [])

        st.markdown("---")
        st.subheader("Your Results")
        st.caption(f"Scored for a {age}-year-old {sex.lower()}, {feet}'{extra_inches}\", {weight_lbs} lbs")

        cols = st.columns(3)
        for i, ds in enumerate(disease_scores):
            name = ds.get("disease_name", "Unknown Condition")
            hs = ds.get("health_score", {})
            score = hs.get("health_score", 0)
            min_s = hs.get("min_score", 0)
            max_s = hs.get("max_score", 100)
            rr = ds.get("risk_ratios", {})
            risk_ratio = rr.get("risk_ratio")
            da = ds.get("disease_age", {})
            bio_age = da.get("disease_age")
            delta = da.get("disease_age_delta")
            percentile = ds.get("score_percentile")

            tier = score_tier(score, min_s, max_s)

            with cols[i % 3]:
                st.markdown(
                    f'<div class="score-card {tier}"><strong>{name}</strong><br>'
                    f'<span style="font-size:0.85rem;color:#555">{tier_label(tier)}</span></div>',
                    unsafe_allow_html=True,
                )
                st.metric("Health Score", f"{score:.1f}", f"out of {max_s:.0f}")

                if bio_age is not None and delta is not None:
                    direction = "older" if delta > 0 else "younger"
                    st.metric(
                        "Biological Age",
                        f"{bio_age:.1f} yrs",
                        f"{abs(delta):.1f} yrs {direction} than your age",
                        delta_color="inverse",
                    )

                if risk_ratio is not None:
                    risk_pct = (risk_ratio - 1) * 100
                    risk_label = f"{abs(risk_pct):.0f}% {'above' if risk_pct > 0 else 'below'} average"
                    st.metric("Risk vs. Average", f"{risk_ratio:.2f}x", risk_label, delta_color="inverse")

                if percentile is not None:
                    st.metric("Healthier Than", f"{percentile:.0f}% of peers")

                st.markdown("<br>", unsafe_allow_html=True)

    else:
        st.error(f"API returned an error ({response.status_code}):")
        st.code(response.text)
