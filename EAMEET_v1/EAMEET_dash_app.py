import pandas as pd
import numpy as np
from utils import fitting_distribution
import dash
from dash import html, dcc, Input, Output, State, callback_context
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import base64
import io
from datetime import datetime

try:
    import netCDF4 as nc

    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False

# Import emission event converter
from emission_event_converter import convert_to_emission_event_model

# Import simulation functions
from simulations import extrapolation, simulate_below_mdl, simulate_duration_uncertainty

# Import UI components
from components import (
    create_app_layout,
    get_data_investigation_content,
    get_simulation_selection_content,
    get_results_content,
    get_event_uncertainty_calculator_content,
    create_emission_events_table,
    create_sankey_chart,
    get_active_step_style,
    get_completed_step_style,
    get_inactive_step_style,
    get_disabled_step_style,
    get_button_style,
    get_summary_card_style,
    get_section_container_style,
)


# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "EAMEET V1.0"


# Backend functions
def check_data(data, column_mapping=None):
    """
    Check data quality and validity, validate mandatory fields.
    Returns a dictionary with check results and validation status.

    Args:
        data: DataFrame with uploaded data
        column_mapping: Dictionary mapping required fields to actual column names
    """
    checks = {
        "total_rows": len(data),
        "missing_values": data.isnull().sum().to_dict(),
        "columns": list(data.columns),
        "data_types": data.dtypes.astype(str).to_dict(),
        "status": "OK" if len(data) > 0 else "ERROR",
        "mapping_required": False,
        "mapping_valid": False,
        "validation_errors": [],
    }

    # If mapping is provided, validate mandatory fields
    if column_mapping:
        # Check column-based fields (id, rate, time, source) - in order
        column_fields = ["id", "rate", "time", "source"]
        missing_fields = []

        for field in column_fields:
            mapped_col = column_mapping.get(field)
            if not mapped_col or mapped_col not in data.columns:
                missing_fields.append(field)
            elif data[mapped_col].isnull().all():
                checks["validation_errors"].append(
                    f"Column '{mapped_col}' mapped to '{field}' contains only missing values"
                )

        # source_scale removed - defaults to 'site' in converter

        if missing_fields:
            checks["validation_errors"].append(
                f"Missing mandatory field mappings: {', '.join(missing_fields)}"
            )
            checks["mapping_valid"] = False
        else:
            checks["mapping_valid"] = True

            # Additional validations
            rate_col = column_mapping.get("rate")
            if rate_col and rate_col in data.columns:
                if not pd.api.types.is_numeric_dtype(data[rate_col]):
                    checks["validation_errors"].append(
                        f"Rate column '{rate_col}' must be numeric"
                    )
                    checks["mapping_valid"] = False

            id_col = column_mapping.get("id")
            if id_col and id_col in data.columns:
                if data[id_col].duplicated().any():
                    checks["validation_errors"].append(
                        f"ID column '{id_col}' contains duplicate values"
                    )
                    checks["mapping_valid"] = False
    else:
        # Check if data already has required columns (auto-detection)
        has_rate = "rate" in data.columns or any(
            "rate" in str(col).lower() for col in data.columns
        )
        has_id = "id" in data.columns or any(
            "id" in str(col).lower() for col in data.columns
        )
        has_source = "source" in data.columns or any(
            "source" in str(col).lower() for col in data.columns
        )

        if not (has_rate and has_id and has_source):
            checks["mapping_required"] = True

    return checks


def fit_distribution(data, distribution_type="lognormal"):
    """
    Fit a distribution to the data using the selected distribution type.
    """
    if len(data) == 0:
        return None, None

    try:
        params = fitting_distribution(data, distribution_type)
        return params, distribution_type
    except Exception as e:
        return None, str(e)


# App layout - imported from components module
app.layout = create_app_layout()


def parse_contents(contents, filename):
    """Parse uploaded CSV file"""
    try:
        content_type, content_string = contents.split(",", 1)
    except (ValueError, AttributeError):
        return None, "Error: Invalid file upload format"
    try:
        decoded = base64.b64decode(content_string)
    except Exception:
        return None, "Error: Could not decode file contents"
    try:
        if "csv" in filename:
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        else:
            return None, "Please upload a CSV file"
        return df, None
    except Exception as e:
        return None, f"Error parsing file: {str(e)}"


@app.callback(
    [
        Output("section-content", "children"),
        Output("section-data-investigation-button", "style"),
        Output("section-uncertainty-calculator-button", "style"),
        Output("section-simulation-button", "style"),
        Output("section-results-button", "style"),
    ],
    [
        Input("section-data-investigation-button", "n_clicks"),
        Input("section-uncertainty-calculator-button", "n_clicks"),
        Input("section-simulation-button", "n_clicks"),
        Input("section-results-button", "n_clicks"),
    ],
    [State("workflow-status", "data")],
)
def switch_section(
    data_inv_clicks, uncertainty_clicks, sim_clicks, results_clicks, workflow_status
):
    """Switch between sections and update step styles with workflow enforcement"""
    # Get workflow status (default to False if not set)
    step1_completed = (
        workflow_status.get("step1_completed", False) if workflow_status else False
    )
    step2_completed = (
        workflow_status.get("step2_completed", False) if workflow_status else False
    )

    # Determine step styles based on workflow status
    uncertainty_style = (
        get_disabled_step_style() if not step1_completed else get_inactive_step_style()
    )
    simulation_style = (
        get_disabled_step_style() if not step2_completed else get_inactive_step_style()
    )

    ctx = callback_context
    if not ctx.triggered:
        # Default to step 1
        return (
            get_data_investigation_content(),
            get_active_step_style(),
            uncertainty_style,
            simulation_style,
            get_inactive_step_style(),
        )

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Check if navigation is allowed based on workflow
    if button_id == "section-uncertainty-calculator-button" and not step1_completed:
        raise PreventUpdate
    elif button_id == "section-simulation-button" and not step2_completed:
        raise PreventUpdate

    if button_id == "section-data-investigation-button":
        return (
            get_data_investigation_content(),
            get_active_step_style(),
            uncertainty_style,
            simulation_style,
            get_inactive_step_style(),
        )
    elif button_id == "section-uncertainty-calculator-button":
        return (
            get_event_uncertainty_calculator_content(),
            get_completed_step_style(),  # step 1 completed
            get_active_step_style(),
            simulation_style,
            get_inactive_step_style(),
        )
    elif button_id == "section-simulation-button":
        return (
            get_simulation_selection_content(),
            get_completed_step_style(),   # step 1 completed
            get_completed_step_style(),   # step 2 completed
            get_active_step_style(),
            get_inactive_step_style(),
        )
    elif button_id == "section-results-button":
        return (
            get_results_content(),
            get_completed_step_style(),   # step 1 completed
            get_completed_step_style(),   # step 2 completed
            get_completed_step_style(),   # step 3 completed
            get_active_step_style(),
        )

    return (
        get_data_investigation_content(),
        get_active_step_style(),
        uncertainty_style,
        simulation_style,
        get_inactive_step_style(),
    )


@app.callback(
    Output("workflow-status", "data", allow_duplicate=True),
    [Input("stored-events", "data")],
    [State("workflow-status", "data")],
    prevent_initial_call=True,
)
def update_step1_completion(stored_events, workflow_status):
    """Mark step 1 as completed when events are stored"""
    if workflow_status is None:
        workflow_status = {"step1_completed": False, "step2_completed": False}

    # Step 1 is completed if stored-events has data
    step1_completed = stored_events is not None and len(stored_events) > 0

    workflow_status["step1_completed"] = step1_completed

    return workflow_status


@app.callback(
    Output("workflow-status", "data", allow_duplicate=True),
    [Input("section-uncertainty-calculator-button", "n_clicks")],
    [State("workflow-status", "data"), State("stored-events", "data")],
    prevent_initial_call=True,
)
def update_step2_completion(uncertainty_clicks, workflow_status, stored_events):
    """Mark step 2 as completed when user visits Emissions Event Browser"""
    if workflow_status is None:
        workflow_status = {"step1_completed": False, "step2_completed": False}

    # Step 2 is completed when user clicks the Emissions Event Browser button
    # and step 1 was already completed (events are stored)
    step1_completed = stored_events is not None and len(stored_events) > 0
    if uncertainty_clicks and uncertainty_clicks > 0 and step1_completed:
        workflow_status["step2_completed"] = True

    return workflow_status


@app.callback(
    [
        Output("section-uncertainty-calculator-button", "style", allow_duplicate=True),
        Output("section-simulation-button", "style", allow_duplicate=True),
    ],
    [Input("workflow-status", "data")],
    prevent_initial_call=True,
)
def update_navigation_button_styles(workflow_status):
    """Update step styles based on workflow status"""
    if workflow_status is None:
        workflow_status = {"step1_completed": False, "step2_completed": False}

    step1_completed = workflow_status.get("step1_completed", False)
    step2_completed = workflow_status.get("step2_completed", False)

    uncertainty_style = (
        get_disabled_step_style() if not step1_completed else get_inactive_step_style()
    )
    simulation_style = (
        get_disabled_step_style() if not step2_completed else get_inactive_step_style()
    )

    return uncertainty_style, simulation_style


@app.callback(
    [
        Output("user-guide-content", "style"),
        Output("user-guide-chevron", "style"),
    ],
    [Input("user-guide-toggle", "n_clicks")],
    prevent_initial_call=True,
)
def toggle_user_guide(n_clicks):
    """Toggle the collapsible user guide section"""
    is_open = n_clicks % 2 == 1
    content_style = {"display": "block"} if is_open else {"display": "none"}
    chevron_style = {
        "display": "inline-block",
        "marginRight": "8px",
        "fontSize": "12px",
        "transition": "transform 0.2s ease",
        "color": "#3498db",
        "transform": "rotate(90deg)" if is_open else "rotate(0deg)",
    }
    return content_style, chevron_style


@app.callback(
    [
        Output("stored-data", "data"),
        Output("upload-status", "children"),
        Output("open-mapping-button-container", "children"),
    ],
    [Input("upload-data", "contents")],
    [State("upload-data", "filename")],
)
def update_data(contents, filename):
    """Handle file upload and show button to open mapping modal"""
    if contents is None:
        raise PreventUpdate

    df, error = parse_contents(contents, filename)
    if error:
        return None, html.Div([html.P(error, style={"color": "red"})]), html.Div()

    if df is None:
        raise PreventUpdate

    status = html.Div(
        [
            html.P(
                f"✓ Successfully loaded: {filename} ({len(df)} rows, {len(df.columns)} columns)",
                style={"color": "#27ae60", "fontWeight": "bold"},
            )
        ]
    )

    button = html.Button(
        "Map Columns",
        id="open-mapping-modal-button",
        n_clicks=0,
        style=get_button_style("#3498db"),
    )

    return df.to_dict("records"), status, button


@app.callback(
    [
        Output("upload-status", "children", allow_duplicate=True),
        Output("open-mapping-button-container", "children", allow_duplicate=True),
    ],
    [Input("section-content", "children"), Input("stored-data", "data")],
    [State("column-mapping", "data"), State("stored-events", "data")],
    prevent_initial_call=True,
)
def restore_data_display(section_content, stored_data, column_mapping, stored_events):
    """Restore data display when switching to Loading Emissions Data section"""
    if stored_data is None:
        return html.Div(), html.Div()

    df = pd.DataFrame(stored_data)

    # Check if data has already been mapped and converted
    already_mapped = column_mapping is not None or stored_events is not None

    if already_mapped:
        # Data already mapped - show status but don't show mapping button
        status = html.Div(
            [
                html.P(
                    f"✓ Data loaded ({len(df)} rows, {len(df.columns)} columns)",
                    style={"color": "#27ae60", "fontWeight": "bold"},
                ),
                html.P(
                    "✓ Columns already mapped and events converted",
                    style={"color": "#27ae60", "fontSize": "14px", "marginTop": "5px"},
                ),
            ]
        )
        button = html.Div()  # Empty div - no mapping button
    else:
        # Data not yet mapped - show mapping button
        status = html.Div(
            [
                html.P(
                    f"✓ Data loaded ({len(df)} rows, {len(df.columns)} columns)",
                    style={"color": "#27ae60", "fontWeight": "bold"},
                )
            ]
        )
        button = html.Button(
            "Map Columns",
            id="open-mapping-modal-button",
            n_clicks=0,
            style=get_button_style("#3498db"),
        )

    return status, button


