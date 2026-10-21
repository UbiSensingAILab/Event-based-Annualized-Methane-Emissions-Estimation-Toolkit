"""
Standalone Validation Script for EAMEET Simulation Results

This script validates simulation accuracy through statistical methods:
- Bootstrap Stability Test (consistency across runs)
- Bootstrap Sensitivity Analysis (parameter impact)
- Below-MDL Stability Test (consistency across runs)
- Below-MDL Sensitivity Analysis (parameter impact)

Usage:
    python validate_simulation.py <emission_events.csv> [options]

Example:
    python validate_simulation.py emission_events.csv --start-date 2025-01-01 --end-date 2025-12-31 --iterations 50

Requirements:
    - pandas, numpy (install via: pip install -r requirements.txt)
    - Bootstrap method CSV columns: rate, duration
    - Below-MDL method CSV columns: rate, duration, start_time, end_time, source, quantity
"""

import argparse
import os
import pandas as pd
import numpy as np
import json
import sys

# Import simulation functions
from simulations import extrapolation, simulate_below_mdl
from utils import probability_of_detection

# Default MDL values by technology (kg/hr)
TECHNOLOGY_MDL = {
    "InsightM": 10,
    "Qube": 2,
    "SeekOps": 0.02,
    "Bridger Photonic": 0.5,
    "GHGSat-Air": 13.6,
    "Kuva Systems": 3.5,
    "Sensirion": 3.6,
    "Aeromon": 0.1,
    "Project Canary": 0.2,
    "Long Path": 0.06,
}


def bootstrap_stability_test(rate_list, duration_list, prob_dist, start_time, end_time, num_runs=50, num_iterations=1000):
    """
    Test stability by running simulation multiple times.
    Returns: CV%, mean, std, interpretation
    """
    print("\n" + "="*70)
    print("1. BOOTSTRAP STABILITY TEST")
    print("="*70)
    print(f"Running {num_runs} simulations with {num_iterations} iterations each...")

    # Prepare distributions
    rate_dist = {"UNKNOWN": rate_list}
    duration_dist = {"UNKNOWN": duration_list}

    results = []
    for i in range(num_runs):
        result = extrapolation(
            prob_dist=prob_dist,
            rate_dist=rate_dist,
            duration_dist=duration_dist,
            start_time=start_time,
            end_time=end_time,
            MC=num_iterations
        )
        # Extract total emissions from result
        total_emissions = np.sum(result["UNKNOWN"])
        results.append(total_emissions)
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{num_runs} runs...")

    results_array = np.array(results)
    mean_val = np.mean(results_array)
    std_val = np.std(results_array)
    cv = (std_val / mean_val * 100) if mean_val > 0 else 0

    # Interpretation
    if cv < 10:
        interpretation = "✅ EXCELLENT - Results are highly consistent"
        status = "PASS"
    elif cv < 20:
        interpretation = "⚠️ ACCEPTABLE - Some variation present"
        status = "PASS"
    else:
        interpretation = "❌ POOR - High variation, increase Monte Carlo iterations"
        status = "FAIL"

    print(f"\nResults:")
    print(f"  Mean Emissions:     {mean_val:.2f} kg")
    print(f"  Std Deviation:      {std_val:.2f} kg")
    print(f"  Coefficient of Var: {cv:.2f}%")
    print(f"\nInterpretation: {interpretation}")
    print(f"Status: {status}")

    return {
        'test': 'Bootstrap Stability',
        'mean_emissions': mean_val,
        'std_emissions': std_val,
        'cv': cv,
        'interpretation': interpretation,
        'status': status
    }


