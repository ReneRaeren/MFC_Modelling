# MFC Modelling Prototype

This repository contains a lightweight Python prototype for the two-block CO₂/O₂
manifold simulation described in `Project_Plan.md`.  It implements the
simplified assumptions agreed in the latest discussion:

- identical dynamic behaviour for both mixing and split MFCs, modelled as
  first-order PI controlled actuators with rate limits,
- isothermal, ideal-gas volumes with adjustable buffer capacity between the
  blocks,
- reactor inlets approximated by a linear conductance to a configurable
  pressure sink, and
- an empirical Cp-matching helper that finds the O₂/CO₂ composition whose heat
  capacity best matches air across a temperature grid.

## Usage

1. Install the Python dependency (NumPy) into your active environment:

   ```bash
   pip install -r requirements.txt
   ```

2. Execute a single scenario from the command line:

   ```bash
   python run_simulation.py --o2 20 --co2 80 --supply 8 --buffer 250 --duration 30
   ```

   The script prints a JSON summary and can optionally persist the full
   timeseries via `--output path/to/results.json`.

3. Use the Python API for scripted analyses:

   ```python
   from mfc_modelling import Scenario, SimulationConfig, run_case

   config = SimulationConfig(
       scenario=Scenario(o2_flow_slpm=15.0, co2_flow_slpm=60.0),
       buffer_volume_cm3=250.0,
   )
   result = run_case(config)
   ```

   The returned `SimulationResult` contains pressures and flows over time along
   with metadata and warning flags.

4. Compute the Cp-matched O₂/CO₂ composition:

   ```python
   from mfc_modelling.cp_match import match_air_cp

   match = match_air_cp()
   print(match.y_o2, match.y_co2, match.rms_error)
   ```

## Limitations

This is an initial, idealised model intended to bootstrap further development.
It neglects piping friction, temperature dynamics, and detailed valve
characteristics.  The orifice and conductance coefficients were chosen to give
plausible magnitudes rather than to match vendor data.  As better empirical data
becomes available the coefficients and control tuning should be refined.
