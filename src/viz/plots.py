import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import sqlite3


def plot_solution_table(dvrp_id, db_path='data/cvrp_demo.db'):
    """
    Create a table showing the solution routes

    Args:
        dvrp_id: Solution identifier
        db_path: Path to database file

    Returns:
        plotly figure object
    """
    con = sqlite3.connect(db_path)

    # Get solution data
    routes_query = """
    SELECT
        cluster_id,
        cluster_name,
        point,
        sequence,
        gp.name as store_name,
        gp.pall_avg as pallets,
        gp.lbs_avg as weight_lbs
    FROM dvrp_set ds
    JOIN geo_points gp ON ds.point = gp.id_p
    WHERE dvrp_id = ?
    ORDER BY cluster_id, sequence
    """

    routes_df = pd.read_sql_query(routes_query, con, params=[dvrp_id])
    con.close()

    if routes_df.empty:
        # Create empty table
        fig = go.Figure(data=[go.Table(
            header=dict(values=['No solution data found']),
            cells=dict(values=[['Please run the ACO solver first']])
        )])
        return fig

    # Group by tractor and create summary
    summary_data = []
    for tractor_id, tractor_data in routes_df.groupby('cluster_id'):
        tractor_name = tractor_data['cluster_name'].iloc[0]
        total_pall = tractor_data['pallets'].sum()
        total_weight = tractor_data['weight_lbs'].sum()

        # Build route description
        stops = []
        for _, stop in tractor_data.iterrows():
            stops.append(f"{stop['store_name']} ({stop['pallets']}p, {stop['weight_lbs']:.0f}lbs)")

        route_desc = " → ".join(stops)

        summary_data.append([
            tractor_name,
            len(tractor_data),
            total_pall,
            f"{total_weight:,.0f}",
            route_desc
        ])

    # Create table
    fig = go.Figure(data=[go.Table(
        columnwidth=[150, 80, 80, 100, 400],
        header=dict(
            values=['<b>Tractor</b>', '<b>Stores</b>', '<b>Total Pallets</b>', '<b>Total Weight</b>', '<b>Route</b>'],
            fill_color='lightblue',
            align='left',
            font=dict(size=12, color='black'),
            height=40
        ),
        cells=dict(
            values=list(zip(*summary_data)) if summary_data else [[], [], [], [], []],
            fill_color='white',
            align='left',
            font=dict(size=11),
            height=30
        )
    )])

    fig.update_layout(
        title=f"CVRP Solution: {dvrp_id}",
        margin=dict(l=10, r=10, t=50, b=10)
    )

    return fig


def plot_routes_map(dvrp_id, ors_api_key=None, db_path='data/cvrp_demo.db'):
    """
    Create an interactive map showing delivery routes

    Args:
        dvrp_id: Solution identifier
        ors_api_key: Open Route Service API key (not used in demo)
        db_path: Path to database file

    Returns:
        plotly figure object
    """
    con = sqlite3.connect(db_path)

    # Get route data
    routes_query = """
    SELECT
        cluster_id,
        cluster_name,
        point,
        sequence,
        gp.name as store_name,
        gp.lat,
        gp.lon,
        gp.pall_avg as pallets,
        gp.lbs_avg as weight_lbs
    FROM dvrp_set ds
    JOIN geo_points gp ON ds.point = gp.id_p
    WHERE dvrp_id = ?
    ORDER BY cluster_id, sequence
    """

    routes_df = pd.read_sql_query(routes_query, con, params=[dvrp_id])

    # Get origin
    origin_query = "SELECT dvrp_origin FROM dvrp_origin WHERE dvrp_id = ?"
    origin_result = pd.read_sql_query(origin_query, con, params=[dvrp_id])
    origin_point = origin_result.iloc[0, 0] if not origin_result.empty else None

    # Get origin coordinates
    if origin_point:
        origin_query = "SELECT lat, lon FROM geo_points WHERE id_p = ?"
        origin_coords = pd.read_sql_query(origin_query, con, params=[origin_point])
        dc_lat = origin_coords.iloc[0, 0]
        dc_lon = origin_coords.iloc[0, 1]
    else:
        dc_lat, dc_lon = 40.7505, -73.9934  # Default to Manhattan

    con.close()

    if routes_df.empty:
        # Create empty map centered on Manhattan
        fig = go.Figure()
        fig.add_trace(go.Scattermapbox(
            lat=[dc_lat],
            lon=[dc_lon],
            mode='markers+text',
            marker=dict(size=15, color='red'),
            text=['No route data found'],
            hoverinfo='text'
        ))
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(center=dict(lat=dc_lat, lon=dc_lon), zoom=11),
            title="No Solution Data Found"
        )
        return fig

    # Create map
    fig = go.Figure()

    # Colors for different tractors
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

    # Plot routes for each tractor
    for tractor_id, tractor_data in routes_df.groupby('cluster_id'):
        color = colors[tractor_id % len(colors)]
        tractor_name = tractor_data['cluster_name'].iloc[0]

        # Get route coordinates (start from origin, visit stores, return to origin)
        route_coords = []

        # Start at distribution center
        route_coords.append((dc_lat, dc_lon))

        # Visit each store
        for _, stop in tractor_data.iterrows():
            route_coords.append((stop['lat'], stop['lon']))

        # Return to distribution center
        route_coords.append((dc_lat, dc_lon))

        # Plot route line
        lats, lons = zip(*route_coords)
        fig.add_trace(go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode='lines',
            line=dict(width=3, color=color),
            name=f'{tractor_name} Route',
            hoverinfo='name'
        ))

        # Plot store markers
        for i, (lat, lon) in enumerate(route_coords[1:-1]):  # Skip DC at start and end
            stop_data = tractor_data.iloc[i]
            fig.add_trace(go.Scattermapbox(
                lat=[lat],
                lon=[lon],
                mode='markers+text',
                marker=dict(size=10, color=color),
                text=[f"{stop_data['store_name']}<br>{stop_data['pallets']} pallets"],
                textposition="top center",
                name=f'{tractor_name} Stop {i+1}',
                hoverinfo='text',
                showlegend=False
            ))

    # Plot distribution center
    fig.add_trace(go.Scattermapbox(
        lat=[dc_lat],
        lon=[dc_lon],
        mode='markers+text',
        marker=dict(size=15, color='black', symbol='star'),
        text=['Distribution Center'],
        name='Distribution Center',
        hoverinfo='text'
    ))

    # Configure map
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(
            center=dict(lat=dc_lat, lon=dc_lon),
            zoom=11
        ),
        title=f"CVRP Solution Routes - {dvrp_id}",
        showlegend=True,
        margin=dict(l=0, r=0, t=40, b=0)
    )

    return fig
