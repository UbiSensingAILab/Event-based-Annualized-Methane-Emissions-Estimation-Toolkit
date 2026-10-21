"""
Simulation functions for emission estimation.

This module contains all simulation-related functions:
- extrapolation: Bootstrap simulation for unmeasured emissions
- simulate_below_mdl: Simulation for emissions below detection limit
- simulate_duration_uncertainty: Duration uncertainty simulation
"""

import numpy as np
import pandas as pd
import os
from multiprocessing import Pool, cpu_count
from utils import probability_of_detection
from scipy.stats import lognorm, norm, uniform, expon, weibull_min, gamma

# Load leak rate data (used by simulate_below_mdl)
_leak_rates = None
_leaks_dist = None
_num_comps = None

# The Type 1 simulation integrates rate x duration with durations in HOURS and reports kg, so every
# component-scale rate must be in kg/h when it is sampled. The bundled Rutherford et al. (2021) sample
# (sample_leak_rate.csv, column 'gpersec') is stored in g/s and is converted on loading.
G_PER_S_TO_KG_PER_H = 3.6
LEAK_UNIT_FACTORS = {"kg/h": 1.0, "kg/hr": 1.0, "g/s": G_PER_S_TO_KG_PER_H}


def _load_leak_data(leak_data=None, num_components=None, leak_units="kg/h"):
    """Load leak rate data from CSV file (lazy loading) or use provided leak data
    
    Args:
        leak_data: Optional list of component-scale leak rate values. If provided, uses this instead of
            loading from file. Values are in kg/h unless `leak_units` says otherwise.
        leak_units: Unit of `leak_data`: "kg/h" (default) or "g/s" (converted with the factor 3.6). The
            bundled sample_leak_rate.csv is always read as g/s (its column is named 'gpersec').
        num_components: Optional sample (array) of the number of emitting components per hypothetical event,
            e.g. drawn from a site-specific component count. The rate of a hypothetical event is a
            component-scale rate drawn from `leak_data` times a draw from this sample. Default (None): the
            generic prior of EAMEET v1.0, a normal distribution with mean 2,720 and SD 800 truncated to
            [1, 5440] components, which the synthetic-truth validation (SI Section S12) found to govern the
            Type 1 term; a site-specific count should be supplied whenever the site inventory is known.
    """
    global _leak_rates, _leaks_dist, _num_comps
    
    if leak_units not in LEAK_UNIT_FACTORS:
        raise ValueError(f"leak_units must be one of {sorted(LEAK_UNIT_FACTORS)}, got {leak_units!r}")
    if num_components is not None:
        _num_comps = np.maximum(np.asarray(num_components, dtype=float), 1.0)
    if _leaks_dist is None or leak_data is not None:
        if leak_data is not None:
            # Use user-provided leak data, converted to kg/h
            # Convert to numpy array and ensure values are positive
            leaks_array = np.array(leak_data, dtype=float) * LEAK_UNIT_FACTORS[leak_units]
            # Replace zeros or negative values with 0.0001
            _leaks_dist = np.where(leaks_array <= 0, 0.0001, leaks_array)
            _leak_rates = None  # Not needed when using user data
        else:
            # Load from default CSV file
            # Get the directory where this file is located
            current_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(current_dir, "sample_leak_rate.csv")
            
            if os.path.exists(csv_path):
                _leak_rates = pd.read_csv(csv_path)
                # The file stores g/s (column 'gpersec'); the simulation needs kg/h
                leaks_array = _leak_rates["gpersec"].values * G_PER_S_TO_KG_PER_H
                # Replace zeros with 0.0001 using numpy where
                _leaks_dist = np.where(leaks_array == 0, 0.0001, leaks_array)
            else:
                raise FileNotFoundError(f"Default leak data file not found: {csv_path}")
        
        # Component distribution - use rejection sampling more efficiently
        # (only generate if not already set, or if using new leak data)
        if num_components is None and (_num_comps is None or leak_data is not None):
            mean = 2720  # Centered within the range of 1 and 5440
            std_dev = 800  # Adjust for desired spread
            
            # Generate samples more efficiently using numpy
            # Generate more samples than needed to account for rejection
            samples_needed = 10000
            # Generate ~1.5x samples to account for rejection (empirical)
            samples_to_generate = int(samples_needed * 1.5)
            samples = np.random.normal(mean, std_dev, samples_to_generate)
            # Filter and clip to valid range
            valid_samples = samples[(samples >= 1) & (samples <= 5440)]
            # If we don't have enough, generate more
            while len(valid_samples) < samples_needed:
                additional = np.random.normal(mean, std_dev, samples_needed)
                valid_samples = np.concatenate([valid_samples, additional[(additional >= 1) & (additional <= 5440)]])
            _num_comps = valid_samples[:samples_needed].astype(int)


def _extrapolation_continuous_single_iteration(args):
    """
    Helper function for parallel processing - simulates a single continuous emission iteration.
    For continuous emissions with producing hours: sample rates only, calculate avg_rate × producing_hours.
    This function must be at module level for pickling in multiprocessing.
    """
    (rate_array, producing_hours, seed) = args
    
    # Set random seed for reproducibility
    np.random.seed(seed)
    
    # Sample rates (sample multiple times to get average)
    num_samples = 1000  # Sample 1000 rates to get a good average
    sampled_rates = np.random.choice(rate_array, size=num_samples)
    
    # Calculate average rate
    avg_rate = np.mean(sampled_rates)
    
    # Finalized unmeasured emissions = average rate × producing hours
    total_emissions = avg_rate * producing_hours
    
    return total_emissions


def simulate_renewal_emissions(total_hours, occupancy, rate_array, duration_array, rng,
                               mean_duration=None, paired=False):
    """
    One realization of unmeasured emissions over `total_hours` from an alternating renewal
    process (the Type 2 UE model of EAMEET).

    The source alternates between an emitting state and a non-emitting state:
      * emitting intervals D are drawn from `duration_array` (hours);
      * non-emitting gaps G are exponential with mean E[D] * (1 - phi) / phi,
    so the long-run fraction of time emitting equals the prescribed occupancy `phi`
    (= total event duration / observation period, Section 2.3.3 of the paper) and the
    event frequency equals phi / E[D]. The process is defined in continuous time, so the
    result does not depend on any simulation time step. The process starts in its stationary
    state: emitting with probability phi (with a length-biased residual duration), otherwise
    in a gap (exponential, hence memoryless).

    Args:
        total_hours: length of the unmonitored window (h)
        occupancy: prescribed fraction of time emitting, phi in [0, 1]
        rate_array: sample of event rates (kg/h) to draw from
        duration_array: sample of event durations (h) to draw from
        rng: numpy Generator
        mean_duration: E[D] to use for the gap calibration; defaults to duration_array.mean()
        paired: if True, `rate_array` and `duration_array` are aligned (rate_i, duration_i) pairs
            (observed events, or pairs drawn by `sample_pairs_from_fitted`) and each emitting
            interval takes BOTH its rate and its duration from one sampled pair, so the dependence
            between rate and duration in the sample is preserved. If False (default) rate and
            duration are drawn independently from the two marginal samples.

    Returns:
        (total_emissions_kg, emitting_hours, n_event_onsets_in_window)
    """
    total_hours = float(total_hours)
    rate_array = np.asarray(rate_array, dtype=float)
    duration_array = np.asarray(duration_array, dtype=float)
    if paired and rate_array.shape != duration_array.shape:
        raise ValueError("paired=True requires rate_array and duration_array of equal length "
                         f"(got {rate_array.size} and {duration_array.size})")
    if total_hours <= 0 or occupancy <= 0 or rate_array.size == 0 or duration_array.size == 0:
        return 0.0, 0.0, 0
    if occupancy >= 1:
        rate = float(rng.choice(rate_array))
        return rate * total_hours, total_hours, 1

    mean_d = float(np.mean(duration_array)) if mean_duration is None else float(mean_duration)
    if not np.isfinite(mean_d) or mean_d <= 0:
        return 0.0, 0.0, 0
    mean_gap = mean_d * (1.0 - occupancy) / occupancy

    emissions = 0.0
    emitting = 0.0
    n_events = 0
    t = 0.0

    # Stationary start.
    if rng.random() < occupancy:
        # Residual of a length-biased duration: P(D = d) ∝ d, then uniform fraction remaining.
        w = duration_array / duration_array.sum()
        k = int(rng.choice(duration_array.size, p=w))
        d_res = float(duration_array[k]) * rng.random()
        d_res = min(d_res, total_hours - t)
        q0 = float(rate_array[k]) if paired else float(rng.choice(rate_array))
        emissions += q0 * d_res
        emitting += d_res
        t += d_res

    block = 64
    while t < total_hours:
        gaps = rng.exponential(mean_gap, size=block)
        if paired:
            idx = rng.integers(0, duration_array.size, size=block)
            durs, rates = duration_array[idx], rate_array[idx]
        else:
            durs = rng.choice(duration_array, size=block)
            rates = rng.choice(rate_array, size=block)
        for g, d, q in zip(gaps, durs, rates):
            t += g
            if t >= total_hours:
                t = total_hours
                break
            d = min(float(d), total_hours - t)
            if d <= 0:
                continue
            emissions += float(q) * d
            emitting += d
            n_events += 1
            t += d
            if t >= total_hours:
                break
        block = min(block * 2, 4096)

    return float(emissions), float(emitting), int(n_events)