def sensitivity_analysis(rate_list, duration_list, prob_dist, start_time, end_time, num_iterations=1000, perturbation=0.1):
    """
    Test sensitivity to parameter changes.
    Returns: impact of 10% changes to rates, durations, probability
    """
    print("\n" + "="*70)
    print("2. SENSITIVITY ANALYSIS")
    print("="*70)
    print("Testing impact of 10% parameter changes...")

    rate_array = np.array(rate_list)
    duration_array = np.array(duration_list)

    # Baseline
    rate_dist = {"UNKNOWN": rate_list}
    duration_dist = {"UNKNOWN": duration_list}

    baseline_result = extrapolation(
        prob_dist=prob_dist,
        rate_dist=rate_dist,
        duration_dist=duration_dist,
        start_time=start_time,
        end_time=end_time,
        MC=num_iterations
    )
    baseline_emissions = np.sum(baseline_result["UNKNOWN"])

    sensitivities = {}

    # Test rate sensitivity
    print("  Testing rate sensitivity...")
    perturbed_rate = (rate_array * (1 + perturbation)).tolist()
    perturbed_rate_dist = {"UNKNOWN": perturbed_rate}

    rate_result = extrapolation(
        prob_dist=prob_dist,
        rate_dist=perturbed_rate_dist,
        duration_dist=duration_dist,
        start_time=start_time,
        end_time=end_time,
        MC=num_iterations
    )
    rate_emissions = np.sum(rate_result["UNKNOWN"])
    rate_change = (rate_emissions - baseline_emissions) / baseline_emissions * 100
    sensitivities['rate'] = {
        'change': rate_change,
        'interpretation': f'10% increase in rates → {rate_change:.1f}% change in emissions'
    }

    # Test duration sensitivity
    print("  Testing duration sensitivity...")
    perturbed_duration = (duration_array * (1 + perturbation)).tolist()
    perturbed_duration_dist = {"UNKNOWN": perturbed_duration}

    duration_result = extrapolation(
        prob_dist=prob_dist,
        rate_dist=rate_dist,
        duration_dist=perturbed_duration_dist,
        start_time=start_time,
        end_time=end_time,
        MC=num_iterations
    )
    duration_emissions = np.sum(duration_result["UNKNOWN"])
    duration_change = (duration_emissions - baseline_emissions) / baseline_emissions * 100
    sensitivities['duration'] = {
        'change': duration_change,
        'interpretation': f'10% increase in durations → {duration_change:.1f}% change in emissions'
    }

    # Test probability sensitivity
    print("  Testing probability sensitivity...")
    perturbed_prob = {k: min(v * (1 + perturbation), 1.0) for k, v in prob_dist.items()}

    prob_result = extrapolation(
        prob_dist=perturbed_prob,
        rate_dist=rate_dist,
        duration_dist=duration_dist,
        start_time=start_time,
        end_time=end_time,
        MC=num_iterations
    )
    prob_emissions = np.sum(prob_result["UNKNOWN"])
    prob_change = (prob_emissions - baseline_emissions) / baseline_emissions * 100
    sensitivities['probability'] = {
        'change': prob_change,
        'interpretation': f'10% increase in probability → {prob_change:.1f}% change in emissions'
    }

    print(f"\nResults:")
    print(f"  Baseline Emissions: {baseline_emissions:.2f} kg")
    print(f"  Rate Sensitivity:   {sensitivities['rate']['interpretation']}")
    print(f"  Duration Sensitivity: {sensitivities['duration']['interpretation']}")
    print(f"  Probability Sensitivity: {sensitivities['probability']['interpretation']}")

    return {
        'test': 'Sensitivity Analysis',
        'baseline_emissions': baseline_emissions,
        'sensitivities': sensitivities
    }


