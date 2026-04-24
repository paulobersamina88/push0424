import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Frame Lateral Capacity Estimator", layout="wide")

st.title("Plastic Mechanism Lateral Capacity Estimator for RC/Steel Frames")
st.caption("Educational preliminary tool. Uses plastic moment capacities of beams and columns to estimate lateral capacity using simplified mechanism-based checks.")

with st.expander("Assumptions and limitations", expanded=True):
    st.markdown("""
    This app estimates lateral capacity using simplified plastic mechanism concepts. It is suitable for teaching, screening, and conceptual comparison only.

    **Main assumptions:**
    - Plane frame behavior.
    - Plastic moment capacities are already factored/design capacities.
    - Beam mechanism capacity is based on plastic hinges at beam ends per storey.
    - Column/sway mechanism capacity is based on column plastic moments resisting storey shear.
    - Global capacity is controlled by the lowest estimated storey shear capacity.
    - P-Delta, axial load interaction, joint shear, panel zone, connection limits, shear failure, foundation uplift/sliding, and higher-mode effects are not included.

    For actual design or assessment, verify using nonlinear static pushover or nonlinear dynamic analysis and applicable codes such as NSCP/ASCE/ACI/AISC.
    """)

st.sidebar.header("Frame Geometry")
n_storey = st.sidebar.number_input("Number of storeys", min_value=1, max_value=10, value=3, step=1)
n_bays = st.sidebar.number_input("Number of bays", min_value=1, max_value=10, value=3, step=1)
unit = st.sidebar.selectbox("Moment unit", ["kN-m", "N-m", "ton-m"], index=0)

unit_factor = {"kN-m": 1.0, "N-m": 0.001, "ton-m": 9.80665}[unit]

st.sidebar.header("Default Capacities")
def_beam_mp = st.sidebar.number_input(f"Default beam Mp ({unit})", min_value=0.0, value=150.0, step=10.0)
def_col_mp = st.sidebar.number_input(f"Default column Mp ({unit})", min_value=0.0, value=250.0, step=10.0)
def_height = st.sidebar.number_input("Default storey height (m)", min_value=0.1, value=3.0, step=0.1)
def_bay_width = st.sidebar.number_input("Default bay width (m)", min_value=0.1, value=5.0, step=0.1)

st.sidebar.header("Lateral Load Pattern")
load_pattern = st.sidebar.selectbox("Pattern for distributing base shear", ["Uniform", "Triangular", "User-defined weights"], index=1)

# Geometry tables
storeys = [f"Storey {i}" for i in range(1, n_storey + 1)]
bays = [f"Bay {j}" for j in range(1, n_bays + 1)]
columns = [f"Column Line {j}" for j in range(1, n_bays + 2)]

st.subheader("1. Geometry Input")
col1, col2 = st.columns(2)

with col1:
    height_df = pd.DataFrame({"Storey": storeys, "Height_m": [def_height] * n_storey})
    height_df = st.data_editor(height_df, num_rows="fixed", use_container_width=True, key="height_df")

with col2:
    bay_df = pd.DataFrame({"Bay": bays, "Width_m": [def_bay_width] * n_bays})
    bay_df = st.data_editor(bay_df, num_rows="fixed", use_container_width=True, key="bay_df")

# Capacity input tables
st.subheader("2. Plastic Moment Capacity Input")
st.markdown("Input plastic moment capacities. Values are internally converted to **kN-m**.")

tab1, tab2 = st.tabs(["Beam Mp per Storey and Bay", "Column Mp per Storey and Column Line"])

with tab1:
    beam_mp_df = pd.DataFrame(def_beam_mp, index=storeys, columns=bays)
    beam_mp_df.index.name = "Storey"
    beam_mp_df = st.data_editor(beam_mp_df, use_container_width=True, key="beam_mp")

with tab2:
    col_mp_df = pd.DataFrame(def_col_mp, index=storeys, columns=columns)
    col_mp_df.index.name = "Storey"
    col_mp_df = st.data_editor(col_mp_df, use_container_width=True, key="col_mp")

# Load pattern input
st.subheader("3. Optional Lateral Force Pattern")
if load_pattern == "User-defined weights":
    default_weights = np.arange(1, n_storey + 1, dtype=float)
    weights_df = pd.DataFrame({"Storey": storeys, "Weight_or_factor": default_weights})
    weights_df = st.data_editor(weights_df, num_rows="fixed", use_container_width=True, key="weights_df")
    pattern_weights = np.array(weights_df["Weight_or_factor"], dtype=float)
elif load_pattern == "Uniform":
    pattern_weights = np.ones(n_storey)
else:
    pattern_weights = np.arange(1, n_storey + 1, dtype=float)

if np.sum(pattern_weights) <= 0:
    st.error("Lateral load pattern weights must have positive total value.")
    st.stop()

# Convert inputs
heights = np.array(height_df["Height_m"], dtype=float)
beam_mp = beam_mp_df.to_numpy(dtype=float) * unit_factor
col_mp = col_mp_df.to_numpy(dtype=float) * unit_factor

if np.any(heights <= 0):
    st.error("All storey heights must be greater than zero.")
    st.stop()

