# CVRP-ACO: Solving Constrained Vehicle Routing Problems with Ant Colony Optimization

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/yourusername/gumroad-cvrp/blob/main/notebooks/cvrp_aco_demo.ipynb)

This project demonstrates how to solve Constrained Vehicle Routing Problems (CVRP) using Ant Colony Optimization (ACO). It's designed for educational purposes and can be run locally or in Google Colab.

## What is CVRP?
CVRP involves finding optimal routes for vehicles delivering goods from a central depot to multiple customers, respecting capacity constraints (pallets and weight). Unlike standard VRP, the number of vehicles isn't fixed—it emerges from the constraints.

## What is ACO?
ACO is a nature-inspired metaheuristic. Virtual "ants" explore solutions, depositing "pheromones" on good paths to guide future ants toward better routes.

## Features
- **Modular Code**: Clean Python packages for data prep, solving, and visualization
- **Interactive Demo**: Complete Google Colab notebook walkthrough
- **Real Maps**: Integration with Open Route Service for accurate routing
- **Educational**: Detailed comments and explanations for learning

## Quick Start

### Option 1: Google Colab (Recommended for Beginners)
1. Click the Colab badge above
2. Follow the notebook cells step-by-step
3. No local setup required!

### Option 2: Local Installation
1. Clone this repo
2. Install dependencies: `pip install -r requirements.txt`
3. Get Open Route Service API key: https://openrouteservice.org/
4. Run the demo: `python notebooks/cvrp_aco_demo.ipynb` (or open in Jupyter)

## Project Structure
```
gumroad-cvrp/
├── src/
│   ├── data_prep/      # ETL for geo data and distances
│   ├── solver/         # ACO algorithm implementation
│   └── viz/            # Plotly visualizations
├── notebooks/          # Colab demo
├── data/               # Sample datasets
├── docs/               # Tutorials and guides
├── config.yaml         # Configuration
├── requirements.txt    # Dependencies
└── README.md
```

## Usage Example
```python
from src.solver.aco import ACOSolver

solver = ACOSolver(
    dvrp_id='my_problem',
    points_file='data/input.csv',
    db_path='data/cvrp.db',
    origin='depot_id',
    max_pall=20,
    max_lbs=35000
)
result = solver.solve()
print(result)
```

## Key Components

### Data Preparation (`src/data_prep/`)
- Process geojson files from overpass-turbo
- Generate point permutations and fetch distances via ORS API
- Assign realistic delivery attributes (frequencies, pallet counts, weights)

### ACO Solver (`src/solver/`)
- Implements pheromone-based optimization
- Handles capacity constraints dynamically
- Outputs clustered routes saved to SQLite

### Visualization (`src/viz/`)
- Plotly tables for solution data
- Interactive maps with real routing
- Fallback to straight lines if API fails

## Dependencies
- numpy, pandas: Data processing
- plotly: Visualization
- openrouteservice: Routing API
- tqdm: Progress bars
- jupyter, ipywidgets: Notebook support
- pyyaml: Config management

## API Keys
You'll need an Open Route Service API key. Sign up at https://openrouteservice.org/ for a free tier (2000 requests/day).

## Learning Resources
For in-depth explanations and advanced topics, check out our Gumroad courses:
- [CVRP Fundamentals](https://gumroad.com/yourlink)
- [ACO Algorithm Deep Dive](https://gumroad.com/yourlink)
- [Real-World Logistics Optimization](https://gumroad.com/yourlink)

## Contributing
This is an educational project. Feel free to open issues or PRs for improvements!

## License
MIT License - Free for educational and personal use.