def below_mdl_stability_test(events_df, start_time, end_time, technology, mdl_define,
                              mc_iterations, leak_data, num_runs=50):
    """
    Test below-MDL simulation stability by running it multiple times.
    Tracks both total emissions (measured + unmeasured) and unmeasured emissions separately.
    Returns: CV%, mean, std, interpretation
    """
    print("\n" + "="*70)
    print("3. BELOW-MDL STABILITY TEST")
    print("="*70)
    print(f"Running {num_runs} simulations with {mc_iterations} MC iterations each...")
    print(f"Technology: {technology}")

    total_results = []
    unmeasured_results = []
    for i in range(num_runs):
        result = simulate_below_mdl(
            events=events_df,
            start_time=start_time,
            end_time=end_time,
            mc_iterations=mc_iterations,
            technology=technology,
            mdl_define=mdl_define,
            leak_data=leak_data,
        )
        # result tuple: (total, total_lower, total_upper,
        #                measured, measured_lower, measured_upper,
        #                unmeasured, unmeasured_lower, unmeasured_upper)
        total_results.append(result[0])
        unmeasured_results.append(result[6])
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{num_runs} runs...")

    total_arr = np.array(total_results)
    unmeasured_arr = np.array(unmeasured_results)

    total_mean = np.mean(total_arr)
    total_std = np.std(total_arr)
    total_cv = (total_std / total_mean * 100) if total_mean > 0 else 0

    unmeasured_mean = np.mean(unmeasured_arr)
    unmeasured_std = np.std(unmeasured_arr)
    unmeasured_cv = (unmeasured_std / unmeasured_mean * 100) if unmeasured_mean > 0 else 0

    # Use the higher CV for overall assessment
    cv = max(total_cv, unmeasured_cv)

    if cv < 10:
        interpretation = "✅ EXCELLENT - Results are highly consistent"
        status = "PASS"
    elif cv < 20:
        interpretation = "⚠️ ACCEPTABLE - Some variation present"
        status = "PASS"
    else:
        interpretation = "❌ POOR - High variation, increase Monte Carlo iterations"
        status = "FAIL"

    print(f"\nResults:")
    print(f"  Total Emissions  - Mean: {total_mean:.2f} kg, Std: {total_std:.2f} kg, CV: {total_cv:.2f}%")
    print(f"  Unmeasured Only  - Mean: {unmeasured_mean:.2f} kg, Std: {unmeasured_std:.2f} kg, CV: {unmeasured_cv:.2f}%")
    print(f"  Overall CV (max): {cv:.2f}%")
    print(f"\nInterpretation: {interpretation}")
    print(f"Status: {status}")

    return {
        'test': 'Below-MDL Stability',
        'total_mean_emissions': total_mean,
        'total_std_emissions': total_std,
        'total_cv': total_cv,
        'unmeasured_mean_emissions': unmeasured_mean,
        'unmeasured_std_emissions': unmeasured_std,
        'unmeasured_cv': unmeasured_cv,
        'cv': cv,
        'interpretation': interpretation,
        'status': status,
    }


