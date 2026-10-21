"""
Utility functions for emission estimation toolkit.

This module contains utility functions for statistical analysis and data correction:
- fitting_distribution: Fit statistical distributions to data
- quantification_correction: Apply uncertainty bounds to rate measurements
- duration_correction: Apply uncertainty bounds to duration measurements
"""

import numpy as np
from scipy.stats import lognorm, norm, uniform, expon, weibull_min, gamma


def quantification_correction(
    rates, lower_uncertainty_bound, upper_uncertainty_bound, iterations=1000
):
    """
    Apply quantification correction with uncertainty bounds to emission rates.
    
    Args:
        rates: Array of emission rates
        lower_uncertainty_bound: Lower bound for uncertainty multiplier
        upper_uncertainty_bound: Upper bound for uncertainty multiplier
        iterations: Number of Monte Carlo iterations
    
    Returns:
        List of sampled rates with applied uncertainty
    """
    rates_array = np.asarray(rates)
    total_samples = iterations * len(rates_array)
    sampled = np.random.choice(rates_array, size=total_samples, replace=True)
    multipliers = np.random.uniform(lower_uncertainty_bound, upper_uncertainty_bound, size=total_samples)
    return (sampled * multipliers).tolist()


def duration_correction(durations, lower_uncertainty_bound, upper_uncertainty_bound, iterations=1000):
    """
    Apply duration correction with uncertainty bounds to emission durations.
    
    Args:
        durations: Array of emission durations
        lower_uncertainty_bound: Lower bound for uncertainty multiplier
        upper_uncertainty_bound: Upper bound for uncertainty multiplier
        iterations: Number of Monte Carlo iterations
    
    Returns:
        List of sampled durations with applied uncertainty
    """
    durations_array = np.asarray(durations)
    total_samples = iterations * len(durations_array)
    sampled = np.random.choice(durations_array, size=total_samples, replace=True)
    multipliers = np.random.uniform(lower_uncertainty_bound, upper_uncertainty_bound, size=total_samples)
    return (sampled * multipliers).tolist()


def fitting_distribution(data, distribution_type="lognormal"):
    """
    Fit a statistical distribution to data.
    
    Args:
        data: Array of data points to fit
        distribution_type: Type of distribution to fit. Options:
            - "lognormal": Log-normal distribution
            - "normal": Normal distribution
            - "uniform": Uniform distribution
            - "exponential": Exponential distribution
            - "weibull": Weibull distribution
            - "gamma": Gamma distribution
    
    Returns:
        Distribution parameters (shape, location, scale)
    """
    if distribution_type == "lognormal":
        return lognorm.fit(data, floc=0)
    elif distribution_type == "normal":
        return norm.fit(data, floc=0)
    elif distribution_type == "uniform":
        return uniform.fit(data, floc=0)
    elif distribution_type == "exponential":
        return expon.fit(data, floc=0)
    elif distribution_type == "weibull":
        return weibull_min.fit(data, floc=0)
    elif distribution_type == "gamma":
        return gamma.fit(data, floc=0)
    else:
        raise ValueError(f"Unknown distribution type: {distribution_type}")