def _ppf_from_distribution(distribution_info, q):
    """Quantile function of a fitted distribution described as in `sample_from_distribution`."""
    dist_type = distribution_info.get('type'); params = tuple(distribution_info.get('params'))
    f = {'lognormal': lognorm, 'normal': norm, 'uniform': uniform, 'exponential': expon,
         'weibull': weibull_min, 'gamma': gamma}.get(dist_type)
    if f is None:
        raise ValueError(f"Unknown distribution type: {dist_type}")
    v = f.ppf(q, *params)
    if 'min' in distribution_info:
        v = np.maximum(v, distribution_info['min'])
    if 'max' in distribution_info:
        v = np.minimum(v, distribution_info['max'])
    return v


def sample_pairs_from_fitted(fitted_rate_dist, fitted_duration_dist, rates, durations, size, rng=None):
    """
    Draw (rate, duration) pairs that follow the FITTED marginal distributions but keep the
    dependence structure of the observed events (empirical copula).

    For each draw an observed event i is chosen at random; its rate rank and duration rank
    (jittered within their rank bins) are mapped through the quantile functions of the fitted
    rate and duration distributions. The marginals are therefore those of the fitted distributions
    while the rank correlation between rate and duration is that of the observed sample.

    Returns:
        (rate_samples, duration_samples), aligned arrays of length `size`
    """
    rng = np.random.default_rng() if rng is None else rng
    rates = np.asarray(rates, dtype=float); durations = np.asarray(durations, dtype=float)
    if rates.shape != durations.shape:
        raise ValueError("rates and durations must be aligned (one pair per observed event)")
    n = rates.size
    r_rank = np.argsort(np.argsort(rates)); d_rank = np.argsort(np.argsort(durations))
    i = rng.integers(0, n, size=size)
    u = (r_rank[i] + rng.random(size)) / n
    v = (d_rank[i] + rng.random(size)) / n
    return _ppf_from_distribution(fitted_rate_dist, u), _ppf_from_distribution(fitted_duration_dist, v)


def simulate_renewal_emissions_by_class(total_hours, classes, rng):
    """
    Class-stratified Type 2 simulation: one independent alternating renewal process per event
    class (e.g., equipment type or observation kind), each with its own occupancy and its own
    (rate, duration) sample, summed over classes.

    classes: list of dicts with keys occupancy, rate_array, duration_array and optionally
             mean_duration and paired (default True: pairs are sampled jointly within the class).
    Returns:
        (total_emissions_kg, [emitting_hours of each class])
    """
    total, emitting = 0.0, []
    for c in classes:
        e, h, _ = simulate_renewal_emissions(
            total_hours, c["occupancy"], c["rate_array"], c["duration_array"], rng,
            mean_duration=c.get("mean_duration"), paired=c.get("paired", True))
        total += e; emitting.append(h)
    return total, emitting


def extrapolation(prob_dist, rate_dist, duration_dist, start_time, end_time, MC, 
                  fitted_rate_dist=None, fitted_duration_dist=None,
                  is_continuous=False, producing_hours=None, sampling="independent"):
    """
    Bootstrap simulation for unmeasured emissions (extrapolation).
    
    Args:
        prob_dist: {"UNKNOWN": phi} where phi is the event occupancy = total event duration /
            observation period (fraction of time emitting). Converted internally to the mean
            inter-event gap of an alternating renewal process (see simulate_renewal_emissions).
        rate_dist: Rate distribution dictionary (used if fitted_rate_dist is None)
        duration_dist: Duration distribution dictionary (used if fitted_duration_dist is None)
        start_time: Start datetime for simulation
        end_time: End datetime for simulation
        MC: Number of Monte Carlo iterations
        fitted_rate_dist: Optional fitted distribution info for rate (dict with 'type', 'params', etc.)
        fitted_duration_dist: Optional fitted distribution info for duration (dict with 'type', 'params', etc.)
        is_continuous: If True, emissions are continuous (don't sample duration)
        producing_hours: Producing hours for continuous emissions (required if is_continuous=True)
        sampling: "independent" (default): rate and duration of each simulated event are drawn
            independently from the two marginal samples (or fitted distributions).
            "paired": each simulated event takes rate and duration from one observed event
            (rate_dist/duration_dist must be aligned per event); when fitted distributions are
            supplied, pairs are drawn from the fitted marginals with the empirical copula of the
            observed events (`sample_pairs_from_fitted`).
    
    Returns:
        Dictionary with extrapolated emissions by source category
    """
    if sampling not in ("independent", "paired"):
        raise ValueError(f"Unknown sampling: {sampling!r} (expected 'independent' or 'paired')")
    paired = sampling == "paired"
    # only 1 source category
    final_emissions = {"UNKNOWN": []}
    
    # Use fitted distributions if available, otherwise use raw data arrays
    if fitted_rate_dist is not None:
        # Generate samples from fitted distribution
        rate_array = sample_from_distribution(fitted_rate_dist, size=10000)
    else:
        # Convert distributions to numpy arrays for faster access
        rate_array = np.array(rate_dist["UNKNOWN"])
    
    # Handle continuous emissions case
    if is_continuous and producing_hours is not None:
        # For continuous emissions: sample rates only, use avg_rate × producing_hours
        # Use parallel processing for high MC iterations (threshold: 20)
        PARALLEL_THRESHOLD = 20
        use_parallel = MC >= PARALLEL_THRESHOLD
        
        if use_parallel:
            # Prepare arguments for parallel processing
            seeds = np.random.randint(0, 2**31, size=MC)
            args_list = [
                (rate_array, producing_hours, int(seed))
                for seed in seeds
            ]
            
            # Use multiprocessing Pool
            num_workers = min(cpu_count(), MC)
            with Pool(processes=num_workers) as pool:
                results = pool.map(_extrapolation_continuous_single_iteration, args_list)
            final_emissions["UNKNOWN"] = results
        else:
            # Sequential processing for small iterations
            for mc in range(MC):
                # Sample rates (sample multiple times to get average)
                num_samples = 1000  # Sample 1000 rates to get a good average
                sampled_rates = np.random.choice(rate_array, size=num_samples)
                
                # Calculate average rate
                avg_rate = np.mean(sampled_rates)
                
                # Finalized unmeasured emissions = average rate × producing hours
                total_emissions = avg_rate * producing_hours
                final_emissions["UNKNOWN"].append(total_emissions)
        
        return final_emissions
    
    # Original intermittent emissions logic
    poe = prob_dist.get("UNKNOWN")
    
    if paired and fitted_rate_dist is not None and fitted_duration_dist is not None:
        # fitted marginals + empirical copula of the observed (rate, duration) pairs
        rate_array, duration_array = sample_pairs_from_fitted(
            fitted_rate_dist, fitted_duration_dist, rate_dist["UNKNOWN"], duration_dist["UNKNOWN"],
            size=10000, rng=np.random.default_rng(np.random.randint(0, 2**31)))
    elif paired:
        rate_array = np.array(rate_dist["UNKNOWN"], dtype=float)
        duration_array = np.array(duration_dist["UNKNOWN"], dtype=float)
        if rate_array.shape != duration_array.shape:
            raise ValueError("sampling='paired' requires one (rate, duration) pair per observed event")
    elif fitted_duration_dist is not None:
        # Generate samples from fitted distribution
        duration_array = sample_from_distribution(fitted_duration_dist, size=10000)
    else:
        # Convert distributions to numpy arrays for faster access
        duration_array = np.array(duration_dist["UNKNOWN"])
    
    # Pre-calculate total simulation hours
    total_hours = int((end_time - start_time).total_seconds() / 3600)
    
    # Use parallel processing for high MC iterations (threshold: 20)
    PARALLEL_THRESHOLD = 20
    use_parallel = MC >= PARALLEL_THRESHOLD
    
    if use_parallel:
        # Prepare arguments for parallel processing
        seeds = np.random.randint(0, 2**31, size=MC)
        args_list = [
            (total_hours, poe, rate_array, duration_array, int(seed), paired)
            for seed in seeds
        ]
        
        # Use multiprocessing Pool
        num_workers = min(cpu_count(), MC)
        with Pool(processes=num_workers) as pool:
            results = pool.map(_extrapolation_single_iteration, args_list)
        final_emissions["UNKNOWN"] = results
    else:
        # Sequential processing for small iterations
        seeds = np.random.randint(0, 2**31, size=MC)
        for seed in seeds:
            total_emissions, _, _ = simulate_renewal_emissions(
                total_hours, poe, rate_array, duration_array, np.random.default_rng(int(seed)), paired=paired)
            final_emissions["UNKNOWN"].append(total_emissions)

    return final_emissions


