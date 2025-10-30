"""Network equations for the series MFC system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np

from .constants import (
    R_UNIVERSAL,
    STANDARD_TEMPERATURE_K,
    SLPM_TO_MOL_PER_S,
    MOL_PER_S_TO_SLPM,
    PA_TO_BAR,
)
from .structures import MFCParameters, SimulationConfig


DEFAULT_FEED_VOLUME_CM3 = 120.0
DEFAULT_SPLIT_VOLUME_CM3 = 60.0
DEFAULT_REACTOR_VOLUME_CM3 = 120.0


@dataclass
class NodePressures:
    feed_bar: float
    buffer_bar: float
    split_bar: float
    reactor1_bar: float
    reactor2_bar: float


@dataclass
class NetworkState:
    """Dynamic state of the gas volumes in the network."""

    pressures_bar: NodePressures

    def as_array(self) -> np.ndarray:
        return np.array(
            [
                self.pressures_bar.feed_bar,
                self.pressures_bar.buffer_bar,
                self.pressures_bar.split_bar,
                self.pressures_bar.reactor1_bar,
                self.pressures_bar.reactor2_bar,
            ]
        )

    @classmethod
    def from_array(cls, values: np.ndarray) -> "NetworkState":
        return cls(
            pressures_bar=NodePressures(
                feed_bar=values[0],
                buffer_bar=values[1],
                split_bar=values[2],
                reactor1_bar=values[3],
                reactor2_bar=values[4],
            )
        )


@dataclass
class NetworkFlows:
    o2_in_slpm: float
    co2_in_slpm: float
    restrictor_slpm: float
    split1_slpm: float
    split2_slpm: float
    reactor1_slpm: float
    reactor2_slpm: float


@dataclass
class Volumes:
    feed_m3: float
    buffer_m3: float
    split_m3: float
    reactor_m3: float


def litres_to_m3(value: float) -> float:
    return value / 1000.0


def cm3_to_m3(value: float) -> float:
    return value * 1.0e-6


def _effective_cv(max_flow_slpm: float) -> float:
    return max_flow_slpm


def _orifice_flow(cv: float, upstream_bar: float, downstream_bar: float) -> float:
    delta = max(upstream_bar - downstream_bar, 0.0)
    if delta <= 0.0:
        return 0.0
    return cv * np.sqrt(delta)


@dataclass
class NetworkParameters:
    o2_cv: float
    co2_cv: float
    split_cv: float
    restrictor_cv: float
    sink_conductance: float
    volumes: Volumes


def build_network_parameters(config: SimulationConfig) -> NetworkParameters:
    buffer_volume_cm3 = config.buffer_volume_cm3
    restrictor_cv = 250.0 if buffer_volume_cm3 > 0.0 else 1.0e6
    volumes = Volumes(
        feed_m3=cm3_to_m3(DEFAULT_FEED_VOLUME_CM3),
        buffer_m3=cm3_to_m3(buffer_volume_cm3 if buffer_volume_cm3 > 0 else 1.0),
        split_m3=cm3_to_m3(DEFAULT_SPLIT_VOLUME_CM3),
        reactor_m3=cm3_to_m3(DEFAULT_REACTOR_VOLUME_CM3),
    )
    return NetworkParameters(
        o2_cv=_effective_cv(config.mixing_mfc.max_flow_slpm),
        co2_cv=_effective_cv(config.mixing_mfc.max_flow_slpm),
        split_cv=_effective_cv(config.split_mfc.max_flow_slpm),
        restrictor_cv=restrictor_cv,
        sink_conductance=config.reactor_sink.conductance_slpm_per_bar,
        volumes=volumes,
    )


def compute_flows(
    pressures: NodePressures,
    config: SimulationConfig,
    params: NetworkParameters,
    o2_command_slpm: float,
    co2_command_slpm: float,
    split1_command_slpm: float,
    split2_command_slpm: float,
) -> NetworkFlows:
    supply_bar = config.supply_pressure_bar

    o2_available = _orifice_flow(params.o2_cv, supply_bar, pressures.feed_bar)
    co2_available = _orifice_flow(params.co2_cv, supply_bar, pressures.feed_bar)
    o2_flow = min(o2_available, o2_command_slpm)
    co2_flow = min(co2_available, co2_command_slpm)

    if config.buffer_volume_cm3 > 0.0:
        restrictor_flow = _orifice_flow(
            params.restrictor_cv, pressures.feed_bar, pressures.buffer_bar
        )
        available_to_split = restrictor_flow
    else:
        restrictor_flow = o2_flow + co2_flow
        available_to_split = restrictor_flow

    total_split_command = max(split1_command_slpm + split2_command_slpm, 1e-9)
    total_split_flow = min(available_to_split, total_split_command)
    ratio = total_split_flow / total_split_command
    split1_flow = split1_command_slpm * ratio
    split2_flow = split2_command_slpm * ratio

    desired_reactor1 = params.sink_conductance * max(
        pressures.split_bar - pressures.reactor1_bar, 0.0
    )
    desired_reactor2 = params.sink_conductance * max(
        pressures.split_bar - pressures.reactor2_bar, 0.0
    )
    total_desired = max(desired_reactor1 + desired_reactor2, 1e-9)
    total_available = split1_flow + split2_flow
    scaling = min(1.0, total_available / total_desired)
    reactor1_flow = desired_reactor1 * scaling
    reactor2_flow = desired_reactor2 * scaling

    return NetworkFlows(
        o2_in_slpm=o2_flow,
        co2_in_slpm=co2_flow,
        restrictor_slpm=restrictor_flow,
        split1_slpm=split1_flow,
        split2_slpm=split2_flow,
        reactor1_slpm=reactor1_flow,
        reactor2_slpm=reactor2_flow,
    )


def derivative(
    state: NetworkState,
    flows: NetworkFlows,
    config: SimulationConfig,
    params: NetworkParameters,
) -> np.ndarray:
    p = state.pressures_bar
    v = params.volumes
    T = STANDARD_TEMPERATURE_K
    coeff_feed = PA_TO_BAR * R_UNIVERSAL * T / v.feed_m3
    coeff_buffer = PA_TO_BAR * R_UNIVERSAL * T / max(v.buffer_m3, 1e-9)
    coeff_split = PA_TO_BAR * R_UNIVERSAL * T / v.split_m3
    coeff_reactor = PA_TO_BAR * R_UNIVERSAL * T / v.reactor_m3

    o2_mol = flows.o2_in_slpm * SLPM_TO_MOL_PER_S
    co2_mol = flows.co2_in_slpm * SLPM_TO_MOL_PER_S
    split1_mol = flows.split1_slpm * SLPM_TO_MOL_PER_S
    split2_mol = flows.split2_slpm * SLPM_TO_MOL_PER_S
    restrictor_mol = flows.restrictor_slpm * SLPM_TO_MOL_PER_S
    reactor1_mol = flows.reactor1_slpm * SLPM_TO_MOL_PER_S
    reactor2_mol = flows.reactor2_slpm * SLPM_TO_MOL_PER_S

    feed_in = o2_mol + co2_mol
    if config.buffer_volume_cm3 > 0.0:
        feed_out = restrictor_mol
        buffer_in = restrictor_mol
        buffer_out = split1_mol + split2_mol
    else:
        feed_out = split1_mol + split2_mol
        buffer_in = 0.0
        buffer_out = 0.0

    split_in = split1_mol + split2_mol
    split_out = reactor1_mol + reactor2_mol

    dp_feed = (feed_in - feed_out) * coeff_feed
    dp_buffer = (buffer_in - buffer_out) * coeff_buffer
    dp_split = (split_in - split_out) * coeff_split

    dp_reactor1 = (
        (split1_mol - reactor1_mol)
        * coeff_reactor
        - (state.pressures_bar.reactor1_bar - config.scenario.reactor_pressure_bar)
        * 0.25
    )
    dp_reactor2 = (
        (split2_mol - reactor2_mol)
        * coeff_reactor
        - (state.pressures_bar.reactor2_bar - config.scenario.reactor_pressure_bar)
        * 0.25
    )

    return np.array([dp_feed, dp_buffer, dp_split, dp_reactor1, dp_reactor2])
