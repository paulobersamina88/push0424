import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Frame Lateral Capacity PRO", layout="wide")

st.title("🏗️ Frame Lateral Capacity PRO")
st.caption("Plastic mechanism estimate + Mode 1 response spectrum demand cross-check")

st.warning(
    "Engineering note: This app is a preliminary/teaching-level screening tool. "
    "It does not replace nonlinear pushover analysis, full dynamic analysis, connection checks, "
    "P-Delta checks, diaphragm checks, foundation checks, or code-based design review."
)

# -----------------------------
# Helper functions
# -----------------------------
def interp_sa(periods, sa_values, t1):
    periods = np.asarray(periods, dtype=float)
    sa_values = np.asarray(sa_values, dtype=float)
    order = np.argsort(periods)
    periods = periods[order]
    sa_values = sa_values[order]
    return float(np.interp(t1, periods, sa_values))


def compute_capacity_per_storey(row, mechanism_type, n_bays):
    """Return lateral capacity for one storey using simplified virtual work formulas."""
    h = row["Height_m"]
    if h <= 0:
        return 0.0

    beam_sum = sum(row.get(f"Beam_Bay_{i+1}_Mp_kNm", 0.0) for i in range(n_bays))
    col_top_sum = sum(row.get(f"Col_Line_{j+1}_Top_Mp_kNm", 0.0) for j in range(n_bays + 1))
    col_bot_sum = sum(row.get(f"Col_Line_{j+1}_Bot_Mp_kNm", 0.0) for j in range(n_bays + 1))

    if mechanism_type == "Beam sway mechanism only: V = 2ΣMp_beam / h":
        resisting_moment = 2.0 * beam_sum
    elif mechanism_type == "Column storey mechanism only: V = Σ(Mp_top + Mp_bottom) / h":
        resisting_moment = col_top_sum + col_bot_sum
    else:
        resisting_moment = 2.0 * beam_sum + col_top_sum + col_bot_sum

    return resisting_moment / h


def make_default_spectrum(sds, sd1, tl=8.0):
    """Simple ASCE-like design spectrum shape in Sa/g for demonstration."""
    t0 = 0.2 * sd1 / sds if sds > 0 else 0.0
    ts = sd1 / sds if sds > 0 else 0.0
    t = np.concatenate([
        np.linspace(0.0, max(t0, 0.001), 20),
        np.linspace(max(t0, 0.001), max(ts, t0 + 0.001), 60),
        np.linspace(max(ts, t0 + 0.002), tl, 160),
    ])
    sa = np.zeros_like(t)
    for i, ti in enumerate(t):
        if ti <= t0 and t0 > 0:
            sa[i] = sds * (0.4 + 0.6 * ti / t0)
        elif ti <= ts:
            sa[i] = sds
        else:
            sa[i] = sd1 / ti
    return pd.DataFrame({"Period_s": t, "Sa_g": sa})

# -----------------------------
# Sidebar settings
# -----------------------------
st.sidebar.header("Model Size")
n_storeys = st.sidebar.number_input("Number of storeys", min_value=1, max_value=10, value=3, step=1)
n_bays = st.sidebar.number_input("Number of bays", min_value=1, max_value=10, value=3, step=1)

st.sidebar.header("Mechanism Assumption")
mechanism_type = st.sidebar.selectbox(
    "Capacity mechanism",
    [
        "Beam sway mechanism only: V = 2ΣMp_beam / h",
        "Column storey mechanism only: V = Σ(Mp_top + Mp_bottom) / h",
        "Combined conservative screening: V = [2ΣMp_beam + ΣMp_col] / h",
    ],
)

st.sidebar.header("Units")
st.sidebar.write("Moments: kN-m")
st.sidebar.write("Height/width: m")
st.sidebar.write("Base shear: kN")

# -----------------------------
# Geometry input
# -----------------------------
st.subheader("1) Geometry")
geo_cols = st.columns(2)
with geo_cols[0]:
    typical_height = st.number_input("Typical storey height, h (m)", min_value=0.1, value=3.0, step=0.1)
with geo_cols[1]:
    typical_bay = st.number_input("Typical bay width (m)", min_value=0.1, value=5.0, step=0.1)

storey_names = [f"Storey {i+1}" for i in range(n_storeys)]
geom_df = pd.DataFrame({
    "Storey": storey_names,
    "Height_m": [typical_height] * n_storeys,
})
for i in range(n_bays):
    geom_df[f"Bay_{i+1}_Width_m"] = typical_bay

