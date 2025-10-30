"""First-order MFC actuator model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np

from ..constants import SLPM_TO_MOL_PER_S, MOL_PER_S_TO_SLPM
from ..structures import MFCParameters


@dataclass
class MFCState:
    commanded_flow_slpm: float
    actual_flow_slpm: float
    integrator: float


def step_mfc(
    state: MFCState,
    params: MFCParameters,
    setpoint_slpm: float,
    dt: float,
) -> Tuple[MFCState, float]:
    """Advance the simplified first-order MFC model.

    A PI controller acts on the flow error and commands a target flow with
    a first-order lag representing the valve and sensor dynamics.  A rate
    limit and saturation enforce hardware limits.
    """

    error = setpoint_slpm - state.actual_flow_slpm
    new_integrator = state.integrator + error * dt
    raw_command = params.kp * error + params.ki * new_integrator
    commanded = np.clip(raw_command, 0.0, params.max_flow_slpm)

    # Rate limit
    delta = commanded - state.commanded_flow_slpm
    max_delta = params.rate_limit_slpm_per_s * dt
    if abs(delta) > max_delta:
        commanded = state.commanded_flow_slpm + np.sign(delta) * max_delta

    # First order lag for actual flow
    tau = max(params.tau_s, 1e-3)
    actual = state.actual_flow_slpm + (dt / tau) * (
        commanded - state.actual_flow_slpm
    )

    new_state = MFCState(
        commanded_flow_slpm=commanded,
        actual_flow_slpm=actual,
        integrator=new_integrator,
    )
    return new_state, actual


def initial_state(initial_flow_slpm: float = 0.0) -> MFCState:
    return MFCState(
        commanded_flow_slpm=initial_flow_slpm,
        actual_flow_slpm=initial_flow_slpm,
        integrator=0.0,
    )