# Calculations
# Beam mechanism storey shear capacity: sum of 2Mp/L? For story mechanism using virtual work:
# External work V_i * delta = Internal work sum plastic rotations * Mp.
# Simplified common expression per bay/storey: V_story ~= sum(2 Mp_beams) / h_storey
# Column mechanism: V_story ~= sum(Mp_top + Mp_bottom)/h approximated as 2*sum(Mp columns)/h for storey mechanism.
# Here column Mp input is representative per storey column line, using 2 plastic hinges per column segment.
beam_storey_resisting_moment = 2.0 * np.sum(beam_mp, axis=1)  # kN-m
column_storey_resisting_moment = 2.0 * np.sum(col_mp, axis=1)  # kN-m

beam_story_shear = beam_storey_resisting_moment / heights
column_story_shear = column_storey_resisting_moment / heights
controlled_story_shear = np.minimum(beam_story_shear, column_story_shear)
controlling_mechanism = np.where(beam_story_shear <= column_story_shear, "Beam mechanism", "Column/sway mechanism")

# Base shear using pattern: story shear demand above level i is sum of lateral forces from i to roof.
alpha = pattern_weights / np.sum(pattern_weights)
cumulative_above = np.array([np.sum(alpha[i:]) for i in range(n_storey)])
base_shear_capacity_by_storey = controlled_story_shear / cumulative_above
estimated_base_shear = np.min(base_shear_capacity_by_storey)
critical_storey_idx = int(np.argmin(base_shear_capacity_by_storey))

lateral_forces = estimated_base_shear * alpha
storey_shear_demand = np.array([np.sum(lateral_forces[i:]) for i in range(n_storey)])

results_df = pd.DataFrame({
    "Storey": storeys,
    "Height_m": heights,
    "Beam_Mechanism_Story_Shear_kN": beam_story_shear,
    "Column_Mechanism_Story_Shear_kN": column_story_shear,
    "Controlling_Story_Shear_kN": controlled_story_shear,
    "Controlling_Mechanism": controlling_mechanism,
    "Load_Pattern_Factor": alpha,
    "Story_Shear_Demand_at_Capacity_kN": storey_shear_demand,
    "Base_Shear_Limit_from_Storey_kN": base_shear_capacity_by_storey,
})

# Output summary
st.subheader("4. Results")
metric1, metric2, metric3 = st.columns(3)
metric1.metric("Estimated Base Shear Capacity", f"{estimated_base_shear:,.2f} kN")
metric2.metric("Critical Storey", storeys[critical_storey_idx])
metric3.metric("Critical Mechanism", controlling_mechanism[critical_storey_idx])

st.dataframe(results_df.style.format({
    "Height_m": "{:.3f}",
    "Beam_Mechanism_Story_Shear_kN": "{:,.2f}",
    "Column_Mechanism_Story_Shear_kN": "{:,.2f}",
    "Controlling_Story_Shear_kN": "{:,.2f}",
    "Load_Pattern_Factor": "{:.4f}",
    "Story_Shear_Demand_at_Capacity_kN": "{:,.2f}",
    "Base_Shear_Limit_from_Storey_kN": "{:,.2f}",
}), use_container_width=True)

# Plots
st.subheader("5. Plots")
plot_col1, plot_col2 = st.columns(2)

with plot_col1:
    fig, ax = plt.subplots()
    y = np.arange(1, n_storey + 1)
    ax.plot(beam_story_shear, y, marker="o", label="Beam mechanism")
    ax.plot(column_story_shear, y, marker="o", label="Column/sway mechanism")
    ax.plot(controlled_story_shear, y, marker="o", label="Controlling")
    ax.set_xlabel("Storey Shear Capacity (kN)")
    ax.set_ylabel("Storey")
    ax.set_title("Storey Shear Capacity")
    ax.grid(True)
    ax.legend()
    st.pyplot(fig)

with plot_col2:
    fig2, ax2 = plt.subplots()
    ax2.bar(y, lateral_forces)
    ax2.set_xlabel("Storey")
    ax2.set_ylabel("Lateral Force at Capacity (kN)")
    ax2.set_title("Equivalent Lateral Force Distribution")
    ax2.grid(True, axis="y")
    st.pyplot(fig2)

# Plastic hinge summary
st.subheader("6. Plastic Hinge Interpretation")
st.markdown(f"""
The controlling estimated capacity is reached when **{storeys[critical_storey_idx]}** reaches its mechanism limit.  
The estimated base shear capacity is:

### V = {estimated_base_shear:,.2f} kN

At this capacity level, the lateral forces are distributed according to the selected **{load_pattern}** pattern.
""")

csv = results_df.to_csv(index=False).encode("utf-8")
st.download_button("Download results as CSV", data=csv, file_name="frame_lateral_capacity_results.csv", mime="text/csv")

st.subheader("7. Suggested Formula Basis")
st.latex(r"V_{story,beam} \approx \frac{2\sum M_{p,beam}}{h}")
st.latex(r"V_{story,column} \approx \frac{2\sum M_{p,column}}{h}")
st.latex(r"V_{base} = \min_i \left( \frac{V_{story,i}}{\sum_{j=i}^{n} \alpha_j} \right)")

st.warning("This is not a substitute for full pushover analysis. Always check weak-column/strong-beam behavior, joint shear, connection capacity, shear capacity, axial load interaction, P-Delta, and code requirements.")
