"""Typed containers for simulation configuration and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence
import numpy as np

ArrayLike = Sequence[float]


@dataclass
class MFCParameters:
    """Simplified first-order actuator model parameters."""

    max_flow_slpm: float
    tau_s: float = 1.5
    rate_limit_slpm_per_s: float = 500.0
    kp: float = 1.5
    ki: float = 0.5


@dataclass
class ReactorSink:
    """Simple reactor-side pressure model."""

    target_pressure_bar: float = 2.0
    conductance_slpm_per_bar: float = 200.0


@dataclass
class Scenario:
    """Single steady operating point used in a simulation."""

    o2_flow_slpm: float
    co2_flow_slpm: float
    reactor_pressure_bar: float = 2.0


@dataclass
class SimulationConfig:
    """High-level configuration for a single simulation run."""

    scenario: Scenario
    supply_pressure_bar: float = 8.0
    buffer_volume_cm3: float = 0.0
    dt_controller_s: float = 0.1
    dt_ode_s: float = 0.01
    duration_s: float = 15.0
    mixing_mfc: MFCParameters = field(
        default_factory=lambda: MFCParameters(max_flow_slpm=180.0)
    )
    split_mfc: MFCParameters = field(
        default_factory=lambda: MFCParameters(max_flow_slpm=115.0)
    )
    reactor_sink: ReactorSink = field(default_factory=ReactorSink)


@dataclass
class TimeSeries:
    time: np.ndarray
    pressures_bar: np.ndarray
    flows_slpm: np.ndarray
    commanded_flows_slpm: np.ndarray


@dataclass
class SimulationResult:
    config: SimulationConfig
    timeseries: TimeSeries
    metadata: Mapping[str, float]
    warnings: List[str]


@dataclass
class SweepResult:
    cases: Mapping[str, SimulationResult]
    metadata: Mapping[str, float]
