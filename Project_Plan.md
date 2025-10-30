# Plan.md — ODE Simulation & Web App for Two-Block CO₂/O₂ Manifold with Series MFC Interaction

## 0) Introduction (problem & goal)

* **Problem:** Two MFC “blocks” in series (Mixing → Split) can **interact** via pressure/flow coupling, causing **hunting/swing** and ΔP violations. You want to know if a **buffer volume** (40–3785 cm³) and/or parameter choices prevent issues at your operating points.
* **Why simulate:**

  * Predict stability, ΔP margins, choked-flow risk, and flow-split behavior **before hardware changes**.
  * Compare **no-buffer vs buffer** and explore setpoints across your ranges.
  * Decide on feasible **back-pressure** and **supply pressure** settings.
* **Approach:** Build an **isothermal, ideal-gas** dynamic model (plant + MFC first-order actuators) and a basic **web app** (frontend + Python backend) to run cases and visualize results.

  * Assumptions “ideal gas, isothermal, negligible straight-pipe losses” must be **annotated in code, UI, and outputs** (explicit disclaimer).

---

## 1) System summary (from user requirements)

* **Gases:** O₂ (99.99%), CO₂ (99.99%); supplies regulated to **8 bar** nominal (adjustable **4–10 bar**).
* **Mix targets:**

  * “Air-like” O₂ 21% / CO₂ 79% by mol.
  * “Cp-matching” O₂/CO₂ ratio vs Air cp(T) (use Cantera to fit mix).
* **Block 1 (Mixing MFCs):** Two **Bronkhorst EL-FLOW Select F-203AV-M50** (high-flow thermal MFCs). Family specs (response 1–2 s std; option ~0.5 s fast; ranges up to 1670 ln/min across models). 
* **Block 2 (Split MFCs):** Two **Bronkhorst IN-FLOW F-201AI-PGD-00-V**, max **6900 L/h** (≈115 L/min). (No datasheet provided; treat dynamics/range as parameters).
* **Piping:** 12 mm ID; total straight length ~5 m (losses neglected initially).
* **Buffer study:** Insert optional 40–3785 cm³ vessel between blocks.
* **Operating ranges (user’s targets):**

  * O₂ flow: **7.17–31.92 L/min**
  * CO₂ flow: **26–120 L/min**
  * Reactor pressure: **1.5–2.5 bar** (both entries identical behavior assumed)
  * Known ΔP downstream of Split block: **3.5 bar** (interpretation: available ΔP across downstream elements; see §3 for placement).
* **Controls:** Each MFC runs **independent internal PID** to track its own flow setpoint; no ratio/cascade/override; sampling period configurable in sim.
* **Scope v1:** Focus **steady operating points** and intrinsic loop interaction; disturbances later.

---

## 2) Modeling scope & assumptions (visible everywhere: code, UI, reports)

* **Gas model:** **Ideal gas**, **isothermal** at **298.15 K (25 °C)**; annotate everywhere.
* **Flow network:** Lumps (volumes) + resistive elements (valves/orifices) with compressible-flow relations; **pipe friction neglected** (first pass).
* **MFC dynamics:** Each MFC = **first-order actuator** with saturation & rate limits; default **τ = 1–2 s** (optionally **0.5 s** “fast” per EL-FLOW Select family). 
* **Internal PIDs:** Modeled as ideal PI/PID with anti-windup; default gains chosen to reproduce family-level settling behavior. Specs will be adjustable. (Exact vendor gains not available.)
* **Reactor inlets:** Two identical terminals with a **back-pressure vs flow** characteristic (provide simple configurable law: constant-pressure sink; or affine/quadratic curve to emulate entry losses).
* **Choked-flow check:** Use critical pressure ratio ( (p_d/p_u)_{\text{crit}} = \left(\tfrac{2}{\gamma+1}\right)^{\gamma/(\gamma-1)} ) with user-set γ (defaults: O₂≈1.4, CO₂≈1.3; mixture γ from composition). Flag when predicted.

---

## 3) Physical layout to model

