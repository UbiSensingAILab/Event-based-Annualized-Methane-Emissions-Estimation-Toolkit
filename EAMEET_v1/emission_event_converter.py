"""
Emission Event Converter Module
This module handles conversion of site-level measurement data to Emission Event UML model structure.
Implements Allen's Interval Algebra for temporal event merging and a time-weighted, scale-aware
combination of the observations merged into one event (integrate_event / resolve_rate_at).
Reference: https://en.wikipedia.org/wiki/Allen%27s_interval_algebra
"""
import math
import warnings
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

# Operations used to resolve the event rate when an event contains more than one observation
# (Table 1 of the manuscript).
RATE_OPERATIONS = ('average', 'addition', 'lowest_uncertainty', 'preference')


def _rss(values: List[float]) -> float:
    """Root-sum-square of independent uncertainties."""
    return math.sqrt(sum(v * v for v in values))


def _mean_rate_and_uncertainty(observations: List[Dict]):
    """Average rate; uncertainty propagated for independent errors (RSS / n), or None if any is missing."""
    n = len(observations)
    rate = sum(o['rate'] for o in observations) / n
    uncs = [o.get('uncertainty') for o in observations]
    unc = _rss(uncs) / n if all(u is not None for u in uncs) else None
    return rate, unc


def resolve_event_rate(observations: List[Dict], operation: str = 'average',
                       preferred_observation_type: Optional[str] = None):
    """
    Resolve the event rate (and its uncertainty) from the observations merged into one event.

    Args:
        observations: List of dicts with keys 'rate', 'uncertainty' (absolute, same units as rate;
                      may be None) and 'observation_type' (may be None).
        operation: One of RATE_OPERATIONS.
            - 'average': mean of the observed rates (multiple estimates of the same source).
            - 'addition': sum of the observed rates (observations of individual equipment/components).
            - 'lowest_uncertainty': rate of the observation with the lowest reported uncertainty.
              Falls back to 'average' (with a warning) if no observation reports an uncertainty.
            - 'preference': rate of the observation(s) whose observation_type equals
              preferred_observation_type (several matches are averaged). Falls back to 'average'
              (with a warning) if the event has no observation of the preferred type.
        preferred_observation_type: Required for 'preference'.

    Returns:
        Tuple of (rate, uncertainty). Uncertainties of independent observations are combined in
        quadrature; uncertainty is None when it is not available for every contributing observation.
    """
    if not observations:
        raise ValueError("Cannot resolve an event rate from zero observations")

    op = str(operation).strip().lower().replace('-', '_').replace(' ', '_')
    if op not in RATE_OPERATIONS:
        raise ValueError(f"Unknown rate operation '{operation}'. Expected one of {RATE_OPERATIONS}")

    if len(observations) == 1:
        return observations[0]['rate'], observations[0].get('uncertainty')

    if op == 'average':
        return _mean_rate_and_uncertainty(observations)

    if op == 'addition':
        rate = sum(o['rate'] for o in observations)
        uncs = [o.get('uncertainty') for o in observations]
        return rate, (_rss(uncs) if all(u is not None for u in uncs) else None)

    if op == 'lowest_uncertainty':
        with_unc = [o for o in observations if o.get('uncertainty') is not None]
        if not with_unc:
            warnings.warn("rate_operation='lowest_uncertainty' but no observation reports an "
                          "uncertainty; falling back to 'average'")
            return _mean_rate_and_uncertainty(observations)
        best = min(with_unc, key=lambda o: o['uncertainty'])
        return best['rate'], best['uncertainty']

    # op == 'preference'
    if not preferred_observation_type:
        raise ValueError("rate_operation='preference' requires preferred_observation_type")
    wanted = str(preferred_observation_type).strip().lower()
    preferred = [o for o in observations
                 if str(o.get('observation_type') or '').strip().lower() == wanted]
    if not preferred:
        warnings.warn(f"No observation of type '{preferred_observation_type}' in the event; "
                      "falling back to 'average'")
        return _mean_rate_and_uncertainty(observations)
    return _mean_rate_and_uncertainty(preferred)


# ----------------------------------------------------------------------------------------------
# Time-weighted, scale-aware combination of the observations of one event (reviewer comment 5).
#
# An event's emission quantity is the integral of a piecewise-constant rate over the event's
# temporal bound. The bound is split at every start/end of an observation that carries a measured
# interval (e.g., a CMS alarm). Within each sub-interval the active observations are
#   * the interval observations whose interval covers the sub-interval, and
#   * every instantaneous observation of the event (a snapshot detection has no measured duration,
#     so it is treated as a sample of the event rate rather than as a rate over a known interval).
# The rate of a sub-interval is resolved from its active observations with the hierarchy
#   1. replicates of the same source feature at the same scale -> `rate_operation` (average by default);
#   2. distinct features at the same scale (e.g., two components) -> summed, they emit concurrently;
#   3. a coarser scale already contains the finer ones (a site measurement includes its components), so
#      the coarse-scale rate and the finer-scale aggregate are COMBINED by `rate_operation`
#      (average / lowest uncertainty / preference) and never added.
# The event quantity is sum(rate_i * dt_i); the resolved event rate is quantity / duration. Because the
# rate is integrated in time, (i) the integrated mass of interval observations is preserved,
# (ii) splitting one observation into consecutive pieces does not change the result, (iii) exact
# duplicate records are collapsed before resolution and do not change the result, and (iv) the
# result depends only on the SET of observations in the event, not on the order in which they were
# merged (the former pairwise average of event rates is no longer used).
# ----------------------------------------------------------------------------------------------
SCALE_ORDER = {'component': 0, 'equipment': 1, 'site': 2}
_SCALE_ALIASES = {'facility': 'site', 'source': 'site', 'well': 'site', 'pad': 'site',
                  'unit': 'equipment', 'comp': 'component'}


def normalize_scale(scale) -> str:
    """Map a user-supplied scale label to 'component' | 'equipment' | 'site' (default 'site')."""
    if scale is None:
        return 'site'
    s = str(scale).strip().lower()
    if s in ('', 'nan', 'none'):
        return 'site'
    s = _SCALE_ALIASES.get(s, s)
    if s not in SCALE_ORDER:
        raise ValueError(f"Unknown observation scale '{scale}'. Expected one of {tuple(SCALE_ORDER)}")
    return s