def below_mdl_sensitivity_analysis(events_df, start_time, end_time, technology,
                                    mdl_define, mc_iterations, leak_data,
                                    perturbation=0.1):
    """
    Test below-MDL sensitivity to parameter changes.
    Perturbations: leak rates (+10%), MDL threshold (+10%), event durations (+10%).
    """
    print("\n" + "="*70)
    print("4. BELOW-MDL SENSITIVITY ANALYSIS")
    print("="*70)
    print("Testing impact of 10% parameter changes...")

    # --- Baseline ---
    baseline = simulate_below_mdl(
        events=events_df,
        start_time=start_time,
        end_time=end_time,
        mc_iterations=mc_iterations,
        technology=technology,
        mdl_define=mdl_define,
        leak_data=leak_data,
    )
    baseline_total = baseline[0]

    sensitivities = {}

    # --- Leak-rate perturbation ---
    print("  Testing leak-rate sensitivity...")
    perturbed_leak_data = (np.array(leak_data, dtype=float) * (1 + perturbation)).tolist()
    leak_result = simulate_below_mdl(
        events=events_df,
        start_time=start_time,
        end_time=end_time,
        mc_iterations=mc_iterations,
        technology=technology,
        mdl_define=mdl_define,
        leak_data=perturbed_leak_data,
    )
    leak_total = leak_result[0]
    leak_change = ((leak_total - baseline_total) / baseline_total * 100) if baseline_total > 0 else 0
    sensitivities['leak_rate'] = {
        'change': leak_change,
        'interpretation': f'10% increase in leak rates → {leak_change:.1f}% change in emissions',
    }

    # --- Detection-capability (POD) perturbation ---
    # NOTE: In the constant-POD below-MDL path, the MDL VALUE never enters the detection
    # decision -- detection is a Bernoulli draw against POD, and MDL is not used. The only lever
    # the model responds to is the probability of detection. The previous version perturbed an
    # MDL MAGNITUDE and passed it through the "define_technology" branch, where the code sets
    # POD = mdl_define -- i.e. it fed a kg/hr value in as a probability (>1 for most sensors),
    # forcing certain detection and collapsing unresolved emissions to ~0 (the spurious
    # "10% MDL increase -> -99.9%" result). We instead perturb the detection probability
    # directly: a poorer detector (POD reduced by `perturbation`) should MISS MORE emissions,
    # i.e. INCREASE the unresolved (below-MDL) component. We report the change in that component
    # (return index 6), since that is the quantity an MDL/detection sensitivity concerns.
    print("  Testing detection-capability (POD) sensitivity...")
    baseline_pod, _ = probability_of_detection(technology, mdl_define=mdl_define)
    baseline_ue = baseline[6]  # unresolved (below-MDL) emissions in the baseline run

    if callable(baseline_pod):
        sensitivities['detection_pod'] = {
            'change': 0,
            'interpretation': ('Skipped - wind-dependent POD is a function of emission rate; '
                               'a scalar POD perturbation is not applicable in this mode'),
        }
    else:
        # A poorer detector: reduce POD by `perturbation` (clamped to [0, 1]).
        perturbed_pod = float(np.clip(baseline_pod * (1 - perturbation), 0.0, 1.0))
        pod_result = simulate_below_mdl(
            events=events_df,
            start_time=start_time,
            end_time=end_time,
            mc_iterations=mc_iterations,
            technology="define_technology",
            # define_technology now takes a true MDL (mdl_define) plus an explicit POD (pod_define).
            # MDL is unused in the flat-POD path, so any positive placeholder satisfies the API.
            mdl_define=(mdl_define if mdl_define is not None else TECHNOLOGY_MDL.get(technology, 1.0)),
            pod_define=perturbed_pod,      # the perturbed detection probability
            leak_data=leak_data,
        )
        pod_ue = pod_result[6]
        ue_change = ((pod_ue - baseline_ue) / baseline_ue * 100) if baseline_ue > 0 else 0
        sensitivities['detection_pod'] = {
            'baseline_pod': baseline_pod,
            'perturbed_pod': perturbed_pod,
            'change': ue_change,
            'interpretation': (f'{perturbation*100:.0f}% lower POD ({baseline_pod:.2f} -> '
                               f'{perturbed_pod:.2f}) -> {ue_change:+.1f}% change in unresolved '
                               f'(below-MDL) emissions'),
        }

    # --- Event-duration perturbation ---
    print("  Testing event-duration sensitivity...")
    perturbed_events = events_df.copy()
    perturbed_events['duration'] = perturbed_events['duration'] * (1 + perturbation)
    perturbed_events['quantity'] = perturbed_events['rate'] * perturbed_events['duration']
    dur_result = simulate_below_mdl(
        events=perturbed_events,
        start_time=start_time,
        end_time=end_time,
        mc_iterations=mc_iterations,
        technology=technology,
        mdl_define=mdl_define,
        leak_data=leak_data,
    )
    dur_total = dur_result[0]
    dur_change = ((dur_total - baseline_total) / baseline_total * 100) if baseline_total > 0 else 0
    sensitivities['event_duration'] = {
        'change': dur_change,
        'interpretation': f'10% increase in event durations → {dur_change:.1f}% change in emissions',
    }

    print(f"\nResults:")
    print(f"  Baseline Total Emissions: {baseline_total:.2f} kg")
    print(f"  Leak-Rate Sensitivity:    {sensitivities['leak_rate']['interpretation']}")
    print(f"  Detection (POD) Sensitivity: {sensitivities['detection_pod']['interpretation']}")
    print(f"  Duration Sensitivity:     {sensitivities['event_duration']['interpretation']}")

    return {
        'test': 'Below-MDL Sensitivity Analysis',
        'baseline_emissions': baseline_total,
        'sensitivities': sensitivities,
    }