geom_df = st.data_editor(
    geom_df,
    use_container_width=True,
    num_rows="fixed",
    key="geom_editor",
)

# -----------------------------
# Plastic moment input
# -----------------------------
st.subheader("2) Plastic Moment Capacities")
input_mode = st.radio("Input method", ["Uniform values", "Editable table"], horizontal=True)

if input_mode == "Uniform values":
    c1, c2, c3 = st.columns(3)
    with c1:
        default_beam_mp = st.number_input("Typical beam Mp per bay (kN-m)", min_value=0.0, value=250.0, step=10.0)
    with c2:
        default_col_top_mp = st.number_input("Typical column top Mp per column line (kN-m)", min_value=0.0, value=300.0, step=10.0)
    with c3:
        default_col_bot_mp = st.number_input("Typical column bottom Mp per column line (kN-m)", min_value=0.0, value=300.0, step=10.0)

    mp_df = pd.DataFrame({"Storey": storey_names})
    for i in range(n_bays):
        mp_df[f"Beam_Bay_{i+1}_Mp_kNm"] = default_beam_mp
    for j in range(n_bays + 1):
        mp_df[f"Col_Line_{j+1}_Top_Mp_kNm"] = default_col_top_mp
        mp_df[f"Col_Line_{j+1}_Bot_Mp_kNm"] = default_col_bot_mp
else:
    mp_df = pd.DataFrame({"Storey": storey_names})
    for i in range(n_bays):
        mp_df[f"Beam_Bay_{i+1}_Mp_kNm"] = 250.0
    for j in range(n_bays + 1):
        mp_df[f"Col_Line_{j+1}_Top_Mp_kNm"] = 300.0
        mp_df[f"Col_Line_{j+1}_Bot_Mp_kNm"] = 300.0
    mp_df = st.data_editor(
        mp_df,
        use_container_width=True,
        num_rows="fixed",
        key="mp_editor",
    )

# Merge geometry height into capacity table
calc_df = mp_df.copy()
calc_df["Height_m"] = geom_df["Height_m"].astype(float).values
calc_df["Elevation_m"] = np.cumsum(calc_df["Height_m"].values)

capacity_values = []
for _, row in calc_df.iterrows():
    capacity_values.append(compute_capacity_per_storey(row, mechanism_type, n_bays))
calc_df["Storey_Lateral_Capacity_kN"] = capacity_values

# Overall capacity assumptions
critical_storey_capacity = float(np.min(capacity_values))
sum_storey_capacity = float(np.sum(capacity_values))

st.subheader("3) Plastic Lateral Capacity Results")
r1, r2, r3 = st.columns(3)
r1.metric("Critical storey capacity", f"{critical_storey_capacity:,.1f} kN")
r2.metric("Sum of storey capacities", f"{sum_storey_capacity:,.1f} kN")
r3.metric("Critical storey", calc_df.loc[calc_df["Storey_Lateral_Capacity_kN"].idxmin(), "Storey"])

st.info(
    "For a quick base shear capacity screen, the critical storey capacity is usually the safer reference. "
    "The sum of storey capacities may be unconservative if a soft-storey mechanism controls."
)

fig_cap = go.Figure()
fig_cap.add_trace(go.Bar(
    x=calc_df["Storey"],
    y=calc_df["Storey_Lateral_Capacity_kN"],
    name="Storey lateral capacity"
))
fig_cap.update_layout(
    title="Storey Lateral Capacity from Plastic Mechanism",
    xaxis_title="Storey",
    yaxis_title="Capacity (kN)",
    height=420,
)
st.plotly_chart(fig_cap, use_container_width=True)

# -----------------------------
# Response spectrum demand check
# -----------------------------
st.subheader("4) Mode 1 Response Spectrum Cross-Check")

c1, c2, c3, c4 = st.columns(4)
with c1:
    t1 = st.number_input("Mode 1 period, T₁ (sec)", min_value=0.01, value=0.50, step=0.01)
with c2:
    seismic_weight = st.number_input("Total seismic weight, W (kN)", min_value=0.0, value=10000.0, step=100.0)
with c3:
    importance = st.number_input("Importance factor, Ie", min_value=0.1, value=1.0, step=0.05)
with c4:
    r_factor = st.number_input("Response modification factor, R", min_value=0.1, value=5.0, step=0.1)