def _combine_two(a, b, operation, preferred_observation_type=None):
    """Combine the (rate, unc, obs_types) of two nested-scale estimates by the chosen operation."""
    (ra, ua, ta), (rb, ub, tb) = a, b
    op = str(operation).strip().lower().replace('-', '_').replace(' ', '_')
    if op == 'lowest_uncertainty' and ua is not None and ub is not None:
        return (ra, ua, ta) if ua <= ub else (rb, ub, tb)
    if op == 'preference' and preferred_observation_type:
        w = str(preferred_observation_type).strip().lower()
        ia, ib = w in ta, w in tb
        if ia and not ib:
            return (ra, ua, ta)
        if ib and not ia:
            return (rb, ub, tb)
    # 'average', 'addition' (never applied across scales) and all fall-backs: mean of the two estimates
    unc = None if ua is None or ub is None else _rss([ua, ub]) / 2.0
    return ((ra + rb) / 2.0, unc, ta | tb)


def resolve_rate_at(active: List[Dict], operation: str = 'average',
                    preferred_observation_type: Optional[str] = None):
    """
    Resolve the rate (and absolute uncertainty) in force over one sub-interval from the observations
    active in it, honouring the spatial hierarchy component < equipment < site.

    Each observation dict carries 'rate', 'uncertainty' (absolute or None), 'observation_type',
    'scale' ('component'|'equipment'|'site') and 'feature' (the physical source it was attributed to).
    Returns (rate, uncertainty).
    """
    if not active:
        return 0.0, 0.0
    by_scale: Dict[str, Dict[str, List[Dict]]] = {}
    for o in active:
        sc = normalize_scale(o.get('scale'))
        ft = str(o.get('feature') if o.get('feature') is not None else '')
        by_scale.setdefault(sc, {}).setdefault(ft, []).append(o)

    est = None   # (rate, unc, set_of_observation_types) at the finest scale resolved so far
    for sc in sorted(by_scale, key=SCALE_ORDER.get):
        # 1. replicates of the same feature -> rate_operation;  2. distinct features -> sum
        tot_rate, tot_uncs, types, unc_missing = 0.0, [], set(), False
        for ft, group in by_scale[sc].items():
            r, u = resolve_event_rate(group, operation, preferred_observation_type)
            tot_rate += r
            if u is None:
                unc_missing = True
            else:
                tot_uncs.append(u)
            types |= {str(o.get('observation_type') or '').strip().lower() for o in group}
        level = (tot_rate, None if unc_missing else _rss(tot_uncs), types)
        # 3. nested coverage: combine with the finer-scale aggregate, never add
        est = level if est is None else _combine_two(level, est, operation, preferred_observation_type)
    return est[0], est[1]


def _dedupe_observations(observations: List[Dict]) -> List[Dict]:
    """Collapse exact duplicate records (same id, or identical in every field) so that a duplicated
    observation does not change the resolved rate, its uncertainty or the integrated quantity."""
    seen_ids, seen_keys, out = set(), set(), []
    for o in observations:
        oid = o.get('id')
        key = (o.get('rate'), o.get('uncertainty'), str(o.get('observation_type') or '').lower(),
               normalize_scale(o.get('scale')), str(o.get('feature') or ''),
               str(o.get('start') or ''), str(o.get('end') or ''), str(o.get('time') or ''))
        if (oid is not None and oid in seen_ids) or key in seen_keys:
            continue
        if oid is not None:
            seen_ids.add(oid)
        seen_keys.add(key)
        out.append(o)
    return out


def integrate_event(observations: List[Dict], event_start, event_end, operation: str = 'average',
                    preferred_observation_type: Optional[str] = None) -> Dict:
    """
    Integrate the piecewise-constant rate of an event over its temporal bound.

    observations: dicts with 'id', 'rate', 'uncertainty', 'observation_type', 'scale', 'feature' and,
        for observations with a measured interval, 'start' and 'end' (ISO strings or timestamps;
        None for instantaneous observations).
    event_start, event_end: the event's temporal bound (union of the constituent bounds).

    Returns dict(rate, uncertainty, quantity, duration, segments) where rate = quantity / duration
    (kg/h), uncertainty is the absolute uncertainty of that rate (sub-interval uncertainties are
    combined linearly, i.e., treated as fully correlated within the event, which is exact for a
    single observation and conservative otherwise), quantity is in kg and duration in hours.
    """
    obs = _dedupe_observations(observations)
    t0, t1 = pd.to_datetime(event_start), pd.to_datetime(event_end)
    duration = max((t1 - t0).total_seconds() / 3600.0, 0.0)

    interval_obs, instant_obs = [], []
    for o in obs:
        if o.get('start') is not None and o.get('end') is not None:
            a, b = pd.to_datetime(o['start']), pd.to_datetime(o['end'])
            a, b = max(a, t0), min(b, t1)
            if b > a:
                interval_obs.append((a, b, o))
                continue
        instant_obs.append(o)

    if duration <= 0 or not interval_obs:
        # zero-length bound, or only instantaneous observations: every observation is active throughout
        rate, unc = resolve_rate_at([o for _, _, o in interval_obs] + instant_obs, operation,
                                    preferred_observation_type)
        return dict(rate=rate, uncertainty=unc, quantity=rate * duration if duration > 0 else rate,
                    duration=duration, segments=[(t0, t1, rate, unc)])

    cuts = sorted({t0, t1} | {a for a, _, _ in interval_obs} | {b for _, b, _ in interval_obs})
    quantity, unc_mass, segments = 0.0, 0.0, []
    unc_missing = False
    for a, b in zip(cuts[:-1], cuts[1:]):
        dt = (b - a).total_seconds() / 3600.0
        if dt <= 0:
            continue
        active = [o for s, e, o in interval_obs if s <= a and e >= b] + instant_obs
        if not active:   # gap inside the bound covered by no observation: nothing is emitted there
            segments.append((a, b, 0.0, 0.0))
            continue
        r, u = resolve_rate_at(active, operation, preferred_observation_type)
        quantity += r * dt
        if u is None:
            unc_missing = True
        else:
            unc_mass += u * dt
        segments.append((a, b, r, u))
    rate = quantity / duration
    unc = None if unc_missing else unc_mass / duration
    return dict(rate=rate, uncertainty=unc, quantity=quantity, duration=duration, segments=segments)


