"""High level simulation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping
import numpy as np

from .network import (
    NetworkState,
    NodePressures,
    build_network_parameters,
    compute_flows,
    derivative,
)
from .models.mfc import MFCState, initial_state, step_mfc
from .structures import (
    Scenario,
    SimulationConfig,
    SimulationResult,
    SweepResult,
    TimeSeries,
)


def _initial_pressures(config: SimulationConfig) -> NodePressures:
    p_reactor = config.scenario.reactor_pressure_bar
    return NodePressures(
        feed_bar=p_reactor,
        buffer_bar=p_reactor,
        split_bar=p_reactor,
        reactor1_bar=p_reactor,
        reactor2_bar=p_reactor,
    )


def run_case(config: SimulationConfig) -> SimulationResult:
    params = build_network_parameters(config)
    state = NetworkState(pressures_bar=_initial_pressures(config))

    mfc_o2 = initial_state()
    mfc_co2 = initial_state()
    mfc_split1 = initial_state()
    mfc_split2 = initial_state()

    steps = int(config.duration_s / config.dt_ode_s) + 1
    t = np.linspace(0.0, config.duration_s, steps)
    pressures = np.zeros((steps, 5))
    actual_flows = np.zeros((steps, 4))
    commanded_flows = np.zeros((steps, 4))

    controller_counter = 0.0
    controller_period = config.dt_controller_s

    o2_setpoint = config.scenario.o2_flow_slpm
    co2_setpoint = config.scenario.co2_flow_slpm
    split_setpoint = (o2_setpoint + co2_setpoint) / 2.0

    for i in range(steps):
        time = t[i]
        controller_counter += config.dt_ode_s
        if controller_counter >= controller_period:
            controller_counter = 0.0
            mfc_o2, o2_actual = step_mfc(
                mfc_o2, config.mixing_mfc, o2_setpoint, controller_period
            )
            mfc_co2, co2_actual = step_mfc(
                mfc_co2, config.mixing_mfc, co2_setpoint, controller_period
            )
            mfc_split1, split1_actual = step_mfc(
                mfc_split1, config.split_mfc, split_setpoint, controller_period
            )
            mfc_split2, split2_actual = step_mfc(
                mfc_split2, config.split_mfc, split_setpoint, controller_period
            )
        else:
            o2_actual = mfc_o2.actual_flow_slpm
            co2_actual = mfc_co2.actual_flow_slpm
            split1_actual = mfc_split1.actual_flow_slpm
            split2_actual = mfc_split2.actual_flow_slpm

        flows = compute_flows(
            state.pressures_bar,
            config,
            params,
            o2_actual,
            co2_actual,
            split1_actual,
            split2_actual,
        )

        pressures[i] = state.as_array()
        actual_flows[i] = np.array(
            [flows.o2_in_slpm, flows.co2_in_slpm, flows.split1_slpm, flows.split2_slpm]
        )
        commanded_flows[i] = np.array(
            [
                mfc_o2.commanded_flow_slpm,
                mfc_co2.commanded_flow_slpm,
                mfc_split1.commanded_flow_slpm,
                mfc_split2.commanded_flow_slpm,
            ]
        )

        k1 = derivative(state, flows, config, params)
        mid_state = NetworkState.from_array(state.as_array() + 0.5 * config.dt_ode_s * k1)
        mid_flows = compute_flows(
            mid_state.pressures_bar,
            config,
            params,
            o2_actual,
            co2_actual,
            split1_actual,
            split2_actual,
        )
        k2 = derivative(mid_state, mid_flows, config, params)

        new_pressures = state.as_array() + config.dt_ode_s * k2
        state = NetworkState.from_array(new_pressures)

    ts = TimeSeries(
        time=t,
        pressures_bar=pressures,
        flows_slpm=actual_flows,
        commanded_flows_slpm=commanded_flows,
    )

    metadata = {
        "o2_setpoint_slpm": o2_setpoint,
        "co2_setpoint_slpm": co2_setpoint,
        "split_setpoint_slpm": split_setpoint,
    }

    warnings = []
    if np.any(ts.pressures_bar < 0.5):
        warnings.append("Pressures dropped below 0.5 bar; check supply or conductance settings.")
    targets = np.array([[o2_setpoint, co2_setpoint]])
    steady_slice = ts.flows_slpm[int(0.8 * len(ts.time)) :, :2]
    if np.any(steady_slice < 0.98 * targets):
        warnings.append("Upstream flow saturation detected in mixing block.")

    return SimulationResult(config=config, timeseries=ts, metadata=metadata, warnings=warnings)


def run_sweep(configs: Mapping[str, SimulationConfig]) -> SweepResult:
    cases: Dict[str, SimulationResult] = {}
    for key, config in configs.items():
        cases[key] = run_case(config)
    return SweepResult(cases=cases, metadata={"count": float(len(cases))})
