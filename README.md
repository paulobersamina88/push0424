# Frame Lateral Capacity Estimator

A Streamlit app for preliminary estimation of frame lateral capacity using plastic moment capacities of beams and columns.

## Features
- Up to 10 storeys
- Up to 10 bays
- Beam plastic moment input per storey and bay
- Column plastic moment input per storey and column line
- Uniform, triangular, or user-defined lateral load pattern
- Estimated base shear capacity
- Critical storey and controlling mechanism
- CSV export

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Engineering caution
This is a simplified educational/preliminary tool only. It does not replace nonlinear pushover analysis or code-based design checks.