def probability_of_detection(technology, wind_speed=None, wind_consider=False, mdl_define=None,
                             pod_define=None, pod_model="flat"):
    """
    Get Probability of Detection (POD) and Minimum Detection Limit (MDL) for a given technology.
    
    Args:
        technology: Technology name (e.g., "InsightM", "Qube", "SeekOps", etc.)
        wind_speed: Wind speed value (required when wind_consider=True)
        wind_consider: Whether to consider wind effects (default: False)
        mdl_define: User-defined MDL value for "User Defined" technology
    
    Returns:
        tuple: (POD, MDL) where:
            - POD: Either a constant (float) or a function that takes Q_sample and returns POD
            - MDL: Either a constant (float) or a function that takes Q_sample and returns MDL
    
    Note:
        When wind_consider=True, POD and MDL are returned as functions that take Q_sample as input.
        When wind_consider=False, POD and MDL are returned as constants.
    """
    # Helper function to create POD function with wind consideration
    def _create_pod_function_with_wind(coeff_a, coeff_b, ws, formula_type='logistic'):
        """Create POD function based on formula type"""
        # `ws` is the wind speed captured at creation (scalar, array or time-indexed Series).
        # The simulation passes the wind speed that applies to each hypothetical event explicitly
        # (sampled from the array, or matched in time from the Series), so the closure default is
        # only used when a scalar wind speed was supplied.
        if formula_type == 'insightm':
            def pod_func(Q_sample, ws=ws):
                return 1 - (1 + (((coeff_a / ws**coeff_b) * Q_sample**1.87)**2))**-1.5
            return pod_func
        else:  # logistic
            def pod_func(Q_sample, ws=ws):
                return 1 / (1 + np.exp(coeff_a - coeff_b * (Q_sample / ws)))
            return pod_func
    
    # Helper function for MDL when wind is considered (MDL = Q_sample)
    def _mdl_with_wind(Q_sample):
        return Q_sample

    # Helper: size-dependent POD that makes the MDL gate detection (opt-in via pod_model="mdl_gated").
    # Logistic in log10(Q/MDL): POD -> 0 for Q << MDL, = plateau/2 at Q = MDL, -> plateau for Q >> MDL.
    _POD_LOGISTIC_K = 2.2   # ~plateau*0.9 at 10x MDL, ~plateau*0.1 at 0.1x MDL
    def _pod_from_mdl(mdl, plateau):
        mdl = float(mdl)   # fixed at closure-creation; hoisted out of the per-call hot path
        def pod_func(Q_sample, ws=None):   # ws accepted for a uniform call signature; unused
            Q = np.asarray(Q_sample, dtype=float)
            x = np.log10(np.where(Q > 0, Q, 1e-12) / mdl)
            return plateau / (1.0 + np.exp(-_POD_LOGISTIC_K * x))
        return pod_func

    # Validate the detection-model choice up front (not buried in the wrap step below).
    if pod_model not in ("flat", "mdl_gated"):
        raise ValueError(f"Unknown pod_model: {pod_model!r} (expected 'flat' or 'mdl_gated')")
    if pod_model == "mdl_gated" and wind_consider:
        raise ValueError("pod_model='mdl_gated' applies to the constant-POD path; wind mode "
                         "(wind_consider=True) already provides an emission-rate-dependent POD.")

    if technology == "InsightM":
        if wind_consider:
            if wind_speed is None:
                raise ValueError("wind_speed is required when wind_consider=True")
            POD = _create_pod_function_with_wind(0.00771, 1.41, wind_speed, formula_type='insightm')
            MDL = _mdl_with_wind
        else:
            POD = 0.9
            MDL = 10
                
    elif technology == "Qube":
        if wind_consider:
            if wind_speed is None:
                raise ValueError("wind_speed is required when wind_consider=True")
            POD = _create_pod_function_with_wind(-0.309, 1.047, wind_speed)
            MDL = _mdl_with_wind
        else:
            POD = 0.9
            MDL = 2
            
    elif technology == "SeekOps":
        POD = 0.9
        MDL = 0.02
        
    elif technology == "Bridger Photonic":
        if wind_consider:
            if wind_speed is None:
                raise ValueError("wind_speed is required when wind_consider=True")
            POD = _create_pod_function_with_wind(5.222, 30.286, wind_speed)
            MDL = _mdl_with_wind
        else:
            POD = 0.9
            MDL = 0.5
        
    elif technology == "GHGSat-Air":
        POD = 0.9
        MDL = 13.6
        
    elif technology == "Kuva Systems":
        if wind_consider:
            if wind_speed is None:
                raise ValueError("wind_speed is required when wind_consider=True")
            POD = _create_pod_function_with_wind(6.01, 0.13, wind_speed)
            MDL = _mdl_with_wind
        else:
            POD = 0.9
            MDL = 3.5
            
    elif technology == "Sensirion":
        if wind_consider:
            if wind_speed is None:
                raise ValueError("wind_speed is required when wind_consider=True")
            POD = _create_pod_function_with_wind(-6.41, 0.505, wind_speed)
            MDL = _mdl_with_wind
        else:
            POD = 0.9
            MDL = 3.6
            
    elif technology == "Aeromon":
        POD = 0.9
        MDL = 0.1
        
    elif technology == "Project Canary":
        if wind_consider:
            if wind_speed is None:
                raise ValueError("wind_speed is required when wind_consider=True")
            POD = _create_pod_function_with_wind(-1.661, 2.724, wind_speed)
            MDL = _mdl_with_wind
        else:
            POD = 0.9
            MDL = 0.2
            
    elif technology == "Long Path":
        POD = 0.9
        MDL = 0.06
        
    elif technology == "User Defined" or technology == "define_technology":
        # mdl_define is the MDL (a flow rate, kg/hr) -- NOT the probability of detection. The POD is
        # either an explicit constant (pod_define) or, when pod_model="mdl_gated", derived from the
        # MDL by the logistic curve (post-step below). It defaults to the standard plateau (0.9).
        # (Previously this branch set POD = mdl_define, conflating a probability with a flow rate.)
        if mdl_define is None:
            raise ValueError("mdl_define (MDL in kg/hr) is required for User Defined technology")
        MDL = mdl_define
        POD = pod_define if pod_define is not None else 0.9

    else:
        raise ValueError(f"Unknown technology: {technology}")

    # Opt-in (constant-POD path only): make the MDL gate detection by converting the scalar POD
    # into a logistic curve that plateaus at that constant and equals plateau/2 at Q = MDL. The
    # mdl_gated + wind_consider combination is rejected on entry (wind mode is already
    # Q-dependent), so here mdl_gated implies scalar POD and MDL. Default ('flat') is unchanged.
    if pod_model == "mdl_gated":
        POD = _pod_from_mdl(MDL, plateau=POD)

    return POD, MDL