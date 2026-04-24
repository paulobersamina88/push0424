# Frame Lateral Capacity PRO

A Streamlit app for preliminary lateral capacity screening of a moment frame using plastic moment capacities of beams and columns, then cross-checking against Mode 1 response spectrum demand.

## Features

- Up to 10 storeys and 10 bays
- Input beam and column plastic moment capacities
- Simplified beam sway, column storey, or combined mechanism estimates
- Mode 1 period input
- Manual Sa/g, generated design spectrum, or uploaded Period-Sa/g CSV
- Elastic and reduced design base shear demand
- Capacity/demand ratios
- Optional equivalent lateral force distribution
- Excel export of results

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## CSV spectrum format

Upload a CSV with this format:

```csv
Period_s,Sa_g
0.0,0.4
0.2,0.8
0.5,0.8
1.0,0.5
2.0,0.25
```

## Engineering limitation

This is a preliminary/teaching tool. It is not a substitute for nonlinear pushover analysis, response spectrum analysis, time-history analysis, drift checks, P-Delta checks, joint checks, connection checks, or code compliance review.