def convert_to_emission_event_model(data: pd.DataFrame, column_mapping: Optional[Dict[str, str]] = None,
                                    time_column: Optional[str] = None,
                                    emission_characteristics: str = 'intermittent',
                                    rate_operation: str = 'average',
                                    preferred_observation_type: Optional[str] = None) -> pd.DataFrame:
    """
    Convert site-level measurement data to Emission Event data model.
    Based on UML: Emission Event has eventType, and relationships to:
    - Quantity (calculated from rate * duration)
    - Observation (quantity/rate, duration)
    - Duration (duration, durationEstimationType)
    - Cause (root cause analysis)
    - Source (sourceLocation, sourceCategory, physicalSource)
    
    Implements temporal event creation and merging using Allen's Interval Algebra:
    1. Creates initial events from detections (rate > 0)
    2. Determines start/end times based on non-detects (rate = 0)
    3. Merges events using Allen's temporal relations
    
    Args:
        data: DataFrame with uploaded data
        column_mapping: Dictionary mapping required fields to actual column names.
                       Required keys: 'rate', 'id', 'source'
                       Optional keys: 'cause', 'duration', 'time', 'emission_characteristics', 'uncertainties', 'source_scale',
                       'observation_scale' (column giving the scale of each observation: component / equipment / site)
                       and 'feature' (column naming the physical source feature each observation is attributed to,
                       e.g. the equipment or component; defaults to the source).
                       Note: 'source_scale' is the default scale (defaults to 'site') used when no 'observation_scale'
                       column is mapped
        time_column: Name of time/timestamp column (optional, will try to auto-detect)
        emission_characteristics: 'continuous' or 'intermittent'. If 'continuous', each row is an independent event.
                                 If 'intermittent', events are merged using Allen's interval algebra.
        rate_operation: How the event rate is resolved when several observations are merged into one
                        event: 'average' (default), 'addition', 'lowest_uncertainty' or 'preference'
                        (see resolve_event_rate).
        preferred_observation_type: Observation type (value of the mapped 'observation_type' column,
                        e.g. 'flyover') whose rate takes precedence when rate_operation='preference'.

    Returns:
        DataFrame with converted emission events (flattened structure)
    
    Raises:
        ValueError: If required columns are missing or not mapped
    """
    # Use column mapping if provided, otherwise try to auto-detect
    if column_mapping:
        rate_col = column_mapping.get('rate')
        uncertainties_col = column_mapping.get('uncertainties')
        id_col = column_mapping.get('id')
        # source_scale removed from mapping - defaults to 'site'
        source_scale_value = column_mapping.get('source_scale', 'site')  # Default to 'site' if not provided
        source_col = column_mapping.get('source')
        cause_col = column_mapping.get('cause')
        start_time_col = column_mapping.get('start_time')
        end_time_col = column_mapping.get('end_time')
        observation_type_col = column_mapping.get('observation_type')  # Optional: column indicating observation type (used to determine operational status)
        observation_scale_col = column_mapping.get('observation_scale')  # Optional: per-observation scale column
        feature_col = column_mapping.get('feature')  # Optional: physical source feature (equipment/component) of the observation
        time_col = time_column or column_mapping.get('time')
    else:
        # Auto-detect columns
        rate_col = 'rate' if 'rate' in data.columns else None
        uncertainties_col = 'uncertainties' if 'uncertainties' in data.columns else None
        id_col = 'id' if 'id' in data.columns else None
        source_scale_value = 'site'  # Default value
        source_col = 'source' if 'source' in data.columns else None
        cause_col = 'cause' if 'cause' in data.columns else None
        start_time_col = 'start_time' if 'start_time' in data.columns else ('startTime' if 'startTime' in data.columns else None)
        end_time_col = 'end_time' if 'end_time' in data.columns else ('endTime' if 'endTime' in data.columns else None)
        observation_type_col = 'observation_type' if 'observation_type' in data.columns else ('observationType' if 'observationType' in data.columns else ('Observation_Type' if 'Observation_Type' in data.columns else None))
        observation_scale_col = 'observation_scale' if 'observation_scale' in data.columns else None
        feature_col = 'feature' if 'feature' in data.columns else None
        time_col = time_column
    
    # Auto-detect time column if not provided
    if not time_col:
        time_candidates = ['time', 'timestamp', 'datetime', 'date', 'detectionTime', 
                          'surveyTime', 'startTime', 'start_time', 'endTime', 'end_time']
        for candidate in time_candidates:
            if candidate in data.columns:
                time_col = candidate
                break
    
    # Validate mandatory fields
    if not rate_col or rate_col not in data.columns:
        raise ValueError("Rate column is required but not found or not mapped")
    if not id_col or id_col not in data.columns:
        raise ValueError("ID column is required but not found or not mapped")
    if not source_col or source_col not in data.columns:
        raise ValueError("Source column is required but not found or not mapped")
    # source_scale defaults to 'site' if not provided
    if not source_scale_value:
        source_scale_value = 'site'
    
    # Get emission characteristics from mapping or parameter
    emission_char = column_mapping.get('emission_characteristics', emission_characteristics) if column_mapping else emission_characteristics
    emission_char = emission_char.lower() if emission_char else 'intermittent'

    # Validate the rate-resolution options up front
    if str(rate_operation).strip().lower().replace('-', '_').replace(' ', '_') not in RATE_OPERATIONS:
        raise ValueError(f"Unknown rate operation '{rate_operation}'. Expected one of {RATE_OPERATIONS}")
    if str(rate_operation).strip().lower() == 'preference':
        if not preferred_observation_type:
            raise ValueError("rate_operation='preference' requires preferred_observation_type")
        if not observation_type_col or observation_type_col not in data.columns:
            raise ValueError("rate_operation='preference' requires an 'observation_type' column to be mapped")

    # Step 1: Create initial events from detections with temporal boundaries
    if time_col and time_col in data.columns:
            # Use temporal event creation logic
            emission_events = create_initial_events(data, {
                'rate': rate_col,
                'uncertainties': uncertainties_col,
                'id': id_col,
                'source': source_col,
                'source_scale': source_scale_value,  # This is now the enum value, not a column
                'cause': cause_col,
                'start_time': start_time_col,
                'end_time': end_time_col,
                'observation_type': observation_type_col,  # Pass observation_type column mapping
                'observation_scale': observation_scale_col,
                'feature': feature_col,
            }, time_col)
            
            # Step 2: Merge events using Allen's interval algebra (only if intermittent)
            if emission_char == 'intermittent':
                emission_events = merge_events_by_allen_algebra(
                    emission_events,
                    rate_operation=rate_operation,
                    preferred_observation_type=preferred_observation_type,
                )
            # If continuous, skip merging - each row is an independent event
    else:
        # Fallback to original logic if no time column
        emission_events = []
        for idx, row in data.iterrows():
            # Only process detections (rate > 0)
            rate = pd.to_numeric(row.get(rate_col, 0), errors='coerce')
            if pd.isna(rate) or rate == 0:
                continue
            
            # Get uncertainties if available
            uncertainties = None
            if uncertainties_col and uncertainties_col in data.columns:
                uncertainties_val = row.get(uncertainties_col)
                if pd.notna(uncertainties_val):
                    uncertainties = pd.to_numeric(uncertainties_val, errors='coerce')
                    if pd.isna(uncertainties):
                        uncertainties = None
            
            original_data_id = str(row.get(id_col, idx))
            # Generate UUID for event ID
            event_id = str(uuid.uuid4())
            # source_scale is now a direct enum value, not from a column
            # source_scale is now a direct enum value, not from a column
            source_scale = str(source_scale_value).lower()
            source_name = str(row.get(source_col, 'Unknown'))
            
            # Start time and end time handling
            start_time = None
            end_time = None
            duration = 0
            
            # If start_time and end_time columns are provided, use them
            if start_time_col and start_time_col in data.columns and end_time_col and end_time_col in data.columns:
                start_time_val = row.get(start_time_col)
                end_time_val = row.get(end_time_col)
                if pd.notna(start_time_val) and pd.notna(end_time_val):
                    try:
                        start_time = pd.to_datetime(start_time_val)
                        end_time = pd.to_datetime(end_time_val)
                        duration = (end_time - start_time).total_seconds() / 3600
                        duration_estimation_type = 'Measured'
                    except (ValueError, TypeError):
                        duration_estimation_type = 'Estimated'
                else:
                    duration_estimation_type = 'Estimated'
            else:
                duration_estimation_type = 'Estimated'
            
            # Cause handling (optional)
            cause_value = None
            if cause_col and cause_col in data.columns:
                cause_value = str(row.get(cause_col, ''))
                if cause_value == 'nan' or cause_value == '':
                    cause_value = None
            
            # Get observation_type from original data to determine operational status
            # Resolved events (RE): observation_type == "operation"
            # Partially resolved events (PRE): observation_type != "operation"
            is_operational = False  # Track if this is an operational event
            if observation_type_col and observation_type_col in data.columns:
                observation_type_value = str(row.get(observation_type_col, '')).strip().lower()
                # Check if observation_type equals "operation" (case-insensitive)
                if observation_type_value == 'operation':
                    is_operational = True
                else:
                    is_operational = False
            
            # Calculate quantity (rate * duration)
            quantity = rate * duration if duration > 0 else rate
            
            # Create emission event following UML structure
            event = {
                'id': event_id,
                'original_data_id': original_data_id,  # Store original data ID separately
                'eventType': 'Emission Event',
                'is_operational': is_operational,  # Track operational status (True if observation_type == "operation")
                'quantity': {
                    'value': quantity,
                    'unit': 'kg'
                },
                'observation': {
                    'quantity': rate,
                    'duration': duration
                },
                'duration': {
                    'duration': duration,
                    'durationEstimationType': duration_estimation_type
                },
                'cause': {
                    'rootCauseAnalysis': cause_value
                } if cause_value else None,
                'source': {
                    'sourceLocation': source_name,
                    'sourceCategory': source_scale,
                    'physicalSource': source_name
                },
                'rate': rate,
                'uncertainties': uncertainties,
                'source_scale': source_scale,
                'source_name': source_name,
                'startTime': start_time.isoformat() if start_time else None,
                'endTime': end_time.isoformat() if end_time else None,
                # detection evidence: a single observation at the row's time
                'first_detection': pd.to_datetime(row[time_col]).isoformat() if time_col in data.columns and pd.notna(row.get(time_col)) else None,
                'last_detection': pd.to_datetime(row[time_col]).isoformat() if time_col in data.columns and pd.notna(row.get(time_col)) else None,
            }
            emission_events.append(event)
    
    # Convert to DataFrame for easier display (flattened structure)
    events_list = []
    for e in emission_events:
        # Format merged_from: show list of original data IDs
        merged_from_display = None
        if 'merged_from' in e and e['merged_from']:
            # merged_from is already a list of original data IDs (for merged events)
            if isinstance(e['merged_from'], list):
                merged_from_display = ', '.join(str(oid) for oid in e['merged_from'])
            else:
                merged_from_display = str(e['merged_from'])
        elif 'original_data_id' in e:
            # Single event (not merged), still show its original data ID
            merged_from_display = str(e['original_data_id'])
        
        # Format startTime and endTime to strings if they're datetime objects
        start_time = e.get('startTime')
        if start_time and not isinstance(start_time, str):
            start_time = start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time)
        
        end_time = e.get('endTime')
        if end_time and not isinstance(end_time, str):
            end_time = end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time)
        
        # Determine event_type: RE if operational (observation_type == "operation"), PRE if non-operational (observation_type != "operation")
        is_operational = e.get('is_operational', False)
        if is_operational:
            event_type = 'RE'  # Resolved - includes data with observation_type == "operation"
        else:
            event_type = 'PRE'  # Partially Resolved - only includes data with observation_type != "operation"
        
        event_dict = {
            'id': e['id'],
            'rate': e['rate'],
            'duration': e['duration']['duration'],
            'quantity': e['quantity']['value'],
            'sourceLocation': e['source']['sourceLocation'],
            'startTime': start_time,
            'endTime': end_time,
            'merged_from': merged_from_display,
            'event_type': event_type,  # Add event_type to output
            'first_detection': e.get('first_detection'),
            'last_detection': e.get('last_detection'),
            'n_observations': len(e.get('observations') or []) or 1,
        }
        # Add uncertainties if available
        if 'uncertainties' in e and e['uncertainties'] is not None:
            event_dict['uncertainties'] = e['uncertainties']
        events_list.append(event_dict)
    
    events_df = pd.DataFrame(events_list)
    
    # Calculate statistics: resolved vs partially resolved events
    resolved_count = len(events_df[events_df['event_type'] == 'RE']) if 'event_type' in events_df.columns else 0
    partially_resolved_count = len(events_df[events_df['event_type'] == 'PRE']) if 'event_type' in events_df.columns else 0
    total_events = len(events_df)
    
    # Store statistics as attributes (can be accessed via events_df.attrs)
    events_df.attrs['resolved_count'] = resolved_count
    events_df.attrs['partially_resolved_count'] = partially_resolved_count
    events_df.attrs['total_events'] = total_events
    
    return events_df