1. **Supplies:** O₂ and CO₂ at adjustable **4–10 bar**, nominal 8 bar.
2. **Block 1 (Mixing):** Two MFCs in parallel (O₂, CO₂) → T-mix to **Feed node**.
3. **Inter-block link:** **Optional buffer** (Vb = 40–3785 cm³) possibly with an optional small **restrictor** (Cv/orifice) for damping; else direct line.
4. **Block 2 (Split):** Two MFCs in parallel fed from Feed → two reactor inlets.
5. **Reactor side:** Target absolute pressure **1.5–2.5 bar** at each inlet; implement as sink elements with chosen P–Q law.
6. **ΔP=3.5 bar (given):** In sim, interpret as **available differential** across the **Split block + reactor entry path**. Provide a toggle to treat it as:

   * (A) Fixed **back-pressure controller** holding reactor inlet pressure; or
   * (B) Fixed downstream sink pressure = upstream node pressure − 3.5 bar (for sensitivity sweeps).

---

## 4) Equations & component models (concise)

* **State variables (suggested):** Pressures in each lumped volume:
  ( \mathbf{x} = [p_{\text{O2,in}}, p_{\text{CO2,in}}, p_{\text{feed}}, p_{\text{buffer}}, p_{\text{split}}, p_{\text{reactor1}}, p_{\text{reactor2}}] )
  (Reduce/expand depending on chosen lumping; at minimum: O₂ line, CO₂ line, feed, (buffer), split node(s), reactor sinks.)
* **Mass balance per volume (V):**
  ( \dot{p} = \dfrac{RT}{V},\big(\dot{n}*{\text{in}} - \dot{n}*{\text{out}}\big) )  (isothermal ideal gas)
* **Resistive element (valve/orifice) flow (subsonic):**
  ( \dot{n} = C,\sqrt{\max(p_u^2 - p_d^2,,0)},/(\bar{Z}RT) )  (use standard compressible orifice formulation; choose one canonical form; normalize to SI)
  **Choked:** if (p_d/p_u \le (2/(\gamma+1))^{\gamma/(\gamma-1)}), then
  ( \dot{n} = C_{\text{choked}}; p_u /(\sqrt{T}) ) (use γ-dependent form).
  *Note:* Use effective **Cv/Kv** parameters; tune per MFC/orifice.
* **MFC actuator:**

  * Commanded flow setpoint ( \dot{n}_{sp}(t) ) given by user (Block 1 and 2 independently).
  * Internal PID acts on measured flow = valve law((p_u,p_d), position) to achieve (\dot{n}_{sp}).
  * Approximate as **1st-order**: ( \tau,\dot{\dot{n}}*{cmd} + \dot{n}*{cmd} = \text{sat}(\dot{n}*{sp}, \text{range}) ) with **rate limits**, then compute required valve position iteratively each step (or directly clamp outlet stream to (\dot{n}*{cmd}) while enforcing ΔP limits).
  * Default **τ=1.5 s** (range 0.5–2 s) from EL-FLOW Select family settling times. 
* **Mixture properties:**

  * Mole-based mixing at nodes; compute mixture (M), (R), (c_p), (γ) from composition.
  * **Cp-match tool:** by Cantera, minimize (\sum_i w_i,[c_{p,\text{mix}}(T_i)-c_{p,\text{air}}(T_i)]^2) over (y_{O2}) subject to (y_{CO2}=1-y_{O2}) on (T\in[T_{\min},T_{\max}]).

---

## 5) Inputs & parameterization (UI + JSON schema)

* **Global:** `temperature_K (default 298.15)`, `is_isothermal: true`, `use_ideal_gas: true`.
* **Supplies:** `p_supply_bar_abs` for O₂, CO₂ (range 4–10).
* **Block1 MFCs:** For each gas: `flow_min_L_min`, `flow_max_L_min`, `tau_s (0.5–2)`, `rate_limit_L_min_s`, `Kv` or `Cv` (optional).

  * Family reference for achievable ranges & dynamics (EL-FLOW Select). 
* **Inter-block:** `buffer_volume_cm3` (0 for none), `restrictor_Cv` (optional).
* **Block2 MFCs:** Two channels identical by default: `max_flow_L_min (≤115)`, `tau_s`, limits; (exact vendor data TBD).
* **Reactor sinks:** Either `p_reactor_bar_abs` fixed, or `curve`: `{type: "quadratic", params: {...}}`.
* **Sampling:** `dt_controller_s` (e.g., 0.05–0.2 s), `dt_ode_s` (e.g., 0.005–0.02 s).
* **Scenarios:** Arrays of steady operating points (O₂/CO₂ setpoints; optional back-pressure settings).