spectrum_mode = st.radio(
    "Response spectrum input",
    ["Manual Sa/g at T₁", "Generate simple design spectrum", "Upload Period-Sa/g CSV"],
    horizontal=True,
)

spectrum_df = None
if spectrum_mode == "Manual Sa/g at T₁":
    sa_t1 = st.number_input("Spectral acceleration at T₁, Sa/g", min_value=0.0, value=0.60, step=0.01)
    spectrum_df = pd.DataFrame({"Period_s": [0.0, t1, max(2.0 * t1, t1 + 0.5)], "Sa_g": [sa_t1, sa_t1, sa_t1]})
elif spectrum_mode == "Generate simple design spectrum":
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        sds = st.number_input("SDS", min_value=0.0, value=0.80, step=0.01)
    with sc2:
        sd1 = st.number_input("SD1", min_value=0.0, value=0.50, step=0.01)
    with sc3:
        tl = st.number_input("Long-period limit TL (sec)", min_value=1.0, value=8.0, step=0.5)
    spectrum_df = make_default_spectrum(sds, sd1, tl)
    sa_t1 = interp_sa(spectrum_df["Period_s"], spectrum_df["Sa_g"], t1)
else:
    uploaded = st.file_uploader("Upload CSV with columns: Period_s, Sa_g", type=["csv"])
    if uploaded is not None:
        spectrum_df = pd.read_csv(uploaded)
        if not {"Period_s", "Sa_g"}.issubset(set(spectrum_df.columns)):
            st.error("CSV must contain columns named Period_s and Sa_g.")
            st.stop()
        sa_t1 = interp_sa(spectrum_df["Period_s"], spectrum_df["Sa_g"], t1)
    else:
        st.warning("Upload a spectrum CSV or choose another spectrum input method.")
        sa_t1 = 0.0

# Demand calculations
elastic_base_shear = sa_t1 * importance * seismic_weight
reduced_design_base_shear = elastic_base_shear / r_factor if r_factor > 0 else np.nan

capacity_reference = st.radio(
    "Capacity reference for demand/capacity ratio",
    ["Critical storey capacity", "Sum of storey capacities"],
    horizontal=True,
)
vcap_ref = critical_storey_capacity if capacity_reference == "Critical storey capacity" else sum_storey_capacity

ratio_elastic = vcap_ref / elastic_base_shear if elastic_base_shear > 0 else np.nan
ratio_reduced = vcap_ref / reduced_design_base_shear if reduced_design_base_shear > 0 else np.nan

m1, m2, m3, m4 = st.columns(4)
m1.metric("Sa(T₁)/g", f"{sa_t1:.3f}")
m2.metric("Elastic demand", f"{elastic_base_shear:,.1f} kN")
m3.metric("Reduced design demand", f"{reduced_design_base_shear:,.1f} kN")
m4.metric("Capacity used", f"{vcap_ref:,.1f} kN")

m5, m6 = st.columns(2)
m5.metric("Capacity / Elastic demand", f"{ratio_elastic:.2f}" if np.isfinite(ratio_elastic) else "N/A")
m6.metric("Capacity / Reduced design demand", f"{ratio_reduced:.2f}" if np.isfinite(ratio_reduced) else "N/A")

if np.isfinite(ratio_elastic):
    if ratio_elastic >= 1.0:
        st.success("Elastic demand check: estimated capacity is greater than elastic spectrum demand.")
    elif ratio_reduced >= 1.0:
        st.warning("Capacity is below elastic demand but above reduced design demand. This suggests ductility/inelastic behavior is being relied upon.")
    else:
        st.error("Estimated capacity is below both elastic and reduced design demand. Detailed nonlinear assessment is recommended.")

# Spectrum plot
if spectrum_df is not None and len(spectrum_df) > 1:
    fig_spec = go.Figure()
    fig_spec.add_trace(go.Scatter(
        x=spectrum_df["Period_s"],
        y=spectrum_df["Sa_g"],
        mode="lines",
        name="Response spectrum"
    ))
    fig_spec.add_trace(go.Scatter(
        x=[t1],
        y=[sa_t1],
        mode="markers+text",
        text=[f"T₁={t1:.2f}s, Sa/g={sa_t1:.3f}"],
        textposition="top center",
        name="Mode 1 point"
    ))
    fig_spec.update_layout(
        title="Response Spectrum Cross-Check",
        xaxis_title="Period, T (sec)",
        yaxis_title="Sa/g",
        height=450,
    )
    st.plotly_chart(fig_spec, use_container_width=True)

