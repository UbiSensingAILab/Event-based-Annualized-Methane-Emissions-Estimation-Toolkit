"""
HTML/CSS Components for EAMEET Dash App
This module contains all UI layout functions and styling
"""
import pandas as pd
from dash import dcc, html
import plotly.graph_objects as go

# Distribution options (needed for dropdown)
DISTRIBUTIONS = ['lognormal', 'normal', 'uniform', 'exponential', 'weibull', 'gamma']


# Style dictionaries
def get_active_button_style():
    """Style for active navigation button"""
    return {
        'width': '100%',
        'padding': '12px',
        'marginBottom': '10px',
        'backgroundColor': '#3498db',
        'color': 'white',
        'border': 'none',
        'borderRadius': '5px',
        'cursor': 'pointer',
        'textAlign': 'left',
        'fontSize': '14px'
    }


def get_inactive_button_style():
    """Style for inactive navigation button"""
    return {
        'width': '100%',
        'padding': '12px',
        'marginBottom': '10px',
        'backgroundColor': '#95a5a6',
        'color': 'white',
        'border': 'none',
        'borderRadius': '5px',
        'cursor': 'pointer',
        'textAlign': 'left',
        'fontSize': '14px'
    }


def get_section_container_style():
    """Style for section containers"""
    return {
        'padding': '25px',
        'backgroundColor': 'white',
        'borderRadius': '8px',
        'marginBottom': '25px',
        'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
        'border': '1px solid #e0e0e0'
    }


def get_section_title_style(color='#2c3e50'):
    """Style for section titles"""
    return {
        'color': color,
        'marginBottom': '40px',
        'textAlign': 'center',
        'fontSize': '28px',
        'fontWeight': '500',
        'paddingBottom': '15px',
        'borderBottom': f'3px solid {color}'
    }


def get_h3_style():
    """Style for H3 headings"""
    return {
        'color': '#2c3e50',
        'marginBottom': '20px',
        'fontSize': '20px',
        'fontWeight': '500'
    }


def get_summary_card_style(border_color='#3498db'):
    """Style for KPI summary cards on results page"""
    return {
        'flex': '1 1 200px',
        'padding': '20px',
        'backgroundColor': 'white',
        'borderRadius': '8px',
        'borderLeft': f'4px solid {border_color}',
        'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
        'minWidth': '180px',
    }


def get_disabled_button_style():
    """Style for disabled navigation buttons"""
    base_nav_button_style = {
        'marginRight': '10px',
        'marginBottom': '0',
        'padding': '10px 20px',
        'width': 'auto',
        'textAlign': 'center',
        'display': 'inline-block'
    }
    return {
        **base_nav_button_style,
        'backgroundColor': '#bdc3c7',
        'color': '#7f8c8d',
        'border': 'none',
        'borderRadius': '5px',
        'cursor': 'not-allowed',
        'fontSize': '14px',
        'opacity': '0.6'
    }


def get_active_step_style():
    """Style for the currently active step circle"""
    return {
        'backgroundColor': '#3498db',
        'color': 'white',
        'borderColor': '#2980b9',
        'cursor': 'pointer',
    }


def get_completed_step_style():
    """Style for a completed step circle"""
    return {
        'backgroundColor': '#27ae60',
        'color': 'white',
        'borderColor': '#219a52',
        'cursor': 'pointer',
    }


def get_inactive_step_style():
    """Style for an available but not active step circle"""
    return {
        'backgroundColor': '#ffffff',
        'color': '#7f8c8d',
        'borderColor': '#bdc3c7',
        'cursor': 'pointer',
    }


def get_disabled_step_style():
    """Style for a locked/disabled step circle"""
    return {
        'backgroundColor': '#f0f0f0',
        'color': '#bdc3c7',
        'borderColor': '#e0e0e0',
        'cursor': 'not-allowed',
        'opacity': '0.5',
    }


def get_button_style(color='#3498db'):
    """Style for action buttons"""
    # Color-specific shadow colors
    shadow_colors = {
        '#3498db': 'rgba(52, 152, 219, 0.3)',
        '#27ae60': 'rgba(39, 174, 96, 0.3)',
        '#e74c3c': 'rgba(231, 76, 60, 0.3)',
        '#9b59b6': 'rgba(155, 89, 182, 0.3)'
    }
    shadow = shadow_colors.get(color, 'rgba(0, 0, 0, 0.3)')
    
    return {
        'padding': '12px 24px',
        'backgroundColor': color,
        'color': 'white',
        'border': 'none',
        'borderRadius': '6px',
        'cursor': 'pointer',
        'fontSize': '14px',
        'fontWeight': '500',
        'transition': 'all 0.3s ease',
        'boxShadow': f'0 2px 4px {shadow}'
    }


def create_modal(modal_id, children, is_open=False):
    """Create a modal/popup window"""
    return html.Div([
        # Modal backdrop (clickable to close)
        html.Div(
            id=f'{modal_id}-backdrop',
            n_clicks=0,
            style={
                'display': 'block' if is_open else 'none',
                'position': 'fixed',
                'top': 0,
                'left': 0,
                'width': '100%',
                'height': '100%',
                'backgroundColor': 'rgba(0, 0, 0, 0.5)',
                'zIndex': 1000,
                'overflow': 'auto',
                'cursor': 'pointer'
            }
        ),
        # Modal content
        html.Div(
            children,
            id=modal_id,
            style={
                'display': 'block' if is_open else 'none',
                'position': 'fixed',
                'top': '50%',
                'left': '50%',
                'transform': 'translate(-50%, -50%)',
                'backgroundColor': 'white',
                'padding': '30px',
                'borderRadius': '10px',
                'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
                'zIndex': 1001,
                'maxWidth': '800px',
                'width': '90%',
                'maxHeight': '90vh',
                'overflowY': 'auto'
            }
        )
    ])