def run_validation(csv_file, start_date, end_date, num_iterations=50, output_json=None,
                   method="both", technology="Qube", mdl_define=None, mc_iterations=10):
    """
    Main validation function - runs all tests and generates report.

    Args:
        csv_file: Path to emission events CSV
        start_date: Simulation start date string (YYYY-MM-DD)
        end_date: Simulation end date string (YYYY-MM-DD)
        num_iterations: Number of validation runs (bootstrap stability & below-MDL stability)
        output_json: Optional path for JSON results
        method: "bootstrap", "below-mdl", or "both"
        technology: Detection technology name for below-MDL
        mdl_define: User-defined MDL value (float or None)
        mc_iterations: MC iterations per below-MDL run
    """
    print("\n" + "="*70)
    print("EAMEET SIMULATION VALIDATION")
    print("="*70)
    print(f"Input File: {csv_file}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Validation Iterations: {num_iterations}")
    print(f"Method: {method}")
    if method in ("below-mdl", "both"):
        print(f"Technology: {technology}")
        print(f"MC Iterations per below-MDL run: {mc_iterations}")
    print("="*70)

    # Load data
    try:
        df = pd.read_csv(csv_file)
        print(f"\n✓ Loaded {len(df)} emission events")
    except Exception as e:
        print(f"\n❌ Error loading CSV: {e}")
        return 1

    # Determine which methods to run
    run_bootstrap = method in ("bootstrap", "both")
    run_below_mdl = method in ("below-mdl", "both")

    # Validate columns for bootstrap
    bootstrap_cols = ['rate', 'duration']
    if run_bootstrap:
        missing = [c for c in bootstrap_cols if c not in df.columns]
        if missing:
            print(f"❌ Missing required columns for bootstrap: {missing}")
            print(f"Available columns: {list(df.columns)}")
            return 1

    # Validate columns for below-MDL
    below_mdl_cols = ['rate', 'duration', 'start_time', 'end_time', 'source', 'quantity']
    if run_below_mdl:
        missing_bdm = [c for c in below_mdl_cols if c not in df.columns]
        if missing_bdm:
            if method == "both":
                print(f"⚠️  CSV lacks columns for below-MDL ({missing_bdm}); running bootstrap only.")
                run_below_mdl = False
            else:
                print(f"❌ Missing required columns for below-MDL: {missing_bdm}")
                print(f"Available columns: {list(df.columns)}")
                return 1

    # Ensure at least one method can run
    if not run_bootstrap and not run_below_mdl:
        print("❌ No validation method could run with the provided data.")
        return 1

    # Parse dates
    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date)

    results = {}

    # ---- Bootstrap validation ----
    if run_bootstrap:
        rate_array = df['rate'].values
        duration_array = df['duration'].values

        # Remove NaN or zero values
        valid_mask = (rate_array > 0) & (duration_array > 0) & ~np.isnan(rate_array) & ~np.isnan(duration_array)
        rate_array = rate_array[valid_mask]
        duration_array = duration_array[valid_mask]

        rate_list = rate_array.tolist()
        duration_list = duration_array.tolist()

        print(f"\n✓ Valid emission events (bootstrap): {len(rate_array)}")
        print(f"  Rate range: {rate_array.min():.4f} to {rate_array.max():.2f} kg/hr")
        print(f"  Duration range: {duration_array.min():.2f} to {duration_array.max():.2f} hours")

        total_hours = (end_datetime - start_datetime).total_seconds() / 3600
        total_event_hours = duration_array.sum()
        poe = min(max(total_event_hours / total_hours, 0.001), 0.999)

        print(f"\nBootstrap Simulation Parameters:")
        print(f"  Total Hours: {total_hours:.1f}")
        print(f"  Event Hours: {total_event_hours:.1f}")
        print(f"  Probability of Emission (POE): {poe:.4f}")

        prob_dist = {"UNKNOWN": poe}

        results['bootstrap_stability'] = bootstrap_stability_test(
            rate_list, duration_list, prob_dist, start_datetime, end_datetime,
            num_runs=num_iterations, num_iterations=1000
        )

        results['bootstrap_sensitivity'] = sensitivity_analysis(
            rate_list, duration_list, prob_dist, start_datetime, end_datetime,
            num_iterations=1000, perturbation=0.1
        )

    # ---- Below-MDL validation ----
    if run_below_mdl:
        # Prepare events DataFrame for simulate_below_mdl
        events_df = df.copy()

        # Build leak_data from the CSV rate column so we pass it explicitly
        leak_data = df['rate'].dropna().values
        leak_data = leak_data[leak_data > 0].tolist()

        print(f"\n✓ Valid emission events (below-MDL): {len(events_df)}")
        print(f"  Sources: {events_df['source'].nunique()}")

        results['below_mdl_stability'] = below_mdl_stability_test(
            events_df, start_datetime, end_datetime,
            technology=technology, mdl_define=mdl_define,
            mc_iterations=mc_iterations, leak_data=leak_data,
            num_runs=num_iterations,
        )

        results['below_mdl_sensitivity'] = below_mdl_sensitivity_analysis(
            events_df, start_datetime, end_datetime,
            technology=technology, mdl_define=mdl_define,
            mc_iterations=mc_iterations, leak_data=leak_data,
            perturbation=0.1,
        )

    # ---- Overall Assessment ----
    print("\n" + "="*70)
    print("OVERALL ASSESSMENT")
    print("="*70)

    all_passed = True
    if run_bootstrap:
        bs_status = results['bootstrap_stability']['status']
        print(f"Bootstrap Stability Test: {bs_status}")
        if bs_status != 'PASS':
            all_passed = False
    if run_below_mdl:
        bdm_status = results['below_mdl_stability']['status']
        print(f"Below-MDL Stability Test: {bdm_status}")
        if bdm_status != 'PASS':
            all_passed = False

    if all_passed:
        overall = "✅ PASS - Simulation is stable and consistent"
        recommendation = "Results are suitable for use. CV is within acceptable limits."
        exit_status = 0
    else:
        overall = "❌ FAIL - Simulation shows high variation"
        recommendation = "Increase Monte Carlo iterations in your simulation or collect more data."
        exit_status = 1

    print(f"Assessment: {overall}")
    print(f"\nRecommendation: {recommendation}")
    print("="*70 + "\n")

    # Save results to JSON if requested
    if output_json:
        results['overall'] = {
            'all_passed': all_passed,
            'methods_run': {
                'bootstrap': run_bootstrap,
                'below_mdl': run_below_mdl,
            },
            'assessment': overall,
            'recommendation': recommendation
        }

        # Convert numpy types to Python types for JSON serialization
        def convert_types(obj):
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(item) for item in obj]
            return obj

        results = convert_types(results)

        with open(output_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✓ Results saved to: {output_json}\n")

    return exit_status


def main():
    parser = argparse.ArgumentParser(
        description='Validate EAMEET simulation results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Bootstrap only (backward compatible)
  python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -i 50 -m bootstrap

  # Below-MDL only
  python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -i 5 -m below-mdl -t Qube --mc-iterations 5

  # Both methods
  python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -i 5 -m both --mc-iterations 5

  # JSON output
  python validate_simulation.py emission_events.csv -s 2025-01-01 -e 2025-12-31 -m both -i 5 --mc-iterations 5 -o results.json
        """
    )

    parser.add_argument('csv_file', help='Path to emission events CSV file')
    parser.add_argument('-s', '--start-date', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('-e', '--end-date', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('-i', '--iterations', type=int, default=50,
                       help='Number of validation iterations (default: 50)')
    parser.add_argument('-o', '--output', help='Output JSON file for results (optional)')
    parser.add_argument('-m', '--method', choices=['bootstrap', 'below-mdl', 'both'],
                       default='both', help='Validation method (default: both)')
    parser.add_argument('-t', '--technology', default='Qube',
                       help='Detection technology name for below-MDL (default: Qube)')
    parser.add_argument('--mdl', type=float, default=None,
                       help='User-defined MDL value (float)')
    parser.add_argument('--mc-iterations', type=int, default=10,
                       help='MC iterations per below-MDL run (default: 10)')

    args = parser.parse_args()

    # Run validation
    exit_code = run_validation(
        args.csv_file,
        args.start_date,
        args.end_date,
        args.iterations,
        args.output,
        method=args.method,
        technology=args.technology,
        mdl_define=args.mdl,
        mc_iterations=args.mc_iterations,
    )

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