---

## 6) Experiments (v1 steady-state focus)

**E0 Sanity:** Single point, buffer OFF.

* O₂=15 L/min; CO₂=60 L/min; `p_supply=8 bar`; `p_reactor=2.0 bar`. Record flows/pressures; verify ΔP across MFCs stays within capability.

**E1 Range sweep (buffer OFF vs ON):**

* O₂ in [7.2, 31.9] L/min; CO₂ in [26, 120] L/min; grid of 3×3 points.
* Buffer volumes: 0, 250, 1000, 3785 cm³.
* Metrics: overshoot, settling time, ΔP across each MFC, choked flags, flow-split error.

**E2 Sensitivity to supply pressure:**

* `p_supply` = 4, 6, 8, 10 bar; fixed setpoints. Observe stability margins and ΔP.

**E3 Downstream ΔP interpretation:**

* Compare mode A (fixed `p_reactor`) vs mode B (constant ΔP=3.5 bar downstream of split). Check feasibility and differences.

---

## 7) Outputs & acceptance criteria

* **Plots:** time series of node pressures, MFC commanded & achieved flows, valve utilization (% of max), choked indicators.
* **Tables (CSV & MD):** steady-state values, stability metrics, ΔP compliance, choked status per element.
* **Acceptance (per operating point):**

  * Overshoot ≤ **5 %**; settling (2 % band) ≤ **3 s**; no sustained oscillation.
  * ΔP across every MFC within vendor-capable window (flag when violated).
  * No choked flow unless intended; if choked, UI must **warn** prominently.
* **Disclaimers:** Results valid under **ideal-gas, isothermal, negligible pipe-loss** assumptions; clearly printed on plots and reports.

---

## 8) Software architecture (web app)

### 8.1 Frontend (SPA)

* **Stack:** React (Vite) or similar; Typescript recommended.
* **Panels:**

  * **Inputs:** Gas selection, setpoints, pressures, buffer size, toggles (ΔP mode), controller timings.
  * **Run Controls:** Run single case / sweep; progress & status.
  * **Results:** Plots (timeseries), badges (warnings), tables (export CSV/MD).
  * **Cp-matching tool:** small widget to compute O₂/CO₂ mix that best matches air cp(T).
* **I/O:** JSON forms; client-side validation; download buttons for CSV/MD.
* **CORS:** Enabled to talk to backend on `localhost:5000` (configurable).

### 8.2 Backend (Python)

* **Stack:** Flask (or FastAPI), `numpy`, `scipy` (ode integration), `pandas`, `CoolProp` (optional), `cantera` (cp matching), `python-control` (optional for loop design).
* **Endpoints (JSON):**

  * `POST /simulate` → single run (params + seeds) → `{timeseries, summary, flags}`
  * `POST /sweep` → grid of runs → aggregated tables + compact KPIs
  * `POST /cp_match` → returns cp-matched O₂/CO₂ mole fractions & residuals
  * `GET /defaults` → default parameter pack (reflects this plan)
  * `POST /export` → returns MD/CSV blobs of summary results
* **Structure:**

  * `plant/` component models (MFC, orifice, volume, sink)
  * `solver/` ODE right-hand side + stepper config
  * `experiments/` scenario builders (E0–E3)
  * `reports/` plotting & MD/CSV writers
  * `tools/` cp-match; unit conversion; choked test

---

## 9) Detailed build steps

### 9.1 Data & constants

* Gas constants, molar masses for O₂/CO₂, default γ values; default **T=298.15 K (25 °C)** and show **(25 °C)** in UI and reports.
* EL-FLOW Select family **dynamic envelope** for τ and ranges (for Block 1 F-203AV class). Cite family datasheet. 
* Unknowns for Block 2 → expose as **tunable**: `tau_s`, `range_max_L_min`, `Cv`.

### 9.2 Component implementations