# -----------------------------
# Optional lateral force distribution
# -----------------------------
st.subheader("5) Optional Equivalent Lateral Force Distribution")
st.write("This distributes the selected base shear using a simple vertical distribution proportional to Wᵢhᵢᵏ.")

fc1, fc2, fc3 = st.columns(3)
with fc1:
    distribution_base = st.selectbox("Base shear to distribute", ["Elastic demand", "Reduced design demand", "Plastic capacity reference"])
with fc2:
    k_exp = st.number_input("Height exponent k", min_value=0.5, max_value=2.5, value=1.0, step=0.1)
with fc3:
    typical_floor_weight = st.number_input("Typical floor weight Wᵢ (kN)", min_value=0.0, value=seismic_weight / n_storeys if n_storeys else 0.0, step=100.0)

floor_df = pd.DataFrame({
    "Storey": storey_names,
    "Elevation_m": calc_df["Elevation_m"].values,
    "Floor_Weight_kN": [typical_floor_weight] * n_storeys,
})
floor_df = st.data_editor(floor_df, use_container_width=True, num_rows="fixed", key="floor_weight_editor")

if distribution_base == "Elastic demand":
    v_to_dist = elastic_base_shear
elif distribution_base == "Reduced design demand":
    v_to_dist = reduced_design_base_shear
else:
    v_to_dist = vcap_ref

weights = floor_df["Floor_Weight_kN"].astype(float).values
heights = floor_df["Elevation_m"].astype(float).values
factor = weights * np.power(heights, k_exp)
if factor.sum() > 0:
    floor_df["Lateral_Force_kN"] = v_to_dist * factor / factor.sum()
else:
    floor_df["Lateral_Force_kN"] = 0.0
floor_df["Storey_Shear_from_Top_kN"] = floor_df["Lateral_Force_kN"][::-1].cumsum()[::-1].values

st.dataframe(floor_df, use_container_width=True)

fig_force = go.Figure()
fig_force.add_trace(go.Bar(
    x=floor_df["Lateral_Force_kN"],
    y=floor_df["Storey"],
    orientation="h",
    name="Lateral force"
))
fig_force.update_layout(
    title="Equivalent Lateral Force Distribution",
    xaxis_title="Lateral force (kN)",
    yaxis_title="Storey",
    height=450,
)
st.plotly_chart(fig_force, use_container_width=True)

# -----------------------------
# Export
# -----------------------------
st.subheader("6) Export Results")
summary = pd.DataFrame({
    "Parameter": [
        "Number of storeys", "Number of bays", "Mechanism type", "Critical storey capacity kN",
        "Sum storey capacity kN", "T1 sec", "Sa(T1)/g", "Seismic weight kN", "Ie", "R",
        "Elastic base shear kN", "Reduced design base shear kN", "Capacity reference", "Capacity/reference kN",
        "Capacity/Elastic demand", "Capacity/Reduced demand"
    ],
    "Value": [
        n_storeys, n_bays, mechanism_type, critical_storey_capacity, sum_storey_capacity,
        t1, sa_t1, seismic_weight, importance, r_factor, elastic_base_shear,
        reduced_design_base_shear, capacity_reference, vcap_ref, ratio_elastic, ratio_reduced
    ]
})

output = io.BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    summary.to_excel(writer, index=False, sheet_name="Summary")
    calc_df.to_excel(writer, index=False, sheet_name="Plastic_Capacity")
    floor_df.to_excel(writer, index=False, sheet_name="ELF_Distribution")
    if spectrum_df is not None:
        spectrum_df.to_excel(writer, index=False, sheet_name="Spectrum")

st.download_button(
    "Download Excel results",
    data=output.getvalue(),
    file_name="frame_lateral_capacity_results.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.markdown("""
### Suggested interpretation
- **Capacity / Elastic Demand ≥ 1.0**: strong preliminary indication of adequate lateral strength.
- **Capacity / Elastic Demand < 1.0 but Capacity / Reduced Demand ≥ 1.0**: structure may rely on ductility; verify detailing, hinge rotations, and drift.
- **Capacity / Reduced Demand < 1.0**: likely inadequate under the selected assumptions; perform detailed nonlinear assessment.

### Limitations
This tool assumes simplified plastic mechanisms and does not automatically determine the true governing collapse mechanism. For real assessment, validate using pushover analysis, modal participation, response spectrum analysis, drift checks, P-Delta, and member/joint detailing checks.
""")
