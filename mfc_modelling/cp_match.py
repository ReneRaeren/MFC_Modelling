"""Cp-matching helper approximating air with an O₂/CO₂ mixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple
import numpy as np

R = 8.314462618


@dataclass
class CpMatchResult:
    y_o2: float
    y_co2: float
    rms_error: float
    temperature_grid: np.ndarray
    cp_target: np.ndarray
    cp_mix: np.ndarray


# NASA 7-coefficient polynomials for cp/R (JANAF) over 200-1000 K
NASA_COEFFS = {
    "O2": np.array([3.78245636, -2.99673416e-3, 9.84730201e-6, -9.68129509e-9, 3.24372837e-12]),
    "CO2": np.array([2.35677352, 8.98459677e-3, -7.12356269e-6, 2.45919022e-9, -1.43699548e-13]),
    "N2": np.array([3.53100528, -1.23660987e-4, -5.02999433e-7, 2.43530612e-9, -1.40881235e-12]),
}


def _cp_species(name: str, T: np.ndarray) -> np.ndarray:
    a = NASA_COEFFS[name]
    return R * (
        a[0]
        + a[1] * T
        + a[2] * T**2
        + a[3] * T**3
        + a[4] * T**4
    )


def cp_air(T: np.ndarray) -> np.ndarray:
    y_o2 = 0.21
    y_n2 = 0.79
    return y_o2 * _cp_species("O2", T) + y_n2 * _cp_species("N2", T)


def cp_mix(y_o2: float, T: np.ndarray) -> np.ndarray:
    y_co2 = 1.0 - y_o2
    return y_o2 * _cp_species("O2", T) + y_co2 * _cp_species("CO2", T)


def match_air_cp(
    temperature_grid: Iterable[float] = (250.0, 300.0, 400.0, 600.0, 800.0)
) -> CpMatchResult:
    T = np.array(list(temperature_grid))
    target = cp_air(T)

    y_candidates = np.linspace(0.0, 1.0, 501)
    best_err = float("inf")
    best_y = 0.0
    best_cp = None

    for y in y_candidates:
        mix = cp_mix(y, T)
        err = np.sqrt(np.mean((mix - target) ** 2))
        if err < best_err:
            best_err = err
            best_y = y
            best_cp = mix

    return CpMatchResult(
        y_o2=best_y,
        y_co2=1.0 - best_y,
        rms_error=best_err,
        temperature_grid=T,
        cp_target=target,
        cp_mix=best_cp,
    )