# Allen's Interval Algebra Relations
# Based on: https://en.wikipedia.org/wiki/Allen%27s_interval_algebra

def check_allen_relation(event1_start: datetime, event1_end: datetime, 
                         event2_start: datetime, event2_end: datetime) -> List[str]:
    """
    Check which Allen's interval algebra relations hold between two events.
    
    Returns list of relations that are true:
    - 'before' (<): event1 ends before event2 starts
    - 'meets' (m): event1 ends exactly when event2 starts
    - 'overlaps' (o): event1 starts before event2, but they overlap
    - 'starts' (s): event1 starts when event2 starts, but event1 ends before event2
    - 'during' (d): event1 is completely contained within event2
    - 'finishes' (f): event1 ends when event2 ends, but event1 starts after event2
    - 'equals' (=): event1 and event2 have the same start and end times
    
    Args:
        event1_start: Start time of first event
        event1_end: End time of first event
        event2_start: Start time of second event
        event2_end: End time of second event
    
    Returns:
        List of relation strings that are true
    """
    relations = []
    
    # Ensure times are datetime objects
    if isinstance(event1_start, str):
        event1_start = pd.to_datetime(event1_start)
    if isinstance(event1_end, str):
        event1_end = pd.to_datetime(event1_end)
    if isinstance(event2_start, str):
        event2_start = pd.to_datetime(event2_start)
    if isinstance(event2_end, str):
        event2_end = pd.to_datetime(event2_end)
    
    # before (<): event1 ends before event2 starts
    if event1_end < event2_start:
        relations.append('before')
    
    # meets (m): event1 ends exactly when event2 starts
    if event1_end == event2_start:
        relations.append('meets')
    
    # overlaps (o): event1 starts before event2, overlaps, but ends before event2 ends
    if event1_start < event2_start < event1_end < event2_end:
        relations.append('overlaps')
    
    # starts (s): event1 starts when event2 starts, but event1 ends before event2
    if event1_start == event2_start and event1_end < event2_end:
        relations.append('starts')
    
    # during (d): event1 is completely contained within event2
    if event2_start < event1_start and event1_end < event2_end:
        relations.append('during')
    
    # finishes (f): event1 ends when event2 ends, but event1 starts after event2
    if event1_start > event2_start and event1_end == event2_end:
        relations.append('finishes')
    
    # equals (=): same start and end
    if event1_start == event2_start and event1_end == event2_end:
        relations.append('equals')
    
    return relations