def sample_from_distribution(distribution_info, size=1):
    """
    Sample values from a fitted statistical distribution.
    
    Args:
        distribution_info: Dictionary with keys:
            - 'type': Distribution type ('lognormal', 'normal', 'uniform', 'exponential', 'weibull', 'gamma')
            - 'params': Distribution parameters (tuple or list)
            - 'min': Minimum value (optional, for clipping)
            - 'max': Maximum value (optional, for clipping)
        size: Number of samples to generate
    
    Returns:
        Array of sampled values
    """
    if distribution_info is None:
        raise ValueError("Distribution info is required")
    
    dist_type = distribution_info.get('type')
    params = distribution_info.get('params')
    
    if params is None:
        raise ValueError("Distribution parameters are required")
    
    # Convert params to tuple if it's a list
    if isinstance(params, list):
        params = tuple(params)
    
    # Sample from distribution
    if dist_type == 'lognormal':
        samples = lognorm.rvs(*params, size=size)
    elif dist_type == 'normal':
        samples = norm.rvs(*params, size=size)
    elif dist_type == 'uniform':
        samples = uniform.rvs(*params, size=size)
    elif dist_type == 'exponential':
        samples = expon.rvs(*params, size=size)
    elif dist_type == 'weibull':
        samples = weibull_min.rvs(*params, size=size)
    elif dist_type == 'gamma':
        samples = gamma.rvs(*params, size=size)
    else:
        raise ValueError(f"Unknown distribution type: {dist_type}")
    
    # Clip to min/max if provided
    if 'min' in distribution_info:
        samples = np.maximum(samples, distribution_info['min'])
    if 'max' in distribution_info:
        samples = np.minimum(samples, distribution_info['max'])
    
    return samples


def _coverage_covers(cov, real_start, real_end):
    """Does a technology's coverage schedule (hour offsets) include the interval [real_start, real_end)?"""
    if cov is None:
        return True                                   # no schedule: observes the whole window
    iv = cov.get("intervals")
    if iv is not None and len(iv):
        if np.any((iv[:, 0] < real_end) & (iv[:, 1] > real_start)):
            return True
    inst = cov.get("instants")
    if inst is not None and len(inst):
        if np.any((inst >= real_start) & (inst < real_end)):
            return True
    return False


def _timed_wind(series, start_time):
    """Time-indexed wind Series -> ('timed', hour offsets from start_time, values), picklable."""
    offs = ((series.index - pd.Timestamp(start_time)).total_seconds() / 3600.0).to_numpy()
    return ("timed", offs, series.to_numpy(dtype=float))


def _make_wind_picker(wind_speed, rng):
    """
    Return f(real_start_h) -> wind speed for a hypothetical event starting at that hour offset.

      * scalar                  -> constant;
      * time-indexed pd.Series  -> value in force at the event start (time-matched);
      * 1-D array / list        -> one value drawn at random per event (the observing conditions are
                                   sampled, never evaluated as a best case over the whole series).
    """
    if wind_speed is None:
        return lambda t: None
    if isinstance(wind_speed, pd.Series) and isinstance(wind_speed.index, pd.DatetimeIndex):
        # Direct call with a Series: offsets are taken from the first timestamp of the series
        # (the public routine converts the Series to offsets from the window start, see below).
        wind_speed = _timed_wind(wind_speed, wind_speed.index[0])
    if isinstance(wind_speed, tuple) and len(wind_speed) == 3 and wind_speed[0] == "timed":
        _, offs, vals = wind_speed

        def pick(t):
            k = int(np.searchsorted(offs, t, side="right") - 1)
            return float(vals[min(max(k, 0), len(vals) - 1)])
        return pick
    arr = np.asarray(wind_speed, dtype=float).ravel()
    if arr.size == 1:
        v = float(arr[0])
        return lambda t: v
    return lambda t: float(arr[rng.integers(arr.size)])


def _simulate_below_mdl_single_iteration(args):
    """
    One Monte Carlo realization of the undetected emissions during the monitored period.
    Module-level for pickling in multiprocessing.

    The budget is a list of gap segments (hour offsets from the window start) in which no RE or
    PRE was observed and at least one technology was observing. The segments are tiled with
    hypothetical events, each with a sampled rate Q and duration D. Each technology tests only the
    hypothetical events that overlap its own coverage schedule (CMS uptime intervals, or survey
    instants for snapshot technologies); an event is detected if ANY covering technology detects it
    and is missed with probability prod_k (1 - POD_k(Q)) (SI Eq. S1). An event that no technology
    covers is unresolved by construction. Detected and missed events both advance the clock by D.
    """
    (gap_segments, durations_dist, leaks_dist, num_comps,
     pod_config_or_list, wind_speed, seed, coverage_offsets) = args

    # Handle both PODs_list (for sequential) and technologies_config (for parallel)
    if isinstance(pod_config_or_list, list) and len(pod_config_or_list) > 0:
        if isinstance(pod_config_or_list[0], dict):
            PODs_list = []
            for tech_config in pod_config_or_list:
                POD, _ = probability_of_detection(
                    technology=tech_config['technology'],
                    wind_speed=wind_speed,
                    wind_consider=tech_config['consider_wind'],
                    mdl_define=tech_config.get('mdl_define'),
                    pod_define=tech_config.get('pod_define'),
                    pod_model=tech_config.get('pod_model', 'flat')
                )
                PODs_list.append(POD)
        else:
            PODs_list = pod_config_or_list
    else:
        PODs_list = []
    if coverage_offsets is None:
        coverage_offsets = [None] * len(PODs_list)

    np.random.seed(seed)
    rng = np.random.default_rng(seed)
    pick_wind = _make_wind_picker(wind_speed, rng)

    seg = np.asarray(gap_segments, dtype=float).reshape(-1, 2)
    if seg.size == 0:
        return 0.0
    lengths = seg[:, 1] - seg[:, 0]
    cum = np.concatenate([[0.0], np.cumsum(lengths)])
    total = float(cum[-1])

    E_miss = 0.0
    elapsed = 0.0
    i_seg = 0
    while elapsed < total:
        while i_seg < len(seg) - 1 and elapsed >= cum[i_seg + 1]:
            i_seg += 1
        remaining_in_seg = cum[i_seg + 1] - elapsed
        if remaining_in_seg <= 0:
            elapsed = cum[i_seg + 1]
            continue

        Q_sample = np.random.choice(leaks_dist) * np.random.choice(num_comps)
        # A hypothetical event never straddles an observed event: it is clipped to its gap segment.
        sampled_duration = float(np.random.choice(durations_dist))
        sampled_duration = min(sampled_duration, remaining_in_seg)
        if sampled_duration <= 0:
            break  # guard against non-positive sampled durations (prevents an infinite loop)

        real_start = seg[i_seg, 0] + (elapsed - cum[i_seg])
        real_end = real_start + sampled_duration
        ws_event = pick_wind(real_start)

        detection_label = False
        for POD_func_or_const, cov in zip(PODs_list, coverage_offsets):
            if not _coverage_covers(cov, real_start, real_end):
                continue                             # this technology could not have seen it
            if callable(POD_func_or_const):
                POD = POD_func_or_const(Q_sample, ws_event) if ws_event is not None else POD_func_or_const(Q_sample)
            else:
                POD = POD_func_or_const
            if float(np.asarray(POD).ravel()[0]) > np.random.random():
                detection_label = True
                break

        if not detection_label:
            E_miss += Q_sample * sampled_duration

        elapsed += sampled_duration

    return E_miss