* **Volume:** pressure ODE using ideal-gas mass balance.
* **Orifice/restrictor:** compressible flow; subsonic vs choked branch; unit-safe.
* **MFC:**

  * Option A (simplified): achieved flow = 1st-order lag to setpoint with saturation & ΔP-feasibility check; flag when infeasible.
  * Option B (richer): internal PID computing **valve position** → valve orifice law → flow; includes anti-windup and rate limit.
  * Provide switch between A and B (start with A; add B later).

### 9.3 Network assembly

* Build nodes: O₂ line, CO₂ line, feed node, (buffer node), split node, reactor1, reactor2.
* Wire elements: supplies → MFCs → mix → (buffer or short) → split-MFCs → sinks.
* Ensure **composition tracking** (molar streams) at mix/split nodes.

### 9.4 Solver & stepping

* `scipy.integrate.solve_ivp` with dense output off; fixed max step (e.g., 0.01–0.02 s).
* Controller update at `dt_controller_s`; hold command between updates.
* Terminate at `t_end=30–60 s` or early when steady criteria met.

### 9.5 Metrics & flags

* **Stability:** peak overshoot, 2 % settling time, oscillation index (e.g., last N peaks ratio).
* **ΔP margins:** compute ΔP across each MFC and compare to **capable window**; flag low ΔP or reversal. (Use vendor guidance where available; EL-FLOW Select family supports a variety of ΔP/valves; treat as config.) 
* **Choked:** element-wise status time series.
* **Flow split error:** difference between the two reactor branches.

### 9.6 Cp-matching tool (optional but included)

* Temperature grid (e.g., 250–450 K).
* Cantera: build Air and O₂/CO₂ mixtures; minimize squared cp error via 1-D search over y(O₂).
* Output suggested composition plus plot cp(T) curves and % error.

### 9.7 Validation & sanity checks (no plant data available)

* **Unit tests:** orifice law limits; choked threshold; mass balance closure.
* **Cross-checks:**

  * With MFC τ→0, system reduces to algebraic steady mixing/splitting.
  * With huge buffer, upstream/downstream loops decouple (reduced oscillation).
  * With low supply pressure or high reactor pressure, check for infeasible setpoints → proper warnings.

---

## 10) UI/UX requirements (make assumptions obvious)

* Prominent banner on results:

  * “**Assumptions:** isothermal ideal gas; negligible pipe losses; simplified MFC dynamics; see Plan.md.”
* Warnings as badges: **Low ΔP**, **Choked**, **Sustained Oscillation**, **Setpoint infeasible**.
* Each plot subtitle must include **T in K (°C)** and **pressures in Pa (bar)**.

---

## 11) Units & conversions

* **Internal:** SI (Pa, K, mol/s, m³, kg).
* **Display:** include bar and °C in parentheses (e.g., `298.15 K (25 °C)`, `100000 Pa (1.0 bar)`).
* **Flow entries:** accept **L/min** (convert to mol/s by composition and P,T at the element’s upstream node).

---

## 12) Deliverables

* **Backend:** Flask app + simulation core; JSON API; tests.
* **Frontend:** SPA with forms, plots, tables; export MD/CSV.
* **Docs:**

  * `README.md` (run instructions, examples)
  * `ASSUMPTIONS.md` (highlight modeling simplifications)
  * `REPORT_*.md` (auto-generated summaries per sweep)
* **Examples:** Pre-baked scenarios E0–E3.

---

## 13) Directory layout (proposed)

```
project/
  backend/
    app.py
    requirements.txt
    src/
      plant/
        mfc.py
        orifice.py
        volume.py
        sinks.py
      solver/
        rhs.py
        integrate.py
      experiments/
        scenarios.py
      tools/
        units.py
        cp_match.py
        mix_props.py
        choke.py
      reports/
        plots.py
        tables.py
        md_writer.py
    tests/
  frontend/
    package.json
    src/
      App.tsx
      components/
      pages/
      api/
  docs/
    Plan.md  <-- (this file)
    ASSUMPTIONS.md
```

---

## 14) Configuration example (JSON)