def _continuation(event1: Dict, event2: Dict) -> bool:
    """
    True when the two events touch (end of one == start of the other) through two observations that
    carry MEASURED intervals of the same source feature and observation type, i.e., one record that was
    split into consecutive pieces (e.g., a CMS alarm cut at midnight). Such pieces are one continued
    observation and are merged, so splitting a record does not change the event count. Snapshot
    detections never qualify: their bounds end at a null detection, which is evidence that the
    emission stopped, and bounds that meet at a null detection remain separate events.
    """
    def _touch(e_end, e_start):
        for o1 in _event_observations(e_end):
            if o1.get('end') is None or o1.get('start') is None:
                continue
            for o2 in _event_observations(e_start):
                if o2.get('end') is None or o2.get('start') is None:
                    continue
                if (pd.to_datetime(o1['end']) == pd.to_datetime(o2['start'])
                        and str(o1.get('feature') or '') == str(o2.get('feature') or '')
                        and normalize_scale(o1.get('scale')) == normalize_scale(o2.get('scale'))
                        and str(o1.get('observation_type') or '').lower() == str(o2.get('observation_type') or '').lower()):
                    return True
        return False
    return _touch(event1, event2) or _touch(event2, event1)


def can_merge_events(event1: Dict, event2: Dict) -> bool:
    """
    Check if two events can be merged based on Allen's interval algebra.
    Events can be merged if they:
    1. Have the same source
    2. Overlap in time (share a non-zero stretch of time)

    Of Allen's 13 relations, 'precedes'/'preceded by' and 'meets'/'met by' keep the events
    separate; the remaining nine (overlaps, overlapped by, starts, started by, during, contains,
    finishes, finished by, equals) merge them. One exception applies to 'meets': two measured-interval
    records of the same feature and observation type that touch end-to-start are pieces of one
    continued record and are merged (see _continuation).

    Args:
        event1: First event dictionary
        event2: Second event dictionary
    
    Returns:
        True if events can be merged, False otherwise
    """
    # Check if same source
    source1 = event1.get('source', {}).get('physicalSource', '')
    source2 = event2.get('source', {}).get('physicalSource', '')
    
    # Also check sourceLocation for compatibility
    if source1 != source2:
        source_loc1 = event1.get('source', {}).get('sourceLocation', '')
        source_loc2 = event2.get('source', {}).get('sourceLocation', '')
        if source_loc1 != source_loc2:
            return False
    
    # Get time intervals
    start1 = event1.get('startTime')
    end1 = event1.get('endTime')
    start2 = event2.get('startTime')
    end2 = event2.get('endTime')
    
    if None in [start1, end1, start2, end2]:
        return False
    
    # Convert to datetime if needed
    if isinstance(start1, str):
        start1 = pd.to_datetime(start1)
    if isinstance(end1, str):
        end1 = pd.to_datetime(end1)
    if isinstance(start2, str):
        start2 = pd.to_datetime(start2)
    if isinstance(end2, str):
        end2 = pd.to_datetime(end2)
    
    # Two intervals overlap if: start1 < end2 AND start2 < end1. The strict inequalities exclude
    # 'meets'/'met by' (end1 == start2 or end2 == start1), which stay separate events unless the
    # touching records are consecutive pieces of one measured-interval observation.
    # Identical intervals ('equals') merge even if zero-length.
    if ((start1 < end2) and (start2 < end1)) or (start1 == start2 and end1 == end2):
        return True
    if (end1 == start2 or end2 == start1) and _continuation(event1, event2):
        return True
    return False