# NOTE: The former helper `_simulate_duration_uncertainty_single_iteration` -- an
# unconditional bracket-filling model that stepped hour-by-hour and assigned the FULL
# interval duration whenever no onset was sampled (and ran to the interval end whenever
# no repair was sampled) -- has been removed. That model was not conditioned on the
# detection that defines a PRE, so "no simulated onset" became "emitting the whole
# bracket", pinning inferred durations to the upper boundary. Duration inference is now
# conditioned on the detection evidence: see `sample_conditional_duration` and the
# rewritten `simulate_duration_uncertainty` below.


def _extrapolation_single_iteration(args):
    """
    Helper function for parallel processing - simulates a single extrapolation iteration
    of the alternating renewal process (see `simulate_renewal_emissions`).
    This function must be at module level for pickling in multiprocessing.
    """
    total_hours, poe, rate_array, duration_array, seed = args[:5]
    paired = args[5] if len(args) > 5 else False
    rng = np.random.default_rng(seed)
    total_emissions, _, _ = simulate_renewal_emissions(
        total_hours, poe, rate_array, duration_array, rng, paired=paired)
    return total_emissions


def _get_pod_mdl_config(technology, mdl_define, consider_wind, wind_speed,
                        pod_define=None, pod_model="flat"):
    """
    Get POD (Probability of Detection) and MDL (Minimum Detection Limit) configuration.
    
    Args:
        technology: Measurement technology name (single technology)
        mdl_define: User-defined MDL value (if technology is 'define_technology')
        consider_wind: Whether to consider wind conditions
        wind_speed: Wind speed value (required when consider_wind=True)
    
    Returns:
        Tuple of (POD, MDL) where POD can be a function or constant
    """
    try:
        # probability_of_detection accepts both 'define_technology' and 'User Defined', so no
        # separate alias mapping is needed here.
        POD, MDL = probability_of_detection(
            technology=technology,
            wind_speed=wind_speed,
            wind_consider=consider_wind,
            mdl_define=mdl_define,
            pod_define=pod_define,
            pod_model=pod_model
        )
    except ValueError as e:
        raise ValueError(f"Error getting POD/MDL for technology '{technology}': {str(e)}")
    
    return POD, MDL

def _event_cols(event_df):
    if 'startTime' in event_df.columns:
        return 'startTime', 'endTime'
    if 'start_time' in event_df.columns:
        return 'start_time', 'end_time'
    raise ValueError("Event DataFrame must have 'startTime'/'endTime' or 'start_time'/'end_time' columns")