# Layout Components
def get_data_investigation_content():
    """Content for Loading Emissions Data section (Steps 1-5)"""
    return html.Div([
        html.H2("Load Emissions Data", style=get_section_title_style('#3498db')),
        
        # Combined upload and mapping section
        html.Div([
            html.H3("1. Load Emissions Measurements Data", style=get_h3_style()),
            html.P("Upload your CSV file that contains the emission data:", 
                  style={'marginBottom': '15px', 'color': '#7f8c8d'}),
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select CSV File')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px 0',
                    'backgroundColor': '#f8f9fa'
                },
                multiple=False
            ),
            html.Div(id='upload-status', style={'marginTop': '10px'}),
            html.Div(id='open-mapping-button-container', style={'marginTop': '15px'}),
            html.Div(id='mapping-status', style={'marginTop': '15px'}),
            html.Div(id='validation-status', style={'marginTop': '15px'}),
        ], style=get_section_container_style()),
        
        # Mapping Modal
        create_mapping_modal(),
        
        # Converted emission events display
        html.Div([
            html.H3("2. Converted to Emission Events", style=get_h3_style()),
            html.P("Click download to browse the full list of emission events", style={'marginBottom': '15px', 'color': '#7f8c8d'}),
            html.Div([
                html.Button('Download as CSV', id='download-csv-button', n_clicks=0,
                          style={**get_button_style('#27ae60'), 'marginRight': '10px'}),
                html.Button('Download as JSON', id='download-json-button', n_clicks=0,
                          style=get_button_style('#3498db')),
            ], style={'marginBottom': '15px'}),
            dcc.Download(id="download-dataframe"),
            dcc.Loading(
                id="loading-conversion",
                type="default",
                children=html.Div([
                    html.Div(id='converted-events-table', style={'marginTop': '10px'}),
                    html.Div(id='conversion-status', style={'marginTop': '15px'}),
                ]),
                style={'minHeight': '200px'}
            ),
        ], style=get_section_container_style()),
        
        # Sankey chart visualization
        html.Div([
            html.H3("3. Data Flow Visualization", style=get_h3_style()),
            html.P("Sankey chart showing the relationship between loaded emissions observations and converted emission events (only first 10 events are shown)", 
                  style={'marginBottom': '15px', 'color': '#7f8c8d'}),
            dcc.Loading(
                id="loading-sankey",
                type="default",
                children=html.Div(id='sankey-chart-container', style={'marginTop': '10px'}),
                style={'minHeight': '400px'}
            ),
        ], style=get_section_container_style()),
    ])