def _event_observations(event: Dict) -> List[Dict]:
    """Observations constituting an event (a single pseudo-observation for legacy event dicts)."""
    if event.get('observations'):
        return list(event['observations'])
    return [{
        'id': event.get('original_data_id'),
        'rate': event.get('rate', 0),
        'uncertainty': event.get('uncertainties'),
        'observation_type': None,
        'scale': event.get('source_scale') or 'site',
        'feature': event.get('source_name'),
        'start': None,
        'end': None,
    }]


def merge_events(event1: Dict, event2: Dict, rate_operation: str = 'average',
                 preferred_observation_type: Optional[str] = None) -> Dict:
    """
    Merge two events into a single event.
    - Pool the constituent observations of both events (duplicates collapsed)
    - Combine the time intervals (min start, max end)
    - Integrate the piecewise-constant rate over the combined bound (see integrate_event): the
      quantity is sum(rate_i * dt_i) over the sub-intervals of the bound and the resolved event
      rate is quantity / duration, so integrated mass is preserved, nested spatial coverage is
      honoured and the result does not depend on the merge order.

    Args:
        event1: First event dictionary
        event2: Second event dictionary
        rate_operation: 'average' (default), 'addition', 'lowest_uncertainty' or 'preference'
        preferred_observation_type: Observation type taking precedence when rate_operation='preference'

    Returns:
        Merged event dictionary
    """
    merged_observations = _dedupe_observations(_event_observations(event1) + _event_observations(event2))

    # Get time intervals
    start1 = pd.to_datetime(event1.get('startTime'))
    end1 = pd.to_datetime(event1.get('endTime'))
    start2 = pd.to_datetime(event2.get('startTime'))
    end2 = pd.to_datetime(event2.get('endTime'))
    
    # Combine intervals: min start, max end
    merged_start = min(start1, start2)
    merged_end = max(end1, end2)

    integ = integrate_event(merged_observations, merged_start, merged_end, rate_operation,
                            preferred_observation_type)
    avg_rate, avg_uncertainties = integ['rate'], integ['uncertainty']
    duration = integ['duration']
    quantity = integ['quantity']
    
    # Merge other attributes (prefer non-None values)
    cause1 = event1.get('cause', {}).get('rootCauseAnalysis') if event1.get('cause') else None
    cause2 = event2.get('cause', {}).get('rootCauseAnalysis') if event2.get('cause') else None
    merged_cause = cause1 if cause1 else cause2
    
    # Collect original data IDs from both events
    original_ids = []
    if 'original_data_id' in event1:
        original_ids.append(event1['original_data_id'])
    elif 'merged_from' in event1:
        # If event1 was already merged, get its original IDs
        merged_from_1 = event1.get('merged_from', [])
        if isinstance(merged_from_1, list):
            original_ids.extend(merged_from_1)
        else:
            original_ids.append(str(merged_from_1))
    
    if 'original_data_id' in event2:
        original_ids.append(event2['original_data_id'])
    elif 'merged_from' in event2:
        # If event2 was already merged, get its original IDs
        merged_from_2 = event2.get('merged_from', [])
        if isinstance(merged_from_2, list):
            original_ids.extend(merged_from_2)
        else:
            original_ids.append(str(merged_from_2))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_original_ids = []
    for oid in original_ids:
        if oid not in seen:
            seen.add(oid)
            unique_original_ids.append(oid)
    
    # Determine operational status: merged event is operational if at least one event is operational
    is_operational1 = event1.get('is_operational', False)
    is_operational2 = event2.get('is_operational', False)
    merged_is_operational = is_operational1 or is_operational2
    
    # Generate UUID for merged event
    merged_event_id = str(uuid.uuid4())
    
    # Create merged event
    merged_event = {
        'id': merged_event_id,
        'eventType': event1.get('eventType', 'Emission Event'),
        'is_operational': merged_is_operational,  # True if at least one merged event has observation_type == "operation" (RE)
        'quantity': {
            'value': quantity,
            'unit': 'kg'
        },
        'observation': {
            'quantity': avg_rate,
            'duration': duration
        },
        'duration': {
            'duration': duration,
            'durationEstimationType': 'Measured'
        },
        'cause': {
            'rootCauseAnalysis': merged_cause
        } if merged_cause else None,
        'source': event1.get('source', {}),
        'rate': avg_rate,
        'uncertainties': avg_uncertainties,
        'source_scale': event1.get('source_scale', ''),
        'source_name': event1.get('source_name', ''),
        'startTime': merged_start.isoformat() if hasattr(merged_start, 'isoformat') else merged_start,
        'endTime': merged_end.isoformat() if hasattr(merged_end, 'isoformat') else merged_end,
        'merged_from': unique_original_ids,  # Store list of original data IDs
        'observations': merged_observations,  # Constituent observations (needed to re-resolve the rate on further merges)
        # detection evidence: earliest / latest detection among the merged observations
        'first_detection': _detection_span(event1, event2)[0],
        'last_detection': _detection_span(event1, event2)[1],
    }
    
    return merged_event


def _detection_span(event1: Dict, event2: Dict) -> tuple:
    """Earliest first_detection and latest last_detection across two events (ISO strings).
    Falls back to an event's startTime/endTime when it carries no detection evidence."""
    firsts = [pd.to_datetime(e.get('first_detection') or e.get('startTime')) for e in (event1, event2)]
    lasts = [pd.to_datetime(e.get('last_detection') or e.get('endTime')) for e in (event1, event2)]
    firsts = [t for t in firsts if pd.notna(t)]
    lasts = [t for t in lasts if pd.notna(t)]
    return (min(firsts).isoformat() if firsts else None, max(lasts).isoformat() if lasts else None)