def _union_intervals(iv):
    """Union of [a, b) intervals given as an (n, 2) array; returns a sorted, merged (m, 2) array."""
    iv = np.asarray(iv, dtype=float).reshape(-1, 2)
    iv = iv[iv[:, 1] > iv[:, 0]]
    if iv.size == 0:
        return np.empty((0, 2))
    iv = iv[np.argsort(iv[:, 0])]
    out = [iv[0].copy()]
    for a, b in iv[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append(np.array([a, b]))
    return np.array(out)


def _subtract_intervals(base, holes):
    """base minus holes, both (n, 2) arrays of [a, b) hour offsets (already unions)."""
    out = []
    for a, b in base:
        cur = a
        for h0, h1 in holes:
            if h1 <= cur or h0 >= b:
                continue
            if h0 > cur:
                out.append([cur, h0])
            cur = max(cur, h1)
            if cur >= b:
                break
        if cur < b:
            out.append([cur, b])
    return np.array(out).reshape(-1, 2)


def _intervals_to_offsets(intervals, start_time, end_time):
    """[(t0, t1), ...] timestamps -> (n, 2) hour offsets clipped to the window."""
    total_hours = (end_time - start_time).total_seconds() / 3600.0
    rows = []
    for t0, t1 in intervals:
        a = (pd.Timestamp(t0) - start_time).total_seconds() / 3600.0
        b = (pd.Timestamp(t1) - start_time).total_seconds() / 3600.0
        a, b = max(a, 0.0), min(b, total_hours)
        if b > a:
            rows.append([a, b])
    return np.array(rows).reshape(-1, 2)


def _coverage_to_offsets(entry, start_time, end_time):
    """
    One technology's coverage schedule -> hour offsets. `entry` is None (whole window), a list of
    (start, end) pairs (intervals, e.g. CMS uptime) or a list of timestamps (survey instants).
    """
    if entry is None:
        return None
    entry = list(entry)
    if len(entry) == 0:
        return {"intervals": np.empty((0, 2)), "instants": np.empty(0)}
    if isinstance(entry[0], (tuple, list)) and len(entry[0]) == 2:
        return {"intervals": _union_intervals(_intervals_to_offsets(entry, start_time, end_time))}
    total_hours = (end_time - start_time).total_seconds() / 3600.0
    inst = np.array([(pd.Timestamp(t) - start_time).total_seconds() / 3600.0 for t in entry])
    return {"instants": inst[(inst >= 0) & (inst <= total_hours)]}


def monitored_gap_segments(event_df, start_time, end_time, coverage=None, exclude_observed_events=True):
    """
    Time budget of the Type 1 (undetected-during-monitoring) simulation as explicit intervals.

    Hours of informative coverage inside [start_time, end_time] minus the union of the hours already
    occupied by observed events (REs and PREs). `coverage` is None (every technology observes the
    whole window) or a list of (start, end) pairs, e.g. CMS uptime; with several technologies pass the
    union of their interval schedules. Survey instants carry no hours and are handled by the
    per-technology coverage check inside the simulation. Returns an (n, 2) array of hour offsets.
    """
    total_hours = (end_time - start_time).total_seconds() / 3600.0
    if coverage is None:
        base = np.array([[0.0, total_hours]])
    else:
        base = _union_intervals(_intervals_to_offsets(coverage, start_time, end_time))
    if not exclude_observed_events or len(event_df) == 0:
        return base
    sc, ec = _event_cols(event_df)
    st = pd.to_datetime(event_df[sc], errors='coerce')
    en = pd.to_datetime(event_df[ec], errors='coerce')
    ok = st.notna() & en.notna()
    holes = np.column_stack([
        ((st[ok] - start_time).dt.total_seconds() / 3600.0).clip(lower=0.0),
        ((en[ok] - start_time).dt.total_seconds() / 3600.0).clip(upper=total_hours),
    ]) if ok.any() else np.empty((0, 2))
    return _subtract_intervals(base, _union_intervals(holes))


def calculate_total_simulation_time_steps(event_df, start_time, end_time, mode="gaps", coverage=None):
    """
    Length (hours) of the Type 1 simulation time budget.

    mode="gaps" (default): informative-coverage hours of the window not occupied by any observed
        event, i.e. the total length of `monitored_gap_segments`. This is what Section S4.1 of the SI
        describes (hypothetical events are only placed where no RE or PRE was observed).
    mode="observed_event_hours": the superseded EAMEET v1.0 budget, the SUM of the observed event
        durations overlapping the window (capped at the window length). Kept for comparison only.
    """
    total_hours = (end_time - start_time).total_seconds() / 3600.0
    if mode == "gaps":
        seg = monitored_gap_segments(event_df, start_time, end_time, coverage=coverage)
        return float(np.sum(seg[:, 1] - seg[:, 0])) if seg.size else 0.0
    if mode != "observed_event_hours":
        raise ValueError(f"Unknown mode: {mode!r} (expected 'gaps' or 'observed_event_hours')")
    sc, ec = _event_cols(event_df)
    st = pd.to_datetime(event_df[sc], errors='coerce')
    en = pd.to_datetime(event_df[ec], errors='coerce')
    total = 0.0
    for a, b in zip(st, en):
        if pd.isna(a) or pd.isna(b):
            continue
        a, b = max(a, start_time), min(b, end_time)
        if a < end_time and b > start_time:
            total += (b - a).total_seconds() / 3600.0
    return min(total, total_hours)


def _get_pod_mdl_configs_multiple(technologies, mdl_define, consider_wind, wind_speed,
                                  pod_define=None, pod_model="flat"):
    """
    Get POD (Probability of Detection) and MDL (Minimum Detection Limit) configurations for multiple technologies.
    
    Args:
        technologies: List of measurement technology names
        mdl_define: User-defined MDL value (if any technology is 'define_technology')
        consider_wind: Whether to consider wind conditions
        wind_speed: Wind speed value (required when consider_wind=True)
    
    Returns:
        Tuple of (PODs_list, MDLs_list) where:
        - PODs_list: List of POD values (functions or constants), one per technology
        - MDLs_list: List of MDL values (functions or constants), one per technology
    """
    PODs_list = []
    MDLs_list = []
    
    for technology in technologies:
        POD, MDL = _get_pod_mdl_config(technology, mdl_define, consider_wind, wind_speed,
                                       pod_define=pod_define, pod_model=pod_model)
        PODs_list.append(POD)
        MDLs_list.append(MDL)
    
    return PODs_list, MDLs_list


def _validate_and_prepare_events(events):
    """
    Validate events DataFrame and ensure required columns exist.
    
    Args:
        events: DataFrame with emission events
    
    Returns:
        Prepared events DataFrame with 'source' and 'quantity' columns
    """
    events = events.copy()
    
    # Ensure 'source' column exists
    if 'source' not in events.columns:
        if 'sourceLocation' in events.columns:
            events['source'] = events['sourceLocation']
        else:
            raise ValueError("Events DataFrame must have 'source' or 'sourceLocation' column")
    
    # Ensure 'quantity' column exists
    if 'quantity' not in events.columns:
        if 'rate' in events.columns and 'duration' in events.columns:
            events['quantity'] = events['rate'] * events['duration']
        else:
            raise ValueError("Events DataFrame must have 'quantity' column or both 'rate' and 'duration' columns")
    
    return events


def _calculate_measured_emissions(source_events, start_time, end_time):
    """
    Calculate measured emissions for a source within the simulation time range.
    
    Args:
        source_events: DataFrame with events for a single source
        start_time: Start datetime for simulation
        end_time: End datetime for simulation
    
    Returns:
        Tuple of (measured_emissions, measured_emissions_lower, measured_emissions_upper)
    """
    # Filter events that overlap with the simulation time range
    start_times = pd.to_datetime(source_events['start_time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    end_times = pd.to_datetime(source_events['end_time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    
    # Filter events that overlap with simulation period
    overlapping_mask = (end_times >= start_time) & (start_times <= end_time)
    overlapping_events = source_events[overlapping_mask]
    
    # Calculate total measured emissions for this source
    measured_emissions = overlapping_events['quantity'].sum() if len(overlapping_events) > 0 else 0
    
    # Calculate uncertainty for measured emissions (±20% default)
    # TODO This could be enhanced to use actual uncertainty data if available
    measured_uncertainty_pct = 0.20  # 20% uncertainty
    measured_emissions_lower = measured_emissions * (1 - measured_uncertainty_pct)
    measured_emissions_upper = measured_emissions * (1 + measured_uncertainty_pct)
    
    return measured_emissions, measured_emissions_lower, measured_emissions_upper


def _build_events_times(source_events, start_time):
    """
    Build Events_Times set and sorted array from source events.
    
    Args:
        source_events: DataFrame with events for a single source
        start_time: Start datetime for simulation
    
    Returns:
        Tuple of (Events_Times_set, Events_Times_sorted)
    """
    # Pre-parse datetime strings once (much faster than parsing in loops)
    start_times_parsed = pd.to_datetime(source_events['start_time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    end_times_parsed = pd.to_datetime(source_events['end_time'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    
    # Build Events_Times set using pandas date_range (much faster than hour-by-hour loop)
    Events_Times_set = set()
    for st, et in zip(start_times_parsed, end_times_parsed):
        if pd.isna(st) or pd.isna(et):
            continue
        # Calculate hours since start_time for each event period
        hours_start = int((st - start_time).total_seconds() / 3600)
        hours_end = int((et - start_time).total_seconds() / 3600)
        # Add all hours in range to set
        Events_Times_set.update(range(hours_start, hours_end + 1))
    
    # Convert to sorted numpy array
    Events_Times_sorted = np.array(sorted(Events_Times_set)) if Events_Times_set else np.array([])
    
    return Events_Times_set, Events_Times_sorted


def _run_monte_carlo_simulation(
    total_hours, Events_Times_set, Events_Times_sorted, durations,
    PODs_list, wind_speed, mc_iterations, source_events=None, start_time=None, end_time=None,
    technologies=None, mdl_define=None, consider_wind=False, pod_define=None, pod_model="flat",
    coverage=None, exclude_observed_events=True
):
    """
    Run Monte Carlo simulation for unmeasured emissions below MDL.
    
    Args:
        total_hours: Total simulation hours
        Events_Times_set: Set of hours with measured events
        Events_Times_sorted: Sorted array of hours with measured events
        durations: Array of duration values for sampling
        PODs_list: List of Probability of Detection values (functions or constants), one per technology
        wind_speed: Wind speed value
        mc_iterations: Number of Monte Carlo iterations
        source_events: Optional DataFrame with events for calculating total simulation time steps
        start_time: Optional start datetime for calculating total simulation time steps
        end_time: Optional end datetime for calculating total simulation time steps
        technologies: List of technology names (needed for pickling POD functions)
        mdl_define: User-defined MDL value (needed for pickling POD functions)
        consider_wind: Whether wind is considered (needed for pickling POD functions)
    
    Returns:
        List of unmeasured emission values from each iteration
    """
    PARALLEL_THRESHOLD = 20
    use_parallel = mc_iterations >= PARALLEL_THRESHOLD
    
    # Convert POD functions to serializable configuration for multiprocessing
    if use_parallel and technologies is not None:
        # Create technology configuration list (picklable)
        technologies_config = []
        for tech in technologies:
            tech_config = {
                'technology': tech if tech != 'define_technology' else 'User Defined',
                'mdl_define': mdl_define if tech == 'define_technology' else None,
                'pod_define': pod_define if tech == 'define_technology' else None,
                'pod_model': pod_model,
                'consider_wind': consider_wind
            }
            technologies_config.append(tech_config)
    else:
        # For sequential processing, use PODs_list directly
        technologies_config = None
    
    # Common setup for both execution paths (calculate_total_simulation_time_steps consumes no
    # RNG, so hoisting these ahead of the branch leaves the seeded draw sequence unchanged).
    # Time budget: informative-coverage hours not occupied by observed events, as explicit segments.
    # The budget's coverage is the union of the interval schedules of the listed technologies
    # (a technology without a schedule observes the whole window; survey instants add no hours).
    tech_names = technologies if technologies is not None else [None] * len(PODs_list)
    if coverage is None:
        coverage_offsets = None
        budget_cov = None
    else:
        coverage_offsets = [_coverage_to_offsets(coverage.get(t), start_time, end_time) for t in tech_names]
        if any(coverage.get(t) is None for t in tech_names):
            budget_cov = None
        else:
            budget_cov = []
            for t in tech_names:
                entry = list(coverage.get(t) or [])
                if entry and isinstance(entry[0], (tuple, list)):
                    budget_cov.extend(entry)
    if isinstance(wind_speed, pd.Series) and isinstance(wind_speed.index, pd.DatetimeIndex) and start_time is not None:
        wind_speed = _timed_wind(wind_speed, start_time)   # time-matched wind, offsets from the window start
    if source_events is not None and start_time is not None and end_time is not None:
        gap_segments = monitored_gap_segments(source_events, start_time, end_time, coverage=budget_cov,
                                              exclude_observed_events=exclude_observed_events)
    else:
        gap_segments = np.array([[0.0, float(total_hours)]])
    seeds = np.random.randint(0, 2**31, size=mc_iterations)

    if use_parallel:
        # Parallel: ship picklable technologies_config (closures can't cross the process boundary).
        args_list = [
            (gap_segments, durations,
             _leaks_dist, _num_comps, technologies_config, wind_speed, int(seed), coverage_offsets)
            for seed in seeds
        ]
        num_workers = min(cpu_count(), mc_iterations)
        with Pool(processes=num_workers) as pool:
            unmeasured_emissions = list(pool.map(_simulate_below_mdl_single_iteration, args_list))
    else:
        # Sequential: pass the prebuilt PODs_list directly (no pickling needed).
        unmeasured_emissions = []
        for seed in seeds:
            args = (gap_segments, durations,
                   _leaks_dist, _num_comps, PODs_list, wind_speed, int(seed), coverage_offsets)
            unmeasured_emissions.append(_simulate_below_mdl_single_iteration(args))

    return unmeasured_emissions


def _process_single_source(
    source_events, start_time, end_time, total_hours,
    durations, PODs_list, wind_speed, mc_iterations,
    technologies=None, mdl_define=None, consider_wind=False, pod_define=None, pod_model="flat",
    coverage=None, exclude_observed_events=True
):
    """
    Process a single source: calculate measured and unmeasured emissions.
    
    Args:
        source_events: DataFrame with events for a single source
        start_time: Start datetime for simulation
        end_time: End datetime for simulation
        total_hours: Total simulation hours
        durations: Array of duration values for sampling
        PODs_list: List of Probability of Detection values (functions or constants), one per technology
        wind_speed: Wind speed value
        mc_iterations: Number of Monte Carlo iterations
        technologies: List of technology names (needed for parallel processing)
        mdl_define: User-defined MDL value (needed for parallel processing)
        consider_wind: Whether wind is considered (needed for parallel processing)
    
    Returns:
        Tuple of (total_emissions, total_emissions_lower, total_emissions_upper)
    """
    # Calculate measured emissions
    measured_emissions, measured_emissions_lower, measured_emissions_upper = \
        _calculate_measured_emissions(source_events, start_time, end_time)
    
    # Build Events_Times data structures
    Events_Times_set, Events_Times_sorted = _build_events_times(source_events, start_time)
    
    # Run Monte Carlo simulation
    unmeasured_emissions = _run_monte_carlo_simulation(
        total_hours, Events_Times_set, Events_Times_sorted, durations,
        PODs_list, wind_speed, mc_iterations,
        source_events=source_events, start_time=start_time, end_time=end_time,
        technologies=technologies, mdl_define=mdl_define, consider_wind=consider_wind,
        pod_define=pod_define, pod_model=pod_model,
        coverage=coverage, exclude_observed_events=exclude_observed_events
    )

    # Calculate statistics from simulation results
    unmeasured_emissions_array = np.array(unmeasured_emissions)
    unmeasured_median = np.median(unmeasured_emissions_array)
    unmeasured_lower = np.percentile(unmeasured_emissions_array, q=2.5)
    unmeasured_upper = np.percentile(unmeasured_emissions_array, q=97.5)
    
    # Combine measured and unmeasured emissions
    total_emissions = measured_emissions + unmeasured_median
    total_emissions_lower = measured_emissions_lower + unmeasured_lower
    total_emissions_upper = measured_emissions_upper + unmeasured_upper
    
    return (total_emissions, total_emissions_lower, total_emissions_upper,
            measured_emissions, measured_emissions_lower, measured_emissions_upper,
            unmeasured_median, unmeasured_lower, unmeasured_upper)


def simulate_below_mdl(
    events,
    start_time,
    end_time,
    mc_iterations=1,
    technologies=None,
    technology=None,
    mdl_define=None,
    consider_wind=False,
    wind_speed=None,
    leak_data=None,
    pod_define=None,
    pod_model="flat",
    coverage=None,
    exclude_observed_events=True,
    num_components=None,
    leak_units="kg/h",
):
    """
    Simulate emissions below the minimum detection limit (MDL) and combine with measured emissions.
    
    For each site/source, calculates:
    1. Total measured emissions from all events within the simulation time range
    2. Simulated unmeasured emissions below detection limit
    3. Combined total emissions (measured + unmeasured) with uncertainty bounds
    
    Supports multiple technologies: an emission is detected if ANY technology detects it.
    
    Args:
        events: DataFrame with emission events (must have 'quantity', 'source'/'sourceLocation', 
                'start_time', 'end_time' columns)
        start_time: Start datetime for simulation
        end_time: End datetime for simulation
        mc_iterations: Number of Monte Carlo iterations
        technologies: List of measurement technology names (preferred). If None, uses 'technology' parameter.
        technology: Single measurement technology name (for backward compatibility).
                   Ignored if 'technologies' is provided.
        mdl_define: User-defined MDL value (if any technology is 'define_technology')
        consider_wind: Whether to consider wind conditions
        wind_speed: Wind speed value (required when consider_wind=True)
        leak_data: Optional list of component-scale leak rate values (kg/h unless leak_units="g/s"). If None,
                loads the bundled Rutherford et al. (2021) sample (g/s in the file, converted to kg/h).
        leak_units: Unit of `leak_data`, "kg/h" (default) or "g/s".
        wind_speed: scalar (constant), 1-D array/list (one value sampled per hypothetical event) or a
                time-indexed pd.Series (value in force at the event's start time).
        coverage: Optional dict {technology: schedule} describing when each technology was actually
                observing. A schedule is a list of (start, end) timestamps (e.g. CMS uptime) or a list
                of timestamps (survey instants of a snapshot technology). Technologies without an entry
                are assumed to observe the whole window. The simulation time budget is the union of the
                interval schedules (or the whole window) minus the hours occupied by observed events, and
                each technology only tests the hypothetical events overlapping its own schedule.
        exclude_observed_events: If True (default) hours occupied by observed REs/PREs are removed from
                the time budget, so emissions already represented by measured events are not simulated again.
        num_components: Optional sample of the number of emitting components per hypothetical event (see
                _load_leak_data); default is the generic prior (mean 2,720 components).
    
    Returns:
        Tuple of (total_emissions, lower_bound, upper_bound) where:
        - total_emissions: Sum across all sites of (measured + unmeasured) emissions
        - lower_bound: Lower 95% confidence bound for total emissions
        - upper_bound: Upper 95% confidence bound for total emissions
    """
    # Load leak data if not already loaded, or use provided leak data
    _load_leak_data(leak_data=leak_data, num_components=num_components, leak_units=leak_units)
    
    # Handle technology/technologies parameter (support both single and multiple)
    if technologies is None or (isinstance(technologies, list) and len(technologies) == 0):
        if technology is None:
            raise ValueError("Either 'technologies' or 'technology' parameter must be provided")
        technologies = [technology]
    elif not isinstance(technologies, list):
        technologies = [technologies]
    
    # Get POD and MDL configurations for all technologies
    PODs_list, MDLs_list = _get_pod_mdl_configs_multiple(technologies, mdl_define, consider_wind, wind_speed,
                                                         pod_define=pod_define, pod_model=pod_model)
    
    # Validate and prepare events DataFrame
    events = _validate_and_prepare_events(events)
    
    # Convert durations to numpy array for faster random choice
    durations = events.duration.values
    
    # Pre-calculate total simulation hours
    total_hours = int((end_time - start_time).total_seconds() / 3600)
    
    # Initialize accumulators
    final_total_emissions = 0
    final_total_emissions_lower = 0
    final_total_emissions_upper = 0
    final_measured_emissions = 0
    final_measured_emissions_lower = 0
    final_measured_emissions_upper = 0
    final_unmeasured_emissions = 0
    final_unmeasured_emissions_lower = 0
    final_unmeasured_emissions_upper = 0
    
    # Process each source
    for source in events['source'].unique():
        source_events = events[events['source'] == source]
        
        (total_emissions, total_emissions_lower, total_emissions_upper,
         measured_emissions, measured_emissions_lower, measured_emissions_upper,
         unmeasured_median, unmeasured_lower, unmeasured_upper) = \
            _process_single_source(
                source_events, start_time, end_time, total_hours,
                durations, PODs_list, wind_speed, mc_iterations,
                technologies=technologies, mdl_define=mdl_define, consider_wind=consider_wind,
                pod_define=pod_define, pod_model=pod_model,
                coverage=coverage, exclude_observed_events=exclude_observed_events
            )
        
        # Accumulate across all sources
        final_total_emissions += total_emissions
        final_total_emissions_lower += total_emissions_lower
        final_total_emissions_upper += total_emissions_upper
        final_measured_emissions += measured_emissions
        final_measured_emissions_lower += measured_emissions_lower
        final_measured_emissions_upper += measured_emissions_upper
        final_unmeasured_emissions += unmeasured_median
        final_unmeasured_emissions_lower += unmeasured_lower
        final_unmeasured_emissions_upper += unmeasured_upper

    return (final_total_emissions, final_total_emissions_lower, final_total_emissions_upper,
            final_measured_emissions, final_measured_emissions_lower, final_measured_emissions_upper,
            final_unmeasured_emissions, final_unmeasured_emissions_lower, final_unmeasured_emissions_upper)


def _prob_to_hourly_hazard(p, step_days=1.0):
    """
    Convert a per-STEP Bernoulli probability into an equivalent continuous per-HOUR hazard.

    A probability p of an event occurring within a step of length dt corresponds to a
    continuous hazard lambda with p = 1 - exp(-lambda*dt); inverting and rescaling to
    hours gives lambda_hr = -ln(1 - p) / (24 * step_days). The leak-production rate is a
    per-DAY probability (step_days = 1); the LDAR-Sim null-repair rate is a per-VISIT
    probability applied at the operator visitation interval V (step_days = V, 7 by default).
    """
    p = min(max(float(p), 1e-9), 1.0 - 1e-9)
    return -np.log(1.0 - p) / (24.0 * float(step_days))


def _daily_prob_to_hourly_hazard(p_daily):
    """Per-DAY probability -> per-hour hazard (see _prob_to_hourly_hazard)."""
    return _prob_to_hourly_hazard(p_daily, 1.0)


def null_repair_rate(leak_production_rate, rate, q_max, p_max=0.25, visit_interval_days=7.0,
                     leaks_per_site=10.0, active_leak_ratio=1.0):
    """
    Null (natural) repair rate of Fox et al. (2021), SI Section S1, Eq. S1:

        NRR = (LPR * V / Lbar_0) * (L_t / L_0) + p_max * Q_i / Q_max

    the probability that an operator detects and repairs a given leak during ONE site
    visit, where V is the visitation interval (days, 7 = weekly visits), Lbar_0 the mean
    number of leaks per site at initialization, L_t/L_0 the active-leak ratio (1 at
    steady state), p_max the 'operator bonus' detection probability assigned to the
    largest source in the dataset (LDAR-Sim explores 0-0.25), Q_i the event rate and
    Q_max the largest rate in the dataset. NRR is a PER-VISIT probability: convert it to
    a hazard with step_days = V (see _prob_to_hourly_hazard).
    """
    q_term = 0.0 if q_max <= 0 else float(rate) / float(q_max)
    return (float(leak_production_rate) * float(visit_interval_days) / float(leaks_per_site)
            * float(active_leak_ratio) + float(p_max) * q_term)


def _truncated_exponential(rate_per_hr, t_max_hr, size, rng):
    """
    Sample X with density proportional to exp(-rate_per_hr * x) on [0, t_max_hr] (hours),
    via inverse-CDF sampling. `t_max_hr` may be a scalar or a per-sample array.

      * rate > 0  -> truncated exponential (density decreasing in x)
      * rate == 0 -> Uniform(0, t_max)
      * rate < 0  -> density INCREASING in x (sampled by reflecting the |rate| draw)
      * t_max <= 0 -> 0 (no room to extend beyond the detection)
    """
    t_max = np.array(np.broadcast_to(np.asarray(t_max_hr, dtype=float), (size,)), dtype=float)
    out = np.zeros(size)
    ok = t_max > 0
    if not np.any(ok):
        return out
    u = rng.random(size)
    if rate_per_hr == 0:
        out[ok] = u[ok] * t_max[ok]
        return out
    r = abs(float(rate_per_hr))
    c = -np.expm1(-r * t_max[ok])            # 1 - exp(-r*T), numerically stable
    x = -np.log1p(-u[ok] * c) / r
    if rate_per_hr < 0:
        x = t_max[ok] - x                     # reflection: density ∝ exp(+|r| x)
    out[ok] = x
    return out


def _resolve_bound_hours(primary_h, primary_pod, fallbacks_h, floor_h, N, rng, label):
    """
    Per-iteration room (hours) available for extending an emission past its detection,
    given a chain of null detections of decreasing proximity.

    A null detection is a VALID bound only with probability POD (the probability that the
    survey would have detected the emission at its rate under the observing conditions).
    Each iteration walks the chain from the nearest null outward; the nearest valid null
    sets the bound. If none is valid, the hard floor/ceiling applies.

    primary_h   : hours from the detection to the nearest null detection (>= 0)
    primary_pod : POD of that null detection (1.0 -> always valid, i.e. a hard bound)
    fallbacks_h : list of (hours, pod) for further null detections, nearest first
    floor_h     : hours to the hard floor/ceiling (analysis window edge or user cap)
    Returns (bound_hours[N], valid_fraction_of_primary)
    """
    fallbacks_h = list(fallbacks_h or [])
    if primary_pod >= 1.0 and not fallbacks_h:
        return np.full(N, float(primary_h)), 1.0
    if floor_h is None:
        raise ValueError(
            f"{label}: a floor/ceiling time is required when the null detection is treated as "
            f"soft (POD < 1) or fallback null detections are given, so the emission has a hard "
            f"limit when every null detection is sampled as a miss.")
    if floor_h < primary_h:
        raise ValueError(f"{label}: the floor/ceiling must lie beyond the nearest null detection.")
    bound = np.full(N, float(floor_h))
    for h, pod in reversed(fallbacks_h):          # farthest first; nearer nulls override
        if h < primary_h or h > floor_h:
            raise ValueError(f"{label}: fallback null detections must lie between the nearest "
                             f"null detection and the floor/ceiling.")
        bound = np.where(rng.random(N) < float(pod), float(h), bound)
    valid = rng.random(N) < float(primary_pod)
    bound = np.where(valid, float(primary_h), bound)
    return bound, float(valid.mean())


def sample_conditional_duration(first_detection, last_detection, pnd_time, snd_time,
                                LPR, NRR, N=100_000, seed=0,
                                pnd_pod=1.0, snd_pod=1.0,
                                pnd_fallbacks=None, snd_fallbacks=None,
                                pnd_floor=None, snd_ceiling=None,
                                nrr_interval_days=1.0):
    """
    Infer an emission's start/end/duration CONDITIONAL on the detection evidence.

    A detection at a known time is proof the emission was active then, so every
    Monte-Carlo realization satisfies the four conditions

        t_PND <= t_start <= t_first      and      t_last <= t_end <= t_SND.

    Only the extent of the emission BEFORE the first detection (a) and AFTER the last
    detection (b) is sampled -- never whether it occurred -- in continuous time:

      onset     t_start = t_first - a,  density(a) ∝ exp[-(lambda_off - lambda_on) a]  on [0, t_first - t_PND]
      cessation t_end   = t_last  + b,  b ~ Exp(lambda_off)                            on [0, t_SND - t_last]
      duration  D = a + (t_last - t_first) + b                      (> 0, always contains the detection)

    lambda_on / lambda_off are the per-hour hazards equivalent to the per-day LPR / NRR.
    The backward draw combines the onset hazard with the probability exp(-lambda_off a) that
    an emission which began a hours before the first detection survived unrepaired until it
    was observed; the forward draw uses the repair hazard alone (memoryless lifetime).

    Soft null-detection bounds
    --------------------------
    A null detection only proves absence if the survey would have detected the emission.
    With `pnd_pod` / `snd_pod` < 1 the nearest null detection is treated as valid with that
    probability in each iteration; otherwise the bound falls back to the next null detection
    in `pnd_fallbacks` / `snd_fallbacks` (list of (time, pod), nearest first) and finally to
    the hard `pnd_floor` / `snd_ceiling` (e.g. the analysis-window edge or a duration cap).

    Parameters
    ----------
    first_detection, last_detection : datetime-like
        Earliest / latest detection time for the (merged) event; equal for a single detection.
    pnd_time, snd_time : datetime-like
        Nearest preceding / succeeding null detection (or the user-supplied cap when no
        succeeding null detection exists; Case Study 2 uses last_detection + 90 days).
    LPR, NRR : float
        Onset (leak production rate, per DAY) and repair (null repair rate) probabilities.
        NRR is a per-step probability over `nrr_interval_days` (1 = per day; 7 = the
        per-VISIT probability of Fox et al. (2021) Eq. S1 at weekly operator visits).
    N, seed : int
        Monte-Carlo draws and RNG seed.
    nrr_interval_days : float
        Step length (days) over which NRR applies; used to convert it to a hazard.
    pnd_pod, snd_pod : float
        Probability of detection of the nearest null detections at the event's rate (1 = hard).
    pnd_fallbacks, snd_fallbacks : list of (datetime-like, float), optional
        Further null detections outward from the nearest one, with their PODs.
    pnd_floor, snd_ceiling : datetime-like, optional
        Hard limits used when every null detection is sampled as a miss. Required when the
        corresponding bound is soft.

    Returns
    -------
    dict with median/mean and 2.5/97.5-percentile simulated start time, end time and
    duration (hours), the raw samples ('a_samples', 'b_samples', 'dur_samples'), the hazards
    used, and the fraction of iterations in which each nearest null detection was valid.
    """
    rng = np.random.default_rng(seed)
    t_first = pd.to_datetime(first_detection)
    t_last = pd.to_datetime(last_detection)
    t_pnd = pd.to_datetime(pnd_time)
    t_snd = pd.to_datetime(snd_time)

    lam_on = _prob_to_hourly_hazard(LPR, 1.0)
    lam_off = _prob_to_hourly_hazard(NRR, nrr_interval_days)
    lam_back = lam_off - lam_on

    def _h(later, earlier):
        return max((pd.to_datetime(later) - pd.to_datetime(earlier)).total_seconds() / 3600.0, 0.0)

    max_before_h = _h(t_first, t_pnd)
    max_after_h = _h(t_snd, t_last)
    det_span_h = _h(t_last, t_first)

    before_h, pnd_valid = _resolve_bound_hours(
        max_before_h, pnd_pod, [(_h(t_first, t), p) for t, p in (pnd_fallbacks or [])],
        None if pnd_floor is None else _h(t_first, pnd_floor), N, rng, "preceding bound")
    after_h, snd_valid = _resolve_bound_hours(
        max_after_h, snd_pod, [(_h(t, t_last), p) for t, p in (snd_fallbacks or [])],
        None if snd_ceiling is None else _h(snd_ceiling, t_last), N, rng, "succeeding bound")

    a = _truncated_exponential(lam_back, before_h, N, rng)   # hours the emission predates first detection
    b = _truncated_exponential(lam_off, after_h, N, rng)     # hours the emission outlasts last detection
    dur_h = a + det_span_h + b                               # total duration (h); >= det_span_h, never zero

    def _t(base, offset_h):
        return base + pd.to_timedelta(float(offset_h), unit="h")

    # A larger 'a' means an EARLIER start, so the low percentile of start time uses the
    # high percentile of 'a' (and vice versa).
    return dict(
        sim_start_time=_t(t_first, -float(np.median(a))),
        sim_start_lo=_t(t_first, -float(np.percentile(a, 97.5))),
        sim_start_hi=_t(t_first, -float(np.percentile(a, 2.5))),
        sim_end_time=_t(t_last, float(np.median(b))),
        sim_end_lo=_t(t_last, float(np.percentile(b, 2.5))),
        sim_end_hi=_t(t_last, float(np.percentile(b, 97.5))),
        sim_duration_h=float(np.median(dur_h)),
        sim_duration_mean_h=float(np.mean(dur_h)),
        sim_duration_lo=float(np.percentile(dur_h, 2.5)),
        sim_duration_hi=float(np.percentile(dur_h, 97.5)),
        lam_on_per_hr=lam_on, lam_off_per_hr=lam_off, lam_back_per_hr=lam_back,
        det_span_h=det_span_h, max_before_h=max_before_h, max_after_h=max_after_h,
        pnd_valid_frac=pnd_valid, snd_valid_frac=snd_valid,
        a_samples=a, b_samples=b, dur_samples=dur_h,
    )


def simulate_duration_uncertainty(leak_production_rate, events, MC_iterations=100,
                                   snd_extension_days=None, p_max=0.25,
                                   visit_interval_days=7.0, leaks_per_site=10.0):
    """
    Duration-uncertainty simulation for PRE events, CONDITIONAL on detection evidence.

    For each PRE event this samples how far the emission extends before/after its
    detection(s) using `sample_conditional_duration` (continuous-time truncated-hazard
    model). It replaces the earlier bracket-filling model, which assigned the full
    interval whenever no onset was sampled and therefore pinned durations to the upper
    boundary.

    Required columns on `events`
    ----------------------------
      'event_type', 'rate', 'start_time', 'end_time', and detection evidence -- EITHER
      'first_detection' & 'last_detection', OR a single 'detection_time'.
      'start_time'/'end_time' are interpreted as the bracketing null detections
      (t_PND / t_SND).

    Parameters
    ----------
    leak_production_rate : float
        Per-day leak production rate (onset probability), LPR.
    events : DataFrame
        Emission events (see required columns).
    MC_iterations : int
        Monte-Carlo draws per event (a floor of 1000 is applied for stable percentiles).
    snd_extension_days : float, optional
        If given, the succeeding bound t_SND is set to last_detection + this many days,
        overriding 'end_time'. Use when no succeeding null detection exists.
    p_max, visit_interval_days, leaks_per_site : float
        Parameters of the null-repair rate (Fox et al. 2021, SI Eq. S1; see
        `null_repair_rate`): operator-bonus detection probability for the largest source
        (default 0.25, the upper end of the range explored in LDAR-Sim), operator
        visitation interval V in days (default 7) and mean leaks per site at steady state
        (default 10). NRR is a per-visit probability and is converted to a hazard over V.

    Optional columns on `events` (soft null-detection bounds, see sample_conditional_duration)
    -------------------------------------------------------------------------------------------
      'pnd_pod', 'snd_pod'       : POD of the nearest preceding / succeeding null detection (default 1)
      'pnd_floor', 'snd_ceiling' : hard limits used when a soft null detection is sampled as a miss

    Returns
    -------
    The PRE-event DataFrame with added columns: simulated_duration (median, hours),
    simulated_duration_lower / simulated_duration_upper (2.5 / 97.5 pct, hours),
    simulated_start_time, simulated_end_time, nrr_per_visit.

    Raises
    ------
    ValueError
        If no detection-time evidence is present. The conditional model cannot run
        without knowing when the emission was observed; silently reverting to the old
        bracket-filling behaviour would reintroduce the boundary-pinning artifact.
    """
    pre_events = events[events.event_type == "PRE"].copy()

    if len(pre_events) == 0:
        pre_events["simulated_duration"] = []
        pre_events["simulated_duration_lower"] = []
        pre_events["simulated_duration_upper"] = []
        pre_events["simulated_start_time"] = []
        pre_events["simulated_end_time"] = []
        return pre_events

    has_first_last = ('first_detection' in pre_events.columns
                      and 'last_detection' in pre_events.columns)
    has_single = 'detection_time' in pre_events.columns
    if not (has_first_last or has_single):
        raise ValueError(
            "simulate_duration_uncertainty requires detection-time evidence: provide "
            "either 'first_detection' & 'last_detection' columns or a 'detection_time' "
            "column. The emission's start_time/end_time are treated as the bracketing "
            "null detections (t_PND / t_SND). This conditional-on-detection model "
            "replaced the previous bracket-filling model, which assigned the full "
            "interval whenever no onset was sampled."
        )

    N = max(int(MC_iterations), 1000)
    Q_max = events.rate.max()

    sim_dur, sim_lo, sim_hi, sim_start, sim_end, nrr_list = [], [], [], [], [], []
    for i, (_, e) in enumerate(pre_events.iterrows()):
        rate = float(e['rate'])
        t_pnd = pd.to_datetime(e['start_time'])
        if has_first_last:
            t_first = pd.to_datetime(e['first_detection'])
            t_last = pd.to_datetime(e['last_detection'])
        else:
            t_first = t_last = pd.to_datetime(e['detection_time'])
        if snd_extension_days is not None:
            t_snd = t_last + pd.to_timedelta(float(snd_extension_days), unit="D")
        else:
            t_snd = pd.to_datetime(e['end_time'])

        # Null-repair rate per operator VISIT (Fox et al. 2021, SI Eq. S1)
        NRR = null_repair_rate(leak_production_rate, rate, Q_max, p_max=p_max,
                               visit_interval_days=visit_interval_days,
                               leaks_per_site=leaks_per_site)
        nrr_list.append(NRR)

        def _opt(col, default=None):
            v = e[col] if col in pre_events.columns else None
            return default if v is None or (isinstance(v, float) and np.isnan(v)) else v

        r = sample_conditional_duration(
            t_first, t_last, t_pnd, t_snd, LPR=leak_production_rate, NRR=NRR, N=N, seed=i,
            pnd_pod=float(_opt('pnd_pod', 1.0)), snd_pod=float(_opt('snd_pod', 1.0)),
            pnd_floor=_opt('pnd_floor'), snd_ceiling=_opt('snd_ceiling'),
            nrr_interval_days=visit_interval_days)
        sim_dur.append(r['sim_duration_h'])
        sim_lo.append(r['sim_duration_lo'])
        sim_hi.append(r['sim_duration_hi'])
        sim_start.append(r['sim_start_time'])
        sim_end.append(r['sim_end_time'])

    pre_events["simulated_duration"] = sim_dur
    pre_events["simulated_duration_lower"] = sim_lo
    pre_events["simulated_duration_upper"] = sim_hi
    pre_events["simulated_start_time"] = sim_start
    pre_events["simulated_end_time"] = sim_end
    pre_events["nrr_per_visit"] = nrr_list

    return pre_events