def get_simulation_selection_content():
    """Content for Simulations section (Step 6)"""
    return html.Div([
        html.H2("Simulations", style=get_section_title_style('#9b59b6')),
        html.Div([
            html.H3("Select Emission Estimation Approach", style=get_h3_style()),
            html.Div([
                html.Label("Emission Estimation Approach:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='estimation-approach-dropdown',
                    options=[
                        {'label': 'Simulate Below Detection Limit', 'value': 'below_MDL'},
                        {'label': 'Bootstrap For Unmeasured Emissions', 'value': 'bootstrap'},
                    ],
                    value='bootstrap',
                    style={'width': '400px', 'marginBottom': '20px'}
                ),
            ]),
            
            # Component-level leak data upload section
            html.Div([
                html.H3("Component-Level Leak Data", style=get_h3_style()),
                html.Div([
                    html.Label("Upload Your Own Component-Level Leak Data:", 
                              style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                    dcc.Dropdown(
                        id='upload-leak-data-dropdown',
                        options=[
                            {'label': 'No', 'value': 'no'},
                            {'label': 'Yes', 'value': 'yes'}
                        ],
                        value='no',
                        style={'width': '400px', 'marginBottom': '20px'}
                    ),
                ], style={'marginBottom': '20px'}),
                
                # Upload component (shown when Yes is selected)
                html.Div([
                    html.P("Upload CSV file with component-level leak data:", 
                          style={'marginBottom': '10px', 'color': '#7f8c8d'}),
                    dcc.Upload(
                        id='upload-leak-data',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select CSV File')
                        ]),
                        style={
                            'width': '100%',
                            'height': '60px',
                            'lineHeight': '60px',
                            'borderWidth': '1px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'margin': '10px 0',
                            'backgroundColor': '#f8f9fa'
                        },
                        multiple=False
                    ),
                    html.Div(id='leak-data-upload-status', style={'marginTop': '10px'}),
                    
                    # Column selection dropdown (shown after file upload)
                    html.Div([
                        html.Label("Select Column for Rate (kg/hr):", 
                                  style={'fontWeight': 'bold', 'marginRight': '10px', 'marginTop': '15px', 'marginBottom': '10px'}),
                        dcc.Dropdown(
                            id='leak-data-column-selector',
                            placeholder="Select column containing leak rates...",
                            style={'width': '100%', 'marginBottom': '10px'}
                        ),
                    ], id='leak-data-column-selector-container', style={'marginTop': '10px', 'display': 'none'}),
                ], id='leak-data-upload-container', style={'marginBottom': '20px', 'display': 'none'}),
                
                # Histogram display
                html.Div([
                    dcc.Graph(id='leak-data-histogram'),
                ], id='leak-data-histogram-container', style={'marginTop': '20px', 'display': 'none'}),
            ], id='component-leak-data-container', style={'marginBottom': '30px'}),
            
            # Processing Resolution
            html.Div([
                html.Label("Select Processing Resolution:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Dropdown(
                    id='resolution-dropdown',
                    options=[
                        {'label': 'By site', 'value': 'by_site'},
                        {'label': 'By site and By source', 'value': 'by_site_source'},
                        {'label': 'By site and By equipment', 'value': 'by_site_equipment'}
                    ],
                    value='by_site',
                    style={'width': '400px', 'display': 'inline-block', 'marginRight': '20px'}
                ),
            ], style={'marginBottom': '20px'}),
            
            # Start time and end time inputs with calendar pickers
            html.Div([
                html.Label("Start Date:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.DatePickerSingle(
                    id='simulation-start-date-picker',
                    date='2025-01-01',  # Default start date
                    display_format='YYYY-MM-DD',
                    style={'marginBottom': '20px'}
                ),
            ], style={'marginBottom': '20px'}),
            
            html.Div([
                html.Label("End Date:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.DatePickerSingle(
                    id='simulation-end-date-picker',
                    date='2025-12-31',  # Default end date
                    display_format='YYYY-MM-DD',
                    style={'marginBottom': '20px'}
                ),
            ], style={'marginBottom': '20px'}),
            
            # Number of iterations (available for both approaches)
            html.Div([
                html.Label("Number of Iterations:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Slider(
                    id='monte-carlo-iterations',
                    min=1,
                    max=100,
                    step=1,
                    value=10,
                    marks={i: str(i) for i in [1, 25, 50, 75, 100]},
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
                html.Div(id='iterations-display', style={'marginTop': '5px', 'fontSize': '14px', 'color': '#7f8c8d'}),
            ], style={'marginBottom': '20px'}),
            
            
            # Measurement Technology (with "define technology" option) - Multiple selection supported
            html.Div([
                html.Label("Measurement Technology (Select one or more):", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                html.P("You can select multiple technologies to simulate a scenario where multiple detection technologies are deployed. An emission is detected if ANY technology detects it.",
                      style={'fontSize': '12px', 'color': '#7f8c8d', 'fontStyle': 'italic', 'marginBottom': '5px'}),
                dcc.Dropdown(
                    id='measurement-technology-dropdown',
                    options=[
                        {'label': 'InsightM', 'value': 'InsightM'},
                        {'label': 'Qube', 'value': 'Qube'},
                        {'label': 'SeekOps', 'value': 'SeekOps'},
                        {'label': 'Bridger Photonic', 'value': 'Bridger Photonic'},
                        {'label': 'GHGSat-Air', 'value': 'GHGSat-Air'},
                        {'label': 'Kuva Systems', 'value': 'Kuva Systems'},
                        {'label': 'Sensirion', 'value': 'Sensirion'},
                        {'label': 'Aeromon', 'value': 'Aeromon'},
                        {'label': 'Project Canary', 'value': 'Project Canary'},
                        {'label': 'Long Path', 'value': 'Long Path'},
                        {'label': 'Define Technology', 'value': 'define_technology'}
                    ],
                    value=['InsightM'],  # Default to list with single value
                    multi=True,  # Enable multiple selection
                    style={'width': '400px', 'marginBottom': '20px'}
                ),
            ], id='measurement-technology-container'),
            
            # Minimum detection limit input (shown when "Define Technology" is selected)
            html.Div([
                html.Label("Minimum Detection Limit (kg/hr):", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Input(
                    id='minimum-detection-limit-input',
                    type='number',
                    min=0,
                    step=0.01,
                    value=0.0,
                    style={'width': '400px', 'marginBottom': '20px', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                ),
            ], id='minimum-detection-limit-container', style={'marginBottom': '20px', 'display': 'none'}),
            
            # Wind consideration dropdown (only shown when "Simulate Below Detection Limit" is selected)
            html.Div([
                html.Label("Consider Wind:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='consider-wind-dropdown',
                    options=[
                        {'label': 'No', 'value': 'no'},
                        {'label': 'Yes', 'value': 'yes'}
                    ],
                    value='no',
                    style={'width': '400px', 'marginBottom': '20px'}
                ),
                
                # Wind data source selection (shown when Yes is selected)
                html.Div([
                    html.Label("Wind Data Source:", 
                              style={'fontWeight': 'bold', 'marginRight': '10px', 'marginTop': '15px', 'marginBottom': '10px'}),
                    dcc.Dropdown(
                        id='wind-data-source-dropdown',
                        options=[
                            {'label': 'Use Default', 'value': 'default'},
                            {'label': 'Upload Your Own', 'value': 'upload'}
                        ],
                        value='default',
                        style={'width': '400px', 'marginBottom': '20px'}
                    ),
                ], id='wind-data-source-container', style={'marginBottom': '20px', 'display': 'none'}),
                
                # Upload component (shown when Upload Your Own is selected)
                html.Div([
                    html.P("Upload CSV file with wind speed data:", 
                          style={'marginBottom': '10px', 'color': '#7f8c8d'}),
                    dcc.Upload(
                        id='upload-wind-data',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select CSV File')
                        ]),
                        style={
                            'width': '100%',
                            'height': '60px',
                            'lineHeight': '60px',
                            'borderWidth': '1px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'margin': '10px 0',
                            'backgroundColor': '#f8f9fa'
                        },
                        multiple=False
                    ),
                    html.Div(id='wind-data-upload-status', style={'marginTop': '10px'}),
                    
                    # Column selection dropdown (shown after file upload)
                    html.Div([
                        html.Label("Select Column for Wind Speed (m/s):", 
                                  style={'fontWeight': 'bold', 'marginRight': '10px', 'marginTop': '15px', 'marginBottom': '10px'}),
                        dcc.Dropdown(
                            id='wind-data-column-selector',
                            placeholder="Select column containing wind speed...",
                            style={'width': '100%', 'marginBottom': '10px'}
                        ),
                    ], id='wind-data-column-selector-container', style={'marginTop': '10px', 'display': 'none'}),
                ], id='wind-data-upload-container', style={'marginBottom': '20px', 'display': 'none'}),
                
                html.Div(id='wind-data-status', style={'marginTop': '10px'}),
            ], id='consider-wind-container', style={'marginBottom': '20px', 'display': 'block', 'visibility': 'hidden', 'height': '0', 'overflow': 'hidden'}),
            
            html.Div([
                html.Button('Run Simulation', id='simulate-button', n_clicks=0,
                          style=get_button_style('#9b59b6')),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '20px'}),
            dcc.Loading(
                id="loading-simulation",
                type="default",
                children=html.Div(id='simulation-status', style={'marginTop': '20px'}),
                style={'marginTop': '20px'}
            ),
        ], style=get_section_container_style()),
    ])


def get_results_content():
    """Content for Results section"""
    return html.Div([
        html.H2("Results", style=get_section_title_style('#e67e22')),

        # KPI summary cards row
        html.Div(id='results-summary-cards', style={'marginTop': '20px'}),

        # Distribution Analysis section
        html.Div([
            html.H3("Distribution Analysis", style=get_h3_style()),
            html.Div(id='results-charts-container'),
        ], style=get_section_container_style()),

        # Detailed Statistics section
        html.Div([
            html.H3("Detailed Statistics", style=get_h3_style()),
            html.Div(id='results-statistics-table'),
        ], style=get_section_container_style()),

        # Simulation Configuration section
        html.Div([
            html.H3("Simulation Configuration", style=get_h3_style()),
            html.Div(id='results-metadata-display'),
        ], style=get_section_container_style()),

        # Export Results section
        html.Div([
            html.H3("Export Results", style=get_h3_style()),
            html.Button('Download Results as CSV', id='download-results-csv-button', n_clicks=0,
                        style=get_button_style('#e67e22')),
            dcc.Download(id='download-results-csv'),
        ], style=get_section_container_style()),

        # Bottom-up inventory input section
        html.Div([
            html.H3("Compare with Bottom-Up Inventory", style=get_h3_style()),
            html.P("Enter bottom-up inventory emissions to compare with simulation results.", 
                  style={'marginBottom': '15px', 'color': '#7f8c8d'}),
            html.Div([
                html.Div([
                    html.Label("Emissions (kg):", 
                              style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                    dcc.Input(
                        id='bottomup-emissions-input',
                        type='number',
                        min=0,
                        step=0.01,
                        value=None,
                        placeholder='Enter emissions in kg',
                        style={'width': '200px', 'marginBottom': '15px', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                    ),
                ], style={'marginRight': '20px'}),
                html.Div([
                    html.Label("Lower Uncertainty (%):", 
                              style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                    dcc.Input(
                        id='bottomup-lower-uncertainty-input',
                        type='number',
                        min=0,
                        max=100,
                        step=0.1,
                        value=None,
                        placeholder='Enter lower %',
                        style={'width': '200px', 'marginBottom': '15px', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                    ),
                ], style={'marginRight': '20px'}),
                html.Div([
                    html.Label("Upper Uncertainty (%):", 
                              style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                    dcc.Input(
                        id='bottomup-upper-uncertainty-input',
                        type='number',
                        min=0,
                        max=100,
                        step=0.1,
                        value=None,
                        placeholder='Enter upper %',
                        style={'width': '200px', 'marginBottom': '15px', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                    ),
                ]),
            ], style={'display': 'flex', 'alignItems': 'flex-start', 'marginBottom': '15px', 'flexWrap': 'wrap'}),
            html.Button('Add Bottom-Up Inventory', id='add-bottomup-button', n_clicks=0,
                      style=get_button_style('#e67e22')),
            html.Div(id='bottomup-comparison-chart', style={'marginTop': '30px'}),
        ], style=get_section_container_style()),

        # Hidden div for backward compatibility with old callback references
        html.Div(id='simulation-results-display', style={'display': 'none'}),
    ])




def get_event_uncertainty_calculator_content():
    """Content for Emissions Event Browser section"""
    return html.Div([
        html.H2("Emissions Event Browser", style=get_section_title_style('#16a085')),
        
        # Histogram plots and distribution fitting section (moved from Data Investigation)
        html.Div([
            html.H3("Display Rate and Duration Distributions", style=get_h3_style()),
            html.Div([
                html.Label("Select Distribution Type:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Dropdown(
                    id='distribution-dropdown',
                    options=[{'label': dist, 'value': dist} for dist in DISTRIBUTIONS],
                    value='lognormal',
                    style={'width': '300px', 'display': 'inline-block', 'marginRight': '20px'}
                ),
                html.Button('Fit Distribution', id='fit-button', n_clicks=0,
                          style=get_button_style('#e74c3c')),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '20px'}),
            html.Div([
                dcc.Graph(id='rate-histogram'),
                dcc.Graph(id='duration-histogram'),
            ]),
        ], style=get_section_container_style()),
        
        html.Div([
            html.H3("Event Over Time by Source", style=get_h3_style()),
            html.P("Configure emission duration characteristics and view emission events plotted over time.", 
                  style={'marginBottom': '15px', 'color': '#7f8c8d'}),
            
            # Step 1: Emission Characteristics Selection
            html.Div([
                html.Label("Emission Duration Characteristics:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='emission-characteristics-dropdown',
                    options=[
                        {'label': 'Intermittent', 'value': 'intermittent'},
                        {'label': 'Continuous', 'value': 'continuous'}
                    ],
                    value=None,
                    placeholder='Select emission type...',
                    style={'width': '400px', 'marginBottom': '20px'}
                ),
            ], style={'marginBottom': '20px'}),
            
            # Step 2a: Continuous - Producing Hours Input
            html.Div([
                html.Label("Producing Hours:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                html.Div([
                    dcc.Input(
                        id='producing-hours-input',
                        type='number',
                        min=0,
                        max=8760,
                        step=1,
                        value=None,
                        placeholder='Enter producing hours (0-8760)',
                        style={'width': '300px', 'marginRight': '10px', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                    ),
                    html.Button('Confirm', id='confirm-producing-hours-button', n_clicks=0,
                              style=get_button_style('#16a085')),
                ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '10px'}),
                html.P("Range: 0 to 8760 hours (full year)", 
                      style={'fontSize': '12px', 'color': '#7f8c8d', 'marginTop': '-5px'}),
                html.Div(id='producing-hours-status', style={'marginTop': '10px'}),
            ], id='continuous-emissions-container', style={'marginTop': '20px', 'display': 'none'}),
            
            # Step 2b: Intermittent - Duration Uncertainty Option
            html.Div([
                html.Label("Consider Duration Estimation Uncertainty:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='consider-duration-uncertainty-dropdown',
                    options=[
                        {'label': 'No', 'value': 'no'},
                        {'label': 'Yes', 'value': 'yes'}
                    ],
                    value='no',
                    style={'width': '400px', 'marginBottom': '20px'}
                ),
            ], id='intermittent-uncertainty-container', style={'marginTop': '20px', 'display': 'none'}),
            
            # Step 3: Source Selection (shown for intermittent emissions)
            html.Div([
                html.Label("Select Source:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='uncertainty-source-dropdown',
                    options=[],
                    value=None,
                    placeholder='Select a source...',
                    style={'width': '400px', 'marginBottom': '20px'}
                ),
            ], id='source-selection-container', style={'marginTop': '20px', 'display': 'none'}),
            
            # Step 4: Duration Uncertainty Method Selection (shown when Yes is selected)
            html.Div([
                html.Label("Duration Uncertainty Method:", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Dropdown(
                    id='duration-uncertainty-method-dropdown',
                    options=[
                        {'label': 'Use default 0.0006', 'value': 'default'},
                        {'label': 'Input leak production rate manually', 'value': 'manual'},
                        {'label': 'Calculate from loaded data', 'value': 'calculate'}
                    ],
                    value='default',
                    style={'width': '400px', 'marginBottom': '20px'}
                ),
            ], id='duration-uncertainty-method-container', style={'marginTop': '20px', 'display': 'none'}),
            
            # Manual input field (shown when manual is selected)
            html.Div([
                html.Label("Leak Production Rate (kg/hr):", 
                          style={'fontWeight': 'bold', 'marginRight': '10px', 'marginBottom': '10px'}),
                dcc.Input(
                    id='manual-leak-production-rate-input',
                    type='number',
                    min=0,
                    step=0.0001,
                    value=0.0006,
                    style={'width': '400px', 'marginBottom': '20px', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                ),
            ], id='manual-leak-production-rate-container', style={'marginTop': '20px', 'display': 'none'}),
            
            # Estimate Duration button (shown when duration uncertainty is considered)
            html.Div([
                html.Button('Estimate Duration', id='estimate-duration-button', n_clicks=0,
                          style=get_button_style('#16a085')),
                dcc.Loading(
                    id="loading-duration-estimation",
                    type="default",
                    children=html.Div(id='duration-estimation-status', style={'marginTop': '10px'}),
                    style={'marginTop': '10px'}
                ),
            ], id='estimate-duration-container', style={'marginTop': '20px', 'display': 'none'}),
            
            html.Div(id='uncertainty-chart-container', style={'marginTop': '20px'}),
            
            # Table to display output events when duration uncertainty is considered
            html.Div(id='uncertainty-events-table-container', style={'marginTop': '20px'}),
        ], style=get_section_container_style()),
    ])


def create_user_guide():
    """Create the collapsible user guide section"""
    return html.Div([
        # Clickable toggle header
        html.Div([
            html.Span('\u25B6', id='user-guide-chevron', style={
                'display': 'inline-block',
                'marginRight': '8px',
                'fontSize': '12px',
                'transition': 'transform 0.2s ease',
                'color': '#3498db',
            }),
            html.Span("User Guide", style={
                'fontSize': '15px',
                'fontWeight': '600',
                'color': '#2c3e50',
            }),
        ], id='user-guide-toggle', n_clicks=0, role='button', style={
            'cursor': 'pointer',
            'padding': '8px 12px',
            'userSelect': 'none',
        }),
        # Collapsible content (hidden by default)
        html.Div([
            html.Ol([
                html.Li([
                    html.Span("Load emissions measurements and map them to the corresponding fields to create emission events.",
                            style={'color': '#34495e'})
                ], style={'marginBottom': '8px', 'lineHeight': '1.5'}),
                html.Li([
                    html.Span("Review the emission events and decide whether emissions should be treated as intermittent or assumed to be continuous. Select whether you would like to simulate duration uncertainty.",
                            style={'color': '#34495e'})
                ], style={'marginBottom': '8px', 'lineHeight': '1.5'}),
                html.Li([
                    html.Span("Configure the simulation settings by selecting the appropriate model and parameter values.",
                            style={'color': '#34495e'})
                ], style={'marginBottom': '8px', 'lineHeight': '1.5'}),
                html.Li([
                    html.Span("Run the simulation and wait for the process to complete.",
                            style={'color': '#34495e'})
                ], style={'marginBottom': '8px', 'lineHeight': '1.5'}),
                html.Li([
                    html.Span("Review and explore the results once the simulation finishes.",
                            style={'color': '#34495e'})
                ], style={'marginBottom': '0', 'lineHeight': '1.5'}),
            ], style={'paddingLeft': '25px', 'margin': '8px 0 0 0', 'fontSize': '13px'}),
        ], id='user-guide-content', style={'display': 'none'}),
    ], style={
        'backgroundColor': '#f8f9fa',
        'borderLeft': '3px solid #3498db',
        'borderRadius': '4px',
        'margin': '0 30px',
    })


def _make_step_item(step_number, label, element_id, style_dict):
    """Create a single step item (circle + label) for the step flow.
    The element_id and n_clicks go on the circle div so the callback
    can set its style directly. The wrapper div handles visual layout."""
    is_completed = style_dict.get('backgroundColor') == '#27ae60'
    circle_content = '\u2713' if is_completed else str(step_number)

    return html.Div([
        html.Div(circle_content, id=element_id, n_clicks=0,
                 className='step-circle', role='button', tabIndex='0',
                 style=style_dict),
        html.Div(label, className='step-label'),
    ], className='step-item')


def create_step_flow():
    """Create the horizontal step-flow stepper component"""
    steps = [
        (1, 'Load Data', 'section-data-investigation-button', get_active_step_style()),
        (2, 'Event Browser', 'section-uncertainty-calculator-button', get_disabled_step_style()),
        (3, 'Simulations', 'section-simulation-button', get_disabled_step_style()),
        (4, 'Results', 'section-results-button', get_disabled_step_style()),
    ]

    children = []
    for i, (num, label, eid, style) in enumerate(steps):
        if i > 0:
            # Add connector line between steps
            children.append(html.Div(className='step-connector'))
        children.append(_make_step_item(num, label, eid, style))

    return html.Div(children, className='step-flow-row')


def create_header_section():
    """Create the persistent header with title, user guide, and step flow"""
    return html.Div([
        # Title row
        html.Div([
            html.H2("EAMEET V1.0", style={
                'color': '#2c3e50',
                'margin': '0',
                'fontSize': '22px',
                'fontWeight': '600',
            }),
        ], style={
            'padding': '10px 30px 4px',
        }),
        # Collapsible user guide
        create_user_guide(),
        # Step flow stepper
        create_step_flow(),
    ], id='persistent-header')


def create_main_content_area():
    """Create the scrollable main content area below the fixed header"""
    return html.Div([
        html.Div(id='section-content', children=get_data_investigation_content()),
    ], style={
        'padding': '40px 60px',
        'maxWidth': '1200px',
        'margin': '0 auto',
        'width': '100%',
        'flex': '1'
    })


def create_footer():
    """Create the footer with disclaimer"""
    return html.Footer([
        html.Div([
            html.H4("Disclaimer", style={
                'color': '#2c3e50',
                'marginBottom': '15px',
                'fontSize': '18px',
                'fontWeight': '600'
            }),
            html.P([
                "This software is provided exclusively for academic research and educational purposes. ",
                "It is not licensed for commercial use, operational deployment, or regulatory compliance ",
                "without explicit written agreement."
            ], style={'marginBottom': '15px', 'lineHeight': '1.6'}),
            html.P([
                "The accuracy and reliability of results produced by this tool depend on appropriate ",
                "parameter selection and configuration. For guidance on parameter selection and to ensure ",
                "accurate and intended use of the tool, please contact the author."
            ], style={'marginBottom': '15px', 'lineHeight': '1.6'}),
            html.P([
                "Unauthorized commercial use, distribution, or modification is prohibited. ",
                "For commercial licensing, collaboration, or technical inquiries, please contact the author at mozhou.gao@ucalgary.ca."
            ], style={'marginBottom': '0', 'lineHeight': '1.6'})
        ], style={
            'maxWidth': '1200px',
            'margin': '0 auto',
            'padding': '30px 60px',
            'color': '#34495e',
            'fontSize': '13px',
            'lineHeight': '1.6'
        })
    ], style={
        'backgroundColor': '#ecf0f1',
        'borderTop': '2px solid #bdc3c7',
        'marginTop': '40px',
        'width': '100%'
    })


def create_app_layout():
    """Create the complete app layout"""
    return html.Div([
        # Hidden stores for data persistence in memory
        dcc.Store(id='stored-data', storage_type='memory'),  # Stores uploaded raw data
        dcc.Store(id='stored-events', storage_type='memory'),  # Stores converted emission events data
        dcc.Store(id='column-mapping', storage_type='memory'),  # Stores column mapping configuration
        dcc.Store(id='stored-sankey-chart', storage_type='memory'),  # Stores Sankey chart figure data
        dcc.Store(id='stored-duration-simulation-results', storage_type='memory'),  # Stores duration uncertainty simulation results
        dcc.Store(id='stored-simulation-results', storage_type='memory'),  # Stores simulation results for results page
        dcc.Store(id='stored-bottomup-inventory', storage_type='memory'),  # Stores bottom-up inventory data
        dcc.Store(id='workflow-status', storage_type='memory', data={'step1_completed': False, 'step2_completed': False}),  # Tracks workflow completion status
        dcc.Store(id='stored-emission-characteristics', storage_type='memory'),  # Stores emission characteristics selection (intermittent/continuous)
        dcc.Store(id='stored-producing-hours', storage_type='memory'),  # Stores producing hours range for continuous emissions
        dcc.Store(id='stored-leak-data', storage_type='memory'),  # Stores component-level leak data
        dcc.Store(id='stored-leak-csv', storage_type='memory'),  # Stores uploaded CSV DataFrame for column selection
        dcc.Store(id='stored-wind-data', storage_type='memory'),  # Stores wind speed data
        dcc.Store(id='stored-wind-csv', storage_type='memory'),  # Stores uploaded CSV DataFrame for wind data column selection
        dcc.Store(id='stored-fitted-distributions', storage_type='memory'),  # Stores fitted distributions for rate and duration
        
        # Hidden elements for callback validation (buttons, graphs, and inputs that appear in dynamically loaded sections)
        # These ensure Dash can validate callbacks at startup even if elements aren't in initial visible layout
        html.Div([
            # From Emissions Event Browser section
            html.Button('Fit Distribution', id='fit-button', n_clicks=0, style={'display': 'none'}),
            dcc.Graph(id='rate-histogram', style={'display': 'none'}),
            dcc.Graph(id='duration-histogram', style={'display': 'none'}),
            dcc.Dropdown(id='distribution-dropdown', style={'display': 'none'}),
            dcc.Dropdown(id='emission-characteristics-dropdown', style={'display': 'none'}),
            dcc.Input(id='producing-hours-input', type='number', style={'display': 'none'}),
            html.Button('Confirm', id='confirm-producing-hours-button', n_clicks=0, style={'display': 'none'}),
            html.Div(id='producing-hours-status', style={'display': 'none'}),
            dcc.Dropdown(id='consider-duration-uncertainty-dropdown', style={'display': 'none'}),
            dcc.Dropdown(id='uncertainty-source-dropdown', style={'display': 'none'}),
            dcc.Dropdown(id='duration-uncertainty-method-dropdown', style={'display': 'none'}),
            dcc.Input(id='manual-leak-production-rate-input', type='number', style={'display': 'none'}),
            html.Button('Estimate Duration', id='estimate-duration-button', n_clicks=0, style={'display': 'none'}),
            html.Div(id='duration-estimation-status', style={'display': 'none'}),
            html.Div(id='uncertainty-chart-container', style={'display': 'none'}),
            html.Div(id='uncertainty-events-table-container', style={'display': 'none'}),
            # From Simulations section
            html.Button('Run Simulation', id='simulate-button', n_clicks=0, style={'display': 'none'}),
            dcc.Graph(id='leak-data-histogram', style={'display': 'none'}),
            html.Div(id='wind-data-status', style={'display': 'none'}),
            html.Div(id='simulation-status', style={'display': 'none'}),
            # Results section elements are NOT duplicated here.
            # They exist only inside get_results_content() to avoid duplicate-ID issues.
        ], style={'display': 'none'}),
        
        # Persistent header (fixed at top: title + user guide + step flow)
        create_header_section(),

        # Scrollable content area below the fixed header
        html.Div([
            create_main_content_area(),
            create_footer(),
        ], id='scrollable-content'),
    ], style={'minHeight': '100vh', 'backgroundColor': '#f5f6fa'})


def create_mapping_modal():
    """Create the column mapping modal popup"""
    # Required fields in order: ID, Rate, Time/Timestamp, Source
    # (Source Scale will be handled separately as enum)
    mandatory_fields = [
        {'id': 'id', 'label': 'ID (Unique Identifier)', 'required': True, 'description': 'Unique ID for each emission measurement'},
        {'id': 'rate', 'label': 'Rate (Emission Quantity)', 'required': True, 'description': 'Quantified Emissions in kg/hr'},
        {'id': 'time', 'label': 'Detection/Measurement time', 'required': True, 'description': 'Time that emissions were detected or measured'},
        {'id': 'source', 'label': 'Source Feature', 'required': True, 'description': 'Feature of detected or measured source'}
    ]
    
    # Optional fields: Cause, Start Time, End Time, Uncertainties, and Observation Type
    optional_fields = [
        {'id': 'cause', 'label': 'Machanism', 'required': False, 'description': 'Root cause or machanism of the emission if known'},
        {'id': 'start_time', 'label': 'Start Time (Temporal Bound)', 'required': False, 'description': 'Start time of the emission if known'},
        {'id': 'end_time', 'label': 'End Time (Temporal Bound)', 'required': False, 'description': 'End time of the emission known'},
        {'id': 'uncertainties', 'label': 'Uncertainties', 'required': False, 'description': 'Uncertainty values for emission measurements'},
        {'id': 'observation_type', 'label': 'Observation Procedure', 'required': False, 'description': 'Procedure that has been used to observe the event (e.g., "operation" for operational events)'}
    ]
    
    mapping_rows = []
    
    # Mandatory fields (in order: ID, Rate, Time/Timestamp, Source)
    for field in mandatory_fields:
        mapping_rows.append(
            html.Div([
                html.Label([
                    field['label'],
                    html.Span(' *', style={'color': 'red'}),
                    html.Span(f" ({field['description']})", 
                             style={'fontSize': '12px', 'color': '#7f8c8d', 'fontWeight': 'normal', 'marginLeft': '5px'})
                ], style={'fontWeight': 'bold', 'width': '250px', 'display': 'inline-block'}),
                dcc.Dropdown(
                    id=f'map-{field["id"]}',
                    options=[],
                    value='',
                    style={'width': '350px', 'display': 'inline-block', 'marginLeft': '20px'}
                )
            ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'center'})
        )
    
    # Optional fields: Cause, Start Time, and End Time
    for field in optional_fields:
        mapping_rows.append(
            html.Div([
                html.Label([
                    field['label'],
                    html.Span(f" ({field['description']})", 
                             style={'fontSize': '12px', 'color': '#7f8c8d', 'fontWeight': 'normal', 'marginLeft': '5px'})
                ], style={'fontWeight': 'bold', 'width': '250px', 'display': 'inline-block'}),
                dcc.Dropdown(
                    id=f'map-{field["id"]}',
                    options=[],
                    value='',
                    style={'width': '350px', 'display': 'inline-block', 'marginLeft': '20px'}
                )
            ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'center'})
        )
    
    # Event-merging option: how the event rate is resolved when several observations are merged
    mapping_rows.append(
        html.Div([
            html.Label([
                'Rate Operation',
                html.Span(" (How the event rate is resolved when observations are merged into one event)",
                          style={'fontSize': '12px', 'color': '#7f8c8d', 'fontWeight': 'normal', 'marginLeft': '5px'})
            ], style={'fontWeight': 'bold', 'width': '250px', 'display': 'inline-block'}),
            dcc.Dropdown(
                id='map-rate-operation',
                options=[
                    {'label': 'Average (multiple estimates of the same source)', 'value': 'average'},
                    {'label': 'Addition (observations of individual equipment/components)', 'value': 'addition'},
                    {'label': 'Select lowest uncertainty', 'value': 'lowest_uncertainty'},
                    {'label': 'Preference (use a specified observation procedure)', 'value': 'preference'},
                ],
                value='average',
                clearable=False,
                style={'width': '350px', 'display': 'inline-block', 'marginLeft': '20px'}
            )
        ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'center',
                  'borderTop': '1px solid #e0e0e0', 'paddingTop': '20px'})
    )
    # Shown only when the 'Preference' operation is selected; options come from the mapped
    # Observation Procedure column.
    mapping_rows.append(
        html.Div([
            html.Label([
                'Preferred Observation Procedure',
                html.Span(" (Observations with this value take precedence)",
                          style={'fontSize': '12px', 'color': '#7f8c8d', 'fontWeight': 'normal', 'marginLeft': '5px'})
            ], style={'fontWeight': 'bold', 'width': '250px', 'display': 'inline-block'}),
            dcc.Dropdown(
                id='map-preferred-type',
                options=[],
                value='',
                style={'width': '350px', 'display': 'inline-block', 'marginLeft': '20px'}
            )
        ], id='preferred-type-row',
           style={'marginBottom': '20px', 'display': 'none', 'alignItems': 'center'})
    )

    modal_content = html.Div([
        # Modal header
        html.Div([
            html.H3("Map Columns to Required Format",
                   style={'margin': '0 0 20px 0', 'color': '#2c3e50', 'fontSize': '24px'}),
            html.Button('×', id='close-mapping-modal', n_clicks=0,
                       style={
                           'position': 'absolute',
                           'top': '10px',
                           'right': '10px',
                           'background': 'none',
                           'border': 'none',
                           'fontSize': '32px',
                           'cursor': 'pointer',
                           'color': '#7f8c8d',
                           'lineHeight': '1',
                           'padding': '0',
                           'width': '30px',
                           'height': '30px'
                       })
        ], style={'position': 'relative', 'marginBottom': '20px'}),
        
        # Modal body with loading indicator
        dcc.Loading(
            id="loading-mapping",
            type="default",
            children=html.Div([
                html.P("Select which columns from your data correspond to each required field:", 
                      style={'marginBottom': '20px', 'color': '#7f8c8d'}),
                html.Div(mapping_rows, id='mapping-fields-container'),
                html.Div(id='modal-mapping-status', style={'marginTop': '15px', 'marginBottom': '15px'}),
            ]),
            style={'minHeight': '200px'}
        ),
        
        # Modal footer
        html.Div([
            html.Button('Cancel', id='cancel-mapping-button', n_clicks=0,
                       style={
                           **get_button_style('#95a5a6'),
                           'marginRight': '10px'
                       }),
            html.Button('Process Data', id='save-mapping-button', n_clicks=0,
                       style=get_button_style('#27ae60'))
        ], style={'marginTop': '25px', 'textAlign': 'right', 'borderTop': '1px solid #e0e0e0', 'paddingTop': '15px'})
    ], style={'position': 'relative'})
    
    return create_modal('mapping-modal', modal_content, is_open=False)


def create_emission_events_table(df):
    """Create table display for converted emission events"""
    if df is None or len(df) == 0:
        return html.Div([
            html.P("No emission events to display.", 
                  style={'color': '#7f8c8d', 'fontStyle': 'italic'})
        ])
    
    # Limit to first 10 events if there are more than 10
    total_events = len(df)
    display_df = df.head(10) if total_events > 10 else df
    num_displayed = len(display_df)
    
    # Map column names to display names with units
    column_display_names = {
        'duration': 'duration (hr)',
        'quantity': 'quantity (kg)',
        'sourceLocation': 'source',
    }
    
    # Create display column names
    display_columns = [column_display_names.get(col, col) for col in display_df.columns]
    
    # Create a scrollable table
    display_text = f"Displaying {num_displayed} of {total_events} converted emission events" if total_events > 10 else f"Displaying {num_displayed} converted emission events"
    table = html.Div([
        html.P(display_text,
               style={'fontWeight': 'bold', 'marginBottom': '10px'}),
        html.Div([
            html.Table([
                html.Thead([
                    html.Tr([html.Th(display_col, style={'padding': '8px', 'border': '1px solid #ddd', 
                                                'backgroundColor': '#f2f2f2', 'textAlign': 'left'}) 
                            for display_col in display_columns])
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td(str(display_df.iloc[i][col])[:100] if pd.notna(display_df.iloc[i][col]) else '', 
                               style={'padding': '8px', 'border': '1px solid #ddd', 'fontSize': '12px'})
                        for col in display_df.columns
                    ])
                    for i in range(num_displayed)
                ])
            ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '12px'})
        ], style={'maxHeight': '500px', 'overflowY': 'auto', 'border': '1px solid #ddd'})
    ])
    
    return table


def create_sankey_chart(original_data: pd.DataFrame, events_df: pd.DataFrame, 
                        column_mapping: dict) -> go.Figure:
    """
    Create a Sankey chart showing the relationship: Data IDs → Merged Events → Source Names.
    Example: Data IDs (126, 124, 127, 130, 131) → Event-1 → Site A
    
    Args:
        original_data: DataFrame with original loaded data
        events_df: DataFrame with converted emission events
        column_mapping: Dictionary mapping field names to column names
    
    Returns:
        Plotly Figure object with Sankey chart
    """
    if original_data is None or len(original_data) == 0 or events_df is None or len(events_df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for Sankey chart",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="#7f8c8d")
        )
        fig.update_layout(title=None)
        return fig
    
    # Get column names from mapping
    source_col = column_mapping.get('source', 'source')
    id_col = column_mapping.get('id', 'id')
    rate_col = column_mapping.get('rate', 'rate')
    
    # Prepare data
    original_df = original_data.copy()
    # Limit to first 10 events if there are more than 10
    events_data = events_df.head(10).copy() if len(events_df) > 10 else events_df.copy()
    
    # Create mapping of data IDs to their rates from original data
    data_id_to_rate = {}
    if id_col in original_df.columns and rate_col in original_df.columns:
        for idx, row in original_df.iterrows():
            data_id = str(row.get(id_col, ''))
            rate = row.get(rate_col)
            if pd.notna(rate):
                data_id_to_rate[data_id] = rate
    
    # Build mapping: event_index -> list of data IDs
    # Now event IDs are UUIDs, so we use merged_from column which contains original data IDs
    event_to_data_ids = {}
    all_data_ids = set()
    
    for event_idx, event_row in events_data.iterrows():
        event_label = f"Event-{events_data.index.get_loc(event_idx)+1:02d}"
        data_ids = []
        
        # Use merged_from column if available (contains original data IDs)
        if 'merged_from' in events_data.columns:
            merged_from = event_row.get('merged_from')
            if pd.notna(merged_from) and merged_from:
                # Parse merged_from (comma-separated string of original data IDs)
                merged_from_str = str(merged_from)
                # Split by comma and strip whitespace
                data_ids = [oid.strip() for oid in merged_from_str.split(',') if oid.strip()]
        
        # If no merged_from, try to get from original_data_id (for single events)
        # Note: This field is not in the DataFrame, but we could add it if needed
        # For now, merged_from should handle both merged and single events
        
        if data_ids:
            event_to_data_ids[event_label] = data_ids
            all_data_ids.update(data_ids)
    
    # Create node labels
    # Left nodes: Individual data IDs (from parsed event IDs)
    left_nodes = sorted(list(all_data_ids), key=lambda x: int(x) if x.isdigit() else 0)[:200]  # Limit to 200 for performance
    
    # Middle nodes: Converted Emission Events
    event_nodes = [f"Event-{i+1:02d}" for i in range(len(events_data))]
    
    # Create hover text for nodes
    # Left nodes: show ID and rate
    left_hover_texts = []
    for data_id in left_nodes:
        rate = data_id_to_rate.get(data_id, None)
        if rate is not None and pd.notna(rate):
            # Format rate with 2 decimal places
            rate_str = f"{float(rate):.2f} kg/hr"
        else:
            rate_str = 'N/A'
        hover_text = f"ID: {data_id}<br>Rate: {rate_str}"
        left_hover_texts.append(hover_text)
    
    # Middle nodes: show event ID (UUID) and rate
    event_hover_texts = []
    for i in range(len(events_data)):
        event_row = events_data.iloc[i]
        event_id = event_row.get('id', 'N/A')
        event_rate = event_row.get('rate', None)
        if event_rate is not None and pd.notna(event_rate):
            # Format rate with 2 decimal places
            rate_str = f"{float(event_rate):.2f} kg/hr"
        else:
            rate_str = 'N/A'
        hover_text = f"Event ID: {event_id}<br>Rate: {rate_str}"
        event_hover_texts.append(hover_text)
    
    # Right nodes: Source names (unique source names from events)
    # Check for sourceLocation first (from converted events), then source column
    if 'sourceLocation' in events_data.columns:
        source_groups = events_data.groupby('sourceLocation').size()
        right_nodes = [f"{src}" for src in source_groups.index]
    elif 'source' in events_data.columns:
        source_groups = events_data.groupby('source').size()
        right_nodes = [f"{src}" for src in source_groups.index]
    elif source_col in original_df.columns:
        source_groups = original_df.groupby(source_col).size()
        right_nodes = [f"{src}" for src in source_groups.index[:50]]  # Limit to 50 for readability
    else:
        right_nodes = ["Unknown Source"]
    
    # Create node list with indices
    all_nodes = left_nodes + event_nodes + right_nodes
    node_indices = {node: idx for idx, node in enumerate(all_nodes)}
    
    # Calculate positions
    num_left = len(left_nodes)
    num_middle = len(event_nodes)
    num_right = len(right_nodes)
    
    # Create links
    links = []
    
    # Link 1: Data IDs → Events
    # Map data IDs to events based on parsed event IDs
    for event_label, data_ids in event_to_data_ids.items():
        if event_label not in node_indices:
            continue
        
        event_node_idx = node_indices[event_label]
        
        # Get event rate for flow value
        event_idx_num = int(event_label.split('-')[1]) - 1
        if event_idx_num < len(events_data):
            event_row = events_data.iloc[event_idx_num]
            flow_value = event_row.get('rate', 1) if 'rate' in event_row else 1
        else:
            flow_value = 1
        
        # Link each data ID to this event
        for data_id in data_ids:
            if data_id in node_indices:
                data_id_idx = node_indices[data_id]
                links.append({
                    'source': data_id_idx,
                    'target': event_node_idx,
                    'value': flow_value / len(data_ids) if len(data_ids) > 0 else flow_value  # Distribute flow evenly
                })
    
    # Link 2: Events → Source Names
    # Map events to their corresponding source names
    # Check for sourceLocation first (from converted events), then source column
    source_column_name = None
    if 'sourceLocation' in events_data.columns:
        source_column_name = 'sourceLocation'
    elif 'source' in events_data.columns:
        source_column_name = 'source'
    
    if source_column_name:
        for event_idx, event_row in events_data.iterrows():
            event_label = f"Event-{events_data.index.get_loc(event_idx)+1:02d}"
            if event_label not in node_indices:
                continue
            
            event_node_idx = node_indices[event_label]
            source_name = str(event_row.get(source_column_name, 'Unknown'))
            
            if source_name in node_indices:
                source_node_idx = node_indices[source_name]
                flow_value = event_row.get('rate', 1) if 'rate' in event_row else 1
                
                links.append({
                    'source': event_node_idx,
                    'target': source_node_idx,
                    'value': flow_value
                })
    
    # Create Sankey diagram
    if len(links) == 0:
        # Fallback: create simple links if mapping fails
        for i in range(min(10, len(left_nodes), len(event_nodes))):
            if i < len(left_nodes) and i < len(event_nodes):
                data_idx = node_indices[left_nodes[i]]
                event_idx = node_indices[event_nodes[i]]
                links.append({
                    'source': data_idx,
                    'target': event_idx,
                    'value': 1
                })
        
        for i in range(min(10, len(event_nodes), len(right_nodes))):
            if i < len(event_nodes):
                event_idx = node_indices[event_nodes[i]]
                if i < len(right_nodes):
                    right_idx = node_indices[right_nodes[i]]
                    links.append({
                        'source': event_idx,
                        'target': right_idx,
                        'value': 1
                    })
    
    # Extract link data
    sources = [link['source'] for link in links]
    targets = [link['target'] for link in links]
    values = [link['value'] for link in links]
    
    # Right nodes hover texts: show source name
    right_hover_texts = []
    for source_name in right_nodes:
        hover_text = f"Source: {source_name}"
        right_hover_texts.append(hover_text)
    
    # Create hover texts for all nodes (left + middle + right)
    all_hover_texts = left_hover_texts + event_hover_texts + right_hover_texts
    
    # Create figure
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=all_nodes,
            color=["#3498db"] * num_left + ["#9b59b6"] * num_middle + ["#e67e22"] * num_right,
            customdata=all_hover_texts,
            hovertemplate='%{label}<br>%{customdata}<extra></extra>'
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color="rgba(128, 128, 128, 0.4)"
        )
    )])
    
    fig.update_layout(
        title=None,
        font=dict(size=12),
        height=600,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    return fig