@app.callback(
    [Output("mapping-modal", "style"), Output("mapping-modal-backdrop", "style")],
    [
        Input("open-mapping-modal-button", "n_clicks"),
        Input("close-mapping-modal", "n_clicks"),
        Input("cancel-mapping-button", "n_clicks"),
        Input("mapping-modal-backdrop", "n_clicks"),
    ],
    [State("mapping-modal", "style"), State("mapping-modal-backdrop", "style")],
    prevent_initial_call=True,
)
def toggle_mapping_modal(
    open_clicks,
    close_clicks,
    cancel_clicks,
    backdrop_clicks,
    modal_style,
    backdrop_style,
):
    """Toggle modal visibility"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Close modal if close, cancel, or backdrop clicked
    if button_id in [
        "close-mapping-modal",
        "cancel-mapping-button",
        "mapping-modal-backdrop",
    ]:
        new_modal_style = modal_style.copy() if modal_style else {}
        new_backdrop_style = backdrop_style.copy() if backdrop_style else {}
        new_modal_style["display"] = "none"
        new_backdrop_style["display"] = "none"
        return new_modal_style, new_backdrop_style

    # Open modal if open button clicked
    if button_id == "open-mapping-modal-button":
        new_modal_style = modal_style.copy() if modal_style else {}
        new_backdrop_style = backdrop_style.copy() if backdrop_style else {}
        new_modal_style["display"] = "block"
        new_backdrop_style["display"] = "block"
        return new_modal_style, new_backdrop_style

    raise PreventUpdate


@app.callback(
    [
        Output("map-id", "options"),
        Output("map-rate", "options"),
        Output("map-time", "options"),
        Output("map-source", "options"),
        Output("map-cause", "options"),
        Output("map-start_time", "options"),
        Output("map-end_time", "options"),
        Output("map-uncertainties", "options"),
        Output("map-observation_type", "options"),
    ],
    [Input("stored-data", "data")],
    prevent_initial_call=True,
)
def update_mapping_dropdowns(stored_data):
    """Update dropdown options when data is loaded (source_scale is now an enum, not a column selector)
    Order: ID, Rate, Time, Source, Cause, Start Time, End Time, Uncertainties"""
    if stored_data is None:
        empty_options = [{"label": "-- Select Column --", "value": ""}]
        return [empty_options] * 9

    df = pd.DataFrame(stored_data)
    column_options = [{"label": "-- Select Column --", "value": ""}] + [
        {"label": col, "value": col} for col in df.columns
    ]

    return [column_options] * 9


@app.callback(
    [
        Output("preferred-type-row", "style"),
        Output("map-preferred-type", "options"),
    ],
    [
        Input("map-rate-operation", "value"),
        Input("map-observation_type", "value"),
        Input("stored-data", "data"),
    ],
)
def update_preferred_type_controls(rate_operation, observation_type_col, stored_data):
    """Show the preferred-procedure dropdown only for the 'Preference' rate operation, with the
    distinct values of the mapped Observation Procedure column as options."""
    row_style = {
        "marginBottom": "20px",
        "display": "flex" if rate_operation == "preference" else "none",
        "alignItems": "center",
    }
    options = []
    if stored_data is not None and observation_type_col:
        df = pd.DataFrame(stored_data)
        if observation_type_col in df.columns:
            values = df[observation_type_col].dropna().astype(str).str.strip().unique()
            options = [{"label": v, "value": v} for v in sorted(values)]
    return row_style, options


@app.callback(
    [
        Output("column-mapping", "data", allow_duplicate=True),
        Output("mapping-status", "children"),
        Output("validation-status", "children"),
        Output("stored-events", "data", allow_duplicate=True),
        Output("converted-events-table", "children"),
        Output("conversion-status", "children"),
        Output("sankey-chart-container", "children", allow_duplicate=True),
        Output("stored-sankey-chart", "data", allow_duplicate=True),
        Output("mapping-modal", "style", allow_duplicate=True),
        Output("mapping-modal-backdrop", "style", allow_duplicate=True),
        Output("modal-mapping-status", "children", allow_duplicate=True),
    ],
    [Input("save-mapping-button", "n_clicks")],
    [
        State("stored-data", "data"),
        State("map-rate", "value"),
        State("map-id", "value"),
        State("map-source", "value"),
        State("map-cause", "value"),
        State("map-start_time", "value"),
        State("map-end_time", "value"),
        State("map-time", "value"),
        State("map-uncertainties", "value"),
        State("map-observation_type", "value"),
        State("map-rate-operation", "value"),
        State("map-preferred-type", "value"),
        State("mapping-modal", "style"),
        State("mapping-modal-backdrop", "style"),
    ],
    prevent_initial_call=True,
)
def process_data_workflow(
    n_clicks,
    data,
    rate_col,
    id_col,
    source_col,
    cause_col,
    start_time_col,
    end_time_col,
    time_col,
    uncertainties_col,
    observation_type_col,
    rate_operation,
    preferred_observation_type,
    modal_style,
    backdrop_style,
):
    """
    Complete data processing workflow:
    1. Save mapping
    2. Validate data format
    3. Convert to emission events
    4. Store in memory
    5. Display converted events
    """
    if n_clicks == 0 or data is None:
        raise PreventUpdate

    df = pd.DataFrame(data)

    # Step 1: Create mapping
    # Note: source_scale removed from UI - defaults to 'site' in converter

    # Emission characteristics will be set later in Emissions Event Browser
    # For now, use default 'intermittent' for conversion
    emission_char_value = "intermittent"

    mapping = {
        "rate": rate_col if rate_col else None,
        "id": id_col if id_col else None,
        "source": source_col if source_col else None,
        "cause": cause_col if cause_col else None,
        "start_time": start_time_col if start_time_col else None,
        "end_time": end_time_col if end_time_col else None,
        "time": time_col if time_col else None,
        "uncertainties": uncertainties_col if uncertainties_col else None,
        "observation_type": observation_type_col if observation_type_col else None,
        "emission_characteristics": emission_char_value,  # Default to 'intermittent', can be updated later
    }

    # Step 2: Validate mandatory fields
    # Check that rate, id, source, and time columns are mapped
    missing = []
    if not mapping.get("id"):
        missing.append("id")
    if not mapping.get("rate"):
        missing.append("rate")
    if not mapping.get("time"):
        missing.append("time")
    if not mapping.get("source"):
        missing.append("source")

    rate_operation = rate_operation or "average"
    if rate_operation == "preference":
        if not mapping.get("observation_type"):
            missing.append("Observation Procedure (required by the Preference rate operation)")
        if not preferred_observation_type:
            missing.append("Preferred Observation Procedure")

    if missing:
        mapping_status = html.Div(
            [
                html.P(
                    f"⚠ Missing mandatory field mappings: {', '.join(missing)}",
                    style={"color": "#e74c3c", "fontWeight": "bold"},
                )
            ]
        )
        # Keep modal open on error
        return (
            None,  # column-mapping
            mapping_status,  # mapping-status
            html.Div(),  # validation-status
            None,  # stored-events
            html.Div(),  # converted-events-table
            html.Div(),  # conversion-status
            html.Div(),  # sankey-chart-container
            None,  # stored-sankey-chart
            modal_style,  # mapping-modal
            backdrop_style,  # mapping-modal-backdrop
            mapping_status,  # modal-mapping-status
        )

    mapping_status = html.Div(
        [html.P("✓ Data saved", style={"color": "#27ae60", "fontWeight": "bold"})]
    )

    # Step 3: Validate data format
    try:
        checks = check_data(df, mapping)
        validation_errors = []

        if checks["validation_errors"]:
            validation_errors = checks["validation_errors"]

        if validation_errors:
            validation_status = html.Div(
                [
                    html.P(
                        "⚠ Data validation issues:",
                        style={
                            "color": "#e67e22",
                            "fontWeight": "bold",
                            "marginTop": "10px",
                        },
                    ),
                    html.Ul(
                        [
                            html.Li(error, style={"color": "#e67e22"})
                            for error in validation_errors
                        ],
                        style={"marginLeft": "20px"},
                    ),
                ]
            )
            # Keep modal open on error
            return (
                mapping,
                mapping_status,
                validation_status,
                None,
                html.Div(),
                html.Div(),
                html.Div(),
                None,
                modal_style,
                backdrop_style,
                validation_status,
            )
        else:
            validation_status = html.Div(
                [
                    html.P(
                        "✓ Data format validated successfully",
                        style={
                            "color": "#27ae60",
                            "fontWeight": "bold",
                            "marginTop": "10px",
                        },
                    )
                ]
            )
    except Exception as e:
        validation_status = html.Div(
            [
                html.P(
                    f"✗ Validation error: {str(e)}",
                    style={
                        "color": "#e74c3c",
                        "fontWeight": "bold",
                        "marginTop": "10px",
                    },
                )
            ]
        )
        # Keep modal open on error
        return (
            mapping,
            mapping_status,
            validation_status,
            None,
            html.Div(),
            html.Div(),
            html.Div(),
            None,
            modal_style,
            backdrop_style,
            validation_status,
        )

    # Step 4: Convert to emission events
    try:
        time_column = mapping.get("time")
        emission_characteristics = mapping.get(
            "emission_characteristics", "intermittent"
        )
        events_df = convert_to_emission_event_model(
            df,
            mapping,
            time_column=time_column,
            emission_characteristics=emission_characteristics,
            rate_operation=rate_operation,
            preferred_observation_type=preferred_observation_type or None,
        )

        # Get statistics about resolved vs partially resolved events
        resolved_count = 0
        partially_resolved_count = 0
        
        # Try to get from DataFrame attributes first
        if hasattr(events_df, 'attrs') and events_df.attrs:
            resolved_count = events_df.attrs.get('resolved_count', 0)
            partially_resolved_count = events_df.attrs.get('partially_resolved_count', 0)
        
        # If not in attrs, calculate from DataFrame event_type column
        if 'event_type' in events_df.columns:
            resolved_count = len(events_df[events_df['event_type'] == 'RE'])
            partially_resolved_count = len(events_df[events_df['event_type'] == 'PRE'])
        
        conversion_status = html.Div(
            [
                html.P(
                    f"✓ Converted {len(events_df)} events to Emission Event model",
                    style={
                        "color": "#27ae60",
                        "fontWeight": "bold",
                        "marginTop": "10px",
                    },
                ),
                html.P(
                    "✓ Events stored in memory",
                    style={"color": "#27ae60", "fontSize": "14px"},
                ),
                html.P(
                    "Rate operation for merged observations: "
                    + rate_operation.replace("_", " ")
                    + (
                        f" (preferred: {preferred_observation_type})"
                        if rate_operation == "preference"
                        else ""
                    ),
                    style={"color": "#7f8c8d", "fontSize": "13px"},
                ),
                html.Div(
                    [
                        html.P(
                            "📊 Event Resolution Statistics:",
                            style={
                                "fontWeight": "bold",
                                "marginTop": "15px",
                                "marginBottom": "10px",
                                "fontSize": "16px",
                                "color": "#2c3e50",
                            },
                        ),
                        html.P(
                            f"• Resolved events (RE): {resolved_count} events",
                            style={
                                "marginLeft": "20px",
                                "color": "#27ae60",
                                "fontSize": "15px",
                                "fontWeight": "500",
                                "marginBottom": "5px",
                            },
                        ),
                        html.P(
                            "  (includes loaded data with observation_type = 'operation')",
                            style={
                                "marginLeft": "40px",
                                "color": "#7f8c8d",
                                "fontSize": "13px",
                                "fontStyle": "italic",
                                "marginBottom": "8px",
                            },
                        ),
                        html.P(
                            f"• Partially resolved events (PRE): {partially_resolved_count} events",
                            style={
                                "marginLeft": "20px",
                                "color": "#e67e22",
                                "fontSize": "15px",
                                "fontWeight": "500",
                                "marginBottom": "5px",
                            },
                        ),
                        html.P(
                            "  (includes loaded data with observation_type ≠ 'operation')",
                            style={
                                "marginLeft": "40px",
                                "color": "#7f8c8d",
                                "fontSize": "13px",
                                "fontStyle": "italic",
                                "marginBottom": "8px",
                            },
                        ),
                        html.P(
                            f"• Total events: {len(events_df)}",
                            style={
                                "marginLeft": "20px",
                                "color": "#2c3e50",
                                "fontSize": "15px",
                                "fontWeight": "bold",
                                "marginTop": "8px",
                                "paddingTop": "8px",
                                "borderTop": "1px solid #dee2e6",
                            },
                        ),
                    ],
                    style={
                        "backgroundColor": "#f8f9fa",
                        "padding": "15px",
                        "borderRadius": "8px",
                        "marginTop": "15px",
                        "border": "2px solid #dee2e6",
                    },
                ),
                html.Details(
                    [
                        html.Summary("UML Model Structure"),
                        html.P("Each event includes:"),
                        html.Ul(
                            [
                                html.Li("Emission Event: id, eventType"),
                                html.Li("Quantity: calculated from rate × duration"),
                                html.Li("Observation: quantity (rate), duration"),
                                html.Li("Duration: duration, durationEstimationType"),
                                html.Li("Cause: rootCauseAnalysis (if provided)"),
                                html.Li(
                                    "Source: sourceLocation, sourceCategory, physicalSource"
                                ),
                            ]
                        ),
                    ],
                    style={"marginTop": "10px"},
                ),
            ]
        )

        # Step 6: Create table display
        events_table = create_emission_events_table(events_df)

        # Step 7: Create Sankey chart
        try:
            sankey_fig = create_sankey_chart(df, events_df, mapping)
            # Store figure data as dict for persistence
            sankey_fig_dict = (
                sankey_fig.to_dict() if hasattr(sankey_fig, "to_dict") else None
            )
            sankey_chart = dcc.Graph(figure=sankey_fig, id="sankey-chart")
        except Exception as e:
            sankey_fig_dict = None
            sankey_chart = html.Div(
                [
                    html.P(
                        f"Could not generate Sankey chart: {str(e)}",
                        style={"color": "#e67e22", "fontStyle": "italic"},
                    )
                ]
            )

        # Close modal on success
        new_modal_style = modal_style.copy() if modal_style else {}
        new_backdrop_style = backdrop_style.copy() if backdrop_style else {}
        new_modal_style["display"] = "none"
        new_backdrop_style["display"] = "none"

        return (
            mapping,
            mapping_status,
            validation_status,
            events_df.to_dict("records"),
            events_table,
            conversion_status,
            sankey_chart,
            sankey_fig_dict,
            new_modal_style,
            new_backdrop_style,
            html.Div(),
        )

    except ValueError as e:
        conversion_status = html.Div(
            [
                html.P(
                    f"✗ Error converting data: {str(e)}",
                    style={
                        "color": "#e74c3c",
                        "fontWeight": "bold",
                        "marginTop": "10px",
                    },
                )
            ]
        )
        # Keep modal open on error
        return (
            mapping,
            mapping_status,
            validation_status,
            None,
            html.Div(),
            conversion_status,
            html.Div(),
            None,
            modal_style,
            backdrop_style,
            conversion_status,
        )
    except Exception as e:
        conversion_status = html.Div(
            [
                html.P(
                    f"✗ Unexpected error: {str(e)}",
                    style={
                        "color": "#e74c3c",
                        "fontWeight": "bold",
                        "marginTop": "10px",
                    },
                )
            ]
        )
        # Keep modal open on error
        return (
            mapping,
            mapping_status,
            validation_status,
            None,
            html.Div(),
            conversion_status,
            html.Div(),
            None,
            modal_style,
            backdrop_style,
            conversion_status,
        )


@app.callback(
    [
        Output("converted-events-table", "children", allow_duplicate=True),
        Output("conversion-status", "children", allow_duplicate=True),
    ],
    [Input("section-content", "children"), Input("stored-events", "data")],
    prevent_initial_call=True,
)
def restore_converted_events(section_content, stored_events):
    """Restore converted events display when switching to Loading Emissions Data section"""
    if stored_events is None:
        return html.Div(), html.Div()

    events_df = pd.DataFrame(stored_events)
    events_table = create_emission_events_table(events_df)

    status = html.Div(
        [
            html.P(
                f"✓ {len(events_df)} events loaded from memory",
                style={"color": "#27ae60", "fontWeight": "bold"},
            )
        ]
    )

    return events_table, status


@app.callback(
    Output("sankey-chart-container", "children", allow_duplicate=True),
    [Input("section-content", "children"), Input("stored-sankey-chart", "data")],
    prevent_initial_call=True,
)
def restore_sankey_chart(section_content, sankey_chart_data):
    """Restore Sankey chart when switching back to Loading Emissions Data section"""
    if sankey_chart_data is None:
        return html.Div()

    try:
        # Recreate figure from stored dict
        fig = go.Figure(sankey_chart_data)
        return dcc.Graph(figure=fig, id="sankey-chart")
    except Exception as e:
        return html.Div(
            [
                html.P(
                    f"Could not restore Sankey chart: {str(e)}",
                    style={"color": "#e67e22", "fontStyle": "italic"},
                )
            ]
        )


@app.callback(
    [
        Output("rate-histogram", "figure"),
        Output("duration-histogram", "figure"),
        Output("stored-fitted-distributions", "data", allow_duplicate=True),
    ],
    [Input("stored-events", "data"), Input("fit-button", "n_clicks")],
    [State("distribution-dropdown", "value")],
    prevent_initial_call=True,
)
def plot_histograms_with_fitting(events_data, fit_clicks, dist_type):
    if events_data is None:
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text="Please convert data first",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return empty_fig, empty_fig, None

    events_df = pd.DataFrame(events_data)
    show_fitted = fit_clicks > 0

    # Initialize storage for fitted distributions
    fitted_distributions = None

    # Rate histogram
    if "rate" in events_df.columns:
        rate_data = events_df["rate"].dropna()
        if len(rate_data) > 0:
            fig_rate = go.Figure()

            # Add histogram
            fig_rate.add_trace(
                go.Histogram(
                    x=rate_data.values,
                    name="Data",
                    opacity=0.7,
                    nbinsx=30,
                    histnorm="probability density",
                )
            )

            # Add fitted distribution if requested
            if show_fitted:
                params, error = fit_distribution(rate_data.values, dist_type)
                if params is not None:
                    # Store fitted distribution
                    if fitted_distributions is None:
                        fitted_distributions = {}
                    fitted_distributions["rate"] = {
                        "type": dist_type,
                        "params": params.tolist()
                        if hasattr(params, "tolist")
                        else list(params),
                        "min": float(rate_data.min()),
                        "max": float(rate_data.max()),
                    }

                    x_range = np.linspace(rate_data.min(), rate_data.max(), 200)
                    from scipy.stats import (
                        lognorm,
                        norm,
                        uniform,
                        expon,
                        weibull_min,
                        gamma,
                    )

                    if dist_type == "lognormal":
                        pdf = lognorm.pdf(x_range, *params)
                    elif dist_type == "normal":
                        pdf = norm.pdf(x_range, *params)
                    elif dist_type == "uniform":
                        pdf = uniform.pdf(x_range, *params)
                    elif dist_type == "exponential":
                        pdf = expon.pdf(x_range, *params)
                    elif dist_type == "weibull":
                        pdf = weibull_min.pdf(x_range, *params)
                    elif dist_type == "gamma":
                        pdf = gamma.pdf(x_range, *params)
                    else:
                        pdf = np.zeros_like(x_range)

                    fig_rate.add_trace(
                        go.Scatter(
                            x=x_range,
                            y=pdf,
                            mode="lines",
                            name=f"Fitted {dist_type}",
                            line=dict(color="red", width=2),
                        )
                    )

            fig_rate.update_layout(
                title="Rate Distribution"
                + (f" with Fitted {dist_type}" if show_fitted else ""),
                xaxis_title="Rate (kg/hr)",
                yaxis_title="Probability Density",
                height=400,
                hovermode="x unified",
            )
        else:
            fig_rate = go.Figure()
            fig_rate.add_annotation(
                text="No rate data available",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
            )
    else:
        fig_rate = go.Figure()
        fig_rate.add_annotation(
            text="Rate data not available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )

    # Duration histogram
    if "duration" in events_df.columns:
        duration_data = events_df["duration"].dropna()
        if len(duration_data) > 0:
            fig_duration = go.Figure()

            # Add histogram
            fig_duration.add_trace(
                go.Histogram(
                    x=duration_data.values,
                    name="Data",
                    opacity=0.7,
                    nbinsx=30,
                    histnorm="probability density",
                )
            )

            # Add fitted distribution if requested
            if show_fitted:
                params, error = fit_distribution(duration_data.values, dist_type)
                if params is not None:
                    # Store fitted distribution
                    if fitted_distributions is None:
                        fitted_distributions = {}
                    fitted_distributions["duration"] = {
                        "type": dist_type,
                        "params": params.tolist()
                        if hasattr(params, "tolist")
                        else list(params),
                        "min": float(duration_data.min()),
                        "max": float(duration_data.max()),
                    }

                    x_range = np.linspace(duration_data.min(), duration_data.max(), 200)
                    from scipy.stats import (
                        lognorm,
                        norm,
                        uniform,
                        expon,
                        weibull_min,
                        gamma,
                    )

                    if dist_type == "lognormal":
                        pdf = lognorm.pdf(x_range, *params)
                    elif dist_type == "normal":
                        pdf = norm.pdf(x_range, *params)
                    elif dist_type == "uniform":
                        pdf = uniform.pdf(x_range, *params)
                    elif dist_type == "exponential":
                        pdf = expon.pdf(x_range, *params)
                    elif dist_type == "weibull":
                        pdf = weibull_min.pdf(x_range, *params)
                    elif dist_type == "gamma":
                        pdf = gamma.pdf(x_range, *params)
                    else:
                        pdf = np.zeros_like(x_range)

                    fig_duration.add_trace(
                        go.Scatter(
                            x=x_range,
                            y=pdf,
                            mode="lines",
                            name=f"Fitted {dist_type}",
                            line=dict(color="red", width=2),
                        )
                    )

            fig_duration.update_layout(
                title="Duration Distribution"
                + (f" with Fitted {dist_type}" if show_fitted else ""),
                xaxis_title="Duration (hours)",
                yaxis_title="Probability Density",
                height=400,
                hovermode="x unified",
            )
        else:
            fig_duration = go.Figure()
            fig_duration.add_annotation(
                text="No duration data available",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
            )
    else:
        fig_duration = go.Figure()
        fig_duration.add_annotation(
            text="Duration data not available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )

    return fig_rate, fig_duration, fitted_distributions


@app.callback(
    Output("iterations-display", "children"), [Input("monte-carlo-iterations", "value")]
)
def update_iterations_display(iterations):
    """Update display of selected iterations"""
    if iterations is None:
        return ""
    return f"Selected: {iterations} iterations"


@app.callback(
    Output("leak-data-upload-container", "style"),
    [Input("upload-leak-data-dropdown", "value")],
)
def toggle_leak_data_upload(upload_choice):
    """Show/hide leak data upload container"""
    if upload_choice == "yes":
        return {"marginBottom": "20px", "display": "block"}
    else:
        return {"marginBottom": "20px", "display": "none"}


@app.callback(
    [
        Output("leak-data-upload-status", "children"),
        Output("stored-leak-csv", "data"),
        Output("stored-leak-data", "data", allow_duplicate=True),
        Output("leak-data-column-selector-container", "style"),
        Output("leak-data-column-selector", "options"),
        Output("leak-data-column-selector", "value"),
        Output("leak-data-histogram-container", "style"),
    ],
    [
        Input("upload-leak-data", "contents"),
        Input("upload-leak-data-dropdown", "value"),
    ],
    [State("upload-leak-data", "filename")],
    prevent_initial_call=True,
)
def handle_leak_data_upload(contents, upload_choice, filename):
    """Handle leak data file upload or load default sample file"""
    # Get the trigger to determine what caused the callback
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if upload_choice == "yes":
        # User wants to upload their own data
        if trigger_id == "upload-leak-data-dropdown":
            # Dropdown changed to 'yes', but no file uploaded yet
            return (
                html.Div(
                    [
                        html.P(
                            "Please upload your CSV file.",
                            style={"color": "#7f8c8d", "fontStyle": "italic"},
                        )
                    ]
                ),
                None,
                None,
                {"marginTop": "10px", "display": "none"},
                [],
                None,
                {"marginTop": "20px", "display": "none"},
            )

        if contents is None:
            return (
                html.Div(),
                None,
                None,
                {"marginTop": "10px", "display": "none"},
                [],
                None,
                {"marginTop": "20px", "display": "none"},
            )

        try:
            # Parse uploaded file
            content_type, content_string = contents.split(",")
            decoded = base64.b64decode(content_string)

            # Try to read as CSV
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))

            # Store the DataFrame as JSON for later column selection
            csv_data = df.to_dict("records")
            column_options = [{"label": col, "value": col} for col in df.columns]

            status = html.Div(
                [
                    html.P(
                        f"✓ File '{filename}' uploaded successfully. Found {len(df)} rows and {len(df.columns)} columns.",
                        style={"color": "#27ae60", "fontWeight": "bold"},
                    ),
                    html.P(
                        "Please select the column containing leak rates.",
                        style={
                            "color": "#7f8c8d",
                            "fontSize": "14px",
                            "marginTop": "5px",
                        },
                    ),
                ]
            )

            return (
                status,
                {"data": csv_data, "columns": df.columns.tolist()},
                None,
                {"marginTop": "10px", "display": "block"},
                column_options,
                None,
                {"marginTop": "20px", "display": "none"},
            )

        except Exception as e:
            return (
                html.Div(
                    [
                        html.P(
                            f"✗ Error reading file: {str(e)}",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                None,
                None,
                {"marginTop": "10px", "display": "none"},
                [],
                None,
                {"marginTop": "20px", "display": "none"},
            )

    else:
        # User selected "No" - load sample_leak_rate.csv
        try:
            import os

            # Get the directory of the current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sample_file_path = os.path.join(current_dir, "sample_leak_rate.csv")

            if os.path.exists(sample_file_path):
                df = pd.read_csv(sample_file_path)

                if "gpersec" in df.columns:
                    # the bundled file is in g/s; the simulation expects kg/h
                    leak_data = (df["gpersec"].dropna() * 3.6).tolist()

                    status = html.Div(
                        [
                            html.P(
                                f"✓ Loaded sample_leak_rate.csv. Found {len(leak_data)} data points.",
                                style={"color": "#27ae60", "fontWeight": "bold"},
                            )
                        ]
                    )

                    # For sample file, store data directly
                    return (
                        status,
                        None,
                        {"data": leak_data, "source": "sample", "column": "kg/hr, converted from gpersec"},
                        {"marginTop": "10px", "display": "none"},
                        [],
                        None,
                        {"marginTop": "20px", "display": "block"},
                    )
                else:
                    return (
                        html.Div(
                            [
                                html.P(
                                    "⚠ 'gpersec' column not found in sample_leak_rate.csv",
                                    style={"color": "#e67e22", "fontWeight": "bold"},
                                )
                            ]
                        ),
                        None,
                        None,
                        {"marginTop": "10px", "display": "none"},
                        [],
                        None,
                        {"marginTop": "20px", "display": "none"},
                    )
            else:
                return (
                    html.Div(
                        [
                            html.P(
                                "⚠ sample_leak_rate.csv not found in the application directory.",
                                style={"color": "#e67e22", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    None,
                    None,
                    {"marginTop": "10px", "display": "none"},
                    [],
                    None,
                    {"marginTop": "20px", "display": "none"},
                )

        except Exception as e:
            return (
                html.Div(
                    [
                        html.P(
                            f"✗ Error loading sample file: {str(e)}",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                None,
                None,
                {"marginTop": "10px", "display": "none"},
                [],
                None,
                {"marginTop": "20px", "display": "none"},
            )


@app.callback(
    [
        Output("stored-leak-data", "data", allow_duplicate=True),
        Output("leak-data-histogram-container", "style", allow_duplicate=True),
        Output("leak-data-upload-status", "children", allow_duplicate=True),
    ],
    [
        Input("leak-data-column-selector", "value"),
        Input("upload-leak-data-dropdown", "value"),
    ],
    [State("stored-leak-csv", "data")],
    prevent_initial_call=True,
)
def handle_column_selection(selected_column, upload_choice, csv_store):
    """Handle column selection and extract leak data"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    # Handle column selection for uploaded file
    if csv_store is None or selected_column is None:
        raise PreventUpdate

    try:
        # Reconstruct DataFrame from stored data
        df = pd.DataFrame(csv_store["data"])

        if selected_column not in df.columns:
            return (
                None,
                {"marginTop": "20px", "display": "none"},
                html.Div(
                    [
                        html.P(
                            f"⚠ Selected column '{selected_column}' not found in CSV.",
                            style={"color": "#e67e22", "fontWeight": "bold"},
                        )
                    ]
                ),
            )

        # Extract data from selected column
        leak_data = df[selected_column].dropna().tolist()

        if len(leak_data) == 0:
            return (
                None,
                {"marginTop": "20px", "display": "none"},
                html.Div(
                    [
                        html.P(
                            f"⚠ No valid data found in column '{selected_column}'.",
                            style={"color": "#e67e22", "fontWeight": "bold"},
                        )
                    ]
                ),
            )

        status = html.Div(
            [
                html.P(
                    f"✓ Column '{selected_column}' selected. Found {len(leak_data)} data points.",
                    style={"color": "#27ae60", "fontWeight": "bold"},
                )
            ]
        )

        return (
            {"data": leak_data, "source": "uploaded", "column": selected_column},
            {"marginTop": "20px", "display": "block"},
            status,
        )

    except Exception as e:
        return (
            None,
            {"marginTop": "20px", "display": "none"},
            html.Div(
                [
                    html.P(
                        f"✗ Error processing column selection: {str(e)}",
                        style={"color": "#e74c3c", "fontWeight": "bold"},
                    )
                ]
            ),
        )