```json
{
  "global": {
    "temperature_K": 298.15,
    "is_isothermal": true,
    "use_ideal_gas": true
  },
  "supplies": {
    "O2": {"p_supply_bar_abs": 8.0},
    "CO2": {"p_supply_bar_abs": 8.0}
  },
  "block1_mfcs": {
    "O2": {"flow_min_L_min": 7.17, "flow_max_L_min": 31.92, "tau_s": 1.5},
    "CO2": {"flow_min_L_min": 26.0, "flow_max_L_min": 120.0, "tau_s": 1.5}
  },
  "interblock": {
    "buffer_volume_cm3": 0,
    "restrictor_Cv": null
  },
  "block2_mfcs": {
    "left":  {"max_flow_L_min": 115.0, "tau_s": 1.5},
    "right": {"max_flow_L_min": 115.0, "tau_s": 1.5}
  },
  "reactor": {
    "mode": "fixed_pressure",
    "p_reactor_bar_abs": 2.0
  },
  "ctrl": {
    "dt_controller_s": 0.1,
    "dt_ode_s": 0.01,
    "t_end_s": 40.0
  },
  "setpoints": {
    "O2_L_min": 15.0,
    "CO2_L_min": 60.0,
    "split_share": "equal"
  }
}
```

---

## 15) Implementation notes & vendor refs

* EL-FLOW Select family (covers **F-203AV** class):

  * **Settling times:** standard **1–2 s**, optional **≈0.5 s** fast.
  * **High-flow ranges:** up to **F-113AC/F-203AV** models (e.g., nominal ranges up to **1670 ln/min** depending on model).
  * Digital features; configurable control characteristics.
    Use these as **family-level guidance** for Block-1 dynamics & range envelopes. 
* Lacking a datasheet for **IN-FLOW F-201AI-PGD-00-V** (Block-2), expose parameters to the user and document assumptions in `ASSUMPTIONS.md`.

---

## 16) Testing checklist (developer)

* [ ] Unit conversions verified (L/min ↔ mol/s) at node conditions.
* [ ] Orifice law: subsonic vs choked branch unit tests.
* [ ] MFC lag: step response meets selected τ within tolerance. (Compare to 1–2 s or 0.5 s where chosen.) 
* [ ] Mass conservation within tolerance for steady points.
* [ ] UI warnings trigger correctly for: ΔP low, choked, oscillation.
* [ ] CSV/MD exports include assumption banner with **K(°C)** and **Pa(bar)**.

---

## 17) Roadmap (beyond v1)

* Add **disturbances** (supply dips, back-pressure ramps).
* Add **pipe friction** & minor losses; spatial discretization if needed.
* Add **controller tuning UI** (PI/PID gains, anti-windup, rate limits).
* Import **vendor-specific curves** (Kv vs valve position) if available.
* Optionally co-simulate in **Modelica** or validate a few points in **Aspen HYSYS Dynamics**.

---

## 18) Quick start (dev)

* **Backend:** create venv; `pip install -r requirements.txt`; run `python backend/app.py` (serves on `:5000`).
* **Frontend:** `npm i` then `npm run dev` (serves on `:5173` by default).
* Ensure **CORS** enabled on backend.

---

## 19) Caveats & disclaimers (repeat in UI/exports)

* This model uses **ideal-gas** and **isothermal** assumptions, and neglects straight-pipe friction; therefore **quantitative** predictions depend on these simplifications. Results should be treated as **engineering guidance**, not certification.

---

### Appendix A — Minimal choked-flow and subsonic formulas

* **Critical ratio:** ( \Pi_c = (2/(\gamma+1))^{\gamma/(\gamma-1)} ). If (p_d/p_u \le \Pi_c) → choked.
* **Subsonic mass flow (ideal gas, orifice-style):** ( \dot{m} = C A p_u \sqrt{\frac{2\gamma}{R T(\gamma-1)}\left[\left(\frac{p_d}{p_u}\right)^{2/\gamma} - \left(\frac{p_d}{p_u}\right)^{(\gamma+1)/\gamma}\right]} ).
* **Choked mass flow:** ( \dot{m} = C A p_u \sqrt{\frac{\gamma}{R T}}\left(\frac{2}{\gamma+1}\right)^{\frac{\gamma+1}{2(\gamma-1)}} ).
  Convert to **mol/s** via ( \dot{n}=\dot{m}/M ).

---

### Appendix B — References

* Bronkhorst **EL-FLOW Select** datasheet (family): dynamics (1–2 s, option ~0.5 s), high-flow ranges, configurable control. Used for F-203AV class guidance. 

---

**End of Plan.md**