def _calculate_temporal_boundaries(source_data: pd.DataFrame, detection_time: pd.Timestamp, 
                                   time_col: str, rate_col: str) -> tuple:
    """
    Calculate start and end times for an event based on non-detects.
    
    Args:
        source_data: DataFrame filtered to a single source
        detection_time: Timestamp of the detection
        time_col: Name of the time column
        rate_col: Name of the rate column
    
    Returns:
        Tuple of (start_time, end_time)
    """
    # Find start time: most recent non-detect before this detection
    non_detects_before = source_data[
        (source_data[time_col] < detection_time) & 
        (pd.to_numeric(source_data[rate_col], errors='coerce') == 0)
    ]
    
    if len(non_detects_before) > 0:
        start_time = non_detects_before[time_col].iloc[-1]
    else:
        # Default: 180 days before detection if no non-detect found
        start_time = detection_time - timedelta(days=180)
    
    # Find end time: next non-detect after this detection
    non_detects_after = source_data[
        (source_data[time_col] > detection_time) & 
        (pd.to_numeric(source_data[rate_col], errors='coerce') == 0)
    ]
    
    if len(non_detects_after) > 0:
        end_time = non_detects_after[time_col].iloc[0]
    else:
        # Default: 1 hour after detection if no non-detect found
        end_time = detection_time + timedelta(hours=1)
    
    return start_time, end_time


def create_initial_events(data: pd.DataFrame, column_mapping: Dict[str, str], 
                          time_col: str) -> List[Dict]:
    """
    Create initial events from data rows.
    For each detection (rate > 0):
    - Start time = most recent non-detect (rate=0) for same source before this detection
    - End time = next non-detect (rate=0) for same source after this detection
    
    Args:
        data: DataFrame with measurement data
        column_mapping: Column mapping dictionary
        time_col: Name of the time/timestamp column
    
    Returns:
        List of initial event dictionaries
    """
    events = []
    
    rate_col = column_mapping.get('rate')
    uncertainties_col = column_mapping.get('uncertainties')
    id_col = column_mapping.get('id')
    source_col = column_mapping.get('source')
    # source_scale is now a direct enum value ('site', 'equipment', 'component'), not a column name
    source_scale_value = column_mapping.get('source_scale')
    cause_col = column_mapping.get('cause')
    start_time_col = column_mapping.get('start_time')
    end_time_col = column_mapping.get('end_time')
    observation_type_col = column_mapping.get('observation_type')  # Optional: column indicating observation type (used to determine operational status)
    observation_scale_col = column_mapping.get('observation_scale')
    feature_col = column_mapping.get('feature')
    
    # Ensure time column is datetime
    if time_col not in data.columns:
        raise ValueError(f"Time column '{time_col}' not found in data")
    
    data = data.copy()
    data[time_col] = pd.to_datetime(data[time_col])
    data = data.sort_values(by=[source_col, time_col]).reset_index(drop=True)
    
    # Group by source
    for source_name, source_group in data.groupby(source_col):
        source_data = source_group.sort_values(by=time_col).reset_index(drop=True)
        
        # Find all detections (rate > 0)
        detections = source_data[pd.to_numeric(source_data[rate_col], errors='coerce') > 0].copy()
        
        for idx, row in detections.iterrows():
            detection_time = row[time_col]
            detection_rate = pd.to_numeric(row[rate_col], errors='coerce')
            if pd.isna(detection_rate):
                continue
            
            # Get uncertainties if available
            detection_uncertainties = None
            if uncertainties_col and uncertainties_col in source_data.columns:
                uncertainties_val = row.get(uncertainties_col)
                if pd.notna(uncertainties_val):
                    detection_uncertainties = pd.to_numeric(uncertainties_val, errors='coerce')
                    if pd.isna(detection_uncertainties):
                        detection_uncertainties = None
            
            # Check if start_time and end_time columns are provided
            interval_measured = False   # True when the observation itself carries a measured interval
            if start_time_col and start_time_col in data.columns and end_time_col and end_time_col in data.columns:
                # Use provided start_time and end_time columns
                start_time_val = row.get(start_time_col)
                end_time_val = row.get(end_time_col)
                if pd.notna(start_time_val) and pd.notna(end_time_val):
                    try:
                        start_time = pd.to_datetime(start_time_val)
                        end_time = pd.to_datetime(end_time_val)
                        interval_measured = True
                    except (ValueError, TypeError):
                        # Fall back to time-based logic if parsing fails
                        start_time, end_time = _calculate_temporal_boundaries(
                            source_data, detection_time, time_col, rate_col
                        )
                else:
                    # Fall back to time-based logic if values are missing
                    start_time, end_time = _calculate_temporal_boundaries(
                        source_data, detection_time, time_col, rate_col
                    )
            else:
                # Use time-based logic: find start/end from non-detects
                start_time, end_time = _calculate_temporal_boundaries(
                    source_data, detection_time, time_col, rate_col
                )
            
            # Calculate duration
            duration = (end_time - start_time).total_seconds() / 3600
            
            # Get other attributes
            original_data_id = str(row.get(id_col, f"{source_name}_{detection_time}"))
            # Generate UUID for event ID
            event_id = str(uuid.uuid4())
            # source_scale is now a direct enum value, not from a column
            source_scale = str(source_scale_value).lower()
            
            cause_value = None
            if cause_col and cause_col in source_data.columns:
                cause_value = str(row.get(cause_col, ''))
                if cause_value == 'nan' or cause_value == '':
                    cause_value = None
            
            # Get observation_type from original data to determine operational status
            # Resolved events (RE): observation_type == "operation"
            # Partially resolved events (PRE): observation_type != "operation"
            is_operational = False  # Track if this is an operational event
            observation_type_value = None
            if observation_type_col and observation_type_col in source_data.columns:
                observation_type_value = str(row.get(observation_type_col, '')).strip().lower()
                # Check if observation_type equals "operation" (case-insensitive)
                if observation_type_value == 'operation':
                    is_operational = True
                else:
                    is_operational = False
            
            # Per-observation scale and physical feature (spatial hierarchy for nested coverage)
            obs_scale = normalize_scale(row.get(observation_scale_col)) if observation_scale_col and observation_scale_col in source_data.columns else normalize_scale(source_scale_value)
            obs_feature = row.get(feature_col) if feature_col and feature_col in source_data.columns else None
            if obs_feature is None or (isinstance(obs_feature, float) and pd.isna(obs_feature)) or str(obs_feature).strip() == '':
                obs_feature = source_name
            observation = {
                'id': original_data_id,
                'rate': float(detection_rate),
                'uncertainty': None if detection_uncertainties is None else float(detection_uncertainties),
                'observation_type': observation_type_value,
                'scale': obs_scale,
                'feature': str(obs_feature),
                'start': start_time.isoformat() if interval_measured else None,
                'end': end_time.isoformat() if interval_measured else None,
                'time': pd.to_datetime(detection_time).isoformat(),
            }
            # Calculate quantity (single observation: rate x duration of the bound)
            quantity = detection_rate * duration if duration > 0 else detection_rate
            
            # Create event
            event = {
                'id': event_id,
                'original_data_id': original_data_id,  # Store original data ID separately
                'eventType': 'Emission Event',
                'is_operational': is_operational,  # Track operational status (True if observation_type == "operation")
                'quantity': {
                    'value': quantity,
                    'unit': 'kg'
                },
                'observation': {
                    'quantity': detection_rate,
                    'duration': duration
                },
                'duration': {
                    'duration': duration,
                    'durationEstimationType': 'Measured'
                },
                'cause': {
                    'rootCauseAnalysis': cause_value
                } if cause_value else None,
                'source': {
                    'sourceLocation': source_name,
                    'sourceCategory': source_scale,
                    'physicalSource': source_name
                },
                'rate': detection_rate,
                'observations': [observation],
                'uncertainties': detection_uncertainties,
                'source_scale': source_scale,
                'source_name': source_name,
                'startTime': start_time.isoformat() if start_time else None,
                'endTime': end_time.isoformat() if end_time else None,
                # detection evidence: the observation's own time (first == last for a single detection)
                'first_detection': pd.to_datetime(detection_time).isoformat(),
                'last_detection': pd.to_datetime(detection_time).isoformat(),
            }
            events.append(event)
    
    return events