@app.callback(
    Output("leak-data-histogram", "figure"),
    [Input("stored-leak-data", "data")],
    prevent_initial_call=True,
)
def plot_leak_data_histogram(leak_data_store):
    """Plot histogram of leak data"""
    if leak_data_store is None or "data" not in leak_data_store:
        return go.Figure()

    leak_data = leak_data_store["data"]
    source = leak_data_store.get("source", "unknown")
    column = leak_data_store.get("column", "unknown")

    if not leak_data or len(leak_data) == 0:
        return go.Figure()

    # Create histogram
    fig = go.Figure()

    fig.add_trace(
        go.Histogram(
            x=leak_data,
            nbinsx=50,
            marker_color="#9b59b6",
            marker_line_color="#7d3c98",
            marker_line_width=1,
            opacity=0.7,
        )
    )

    fig.update_layout(
        title={
            "text": f"Component-Level Leak Data Distribution ({source})",
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis_title=f"Leak Rate ({column})",
        yaxis_title="Frequency",
        template="plotly_white",
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
    )

    return fig


@app.callback(
    [
        Output("wind-data-upload-status", "children"),
        Output("stored-wind-csv", "data"),
        Output("stored-wind-data", "data", allow_duplicate=True),
        Output("wind-data-column-selector-container", "style"),
        Output("wind-data-column-selector", "options"),
        Output("wind-data-column-selector", "value"),
    ],
    [
        Input("upload-wind-data", "contents"),
        Input("wind-data-source-dropdown", "value"),
    ],
    [State("upload-wind-data", "filename")],
    prevent_initial_call=True,
)
def handle_wind_data_upload(contents, upload_choice, filename):
    """Handle wind data file upload"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if upload_choice == "upload":
        # User wants to upload their own data
        if trigger_id == "wind-data-source-dropdown":
            # Dropdown changed to 'upload', but no file uploaded yet
            return (
                html.Div(
                    [
                        html.P(
                            "Please upload your CSV file.",
                            style={"color": "#7f8c8d", "fontStyle": "italic"},
                        )
                    ]
                ),
                None,
                None,
                {"marginTop": "10px", "display": "none"},
                [],
                None,
            )

        if contents is None:
            return (
                html.Div(),
                None,
                None,
                {"marginTop": "10px", "display": "none"},
                [],
                None,
            )

        try:
            # Parse uploaded file
            content_type, content_string = contents.split(",")
            decoded = base64.b64decode(content_string)

            # Try to read as CSV
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))

            # Store the DataFrame as JSON for later column selection
            csv_data = df.to_dict("records")
            column_options = [{"label": col, "value": col} for col in df.columns]

            status = html.Div(
                [
                    html.P(
                        f"✓ File '{filename}' uploaded successfully. Found {len(df)} rows and {len(df.columns)} columns.",
                        style={"color": "#27ae60", "fontWeight": "bold"},
                    ),
                    html.P(
                        "Please select the column containing wind speed (m/s).",
                        style={
                            "color": "#7f8c8d",
                            "fontSize": "14px",
                            "marginTop": "5px",
                        },
                    ),
                ]
            )

            return (
                status,
                {"data": csv_data, "columns": df.columns.tolist()},
                None,
                {"marginTop": "10px", "display": "block"},
                column_options,
                None,
            )

        except Exception as e:
            return (
                html.Div(
                    [
                        html.P(
                            f"✗ Error uploading file: {str(e)}",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                None,
                None,
                {"marginTop": "10px", "display": "none"},
                [],
                None,
            )
    else:
        # Use default - clear upload-related outputs
        return (
            html.Div(),
            None,
            None,
            {"marginTop": "10px", "display": "none"},
            [],
            None,
        )


@app.callback(
    [
        Output("stored-wind-data", "data", allow_duplicate=True),
        Output("wind-data-status", "children"),
    ],
    [
        Input("wind-data-column-selector", "value"),
        Input("wind-data-source-dropdown", "value"),
        Input("consider-wind-dropdown", "value"),
    ],
    [State("stored-wind-csv", "data")],
    prevent_initial_call=True,
)
def handle_wind_column_selection_and_default(
    selected_column, upload_choice, consider_wind, csv_store
):
    """Handle column selection for uploaded wind data or load default wind data"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    # If Consider Wind is No, clear everything
    if consider_wind == "no":
        return None, html.Div()

    # Handle uploaded data
    if upload_choice == "upload":
        if csv_store is None or selected_column is None:
            raise PreventUpdate

        try:
            # Reconstruct DataFrame from stored data
            df = pd.DataFrame(csv_store["data"])

            if selected_column not in df.columns:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                f"⚠ Selected column '{selected_column}' not found in CSV.",
                                style={"color": "#e67e22", "fontWeight": "bold"},
                            )
                        ]
                    ),
                )

            # Extract data from selected column
            wind_data = df[selected_column].dropna().tolist()

            if len(wind_data) == 0:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                f"⚠ No valid data found in column '{selected_column}'.",
                                style={"color": "#e67e22", "fontWeight": "bold"},
                            )
                        ]
                    ),
                )

            status = html.Div(
                [
                    html.P(
                        f"✓ Column '{selected_column}' selected. Found {len(wind_data)} data points.",
                        style={"color": "#27ae60", "fontWeight": "bold"},
                    )
                ]
            )

            return (
                {"data": wind_data, "source": "uploaded", "column": selected_column},
                status,
            )

        except Exception as e:
            return (
                None,
                html.Div(
                    [
                        html.P(
                            f"✗ Error processing column selection: {str(e)}",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
            )

    # Handle default data
    elif upload_choice == "default":
        try:
            import os

            if not HAS_NETCDF:
                return None, html.Div(
                    [
                        html.P(
                            "⚠ netCDF4 library is not available. Cannot load wind data.",
                            style={"color": "#e67e22", "fontWeight": "bold"},
                        )
                    ]
                )

            current_dir = os.path.dirname(os.path.abspath(__file__))
            weather_file_path = os.path.join(current_dir, "weather_permian.nc")

            if os.path.exists(weather_file_path):
                # Load NetCDF file and calculate wind speed from u10 and v10
                wind_data = nc.Dataset(weather_file_path)
                u10 = wind_data.variables["u10"][:]
                v10 = wind_data.variables["v10"][:]
                ws = (u10**2 + v10**2) ** 0.5
                wind_data.close()

                # Convert to list and flatten
                wind_speed_array = ws.flatten()
                wind_speed_list = [float(x) for x in wind_speed_array if not pd.isna(x)]

                if len(wind_speed_list) > 0:
                    status = html.Div(
                        [
                            html.P(
                                "✓ Using default wind data (weather_permian.nc)",
                                style={"color": "#27ae60", "fontWeight": "bold"},
                            )
                        ]
                    )
                    return {
                        "data": wind_speed_list,
                        "source": "default",
                        "file": "weather_permian.nc",
                    }, status
            else:
                return None, html.Div(
                    [
                        html.P(
                            "⚠ weather_permian.nc file not found.",
                            style={"color": "#e67e22", "fontWeight": "bold"},
                        )
                    ]
                )
        except Exception as e:
            return None, html.Div(
                [
                    html.P(
                        f"✗ Error loading wind data: {str(e)}",
                        style={"color": "#e74c3c", "fontWeight": "bold"},
                    )
                ]
            )

    raise PreventUpdate


@app.callback(
    [
        Output("estimation-approach-dropdown", "options"),
        Output("estimation-approach-dropdown", "value"),
    ],
    [Input("column-mapping", "data"), Input("stored-emission-characteristics", "data")],
    prevent_initial_call=True,
)
def update_estimation_approach_options(column_mapping, stored_emission_char):
    """Update estimation approach dropdown options based on emission_characteristics"""
    # Use stored emission characteristics if available, otherwise fall back to mapping
    if stored_emission_char and stored_emission_char.get("value"):
        emission_char = stored_emission_char.get("value")
    elif column_mapping:
        emission_char = column_mapping.get("emission_characteristics", "intermittent")
    else:
        emission_char = "intermittent"  # Default

    if emission_char == "intermittent":
        # Show both options
        options = [
            {"label": "Simulate Below Detection Limit", "value": "below_MDL"},
            {"label": "Bootstrap For Unmeasured Emissions", "value": "bootstrap"},
        ]
        return options, "below_MDL"
    else:
        # Only show bootstrap
        options = [
            {"label": "Bootstrap For Unmeasured Emissions", "value": "bootstrap"},
        ]
        return options, "bootstrap"


@app.callback(
    [
        Output("consider-wind-container", "style"),
        Output("component-leak-data-container", "style"),
        Output("measurement-technology-container", "style"),
    ],
    [Input("estimation-approach-dropdown", "value")],
)
def toggle_approach_specific_fields(estimation_approach):
    """Show/hide fields specific to each estimation approach"""
    if estimation_approach == "below_MDL":
        # Show wind consideration, leak data, and measurement technology for below_MDL
        return (
            {"marginBottom": "20px", "display": "block"},
            {"marginBottom": "30px", "display": "block"},
            {"display": "block"},
        )
    else:
        # Hide wind consideration, leak data, and measurement technology for bootstrap
        # (use visibility so components stay in DOM)
        return (
            {
                "marginBottom": "20px",
                "display": "block",
                "visibility": "hidden",
                "height": "0",
                "overflow": "hidden",
                "position": "absolute",
            },
            {"marginBottom": "30px", "display": "none"},
            {"display": "none"},
        )


@app.callback(
    Output("wind-data-source-container", "style"),
    [Input("consider-wind-dropdown", "value")],
)
def toggle_wind_data_source(consider_wind):
    """Show/hide wind data source selection when Consider Wind is Yes"""
    if consider_wind == "yes":
        return {"marginBottom": "20px", "display": "block"}
    else:
        return {"marginBottom": "20px", "display": "none"}


@app.callback(
    Output("wind-data-upload-container", "style"),
    [Input("wind-data-source-dropdown", "value")],
)
def toggle_wind_data_upload(upload_choice):
    """Show/hide wind data upload container when Upload Your Own is selected"""
    if upload_choice == "upload":
        return {"marginBottom": "20px", "display": "block"}
    else:
        return {"marginBottom": "20px", "display": "none"}


@app.callback(
    Output("minimum-detection-limit-container", "style"),
    [Input("measurement-technology-dropdown", "value")],
)
def toggle_mdl_and_technology(measurement_technology):
    """Show/hide minimum detection limit input based on measurement technology selection"""
    # Handle both single value (backward compatibility) and list (multiple selection)
    if measurement_technology is None:
        return {"marginBottom": "20px", "display": "none"}

    # Convert to list if single value
    if not isinstance(measurement_technology, list):
        measurement_technology = [measurement_technology]

    # Show MDL input if 'define_technology' is in the selected technologies
    if "define_technology" in measurement_technology:
        return {"marginBottom": "20px", "display": "block"}
    else:
        return {"marginBottom": "20px", "display": "none"}


@app.callback(
    [
        Output("stored-simulation-results", "data"),
        Output("simulation-status", "children"),
        Output("section-results-button", "n_clicks", allow_duplicate=True),
    ],
    [Input("simulate-button", "n_clicks")],
    [
        State("stored-events", "data"),
        State("resolution-dropdown", "value"),
        State("estimation-approach-dropdown", "value"),
        State("monte-carlo-iterations", "value"),
        State("measurement-technology-dropdown", "value"),
        State("minimum-detection-limit-input", "value"),
        State("simulation-start-date-picker", "date"),
        State("simulation-end-date-picker", "date"),
        State("consider-wind-dropdown", "value"),
        State("stored-producing-hours", "data"),
        State("stored-emission-characteristics", "data"),
        State("stored-wind-data", "data"),
        State("stored-leak-data", "data"),
        State("stored-fitted-distributions", "data"),
        State("section-results-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def run_simulation_callback(
    n_clicks,
    events_data,
    processing_resolution,
    estimation_approach,
    monte_carlo_iterations,
    measurement_technology,
    minimum_detection_limit,
    start_date,
    end_date,
    consider_wind,
    producing_hours_data,
    emission_char_data,
    wind_data_store,
    leak_data_store,
    fitted_distributions_store,
    results_button_clicks,
):
    if n_clicks == 0:
        raise PreventUpdate

    # Debug: Show that callback was triggered
    print(f"Simulation callback triggered. Approach: {estimation_approach}, Clicks: {n_clicks}")

    if events_data is None:
        error_msg = html.Div(
            [
                html.P(
                    "Please convert data to emission event model first (go to Loading Emissions Data section)",
                    style={"color": "#e74c3c", "fontWeight": "bold"},
                )
            ]
        )
        return (
            None,
            error_msg,
            results_button_clicks or 0,
        )

    # Use default iterations if not provided
    if monte_carlo_iterations is None:
        monte_carlo_iterations = 10

    # Handle multiple technologies selection (only needed for below_MDL)
    # Convert to list if single value (for backward compatibility)
    if estimation_approach == "below_MDL":
        # Only validate measurement technology for below_MDL approach
        if measurement_technology is None:
            return (
                None,
                html.Div(
                    [
                        html.P(
                            "Please select at least one measurement technology",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                results_button_clicks or 0,
            )

        if not isinstance(measurement_technology, list):
            technologies_list = [measurement_technology]
        else:
            technologies_list = measurement_technology

        # Validate that at least one technology is selected
        if len(technologies_list) == 0:
            return (
                None,
                html.Div(
                    [
                        html.P(
                            "Please select at least one measurement technology",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                results_button_clicks or 0,
            )
    else:
        # For bootstrap approach, measurement technology is not needed
        technologies_list = []


    # Determine if using minimum detection limit or measurement technology
    mdl_value = None
    tech_value = None

    # If 'define_technology' is selected, extract MDL value.
    # Keep 'define_technology' in the list — simulations.py maps it to 'User Defined' internally.
    if "define_technology" in technologies_list and minimum_detection_limit is not None:
        mdl_value = float(minimum_detection_limit)

    # Convert start date to datetime.datetime object (at midnight)
    start_datetime = None
    if start_date:
        try:
            # Parse the date (format: YYYY-MM-DD) and set to midnight
            date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            start_datetime = date_obj.replace(hour=0, minute=0, second=0)
        except ValueError:
            start_datetime = None

    # Convert end date to datetime.datetime object (at end of day)
    end_datetime = None
    if end_date:
        try:
            # Parse the date (format: YYYY-MM-DD) and set to end of day
            date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            end_datetime = date_obj.replace(hour=23, minute=59, second=59)
        except ValueError:
            end_datetime = None

    # Validate that start_time and end_time are provided
    if start_datetime is None or end_datetime is None:
        return (
            None,
            html.Div(
                [
                    html.P(
                        "Please select both start date and end date for the simulation",
                        style={"color": "#e74c3c", "fontWeight": "bold"},
                    )
                ]
            ),
            results_button_clicks or 0,
        )

    # Validate that dates are within a year
    date_diff = (end_datetime - start_datetime).days
    if date_diff < 0:
        return (
            None,
            html.Div(
                [
                    html.P(
                        "End date must be after start date",
                        style={"color": "#e74c3c", "fontWeight": "bold"},
                    )
                ]
            ),
            results_button_clicks or 0,
        )
    if date_diff > 365:
        return (
            None,
            html.Div(
                [
                    html.P(
                        "Simulation period must be within a year (365 days)",
                        style={"color": "#e74c3c", "fontWeight": "bold"},
                    )
                ]
            ),
            results_button_clicks or 0,
        )

    # Extract rate and duration distributions from emission events
    events_df = pd.DataFrame(events_data)

    # Calculate estimated duration based on emission characteristics
    # For continuous: use producing hours from stored-producing-hours
    # For intermittent: calculate average duration from events
    estimated_duration = None
    emission_char = emission_char_data.get("value") if emission_char_data else None

    if emission_char == "continuous":
        # Use producing hours for continuous emissions
        if producing_hours_data and "hours" in producing_hours_data:
            estimated_duration = producing_hours_data["hours"]
    else:
        # For intermittent, calculate average duration from events
        if "duration" in events_df.columns:
            durations = events_df["duration"].dropna()
            if len(durations) > 0:
                estimated_duration = float(durations.mean())

    # Initialize simulation_result to None (will be set in try block)
    simulation_result = None

    # Run simulation based on selected approach
    try:
        if estimation_approach == "below_MDL":
            # Prepare events DataFrame for simulate_below_mdl
            # Need columns: duration, source, start_time, end_time
            # start_time and end_time need to be strings in format "%Y-%m-%d %H:%M:%S"
            events_for_simulation = events_df.copy()

            # Ensure required columns exist
            if "duration" not in events_for_simulation.columns:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                "Missing 'duration' column in emission events.",
                                style={"color": "#e74c3c", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    results_button_clicks or 0,
                )

            # Handle source column (may be named 'sourceLocation' in converted events)
            if "sourceLocation" in events_for_simulation.columns:
                events_for_simulation["source"] = events_for_simulation[
                    "sourceLocation"
                ]
            elif "source" not in events_for_simulation.columns:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                "Missing 'source' or 'sourceLocation' column in emission events.",
                                style={"color": "#e74c3c", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    results_button_clicks or 0,
                )

            # Format start_time and end_time as strings in '%Y-%m-%d %H:%M:%S' format
            def format_datetime_string(dt_value):
                """Convert datetime to string in '%Y-%m-%d %H:%M:%S' format"""
                if isinstance(dt_value, datetime):
                    return dt_value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(dt_value, str):
                    # Handle ISO format strings (with 'T' separator)
                    if "T" in dt_value:
                        # Parse ISO format and reformat
                        try:
                            dt_obj = datetime.fromisoformat(
                                dt_value.replace("Z", "+00:00")
                            )
                            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, AttributeError):
                            # If parsing fails, try to replace T with space
                            return dt_value.replace("T", " ", 1).split(".")[
                                0
                            ]  # Remove microseconds if present
                    else:
                        # Already in correct format or different format, return as is
                        return dt_value
                else:
                    return str(dt_value)

            if "startTime" in events_for_simulation.columns:
                events_for_simulation["start_time"] = events_for_simulation[
                    "startTime"
                ].apply(format_datetime_string)
            elif "start_time" not in events_for_simulation.columns:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                "Missing 'startTime' or 'start_time' column in emission events.",
                                style={"color": "#e74c3c", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    results_button_clicks or 0,
                )

            if "endTime" in events_for_simulation.columns:
                events_for_simulation["end_time"] = events_for_simulation[
                    "endTime"
                ].apply(format_datetime_string)
            elif "end_time" not in events_for_simulation.columns:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                "Missing 'endTime' or 'end_time' column in emission events.",
                                style={"color": "#e74c3c", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    results_button_clicks or 0,
                )

            # Convert consider_wind to boolean
            consider_wind_bool = consider_wind == "yes" if consider_wind else False

            # Get wind speed data if wind is considered
            wind_speed = None
            if consider_wind_bool:
                if wind_data_store and "data" in wind_data_store:
                    wind_data_list = wind_data_store["data"]
                    # Convert wind data list to a single representative value (mean)
                    # probability_of_detection expects a single float value, not a list
                    if isinstance(wind_data_list, list) and len(wind_data_list) > 0:
                        # Convert to float and calculate mean
                        try:
                            wind_speed_values = [float(x) for x in wind_data_list if x is not None and not pd.isna(x)]
                            if len(wind_speed_values) > 0:
                                wind_speed = float(np.mean(wind_speed_values))
                            else:
                                raise ValueError("No valid wind speed values found")
                        except (ValueError, TypeError) as e:
                            return (
                                None,
                                html.Div(
                                    [
                                        html.P(
                                            f"⚠ Error processing wind data: {str(e)}",
                                            style={"color": "#e67e22", "fontWeight": "bold"},
                                        )
                                    ]
                                ),
                                results_button_clicks or 0,
                            )
                    elif isinstance(wind_data_list, (int, float)):
                        # Already a single value
                        wind_speed = float(wind_data_list)
                    else:
                        return (
                            None,
                            html.Div(
                                [
                                    html.P(
                                        "⚠ Wind data format is invalid. Expected a list of values or a single number.",
                                        style={"color": "#e67e22", "fontWeight": "bold"},
                                    )
                                ]
                            ),
                            results_button_clicks or 0,
                        )
                else:
                    return (
                        None,
                        html.Div(
                            [
                                html.P(
                                    "⚠ Wind data is required when 'Consider Wind' is set to 'Yes'. Please upload wind data or use default.",
                                    style={"color": "#e67e22", "fontWeight": "bold"},
                                )
                            ]
                        ),
                        results_button_clicks or 0,
                    )

            # Get leak data if user uploaded their own, otherwise use default (None)
            leak_data = None
            if leak_data_store and "data" in leak_data_store:
                # User has uploaded or selected leak data
                leak_data = leak_data_store["data"]
                # Convert to list if needed (should already be a list)
                if not isinstance(leak_data, list):
                    leak_data = (
                        leak_data.tolist()
                        if hasattr(leak_data, "tolist")
                        else list(leak_data)
                    )

                # Uploaded and bundled leak rates are held in kg/hr, the unit simulate_below_mdl()
                # integrates over hours (the former kg/hr -> g/s conversion here made the Type 1
                # term 3.6 times too small).
                leak_data = [float(x) for x in leak_data]

            # Call simulate_below_mdl
            # Returns total emissions (measured + unmeasured) per site, plus measured and unmeasured separately
            # Use technologies parameter for multiple technologies support
            (total_emissions, total_emissions_lower, total_emissions_upper,
             measured_emissions, measured_emissions_lower, measured_emissions_upper,
             unmeasured_emissions, unmeasured_emissions_lower, unmeasured_emissions_upper) = (
                simulate_below_mdl(
                    events=events_for_simulation,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    mc_iterations=monte_carlo_iterations,
                    technologies=technologies_list,  # Pass list of technologies
                    mdl_define=mdl_value,
                    consider_wind=consider_wind_bool,
                    wind_speed=wind_speed,
                    leak_data=leak_data,
                )
            )

            # Store results for display
            simulation_result = {
                "below_mdl_emissions": total_emissions,  # Total emissions (measured + unmeasured)
                "below_mdl_emissions_lower": total_emissions_lower,
                "below_mdl_emissions_upper": total_emissions_upper,
                "measured_emissions": measured_emissions,
                "measured_emissions_lower": measured_emissions_lower,
                "measured_emissions_upper": measured_emissions_upper,
                "unmeasured_emissions": unmeasured_emissions,
                "unmeasured_emissions_lower": unmeasured_emissions_lower,
                "unmeasured_emissions_upper": unmeasured_emissions_upper,
                "processing_resolution": processing_resolution,
                "estimation_approach": estimation_approach,
                "start_time": start_datetime,
                "end_time": end_datetime,
                "monte_carlo_iterations": monte_carlo_iterations,
                "measurement_technology": technologies_list,  # Store as list
                "minimum_detection_limit": mdl_value,
                "consider_wind": consider_wind,
                "estimated_duration": estimated_duration,
            }

        elif estimation_approach == "bootstrap":
            # Get rates and durations from events
            rates = (
                events_df["rate"].dropna().tolist()
                if "rate" in events_df.columns
                else []
            )
            durations = (
                events_df["duration"].dropna().tolist()
                if "duration" in events_df.columns
                else []
            )

            # Check if continuous emissions with producing hours
            is_continuous = emission_char == "continuous"
            producing_hours_value = None
            if is_continuous:
                if producing_hours_data and "hours" in producing_hours_data:
                    producing_hours_value = producing_hours_data["hours"]
                else:
                    return (
                        None,
                        html.Div(
                            [
                                html.P(
                                    "Continuous emissions selected but producing hours not defined. Please define producing hours in Emissions Event Browser.",
                                    style={"color": "#e74c3c", "fontWeight": "bold"},
                                )
                            ]
                        ),
                        results_button_clicks or 0,
                    )

            # For continuous: only need rates; for intermittent: need both rates and durations
            if len(rates) == 0:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                "No rate data found in emission events. Please check your data.",
                                style={"color": "#e74c3c", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    results_button_clicks or 0,
                )

            if not is_continuous and len(durations) == 0:
                return (
                    None,
                    html.Div(
                        [
                            html.P(
                                "No duration data found in emission events. Please check your data.",
                                style={"color": "#e74c3c", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    results_button_clicks or 0,
                )

            # Check for fitted distributions in stored data
            fitted_distributions = (
                fitted_distributions_store if fitted_distributions_store else None
            )

            # Calculate probability of emission event based on actual data
            # poe = (total hours with events) / (total simulation hours)
            total_sim_hours = (end_datetime - start_datetime).total_seconds() / 3600
            total_event_hours = sum(durations) if not is_continuous else 0
            
            # Calculate probability with bounds (min 0.001, max 0.999 to avoid edge cases)
            if total_sim_hours > 0 and not is_continuous:
                poe = min(max(total_event_hours / total_sim_hours, 0.001), 0.999)
            else:
                # For continuous emissions or if calculation fails, use moderate default
                poe = 0.1
            
            # Prepare distributions
            prob_dist = {"UNKNOWN": poe}
            rate_dist = {"UNKNOWN": rates}
            duration_dist = (
                {"UNKNOWN": durations} if not is_continuous else {"UNKNOWN": []}
            )  # Not used for continuous

            # Extract fitted distributions if available
            fitted_rate_dist = None
            fitted_duration_dist = None
            if fitted_distributions:
                fitted_rate_dist = fitted_distributions.get("rate")
                if not is_continuous:
                    fitted_duration_dist = fitted_distributions.get("duration")

            # Call extrapolation
            extrapolation_results = extrapolation(
                prob_dist,
                rate_dist,
                duration_dist,
                start_datetime,
                end_datetime,
                monte_carlo_iterations,
                fitted_rate_dist=fitted_rate_dist,
                fitted_duration_dist=fitted_duration_dist,
                is_continuous=is_continuous,
                producing_hours=producing_hours_value,
            )

            # Store results for display
            simulation_result = {
                "extrapolation_results": extrapolation_results,
                "processing_resolution": processing_resolution,
                "estimation_approach": estimation_approach,
                "start_time": start_datetime,
                "end_time": end_datetime,
                "monte_carlo_iterations": monte_carlo_iterations,
                "measurement_technology": technologies_list,  # Store as list for consistency
                "minimum_detection_limit": mdl_value,
                "consider_wind": consider_wind,
                "estimated_duration": estimated_duration,
            }
        else:
            return (
                None,
                html.Div(
                    [
                        html.P(
                            f"Unknown estimation approach: {estimation_approach}",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                results_button_clicks or 0,
            )

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"Simulation error: {str(e)}")
        print(f"Traceback: {error_details}")
        return (
            None,
            html.Div(
                [
                    html.P(
                        f"Error running simulation: {str(e)}",
                        style={"color": "#e74c3c", "fontWeight": "bold"},
                    ),
                    html.Details(
                        [
                            html.Summary("Error Details (click to expand)"),
                            html.Pre(
                                error_details,
                                style={
                                    "backgroundColor": "#f8f9fa",
                                    "padding": "10px",
                                    "borderRadius": "5px",
                                    "fontSize": "12px",
                                    "overflow": "auto",
                                    "maxHeight": "300px",
                                },
                            ),
                        ],
                        style={"marginTop": "10px"},
                    ),
                ]
            ),
            results_button_clicks or 0,
        )

    # Check if simulation_result was set (should always be set if we reach here)
    if simulation_result is None:
        error_msg = html.Div(
            [
                html.P(
                    f"Simulation completed but no results were generated. Estimation approach: '{estimation_approach}'. Please check your inputs and try again.",
                    style={"color": "#e74c3c", "fontWeight": "bold"},
                ),
                html.P(
                    f"Debug info: events_data={'present' if events_data else 'None'}, estimation_approach={estimation_approach}",
                    style={"color": "#7f8c8d", "fontSize": "12px", "marginTop": "10px"},
                ),
            ]
        )
        print(f"Simulation result is None. Estimation approach: {estimation_approach}")
        return (
            None,
            error_msg,
            results_button_clicks or 0,
        )

    # Store results and show success message, then navigate to results page
    # Convert datetime objects to strings for JSON serialization
    simulation_result_serializable = simulation_result.copy()
    if isinstance(simulation_result_serializable.get("start_time"), datetime):
        simulation_result_serializable["start_time"] = simulation_result_serializable[
            "start_time"
        ].isoformat()
    if isinstance(simulation_result_serializable.get("end_time"), datetime):
        simulation_result_serializable["end_time"] = simulation_result_serializable[
            "end_time"
        ].isoformat()

    # Update status message to show completion (replace the running message)
    completion_status_message = html.Div(
        [
            html.Div(
                [
                    html.H4(
                        "✓ Simulation Completed Successfully!",
                        style={
                            "color": "#27ae60",
                            "marginBottom": "10px",
                            "fontSize": "18px",
                            "fontWeight": "bold",
                        },
                    ),
                    html.P(
                        "Redirecting to Results page...",
                        style={"color": "#2c3e50", "fontSize": "14px"},
                    ),
                ],
                style={
                    "padding": "15px",
                    "backgroundColor": "#d5f4e6",
                    "borderRadius": "8px",
                    "border": "1px solid #27ae60",
                },
            )
        ]
    )

    # Trigger navigation to results page by incrementing results button clicks
    return (
        simulation_result_serializable,
        completion_status_message,
        (results_button_clicks or 0) + 1,
    )


def _build_summary_cards(simulation_result):
    """Build KPI summary cards row for the results dashboard."""
    estimation_approach = simulation_result.get("estimation_approach")
    cards = []

    if estimation_approach == "bootstrap":
        extrapolation_results = simulation_result.get("extrapolation_results", {})
        all_emissions = []
        for key, emissions_list in extrapolation_results.items():
            if len(emissions_list) > 0:
                all_emissions.extend(emissions_list)

        if len(all_emissions) > 0:
            arr = np.array(all_emissions)
            median_val = np.median(arr)
            lower_ci = np.percentile(arr, 2.5)
            upper_ci = np.percentile(arr, 97.5)
            std_val = np.std(arr)
            n_iter = simulation_result.get("monte_carlo_iterations", "N/A")

            cards = [
                html.Div([
                    html.P("Median Emissions", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                    html.P(f"{median_val:,.2f} kg", style={"fontSize": "24px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
                ], style=get_summary_card_style("#e67e22")),
                html.Div([
                    html.P("95% Confidence Interval", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                    html.P(f"[{lower_ci:,.2f}, {upper_ci:,.2f}] kg", style={"fontSize": "18px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
                ], style=get_summary_card_style("#3498db")),
                html.Div([
                    html.P("Std Deviation", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                    html.P(f"{std_val:,.2f} kg", style={"fontSize": "24px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
                ], style=get_summary_card_style("#95a5a6")),
                html.Div([
                    html.P("MC Iterations", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                    html.P(f"{n_iter}", style={"fontSize": "24px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
                ], style=get_summary_card_style("#9b59b6")),
            ]

    elif estimation_approach == "below_MDL":
        total_emissions = simulation_result.get("below_mdl_emissions")
        total_lower = simulation_result.get("below_mdl_emissions_lower")
        total_upper = simulation_result.get("below_mdl_emissions_upper")
        measured = simulation_result.get("measured_emissions")
        unmeasured = simulation_result.get("unmeasured_emissions")
        n_iter = simulation_result.get("monte_carlo_iterations", "N/A")

        ci_text = "N/A"
        if total_lower is not None and total_upper is not None:
            ci_text = f"[{total_lower:,.2f}, {total_upper:,.2f}] kg"

        cards = [
            html.Div([
                html.P("Total Emissions", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                html.P(f"{total_emissions:,.2f} kg" if total_emissions is not None else "N/A",
                       style={"fontSize": "24px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
                html.P(ci_text, style={"fontSize": "12px", "color": "#7f8c8d", "margin": "0"}),
            ], style=get_summary_card_style("#e67e22")),
            html.Div([
                html.P("Measured Emissions", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                html.P(f"{measured:,.2f} kg" if measured is not None else "N/A",
                       style={"fontSize": "24px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
            ], style=get_summary_card_style("#27ae60")),
            html.Div([
                html.P("Unmeasured Emissions", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                html.P(f"{unmeasured:,.2f} kg" if unmeasured is not None else "N/A",
                       style={"fontSize": "24px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
            ], style=get_summary_card_style("#e74c3c")),
            html.Div([
                html.P("MC Iterations", style={"color": "#7f8c8d", "fontSize": "13px", "marginBottom": "5px"}),
                html.P(f"{n_iter}", style={"fontSize": "24px", "fontWeight": "bold", "color": "#2c3e50", "margin": "0"}),
            ], style=get_summary_card_style("#9b59b6")),
        ]

    if not cards:
        return html.Div()

    return html.Div(cards, style={
        "display": "flex", "gap": "15px", "flexWrap": "wrap", "marginBottom": "25px",
    })


def _build_charts(simulation_result):
    """Build distribution analysis charts."""
    estimation_approach = simulation_result.get("estimation_approach")

    if estimation_approach == "bootstrap":
        extrapolation_results = simulation_result.get("extrapolation_results", {})
        all_emissions = []
        for key, emissions_list in extrapolation_results.items():
            if len(emissions_list) > 0:
                all_emissions.extend(emissions_list)

        if len(all_emissions) == 0:
            return html.P("No bootstrap data available.", style={"color": "#7f8c8d", "fontStyle": "italic"})

        arr = np.array(all_emissions)
        mean_val = np.mean(arr)
        median_val = np.median(arr)
        p2_5 = np.percentile(arr, 2.5)
        p97_5 = np.percentile(arr, 97.5)

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=all_emissions, nbinsx=40,
            name="Emission Distribution", marker_color="#3498db", opacity=0.7,
        ))
        fig.add_vline(x=mean_val, line_dash="dash", line_color="red",
                      annotation_text=f"Mean: {mean_val:,.2f}", annotation_position="top right")
        fig.add_vline(x=median_val, line_dash="solid", line_color="orange",
                      annotation_text=f"Median: {median_val:,.2f}", annotation_position="top left")
        fig.add_vline(x=p2_5, line_dash="dot", line_color="green",
                      annotation_text=f"P2.5: {p2_5:,.2f}", annotation_position="bottom right")
        fig.add_vline(x=p97_5, line_dash="dot", line_color="green",
                      annotation_text=f"P97.5: {p97_5:,.2f}", annotation_position="bottom left")
        fig.update_layout(
            title="Distribution of Extrapolated Emissions",
            xaxis_title="Total Emissions (kg)", yaxis_title="Frequency",
            height=450, showlegend=False,
            margin=dict(l=50, r=50, t=60, b=50),
        )
        return html.Div([dcc.Graph(figure=fig)])

    elif estimation_approach == "below_MDL":
        measured = simulation_result.get("measured_emissions")
        unmeasured = simulation_result.get("unmeasured_emissions")
        total = simulation_result.get("below_mdl_emissions")
        if measured is None or unmeasured is None:
            return html.P("No below-MDL data available.", style={"color": "#7f8c8d", "fontStyle": "italic"})

        # Horizontal stacked bar
        bar_fig = go.Figure()
        bar_fig.add_trace(go.Bar(
            y=["Emissions"], x=[measured], name="Measured", orientation="h",
            marker_color="#27ae60", text=[f"{measured:,.2f} kg"], textposition="inside",
        ))
        bar_fig.add_trace(go.Bar(
            y=["Emissions"], x=[unmeasured], name="Unmeasured", orientation="h",
            marker_color="#e74c3c", text=[f"{unmeasured:,.2f} kg"], textposition="inside",
        ))
        bar_fig.update_layout(
            barmode="stack", title="Measured vs Unmeasured Emissions",
            xaxis_title="Emissions (kg)", height=250,
            margin=dict(l=50, r=50, t=60, b=50), legend=dict(orientation="h", y=-0.2),
        )

        return html.Div([
            dcc.Graph(figure=bar_fig),
        ])

    return html.Div()


def _build_statistics_table(simulation_result):
    """Build a detailed statistics HTML table."""
    estimation_approach = simulation_result.get("estimation_approach")

    header_style = {
        "padding": "10px 14px", "border": "1px solid #ddd",
        "backgroundColor": "#f2f2f2", "textAlign": "left",
        "fontWeight": "bold", "fontSize": "13px",
    }
    cell_style = {
        "padding": "10px 14px", "border": "1px solid #ddd",
        "fontSize": "13px",
    }

    rows = []

    if estimation_approach == "bootstrap":
        extrapolation_results = simulation_result.get("extrapolation_results", {})
        all_emissions = []
        for key, emissions_list in extrapolation_results.items():
            if len(emissions_list) > 0:
                all_emissions.extend(emissions_list)

        if len(all_emissions) == 0:
            return html.P("No statistics available.", style={"color": "#7f8c8d"})

        arr = np.array(all_emissions)
        stats = [
            ("Mean", f"{np.mean(arr):,.2f} kg"),
            ("Median", f"{np.median(arr):,.2f} kg"),
            ("Std Deviation", f"{np.std(arr):,.2f} kg"),
            ("CV %", f"{(np.std(arr) / np.mean(arr) * 100):,.1f}%" if np.mean(arr) != 0 else "N/A"),
            ("95% CI Lower", f"{np.percentile(arr, 2.5):,.2f} kg"),
            ("95% CI Upper", f"{np.percentile(arr, 97.5):,.2f} kg"),
        ]
        for label, value in stats:
            rows.append(html.Tr([
                html.Td(label, style=header_style),
                html.Td(value, style=cell_style),
            ]))

    elif estimation_approach == "below_MDL":
        total = simulation_result.get("below_mdl_emissions")
        total_lower = simulation_result.get("below_mdl_emissions_lower")
        total_upper = simulation_result.get("below_mdl_emissions_upper")
        measured = simulation_result.get("measured_emissions")
        measured_lower = simulation_result.get("measured_emissions_lower")
        measured_upper = simulation_result.get("measured_emissions_upper")
        unmeasured = simulation_result.get("unmeasured_emissions")
        unmeasured_lower = simulation_result.get("unmeasured_emissions_lower")
        unmeasured_upper = simulation_result.get("unmeasured_emissions_upper")

        def _fmt(v):
            return f"{v:,.2f} kg" if v is not None else "N/A"

        def _ci(lo, hi):
            if lo is not None and hi is not None:
                return f"[{lo:,.2f}, {hi:,.2f}] kg"
            return "N/A"

        pct_measured = "N/A"
        if measured is not None and total is not None and total != 0:
            pct_measured = f"{(measured / total * 100):,.1f}%"

        stats = [
            ("Total Emissions", _fmt(total)),
            ("Total 95% CI", _ci(total_lower, total_upper)),
            ("Measured Emissions", _fmt(measured)),
            ("Measured 95% CI", _ci(measured_lower, measured_upper)),
            ("Unmeasured Emissions", _fmt(unmeasured)),
            ("Unmeasured 95% CI", _ci(unmeasured_lower, unmeasured_upper)),
            ("% Measured", pct_measured),
        ]
        for label, value in stats:
            rows.append(html.Tr([
                html.Td(label, style=header_style),
                html.Td(value, style=cell_style),
            ]))

    if not rows:
        return html.P("No statistics available.", style={"color": "#7f8c8d"})

    return html.Div([
        html.Table([html.Tbody(rows)], style={
            "width": "100%", "borderCollapse": "collapse", "border": "1px solid #ddd",
        })
    ])


def _build_metadata_display(simulation_result):
    """Build simulation configuration metadata display."""
    approach_names = {
        "below_MDL": "Simulate Below Detection Limit",
        "bootstrap": "Bootstrap For Unmeasured Emissions",
    }
    estimation_approach = simulation_result.get("estimation_approach")
    approach_name = approach_names.get(estimation_approach, estimation_approach or "N/A")

    start_time = simulation_result.get("start_time")
    end_time = simulation_result.get("end_time")
    for dt_str_attr in [start_time, end_time]:
        pass  # we format inline below

    def _fmt_dt(val):
        if isinstance(val, str):
            try:
                val = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return str(val)
        if isinstance(val, datetime):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        return str(val) if val else "N/A"

    # Measurement technology
    measurement_tech = simulation_result.get("measurement_technology")
    if isinstance(measurement_tech, list):
        tech_display = ", ".join(measurement_tech)
    elif measurement_tech:
        tech_display = str(measurement_tech)
    else:
        mdl = simulation_result.get("minimum_detection_limit")
        tech_display = f"Custom MDL: {mdl} kg/hr" if mdl else "N/A"

    items = [
        ("Approach", approach_name),
        ("Processing Resolution", simulation_result.get("processing_resolution", "N/A")),
        ("Start Time", _fmt_dt(start_time)),
        ("End Time", _fmt_dt(end_time)),
        ("MC Iterations", str(simulation_result.get("monte_carlo_iterations", "N/A"))),
        ("Measurement Technology", tech_display),
    ]

    if estimation_approach == "below_MDL":
        wind = simulation_result.get("consider_wind")
        if wind:
            items.append(("Consider Wind", "Yes" if wind == "yes" else "No"))
    elif estimation_approach == "bootstrap":
        dur = simulation_result.get("estimated_duration")
        if dur:
            items.append(("Estimated Duration", f"{dur} hours"))

    label_style = {"fontWeight": "bold", "color": "#2c3e50", "minWidth": "180px", "fontSize": "14px"}
    value_style = {"color": "#34495e", "fontSize": "14px"}

    rows = []
    for label, value in items:
        rows.append(html.Div([
            html.Span(f"{label}:", style=label_style),
            html.Span(str(value), style=value_style),
        ], style={"display": "flex", "gap": "10px", "padding": "8px 0", "borderBottom": "1px solid #f0f0f0"}))

    return html.Div(rows)


@app.callback(
    [
        Output("results-summary-cards", "children"),
        Output("results-charts-container", "children"),
        Output("results-statistics-table", "children"),
        Output("results-metadata-display", "children"),
        Output("simulation-results-display", "children"),
    ],
    [
        Input("section-content", "children"),
        Input("stored-simulation-results", "data"),
        Input("section-results-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def display_simulation_results(
    section_content, simulation_results, results_button_clicks
):
    """Display simulation results across the four dashboard sections."""
    empty = html.Div()
    no_data_msg = html.P(
        "No simulation results available. Please run a simulation first.",
        style={"color": "#7f8c8d", "fontStyle": "italic", "textAlign": "center", "padding": "40px"},
    )

    if simulation_results is None:
        return no_data_msg, empty, empty, empty, empty

    return (
        _build_summary_cards(simulation_results),
        _build_charts(simulation_results),
        _build_statistics_table(simulation_results),
        _build_metadata_display(simulation_results),
        empty,
    )


@app.callback(
    [
        Output("stored-bottomup-inventory", "data"),
        Output("bottomup-comparison-chart", "children"),
    ],
    [Input("add-bottomup-button", "n_clicks")],
    [
        State("bottomup-emissions-input", "value"),
        State("bottomup-lower-uncertainty-input", "value"),
        State("bottomup-upper-uncertainty-input", "value"),
        State("stored-simulation-results", "data"),
        State("stored-bottomup-inventory", "data"),
    ],
    prevent_initial_call=True,
)
def handle_bottomup_inventory(
    n_clicks,
    emissions_value,
    lower_uncertainty,
    upper_uncertainty,
    simulation_results,
    existing_bottomup,
):
    """Handle bottom-up inventory input and create comparison chart"""
    if n_clicks == 0:
        raise PreventUpdate

    # Validate inputs
    if emissions_value is None or emissions_value <= 0:
        return existing_bottomup, html.Div(
            [
                html.P(
                    "Please enter a valid emissions value (kg).",
                    style={
                        "color": "#e74c3c",
                        "fontStyle": "italic",
                        "marginTop": "10px",
                    },
                )
            ]
        )

    if lower_uncertainty is None:
        lower_uncertainty = 0
    if upper_uncertainty is None:
        upper_uncertainty = 0

    # Store bottom-up inventory data
    bottomup_data = {
        "emissions": float(emissions_value),
        "lower_uncertainty_pct": float(lower_uncertainty),
        "upper_uncertainty_pct": float(upper_uncertainty),
    }

    # Calculate uncertainty bounds in kg
    lower_bound = emissions_value * (1 - lower_uncertainty / 100)
    upper_bound = emissions_value * (1 + upper_uncertainty / 100)
    bottomup_data["lower_bound"] = lower_bound
    bottomup_data["upper_bound"] = upper_bound

    # Create comparison chart if simulation results exist
    if simulation_results is None:
        return bottomup_data, html.Div(
            [
                html.P(
                    "Bottom-up inventory saved. Run a simulation to see comparison.",
                    style={
                        "color": "#27ae60",
                        "fontStyle": "italic",
                        "marginTop": "10px",
                    },
                )
            ]
        )

    # Extract simulation result value
    estimation_approach = simulation_results.get("estimation_approach")
    simulation_value = None
    simulation_lower = None
    simulation_upper = None

    if estimation_approach == "below_MDL":
        simulation_value = simulation_results.get("below_mdl_emissions")
        simulation_lower = simulation_results.get("below_mdl_emissions_lower")
        simulation_upper = simulation_results.get("below_mdl_emissions_upper")
    elif estimation_approach == "bootstrap":
        extrapolation_results = simulation_results.get("extrapolation_results", {})
        if extrapolation_results:
            # Get the first key's emissions list (or combine all)
            all_emissions = []
            for key, emissions_list in extrapolation_results.items():
                if isinstance(emissions_list, list):
                    all_emissions.extend(emissions_list)

            if all_emissions:
                simulation_value = np.median(all_emissions)
                simulation_lower = np.percentile(all_emissions, 2.5)  # 95% CI lower
                simulation_upper = np.percentile(all_emissions, 97.5)  # 95% CI upper

    if simulation_value is None:
        return bottomup_data, html.Div(
            [
                html.P(
                    "Bottom-up inventory saved. Simulation results do not contain valid emission values.",
                    style={
                        "color": "#e67e22",
                        "fontStyle": "italic",
                        "marginTop": "10px",
                    },
                )
            ]
        )

    # Create comparison bar chart
    fig = go.Figure()

    # Bottom-up inventory bar with error bars
    fig.add_trace(
        go.Bar(
            x=["Emissions Comparison"],
            y=[bottomup_data["emissions"]],
            name="Bottom-Up Inventory",
            marker_color="#e67e22",
            error_y=dict(
                type="data",
                symmetric=False,
                array=[upper_bound - bottomup_data["emissions"]],
                arrayminus=[bottomup_data["emissions"] - lower_bound],
            ),
            text=[f"{bottomup_data['emissions']:.2f} kg"],
            textposition="outside",
            showlegend=True,
        )
    )

    # Simulation results bar with error bars
    if simulation_lower is not None and simulation_upper is not None:
        fig.add_trace(
            go.Bar(
                x=["Emissions Comparison"],
                y=[simulation_value],
                name="Simulation Results",
                marker_color="#3498db",
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=[simulation_upper - simulation_value],
                    arrayminus=[simulation_value - simulation_lower],
                ),
                text=[f"{simulation_value:.2f} kg"],
                textposition="outside",
                showlegend=True,
            )
        )
    else:
        fig.add_trace(
            go.Bar(
                x=["Emissions Comparison"],
                y=[simulation_value],
                name="Simulation Results",
                marker_color="#3498db",
                text=[f"{simulation_value:.2f} kg"],
                textposition="outside",
                showlegend=True,
            )
        )

    fig.update_layout(
        title="Comparison: Bottom-Up Inventory vs Simulation Results",
        xaxis_title="",
        yaxis_title="Emissions (kg)",
        height=500,
        showlegend=True,
        barmode="group",
        yaxis=dict(rangemode="tozero"),
    )

    return bottomup_data, html.Div(
        [
            html.P(
                "Bottom-up inventory added successfully!",
                style={
                    "color": "#27ae60",
                    "fontWeight": "bold",
                    "marginTop": "10px",
                    "marginBottom": "15px",
                },
            ),
            dcc.Graph(figure=fig),
        ]
    )


@app.callback(
    Output("bottomup-comparison-chart", "children", allow_duplicate=True),
    [Input("stored-simulation-results", "data")],
    [State("stored-bottomup-inventory", "data")],
    prevent_initial_call=True,
)
def update_comparison_chart_on_simulation_change(simulation_results, bottomup_data):
    """Update comparison chart when simulation results change and bottom-up inventory exists"""
    if bottomup_data is None or simulation_results is None:
        raise PreventUpdate

    # Extract simulation result value
    estimation_approach = simulation_results.get("estimation_approach")
    simulation_value = None
    simulation_lower = None
    simulation_upper = None

    if estimation_approach == "below_MDL":
        simulation_value = simulation_results.get("below_mdl_emissions")
        simulation_lower = simulation_results.get("below_mdl_emissions_lower")
        simulation_upper = simulation_results.get("below_mdl_emissions_upper")
    elif estimation_approach == "bootstrap":
        extrapolation_results = simulation_results.get("extrapolation_results", {})
        if extrapolation_results:
            # Get the first key's emissions list (or combine all)
            all_emissions = []
            for key, emissions_list in extrapolation_results.items():
                if isinstance(emissions_list, list):
                    all_emissions.extend(emissions_list)

            if all_emissions:
                simulation_value = np.median(all_emissions)
                simulation_lower = np.percentile(all_emissions, 2.5)  # 95% CI lower
                simulation_upper = np.percentile(all_emissions, 97.5)  # 95% CI upper

    if simulation_value is None:
        raise PreventUpdate

    # Create comparison bar chart
    fig = go.Figure()

    # Bottom-up inventory bar with error bars
    emissions = bottomup_data["emissions"]
    lower_bound = bottomup_data.get("lower_bound", emissions)
    upper_bound = bottomup_data.get("upper_bound", emissions)

    fig.add_trace(
        go.Bar(
            x=["Emissions Comparison"],
            y=[emissions],
            name="Bottom-Up Inventory",
            marker_color="#e67e22",
            error_y=dict(
                type="data",
                symmetric=False,
                array=[upper_bound - emissions],
                arrayminus=[emissions - lower_bound],
            ),
            text=[f"{emissions:.2f} kg"],
            textposition="outside",
            showlegend=True,
        )
    )

    # Simulation results bar with error bars
    if simulation_lower is not None and simulation_upper is not None:
        fig.add_trace(
            go.Bar(
                x=["Emissions Comparison"],
                y=[simulation_value],
                name="Simulation Results",
                marker_color="#3498db",
                error_y=dict(
                    type="data",
                    symmetric=False,
                    array=[simulation_upper - simulation_value],
                    arrayminus=[simulation_value - simulation_lower],
                ),
                text=[f"{simulation_value:.2f} kg"],
                textposition="outside",
                showlegend=True,
            )
        )
    else:
        fig.add_trace(
            go.Bar(
                x=["Emissions Comparison"],
                y=[simulation_value],
                name="Simulation Results",
                marker_color="#3498db",
                text=[f"{simulation_value:.2f} kg"],
                textposition="outside",
                showlegend=True,
            )
        )

    fig.update_layout(
        title="Comparison: Bottom-Up Inventory vs Simulation Results",
        xaxis_title="",
        yaxis_title="Emissions (kg)",
        height=500,
        showlegend=True,
        barmode="group",
        yaxis=dict(rangemode="tozero"),
    )

    return dcc.Graph(figure=fig)


@app.callback(
    Output("uncertainty-source-dropdown", "options"), [Input("stored-events", "data")]
)
def update_uncertainty_source_dropdown(events_data):
    """Update source dropdown options from stored emission events"""
    if events_data is None or len(events_data) == 0:
        return []

    events_df = pd.DataFrame(events_data)

    # Get unique sources from sourceLocation column
    if "sourceLocation" in events_df.columns:
        sources = events_df["sourceLocation"].dropna().unique().tolist()
    elif "source" in events_df.columns:
        sources = events_df["source"].dropna().unique().tolist()
    else:
        return []

    # Create dropdown options
    options = [{"label": source, "value": source} for source in sorted(sources)]
    return options


@app.callback(
    Output("stored-emission-characteristics", "data"),
    [Input("emission-characteristics-dropdown", "value")],
)
def store_emission_characteristics(emission_char):
    """Store emission characteristics selection for use by other callbacks"""
    return {"value": emission_char} if emission_char else None


@app.callback(
    [
        Output("producing-hours-status", "children"),
        Output("stored-producing-hours", "data"),
    ],
    [Input("confirm-producing-hours-button", "n_clicks")],
    [State("producing-hours-input", "value")],
)
def confirm_producing_hours(n_clicks, producing_hours):
    """Store producing hours when user confirms"""
    if n_clicks == 0:
        return html.Div(), None

    # Validate input
    if producing_hours is None:
        return html.Div(
            [
                html.P(
                    "Please enter producing hours.",
                    style={"color": "#e74c3c", "fontWeight": "bold"},
                )
            ]
        ), None

    if producing_hours < 0 or producing_hours > 8760:
        return html.Div(
            [
                html.P(
                    "Producing hours must be between 0 and 8760.",
                    style={"color": "#e74c3c", "fontWeight": "bold"},
                )
            ]
        ), None

    # Store the value
    producing_hours_data = {"hours": producing_hours}

    status = html.Div(
        [
            html.P(
                f"✓ Producing hours confirmed: {producing_hours} hours",
                style={"color": "#27ae60", "fontWeight": "bold"},
            )
        ]
    )

    return status, producing_hours_data


@app.callback(
    [
        Output("duration-uncertainty-method-container", "style"),
        Output("manual-leak-production-rate-container", "style"),
        Output("estimate-duration-container", "style"),
    ],
    [
        Input("consider-duration-uncertainty-dropdown", "value"),
        Input("duration-uncertainty-method-dropdown", "value"),
    ],
)
def toggle_duration_uncertainty_ui(consider_uncertainty, method):
    """Show/hide duration uncertainty UI elements based on user selections"""
    # Show method dropdown if uncertainty is considered
    if consider_uncertainty == "yes":
        method_style = {"marginTop": "20px", "display": "block"}
        # Show manual input only if manual method is selected
        if method == "manual":
            manual_style = {"marginTop": "20px", "display": "block"}
        else:
            manual_style = {"marginTop": "20px", "display": "none"}
        # Show estimate duration button
        estimate_style = {"marginTop": "20px", "display": "block"}
    else:
        method_style = {"marginTop": "20px", "display": "none"}
        manual_style = {"marginTop": "20px", "display": "none"}
        estimate_style = {"marginTop": "20px", "display": "none"}

    return method_style, manual_style, estimate_style


@app.callback(
    Output("estimate-duration-button", "disabled"),
    [
        Input("duration-uncertainty-method-dropdown", "value"),
        Input("manual-leak-production-rate-input", "value"),
    ],
)
def toggle_estimate_duration_button(method, manual_rate):
    """Enable/disable estimate duration button based on manual input"""
    if method == "manual":
        # Disable if no manual rate provided
        return manual_rate is None or manual_rate == ""
    return False


@app.callback(
    [
        Output("uncertainty-chart-container", "children"),
        Output("uncertainty-events-table-container", "children"),
    ],
    [
        Input("uncertainty-source-dropdown", "value"),
        Input("consider-duration-uncertainty-dropdown", "value"),
        Input("duration-uncertainty-method-dropdown", "value"),
        Input("manual-leak-production-rate-input", "value"),
        Input("stored-duration-simulation-results", "data"),
        Input("stored-emission-characteristics", "data"),
    ],
    [State("stored-events", "data"), State("stored-data", "data")],
)
def plot_uncertainty_events(
    selected_source,
    consider_uncertainty,
    uncertainty_method,
    manual_rate,
    simulation_results,
    emission_char_data,
    events_data,
    loaded_data,
):
    """Plot emission events over time for selected source"""
    if events_data is None or len(events_data) == 0:
        return html.Div(
            [
                html.P(
                    "No emission events data available. Please convert data to emission events first.",
                    style={"color": "#7f8c8d", "fontStyle": "italic"},
                )
            ]
        ), html.Div()

    # Check if continuous is selected - if so, don't require source selection
    emission_char = emission_char_data.get("value") if emission_char_data else None
    is_continuous = emission_char == "continuous"

    if selected_source is None and not is_continuous:
        return html.Div(
            [
                html.P(
                    "Please select a source to view events.",
                    style={"color": "#7f8c8d", "fontStyle": "italic"},
                )
            ]
        ), html.Div()

    # For continuous emissions, don't show chart if no source is selected
    if selected_source is None and is_continuous:
        return html.Div(), html.Div()

    # If duration uncertainty is considered, only show plot if simulation is completed
    # Otherwise, show plot with original events
    if consider_uncertainty == "yes":
        if simulation_results is None or len(simulation_results) == 0:
            return html.Div(
                [
                    html.P(
                        "Please run duration uncertainty estimation first, or select 'No' for duration uncertainty.",
                        style={"color": "#7f8c8d", "fontStyle": "italic"},
                    )
                ]
            ), html.Div()

    events_df = pd.DataFrame(events_data)

    # Filter events by selected source
    source_col = "sourceLocation" if "sourceLocation" in events_df.columns else "source"
    if source_col not in events_df.columns:
        return html.Div(
            [
                html.P(
                    "Source column not found in emission events data.",
                    style={"color": "#e74c3c", "fontWeight": "bold"},
                )
            ]
        ), html.Div()

    filtered_events = events_df[events_df[source_col] == selected_source].copy()

    if len(filtered_events) == 0:
        return html.Div(
            [
                html.P(
                    f"No events found for source: {selected_source}",
                    style={"color": "#7f8c8d", "fontStyle": "italic"},
                )
            ]
        ), html.Div()

    # Merge simulation results if available
    if consider_uncertainty == "yes" and simulation_results is not None:
        sim_df = pd.DataFrame(simulation_results)
        # Merge on event ID or index
        if "id" in sim_df.columns:
            filtered_events = filtered_events.merge(
                sim_df[
                    [
                        "id",
                        "simulated_duration",
                        "simulated_duration_lower",
                        "simulated_duration_upper",
                    ]
                ],
                on="id",
                how="left",
            )
        else:
            # If no ID column, merge by index (assuming same order)
            filtered_events = pd.concat(
                [
                    filtered_events.reset_index(drop=True),
                    sim_df[
                        [
                            "simulated_duration",
                            "simulated_duration_lower",
                            "simulated_duration_upper",
                        ]
                    ].reset_index(drop=True),
                ],
                axis=1,
            )

    # Prepare data for plotting
    plot_data = []

    for idx, row in filtered_events.iterrows():
        start_time = row.get("startTime")
        end_time = row.get("endTime")
        rate = row.get("rate")
        event_id = row.get("id", f"Event-{idx}")

        if pd.notna(start_time) and pd.notna(rate):
            try:
                # Convert startTime to datetime if it's a string
                if isinstance(start_time, str):
                    start_dt = pd.to_datetime(start_time)
                else:
                    start_dt = start_time

                # Convert endTime to datetime if available
                if pd.notna(end_time):
                    if isinstance(end_time, str):
                        end_dt = pd.to_datetime(end_time)
                    else:
                        end_dt = end_time
                else:
                    # If no endTime, use startTime + 1 hour as default
                    end_dt = start_dt + pd.Timedelta(hours=1)

                rate_val = float(rate)
                rate_lower = rate_val * 0.8  # rate - 20%
                rate_upper = rate_val * 1.2  # rate + 20%

                # Use simulated duration if available, otherwise use calculated duration
                if consider_uncertainty == "yes" and pd.notna(
                    row.get("simulated_duration")
                ):
                    simulated_duration = float(row["simulated_duration"])
                    # Calculate new end time based on simulated duration
                    end_dt = start_dt + pd.Timedelta(hours=simulated_duration)
                    duration_hours = simulated_duration
                    duration_lower = float(
                        row.get("simulated_duration_lower", simulated_duration)
                    )
                    duration_upper = float(
                        row.get("simulated_duration_upper", simulated_duration)
                    )
                else:
                    duration_hours = (end_dt - start_dt).total_seconds() / 3600
                    duration_lower = duration_hours
                    duration_upper = duration_hours

                plot_data.append(
                    {
                        "start_datetime": start_dt,
                        "end_datetime": end_dt,
                        "rate": rate_val,
                        "rate_lower": rate_lower,
                        "rate_upper": rate_upper,
                        "event_id": event_id,
                        "duration": duration_hours,
                        "duration_lower": duration_lower,
                        "duration_upper": duration_upper,
                    }
                )
            except (ValueError, TypeError, AttributeError):
                continue

    if len(plot_data) == 0:
        return html.Div(
            [
                html.P(
                    f"No valid time/rate data found for source: {selected_source}",
                    style={"color": "#7f8c8d", "fontStyle": "italic"},
                )
            ]
        ), html.Div()

    # Create plot
    plot_df = pd.DataFrame(plot_data)
    plot_df = plot_df.sort_values("start_datetime")  # Sort by start time

    # Calculate axis limits: ±30 days for x-axis, ±30 kg/hr for y-axis
    min_time = plot_df["start_datetime"].min()
    max_time = plot_df["end_datetime"].max()
    x_min = min_time - pd.Timedelta(days=30)
    x_max = max_time + pd.Timedelta(days=30)

    min_rate = plot_df["rate_lower"].min()
    max_rate = plot_df["rate_upper"].max()
    y_min = max(0, min_rate - 30)  # Don't go below 0
    y_max = max_rate + 30

    fig = go.Figure()

    # Define colors based on uncertainty type
    if consider_uncertainty == "no":
        # Rate uncertainty only - use green color
        rate_fill_color = "#2ecc71"  # Green
        rate_line_color = "#27ae60"  # Darker green
    else:
        # Rate uncertainty with duration uncertainty - use blue for rate
        rate_fill_color = "#3498db"  # Blue
        rate_line_color = "#2980b9"  # Darker blue

    # Duration uncertainty color (red)
    duration_color = "#e74c3c"  # Red

    # Add rectangles (boxes) for each event
    for idx, row in plot_df.iterrows():
        # Create rectangle coordinates
        x0 = row["start_datetime"]
        x1 = row["end_datetime"]
        y0 = row["rate_lower"]
        y1 = row["rate_upper"]

        # Add rectangle shape for rate uncertainty
        fig.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            fillcolor=rate_fill_color,
            opacity=0.5,
            line=dict(color=rate_line_color, width=1),
            layer="below",
        )

        # Add error bars for duration if simulated durations are available
        if (
            consider_uncertainty == "yes"
            and row["duration_lower"] != row["duration_upper"]
        ):
            # Calculate error bar positions for duration uncertainty
            duration_lower_hours = row["duration_lower"]
            duration_upper_hours = row["duration_upper"]
            center_y = row["rate"]

            # Calculate the actual start and end times based on simulated duration
            x_lower = row["start_datetime"] + pd.Timedelta(hours=duration_lower_hours)
            x_upper = row["start_datetime"] + pd.Timedelta(hours=duration_upper_hours)

            # Add horizontal error bar line (for duration uncertainty) - red color
            fig.add_trace(
                go.Scatter(
                    x=[x_lower, x_upper],
                    y=[center_y, center_y],
                    mode="lines",
                    line=dict(color=duration_color, width=2),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            # Add error bar caps (vertical lines at ends)
            cap_height = (
                row["rate_upper"] - row["rate_lower"]
            ) * 0.1  # 10% of rate range
            fig.add_trace(
                go.Scatter(
                    x=[x_lower, x_lower],
                    y=[center_y - cap_height, center_y + cap_height],
                    mode="lines",
                    line=dict(color=duration_color, width=2),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[x_upper, x_upper],
                    y=[center_y - cap_height, center_y + cap_height],
                    mode="lines",
                    line=dict(color=duration_color, width=2),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    # Add scatter points at the center of each box for hover information
    hover_texts = []
    for idx, row in plot_df.iterrows():
        hover_text = (
            f"Event ID: {row['event_id']}<br>"
            f"Start: {row['start_datetime'].strftime('%Y-%m-%d %H:%M')}<br>"
            f"End: {row['end_datetime'].strftime('%Y-%m-%d %H:%M')}<br>"
            f"Duration: {row['duration']:.2f} hr<br>"
            f"Rate: {row['rate']:.2f} kg/hr<br>"
            f"Rate Range: {row['rate_lower']:.2f} - {row['rate_upper']:.2f} kg/hr"
        )

        # Add duration uncertainty if available
        if (
            consider_uncertainty == "yes"
            and row["duration_lower"] != row["duration_upper"]
        ):
            hover_text += f"<br>Duration Range: {row['duration_lower']:.2f} - {row['duration_upper']:.2f} hr"

        hover_texts.append(hover_text)

    fig.add_trace(
        go.Scatter(
            x=plot_df["start_datetime"]
            + (plot_df["end_datetime"] - plot_df["start_datetime"]) / 2,
            y=plot_df["rate"],
            mode="markers",
            marker=dict(size=0, opacity=0),  # Invisible markers, just for hover
            text=hover_texts,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    fig.update_layout(
        title=f"Emission Events Over Time - {selected_source}",
        xaxis_title="Time of Year",
        yaxis_title="Rate (kg/hr)",
        height=500,
        hovermode="closest",
        showlegend=False,
        xaxis=dict(range=[x_min, x_max]),
        yaxis=dict(range=[y_min, y_max]),
    )

    # Format x-axis to show dates nicely
    fig.update_xaxes(tickformat="%Y-%m-%d", tickangle=45)

    # Create table for output events if duration uncertainty is considered
    events_table = html.Div()
    if (
        consider_uncertainty == "yes"
        and simulation_results is not None
        and len(simulation_results) > 0
    ):
        # Filter events by selected source and merge with simulation results
        filtered_with_sim = filtered_events.copy()

        # Merge simulation results
        sim_df = pd.DataFrame(simulation_results)
        if "id" in filtered_with_sim.columns and "id" in sim_df.columns:
            filtered_with_sim = filtered_with_sim.merge(
                sim_df[
                    [
                        "id",
                        "simulated_duration",
                        "simulated_duration_lower",
                        "simulated_duration_upper",
                    ]
                ],
                on="id",
                how="inner",
            )

        # Create table with relevant columns
        display_cols = [
            "id",
            "rate",
            "duration",
            "simulated_duration",
            "simulated_duration_lower",
            "simulated_duration_upper",
            "quantity",
            "sourceLocation",
            "startTime",
            "endTime",
        ]
        available_cols = [
            col for col in display_cols if col in filtered_with_sim.columns
        ]
        table_df = filtered_with_sim[available_cols].copy()

        # Format numeric columns
        if "rate" in table_df.columns:
            table_df["rate"] = table_df["rate"].apply(
                lambda x: f"{x:.4f}" if pd.notna(x) else "N/A"
            )
        if "duration" in table_df.columns:
            table_df["duration"] = table_df["duration"].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
            )
        if "simulated_duration" in table_df.columns:
            table_df["simulated_duration"] = table_df["simulated_duration"].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
            )
        if "simulated_duration_lower" in table_df.columns:
            table_df["simulated_duration_lower"] = table_df[
                "simulated_duration_lower"
            ].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
        if "simulated_duration_upper" in table_df.columns:
            table_df["simulated_duration_upper"] = table_df[
                "simulated_duration_upper"
            ].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
        if "quantity" in table_df.columns:
            table_df["quantity"] = table_df["quantity"].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
            )

        # Create table HTML
        events_table = html.Div(
            [
                html.H4(
                    "Output Events with Duration Uncertainty",
                    style={"marginTop": "20px", "marginBottom": "10px"},
                ),
                html.Div(
                    [
                        html.Table(
                            [
                                html.Thead(
                                    [
                                        html.Tr(
                                            [
                                                html.Th(
                                                    col.replace("_", " ").title(),
                                                    style={
                                                        "padding": "8px",
                                                        "textAlign": "left",
                                                        "borderBottom": "2px solid #34495e",
                                                        "backgroundColor": "#ecf0f1",
                                                    },
                                                )
                                                for col in available_cols
                                            ]
                                        )
                                    ]
                                ),
                                html.Tbody(
                                    [
                                        html.Tr(
                                            [
                                                html.Td(
                                                    str(table_df.iloc[i][col]),
                                                    style={
                                                        "padding": "8px",
                                                        "borderBottom": "1px solid #bdc3c7",
                                                    },
                                                )
                                                for col in available_cols
                                            ]
                                        )
                                        for i in range(len(table_df))
                                    ]
                                ),
                            ],
                            style={
                                "width": "100%",
                                "borderCollapse": "collapse",
                                "fontSize": "12px",
                                "backgroundColor": "white",
                            },
                        )
                    ],
                    style={
                        "overflowX": "auto",
                        "maxHeight": "400px",
                        "overflowY": "auto",
                        "border": "1px solid #bdc3c7",
                        "borderRadius": "4px",
                    },
                ),
            ]
        )

    return dcc.Graph(figure=fig), events_table


@app.callback(
    [
        Output("duration-estimation-status", "children"),
        Output("stored-duration-simulation-results", "data"),
        Output("stored-events", "data", allow_duplicate=True),
    ],
    [Input("estimate-duration-button", "n_clicks")],
    [
        State("duration-uncertainty-method-dropdown", "value"),
        State("manual-leak-production-rate-input", "value"),
        State("stored-events", "data"),
    ],
    prevent_initial_call=True,
)
def estimate_duration_uncertainty(n_clicks, method, manual_rate, events_data):
    """Estimate duration uncertainty using simulate_duration_uncertainty function"""
    if n_clicks == 0 or events_data is None or len(events_data) == 0:
        return html.Div(), None, events_data

    try:
        # Calculate leak_production_rate based on method
        if method == "default":
            leak_production_rate = 0.0006
        elif method == "manual":
            if manual_rate is None or manual_rate == "":
                return (
                    html.Div(
                        [
                            html.P(
                                "Please provide a leak production rate value.",
                                style={"color": "#e74c3c", "fontWeight": "bold"},
                            )
                        ]
                    ),
                    None,
                    events_data,
                )
            leak_production_rate = float(manual_rate)
        elif method == "calculate":
            leak_production_rate = 0.5
        else:
            return (
                html.Div(
                    [
                        html.P(
                            "Invalid method selected.",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                None,
                events_data,
            )

        # Convert events data to DataFrame
        events_df = pd.DataFrame(events_data)

        # Transform events to match simulate_duration_uncertainty expectations
        # The function expects: event_type, start_time, end_time, rate, duration
        # Our events have: startTime, endTime, rate, duration

        # Create a copy for transformation
        transformed_events = events_df.copy()

        # Add event_type column (set to "PRE" for all events as per function logic)
        transformed_events["event_type"] = "PRE"

        # Transform startTime and endTime to the expected format
        def format_datetime(dt_str):
            """Convert ISO format datetime to '%Y-%m-%d %H:%M:%S' format"""
            if pd.isna(dt_str):
                return None
            try:
                if isinstance(dt_str, str):
                    # Parse ISO format and convert to required format
                    dt = pd.to_datetime(dt_str)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    return dt_str.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

        transformed_events["start_time"] = transformed_events["startTime"].apply(
            format_datetime
        )
        transformed_events["end_time"] = transformed_events["endTime"].apply(
            format_datetime
        )

        # Filter out events with missing start_time or end_time
        valid_events = transformed_events[
            transformed_events["start_time"].notna()
            & transformed_events["end_time"].notna()
        ].copy()

        if len(valid_events) == 0:
            return (
                html.Div(
                    [
                        html.P(
                            "No valid events with start and end times found.",
                            style={"color": "#e74c3c", "fontWeight": "bold"},
                        )
                    ]
                ),
                None,
                events_data,
            )

        # Call simulate_duration_uncertainty
        # Note: The function modifies the DataFrame in place and returns it
        # MC_iterations=100 is high, so parallel processing will be used automatically
        MC_iterations = 100

        result_events = simulate_duration_uncertainty(
            leak_production_rate=leak_production_rate,
            events=valid_events,
            MC_iterations=MC_iterations,
        )

        # Check if simulation added the new columns
        if "simulated_duration" in result_events.columns:
            num_simulated = len(
                result_events[result_events["simulated_duration"].notna()]
            )

            # Store simulation results (convert to dict for storage)
            # Keep only relevant columns: id, simulated_duration, simulated_duration_lower, simulated_duration_upper
            result_cols = [
                "id",
                "simulated_duration",
                "simulated_duration_lower",
                "simulated_duration_upper",
            ]
            available_cols = [
                col for col in result_cols if col in result_events.columns
            ]
            simulation_results = result_events[available_cols].to_dict("records")

            # Merge simulation results back into original events DataFrame
            # Create a DataFrame from simulation results for merging
            sim_results_df = result_events[available_cols].copy()

            # Merge with original events_df based on 'id' column
            if "id" in events_df.columns and "id" in sim_results_df.columns:
                # Merge the three new columns into the original events
                updated_events_df = events_df.merge(
                    sim_results_df[
                        [
                            "id",
                            "simulated_duration",
                            "simulated_duration_lower",
                            "simulated_duration_upper",
                        ]
                    ],
                    on="id",
                    how="left",
                )
            else:
                # If no ID column, merge by index (assuming same order)
                # Reset index to ensure proper alignment
                events_df_reset = events_df.reset_index(drop=True)
                sim_results_reset = sim_results_df.reset_index(drop=True)
                updated_events_df = pd.concat(
                    [
                        events_df_reset,
                        sim_results_reset[
                            [
                                "simulated_duration",
                                "simulated_duration_lower",
                                "simulated_duration_upper",
                            ]
                        ],
                    ],
                    axis=1,
                )

            # Convert updated events back to dict for storage
            updated_events_data = updated_events_df.to_dict("records")

            status_div = html.Div(
                [
                    html.P(
                        "✓ Duration uncertainty estimation completed successfully!",
                        style={
                            "color": "#27ae60",
                            "fontWeight": "bold",
                            "marginTop": "10px",
                        },
                    ),
                    html.P(
                        f"Simulated durations for {num_simulated} events",
                        style={"color": "#27ae60", "fontSize": "14px"},
                    ),
                    html.P(
                        f"Leak Production Rate used: {leak_production_rate:.6f} kg/hr",
                        style={
                            "color": "#7f8c8d",
                            "fontSize": "14px",
                            "marginTop": "5px",
                        },
                    ),
                    html.P(
                        f"Monte Carlo iterations: {MC_iterations} (parallel processing enabled)",
                        style={
                            "color": "#7f8c8d",
                            "fontSize": "12px",
                            "fontStyle": "italic",
                            "marginTop": "5px",
                        },
                    ),
                ]
            )

            return status_div, simulation_results, updated_events_data
        else:
            return (
                html.Div(
                    [
                        html.P(
                            "Simulation completed but no simulated durations were generated.",
                            style={"color": "#e67e22", "fontWeight": "bold"},
                        )
                    ]
                ),
                None,
                events_data,
            )

    except Exception as e:
        return (
            html.Div(
                [
                    html.P(
                        f"✗ Error during duration uncertainty estimation: {str(e)}",
                        style={
                            "color": "#e74c3c",
                            "fontWeight": "bold",
                            "marginTop": "10px",
                        },
                    )
                ]
            ),
            None,
            events_data,
        )


@app.callback(
    Output("download-dataframe", "data"),
    [
        Input("download-csv-button", "n_clicks"),
        Input("download-json-button", "n_clicks"),
    ],
    [State("stored-events", "data")],
    prevent_initial_call=True,
)
def download_emission_events(csv_clicks, json_clicks, events_data):
    """Handle download of emission events as CSV or JSON"""
    ctx = callback_context
    if not ctx.triggered or events_data is None or len(events_data) == 0:
        raise PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Convert stored events to DataFrame
    df = pd.DataFrame(events_data)

    if button_id == "download-csv-button":
        # Download as CSV
        return dcc.send_data_frame(df.to_csv, "emission_events.csv", index=False)
    elif button_id == "download-json-button":
        # Download as JSON
        return dict(
            content=df.to_json(orient="records", indent=2),
            filename="emission_events.json",
        )

    raise PreventUpdate


@app.callback(
    Output("download-results-csv", "data"),
    Input("download-results-csv-button", "n_clicks"),
    State("stored-simulation-results", "data"),
    prevent_initial_call=True,
)
def download_results_csv(n_clicks, simulation_results):
    """Export simulation results as a CSV file."""
    if not n_clicks or simulation_results is None:
        raise PreventUpdate

    estimation_approach = simulation_results.get("estimation_approach", "N/A")
    rows = []

    # Metadata rows
    rows.append({"Section": "Metadata", "Statistic": "Approach", "Value": estimation_approach})
    rows.append({"Section": "Metadata", "Statistic": "Resolution", "Value": simulation_results.get("processing_resolution", "N/A")})
    rows.append({"Section": "Metadata", "Statistic": "Start Time", "Value": simulation_results.get("start_time", "N/A")})
    rows.append({"Section": "Metadata", "Statistic": "End Time", "Value": simulation_results.get("end_time", "N/A")})
    rows.append({"Section": "Metadata", "Statistic": "MC Iterations", "Value": simulation_results.get("monte_carlo_iterations", "N/A")})

    if estimation_approach == "bootstrap":
        extrapolation_results = simulation_results.get("extrapolation_results", {})
        all_emissions = []
        for key, emissions_list in extrapolation_results.items():
            if len(emissions_list) > 0:
                all_emissions.extend(emissions_list)

        if len(all_emissions) > 0:
            arr = np.array(all_emissions)
            rows.append({"Section": "Statistics", "Statistic": "N", "Value": len(arr)})
            rows.append({"Section": "Statistics", "Statistic": "Mean (kg)", "Value": f"{np.mean(arr):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "Median (kg)", "Value": f"{np.median(arr):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "Std Dev (kg)", "Value": f"{np.std(arr):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "Min (kg)", "Value": f"{np.min(arr):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "P2.5 (kg)", "Value": f"{np.percentile(arr, 2.5):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "P5 (kg)", "Value": f"{np.percentile(arr, 5):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "P25 (kg)", "Value": f"{np.percentile(arr, 25):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "P50 (kg)", "Value": f"{np.percentile(arr, 50):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "P75 (kg)", "Value": f"{np.percentile(arr, 75):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "P95 (kg)", "Value": f"{np.percentile(arr, 95):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "P97.5 (kg)", "Value": f"{np.percentile(arr, 97.5):.4f}"})
            rows.append({"Section": "Statistics", "Statistic": "Max (kg)", "Value": f"{np.max(arr):.4f}"})

            # Add all MC sample values
            for i, val in enumerate(all_emissions):
                rows.append({"Section": "MC Samples", "Statistic": f"Sample {i+1}", "Value": f"{val:.4f}"})

    elif estimation_approach == "below_MDL":
        def _add(label, val):
            rows.append({"Section": "Statistics", "Statistic": label, "Value": f"{val:.4f}" if val is not None else "N/A"})

        _add("Total Emissions (kg)", simulation_results.get("below_mdl_emissions"))
        _add("Total Lower CI (kg)", simulation_results.get("below_mdl_emissions_lower"))
        _add("Total Upper CI (kg)", simulation_results.get("below_mdl_emissions_upper"))
        _add("Measured Emissions (kg)", simulation_results.get("measured_emissions"))
        _add("Measured Lower CI (kg)", simulation_results.get("measured_emissions_lower"))
        _add("Measured Upper CI (kg)", simulation_results.get("measured_emissions_upper"))
        _add("Unmeasured Emissions (kg)", simulation_results.get("unmeasured_emissions"))
        _add("Unmeasured Lower CI (kg)", simulation_results.get("unmeasured_emissions_lower"))
        _add("Unmeasured Upper CI (kg)", simulation_results.get("unmeasured_emissions_upper"))

    df = pd.DataFrame(rows)
    return dcc.send_data_frame(df.to_csv, "simulation_results.csv", index=False)


if __name__ == "__main__":
    app.run(debug=True, port=8050)
