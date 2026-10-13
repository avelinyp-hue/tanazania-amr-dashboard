from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Tanzania AMR Dashboard", page_icon="🧫", layout="wide")

# ---------- STYLE (medical blue and white) ----------
# Chart colors (page colors are in style.css)
NAVY = "#0A2540"
BLUE = "#0B5FA5"
TEAL = "#1AA6B7"
LIGHT = "#EAF3FB"
PALETTE = [BLUE, TEAL, NAVY, "#6FA8DC", "#F2994A", "#8E6BBF", "#2E9E6B", "#C0392B"]

# CSS lives in style.css (same folder as app.py)
CSS_FILE = Path(__file__).parent / "style.css"
if CSS_FILE.exists():
    st.markdown("<style>" + CSS_FILE.read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)


def section(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def style_fig(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font=dict(color=NAVY),
        margin=dict(l=10, r=10, t=30, b=10),
        legend_title_text="",
    )
    return fig


# ---------- DATA ----------
# tanzania_amr_data.csv must be in the SAME folder as app.py
DATA_FILE = Path(__file__).parent / "tanzania_amr_data.csv"


@st.cache_data
def load_data(file_version):
    df = pd.read_csv(DATA_FILE)
    df = df.dropna(subset=["tested", "resistant"])
    df = df[df["tested"] > 0]
    df["year"] = df["year"].astype(int)
    return df


def summarise(data, by):
    """Resistance % = total resistant / total tested (weighted, not a simple average)."""
    out = data.groupby(by, as_index=False).agg(
        resistant=("resistant", "sum"), tested=("tested", "sum")
    )
    out["resistance_pct"] = out["resistant"] / out["tested"] * 100
    return out


if not DATA_FILE.exists():
    st.error(f"File not found: {DATA_FILE}. Put tanzania_amr_data.csv next to app.py.")
    st.stop()

df = load_data(DATA_FILE.stat().st_mtime)

# ---------- FILTERS ----------
st.sidebar.header("Filters")

pathogen = st.sidebar.selectbox("Pathogen", sorted(df["pathogen_group"].unique()))
d1 = df[df["pathogen_group"] == pathogen]

drug_options = sorted(d1["drug"].unique())
drugs = st.sidebar.multiselect("Antibiotics", drug_options, default=drug_options)

region_options = sorted(d1["region"].unique())
regions = st.sidebar.multiselect("Regions", region_options, default=region_options)

min_tested = st.sidebar.number_input(
    "Minimum isolates tested", min_value=0, value=10, step=5,
    help="Hides very small samples, which give unreliable percentages.",
)

filtered = d1[
    d1["drug"].isin(drugs) & d1["region"].isin(regions) & (d1["tested"] >= min_tested)
]

# ---------- HEADER ----------
st.markdown(
    """
<div class="hero">
  <h1>🧫 Antimicrobial Resistance in Tanzania, by Region</h1>
  <p>Data compiled from published hospital studies (not national surveillance). Each result
  comes from one hospital, so it does not represent the whole region.</p>
</div>
""",
    unsafe_allow_html=True,
)

if filtered.empty:
    st.warning("No data for the selected filters. Try lowering 'Minimum isolates tested'.")
    st.stop()

by_region_drug = summarise(filtered, ["region", "drug"])
top = by_region_drug.loc[by_region_drug["resistance_pct"].idxmax()]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Regions covered", filtered["region"].nunique())
c2.metric("Studies used", filtered["source"].nunique())
c3.metric("Isolates tested", f"{int(filtered['tested'].sum()):,}")
c4.metric(
    "Highest resistance", f"{top['resistance_pct']:.0f}%",
    delta=f"{top['drug']} - {top['region']}", delta_color="off",
)

# ---------- REGION VS DRUG ----------
section("Resistance by antibiotic and region")
fig_bar = px.bar(
    by_region_drug, x="drug", y="resistance_pct", color="region", barmode="group",
    color_discrete_sequence=PALETTE,
    hover_data={"tested": True, "resistant": True},
    labels={"resistance_pct": "Resistance (%)", "drug": "Antibiotic", "region": "Region"},
)
fig_bar.update_yaxes(range=[0, 100])
st.plotly_chart(style_fig(fig_bar))

left, right = st.columns(2)

with left:
    section("Region vs antibiotic")
    heat = by_region_drug.pivot(index="region", columns="drug", values="resistance_pct")
    fig_heat = px.imshow(
        heat, text_auto=".0f", color_continuous_scale="Blues", aspect="auto",
        zmin=0, zmax=100, labels={"color": "Resistance (%)"},
    )
    st.plotly_chart(style_fig(fig_heat))

with right:
    section("Isolates tested per region")
    n_by_region = filtered.groupby("region", as_index=False)["tested"].sum()
    fig_n = px.bar(
        n_by_region, x="region", y="tested", color_discrete_sequence=[TEAL],
        labels={"tested": "Isolates tested", "region": "Region"},
    )
    st.plotly_chart(style_fig(fig_n))

# ---------- OVER TIME ----------
section("Resistance over time")
trend = summarise(filtered, ["year", "region", "drug"])
trend["series"] = trend["region"] + " - " + trend["drug"]
fig_trend = px.line(
    trend, x="year", y="resistance_pct", color="series", markers=True,
    color_discrete_sequence=PALETTE,
    hover_data={"tested": True},
    labels={"resistance_pct": "Resistance (%)", "year": "Year", "series": "Region - antibiotic"},
)
fig_trend.update_xaxes(dtick=1)
fig_trend.update_yaxes(range=[0, 100])
st.plotly_chart(style_fig(fig_trend))
st.caption(
    "Most results are single studies, so many series show one point only. "
    "Year = middle of the study period. Only some hospitals have several years of data."
)

# ---------- DATA AND SOURCES ----------
with st.expander("Studies behind these numbers"):
    show = filtered.copy()
    show["resistance_pct"] = (show["resistant"] / show["tested"] * 100).round(1)
    st.dataframe(
        show[[
            "region", "facility", "pathogen_reported", "drug_as_reported", "specimen",
            "study_period", "tested", "resistant", "resistance_pct", "source", "notes",
        ]]
    )
    st.download_button(
        "Download full dataset (CSV)", DATA_FILE.read_bytes(),
        file_name="tanzania_amr_data.csv", mime="text/csv",
    )

with st.expander("Limitations"):
    st.markdown(
        """
- Numbers come from **single-hospital studies** (Mwanza, Kilimanjaro, Dar es Salaam), not a national surveillance system. Other regions have little published data.
- Studies used different methods, patients, specimens and years, so comparisons between regions are **indicative only**.
- "3rd-gen cephalosporins" means ceftriaxone (KCMC) or ceftriaxone/cefotaxime (Bugando). "ESBL production" is a resistance marker, not a single antibiotic.
- Bugando's published abstract uses all isolates as the denominator for some results. This dashboard uses **isolates actually tested**.
- Only results with clear counts (tested and resistant) were included. A few values in the source papers were inconsistent and were left out.
"""
    )