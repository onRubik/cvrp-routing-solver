import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import sqlite3

# Version identifier for debugging module reloads
__version__ = "2.1.0"
print(f"🔧 Loading plots.py version {__version__}")


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
        ors_api_key: Open Route Service API key (optional, will try Colab secrets)
        db_path: Path to database file

    Returns:
        plotly figure object
    """
    # Try to get ORS API key from Colab secrets if not provided
    if ors_api_key is None:
        try:
            from google.colab import userdata
            ors_api_key = userdata.get('ORS_API_KEY')
            print("✅ Found ORS_API_KEY in Colab secrets - will use realistic road routes")
        except:
            print("\n" + "="*80)
            print("⚠️  WARNING: No ORS_API_KEY found in Colab secrets!")
            print("="*80)
            print("📍 Routes will be shown as STRAIGHT LINES between stops.")
            print("🛣️  For realistic road-following routes, add your OpenRouteService API key:")
            print("   1. Get free API key: https://openrouteservice.org/dev/#/signup")
            print("   2. In Colab: Click 🔑 (key icon) in left sidebar")
            print("   3. Add secret: Name='ORS_API_KEY', Value='your-api-key'")
            print("   4. Enable 'Notebook access' toggle")
            print("   5. Re-run this cell")
            print("="*80 + "\n")
            ors_api_key = None
    
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

    # Initialize ORS client if API key is available
    ors_client = None
    if ors_api_key:
        try:
            import openrouteservice
            ors_client = openrouteservice.Client(key=ors_api_key)
        except Exception as e:
            print(f"⚠️  Failed to initialize ORS client: {e}")
            print("Falling back to straight-line routes")
            ors_client = None

    # Plot routes for each tractor
    for tractor_id, tractor_data in routes_df.groupby('cluster_id'):
        color = colors[tractor_id % len(colors)]
        tractor_name = tractor_data['cluster_name'].iloc[0]

        # Build coordinates list for this route
        coords_list = [[float(dc_lon), float(dc_lat)]]  # Start at DC (lon, lat for ORS)
        
        for _, stop in tractor_data.iterrows():
            coords_list.append([float(stop['lon']), float(stop['lat'])])
        
        coords_list.append([float(dc_lon), float(dc_lat)])  # Return to DC
        
        print(f"🚛 {tractor_name} route coordinates: {coords_list}")
        
        # Print store sequence for this tractor
        store_names = [stop['store_name'] for _, stop in tractor_data.iterrows()]
        print(f"🏪 {tractor_name} stops: {', '.join(store_names)}")

        # Get route line coordinates
        if ors_client:
            # Use ORS to get realistic road routes
            try:
                route = ors_client.directions(
                    coordinates=coords_list,
                    profile='driving-hgv',
                    format='geojson'
                )
                # Extract coordinates from GeoJSON
                line_coords = route['features'][0]['geometry']['coordinates']
                # Convert to (lat, lon) for Plotly
                lats = [coord[1] for coord in line_coords]
                lons = [coord[0] for coord in line_coords]
                print(f"✅ {tractor_name}: Retrieved {len(line_coords)} road points from ORS")
            except Exception as e:
                print(f"⚠️  ORS routing failed for {tractor_name}: {e}")
                print("Using straight-line route for this tractor")
                # Fall back to straight lines
                lats = [coord[1] for coord in coords_list]
                lons = [coord[0] for coord in coords_list]
        else:
            # Use straight-line routes
            lats = [coord[1] for coord in coords_list]
            lons = [coord[0] for coord in coords_list]

        # Plot route line
        fig.add_trace(go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode='lines',
            line=dict(width=3, color=color),
            name=f'{tractor_name} Route',
            hoverinfo='name'
        ))

        # Plot store markers with sequence numbers
        for i, stop in enumerate(tractor_data.iterrows()):
            _, stop_data = stop
            sequence_num = i + 1  # Stop sequence in this route
            fig.add_trace(go.Scattermapbox(
                lat=[stop_data['lat']],
                lon=[stop_data['lon']],
                mode='markers+text',
                marker=dict(size=12, color=color),
                text=[f"Stop {sequence_num}"],
                textposition="top center",
                name=f'{tractor_name} Stop {sequence_num}: {stop_data["store_name"]}',
                hovertemplate=f"<b>Stop {sequence_num}</b><br>" +
                             f"{stop_data['store_name']}<br>" +
                             f"Pallets: {stop_data['pallets']}<br>" +
                             f"Weight: {stop_data['weight_lbs']:,.0f} lbs<br>" +
                             "<extra></extra>",
                showlegend=False
            ))

    # Plot distribution center with better visibility
    print(f"🏭 Distribution Center coordinates: [{dc_lon}, {dc_lat}]")
    fig.add_trace(go.Scattermapbox(
        lat=[dc_lat],
        lon=[dc_lon],
        mode='markers+text',
        marker=dict(size=30, color='black', symbol='circle'),
        text=['DC'],
        textposition="top center",
        name='Distribution Center',
        hovertemplate="<b>Distribution Center</b><br>" +
                     "Starting and ending point<br>" +
                     f"Coordinates: {dc_lat:.4f}, {dc_lon:.4f}<br>" +
                     "<extra></extra>",
        showlegend=True
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