def merge_events_by_allen_algebra(events: List[Dict], rate_operation: str = 'average',
                                  preferred_observation_type: Optional[str] = None) -> List[Dict]:
    """
    Merge overlapping events from the same source using Allen's interval algebra.
    Events from the same source that overlap in time are merged; events that merely meet
    (end == start) or are separated by a gap stay separate.

    Args:
        events: List of event dictionaries
        rate_operation: How the rate of a merged event is resolved ('average', 'addition',
                        'lowest_uncertainty' or 'preference')
        preferred_observation_type: Observation type taking precedence when rate_operation='preference'

    Returns:
        List of merged event dictionaries
    """
    if len(events) == 0:
        return []
    
    # Group events by source
    events_by_source = {}
    for event in events:
        # Use physicalSource or sourceLocation as the key
        source = event.get('source', {}).get('physicalSource', '')
        if not source:
            source = event.get('source', {}).get('sourceLocation', 'Unknown')
        if source not in events_by_source:
            events_by_source[source] = []
        events_by_source[source].append(event)
    
    merged_events = []
    
    # Process each source separately
    for source, source_events in events_by_source.items():
        # Sort events by start time
        source_events_sorted = sorted(source_events, 
                                     key=lambda x: pd.to_datetime(x.get('startTime', datetime.min)))
        
        if len(source_events_sorted) == 0:
            continue
        
        # Use a more efficient merging algorithm
        # Process events in order and merge overlapping ones
        result = [source_events_sorted[0]]
        
        for next_event in source_events_sorted[1:]:
            # Check if the last merged event overlaps with the next event
            last_event = result[-1]
            
            if can_merge_events(last_event, next_event):
                # Merge with the last event in result
                merged = merge_events(last_event, next_event, rate_operation,
                                      preferred_observation_type)
                result[-1] = merged
            else:
                # No overlap, add as new event
                result.append(next_event)
        
        merged_events.extend(result)
    
    return merged_events


def validate_column_mapping(data: pd.DataFrame, column_mapping: Dict[str, str]) -> Dict[str, any]:
    """
    Validate that column mapping is correct and all required fields are mapped.
    
    Args:
        data: DataFrame to validate against
        column_mapping: Dictionary mapping required fields to column names
    
    Returns:
        Dictionary with validation results:
        - 'valid': bool indicating if mapping is valid
        - 'errors': list of error messages
        - 'warnings': list of warning messages
    """
    result = {
        'valid': True,
        'errors': [],
        'warnings': []
    }
    
    mandatory_fields = ['rate', 'id', 'source']
    
    # Check mandatory fields
    for field in mandatory_fields:
        mapped_col = column_mapping.get(field)
        if not mapped_col:
            result['valid'] = False
            result['errors'].append(f"Mandatory field '{field}' is not mapped")
        elif mapped_col not in data.columns:
            result['valid'] = False
            result['errors'].append(f"Column '{mapped_col}' mapped to '{field}' does not exist in data")
    
    # Check data types and constraints
    rate_col = column_mapping.get('rate')
    if rate_col and rate_col in data.columns:
        if not pd.api.types.is_numeric_dtype(data[rate_col]):
            result['errors'].append(f"Rate column '{rate_col}' must be numeric")
            result['valid'] = False
    
    # Check uncertainties column (optional)
    uncertainties_col = column_mapping.get('uncertainties')
    if uncertainties_col and uncertainties_col in data.columns:
        if not pd.api.types.is_numeric_dtype(data[uncertainties_col]):
            result['errors'].append(f"Uncertainties column '{uncertainties_col}' must be numeric")
            result['valid'] = False
    
    id_col = column_mapping.get('id')
    if id_col and id_col in data.columns:
        if data[id_col].duplicated().any():
            result['warnings'].append(f"ID column '{id_col}' contains duplicate values")
    
    # source_scale removed from UI - defaults to 'site' if not provided
    # No validation needed as it will default to 'site' in converter
    
    return result

