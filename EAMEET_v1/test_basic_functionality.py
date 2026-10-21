"""
Basic functionality tests for EAMEET tool
Tests core functions without running the full Dash app
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        from emission_event_converter import convert_to_emission_event_model, validate_column_mapping
        from simulations import extrapolation, simulate_below_mdl, simulate_duration_uncertainty
        from utils import fitting_distribution, probability_of_detection
        from components import create_app_layout
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False


def test_emission_event_converter():
    """Test emission event converter with sample data"""
    print("\nTesting emission event converter...")
    try:
        from emission_event_converter import convert_to_emission_event_model, validate_column_mapping
        
        # Create sample data
        data = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'rate': [10.5, 0, 15.2, 0, 8.3],
            'time': pd.date_range('2024-01-01', periods=5, freq='D'),
            'source': ['Site A', 'Site A', 'Site B', 'Site B', 'Site A']
        })
        
        # Test column mapping validation
        column_mapping = {
            'id': 'id',
            'rate': 'rate',
            'time': 'time',
            'source': 'source'
        }
        
        validation = validate_column_mapping(data, column_mapping)
        if not validation['valid']:
            print(f"✗ Validation failed: {validation['errors']}")
            return False
        
        # Convert to emission events
        events_df = convert_to_emission_event_model(
            data,
            column_mapping=column_mapping,
            time_column='time',
            emission_characteristics='intermittent'
        )
        
        print(f"✓ Converted {len(data)} measurements to {len(events_df)} emission events")
        print(f"  Events columns: {list(events_df.columns)}")
        return True
        
    except Exception as e:
        print(f"✗ Emission event converter error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_distribution_fitting():
    """Test distribution fitting"""
    print("\nTesting distribution fitting...")
    try:
        from utils import fitting_distribution
        
        # Create sample data
        data = np.random.lognormal(mean=2, sigma=0.5, size=100)
        
        # Fit lognormal distribution
        params = fitting_distribution(data, 'lognormal')
        
        if params is not None and len(params) > 0:
            print(f"✓ Distribution fitting successful: {len(params)} parameters")
            return True
        else:
            print("✗ Distribution fitting returned None or empty")
            return False
            
    except Exception as e:
        print(f"✗ Distribution fitting error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_probability_of_detection():
    """Test probability of detection function"""
    print("\nTesting probability of detection...")
    try:
        from utils import probability_of_detection
        
        # Test with InsightM technology
        POD, MDL = probability_of_detection('InsightM', wind_consider=False)
        
        print(f"✓ POD: {POD}, MDL: {MDL}")
        
        # Test with wind consideration
        POD_wind, MDL_wind = probability_of_detection('InsightM', wind_speed=5.0, wind_consider=True)
        
        print(f"✓ POD (with wind): {POD_wind}, MDL (with wind): {MDL_wind}")
        return True
        
    except Exception as e:
        print(f"✗ Probability of detection error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extrapolation_simulation():
    """Test extrapolation simulation"""
    print("\nTesting extrapolation simulation...")
    try:
        from simulations import extrapolation
        
        # Create sample distributions
        prob_dist = {"UNKNOWN": 0.1}
        rate_dist = {"UNKNOWN": [10.0, 15.0, 20.0, 25.0, 30.0]}
        duration_dist = {"UNKNOWN": [1.0, 2.0, 3.0, 4.0, 5.0]}
        
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 31)
        
        # Run simulation with small iterations
        results = extrapolation(
            prob_dist=prob_dist,
            rate_dist=rate_dist,
            duration_dist=duration_dist,
            start_time=start_time,
            end_time=end_time,
            MC=5  # Small number for testing
        )
        
        if "UNKNOWN" in results and len(results["UNKNOWN"]) == 5:
            print(f"✓ Extrapolation simulation successful: {len(results['UNKNOWN'])} iterations")
            print(f"  Sample results: {results['UNKNOWN'][:3]}")
            return True
        else:
            print(f"✗ Unexpected results format: {results}")
            return False
            
    except Exception as e:
        print(f"✗ Extrapolation simulation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_continuous_emissions():
    """Test continuous emissions simulation"""
    print("\nTesting continuous emissions simulation...")
    try:
        from simulations import extrapolation
        
        # Create sample distributions
        prob_dist = {"UNKNOWN": 0.1}
        rate_dist = {"UNKNOWN": [10.0, 15.0, 20.0, 25.0, 30.0]}
        duration_dist = {"UNKNOWN": [1.0, 2.0, 3.0, 4.0, 5.0]}
        
        start_time = datetime(2024, 1, 1)
        end_time = datetime(2024, 1, 31)
        
        # Run simulation for continuous emissions
        results = extrapolation(
            prob_dist=prob_dist,
            rate_dist=rate_dist,
            duration_dist=duration_dist,
            start_time=start_time,
            end_time=end_time,
            MC=5,
            is_continuous=True,
            producing_hours=720  # 30 days * 24 hours
        )
        
        if "UNKNOWN" in results and len(results["UNKNOWN"]) == 5:
            print(f"✓ Continuous emissions simulation successful: {len(results['UNKNOWN'])} iterations")
            print(f"  Sample results: {results['UNKNOWN'][:3]}")
            return True
        else:
            print(f"✗ Unexpected results format: {results}")
            return False
            
    except Exception as e:
        print(f"✗ Continuous emissions simulation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_components():
    """Test UI components"""
    print("\nTesting UI components...")
    try:
        from components import (
            create_app_layout,
            get_data_investigation_content,
            get_simulation_selection_content,
            get_results_content
        )
        
        # Test layout creation
        layout = create_app_layout()
        print("✓ App layout created successfully")
        
        # Test section content
        data_content = get_data_investigation_content()
        sim_content = get_simulation_selection_content()
        results_content = get_results_content()
        
        print("✓ All section contents created successfully")
        return True
        
    except Exception as e:
        print(f"✗ Components error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("EAMEET Basic Functionality Tests")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("Emission Event Converter", test_emission_event_converter),
        ("Distribution Fitting", test_distribution_fitting),
        ("Probability of Detection", test_probability_of_detection),
        ("Extrapolation Simulation", test_extrapolation_simulation),
        ("Continuous Emissions", test_continuous_emissions),
        ("UI Components", test_components),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
