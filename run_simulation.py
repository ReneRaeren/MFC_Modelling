"""Simple CLI to execute a single scenario and print summary statistics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from mfc_modelling import SimulationConfig, Scenario, run_case


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--o2", type=float, default=15.0, help="O2 flow setpoint [SLPM]")
    parser.add_argument("--co2", type=float, default=60.0, help="CO2 flow setpoint [SLPM]")
    parser.add_argument(
        "--supply", type=float, default=8.0, help="Supply pressure [bar absolute]"
    )
    parser.add_argument(
        "--buffer", type=float, default=0.0, help="Buffer volume between blocks [cm^3]"
    )
    parser.add_argument(
        "--duration", type=float, default=15.0, help="Simulation duration [s]"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Optional path to save JSON results"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SimulationConfig(
        scenario=Scenario(o2_flow_slpm=args.o2, co2_flow_slpm=args.co2),
        supply_pressure_bar=args.supply,
        buffer_volume_cm3=args.buffer,
        duration_s=args.duration,
    )
    result = run_case(config)

    pressures_final = result.timeseries.pressures_bar[-1]
    flows_final = result.timeseries.flows_slpm[-1]

    summary = {
        "o2_setpoint": args.o2,
        "co2_setpoint": args.co2,
        "supply_bar": args.supply,
        "buffer_cm3": args.buffer,
        "final_pressures_bar": pressures_final.tolist(),
        "final_flows_slpm": flows_final.tolist(),
        "warnings": result.warnings,
    }

    print(json.dumps(summary, indent=2))

    if args.output:
        data = {
            "summary": summary,
            "time": result.timeseries.time.tolist(),
            "pressures_bar": result.timeseries.pressures_bar.tolist(),
            "flows_slpm": result.timeseries.flows_slpm.tolist(),
        }
        args.output.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
