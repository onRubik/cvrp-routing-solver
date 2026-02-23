# CVRP-ACO: Solving Constrained Vehicle Routing Problems with Ant Colony Optimization

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/onRubik/cvrp-routing-solver/blob/main/notebooks/cvrp_aco_demo.ipynb)

## 🎓 Gumroad Course Demo

This repository contains the interactive demo for our comprehensive CVRP-ACO course available on Gumroad. Experience hands-on vehicle routing optimization without complex setup!

## What is CVRP?

**Constrained Vehicle Routing Problem (CVRP)** involves finding optimal delivery routes for vehicles with capacity constraints. Each vehicle must:
- Start and end at a distribution center
- Respect pallet and weight limits
- Minimize total distance traveled
- Serve all customer locations

## What is ACO?

**Ant Colony Optimization (ACO)** is a nature-inspired metaheuristic that mimics ant foraging behavior. Virtual "ants" explore solutions, depositing "pheromones" on promising paths to guide future exploration toward optimal routes.

## 🚀 Quick Start

### Google Colab (Recommended)
1. Click the Colab badge above
2. Follow the step-by-step notebook (clock on "Run all")
3. No local installation required!
4. Experiment with different parameters


## 📁 Project Structure

```
cvrp-routing-solver/
├── data/                    # Pre-computed geographic data
│   ├── input_small.csv      # 8 locations to optimize (7 stores + 1 distribution center)
│   ├── geo_points.csv       # Geographic coordinates + delivery requirements
│   └── geo_permutations.csv # Pre-calculated distance matrix
├── notebooks/               # Interactive Colab demo
├── src/                     # Python source code
│   ├── solver/             # ACO algorithm implementation
│   └── viz/                # Plotly visualizations
└── requirements.txt         # Python dependencies
```

## 🎯 Key Features

- **Pre-built Dataset**: 20 Manhattan locations with realistic delivery requirements
- **Interactive Visualizations**: Plotly maps and tables showing solutions
- **Configurable Parameters**: Adjust vehicle constraints, ACO settings
- **Educational Focus**: Clear explanations of algorithms and concepts

## 📊 Sample Problem

**Given:**
- A few locations in Manhattan
- Tractor capacity: 22 pallets, 38,000 lbs

**Find:** Optimal routes that minimize total distance while respecting capacity constraints.

## 🧠 Algorithm Parameters

- **n_ants**: Number of ants per iteration (exploration breadth)
- **n_iterations**: Algorithm iterations (solution quality)
- **alpha**: Pheromone trail importance
- **beta**: Distance preference weight
- **evaporation_rate**: Pheromone decay rate

## 📈 Learning Outcomes

After completing this demo, you'll understand:
- How CVRP problems are formulated
- Ant Colony Optimization mechanics
- Capacity constraint handling
- Route optimization visualization
- Parameter tuning effects

## 🎓 Complete Course on Gumroad

For the full course including:
- **Advanced ACO variants** and improvements
- **Integration with routing APIs**
- **Multiple constraint types**
- **Source code deep dives**

👉 **[Purchase the Complete Course](https://rubiklife.gumroad.com/l/vcxvrx)**

## 🤝 Contributing

This is an educational demo project. For improvements or questions, please open an issue.

## 📄 License

Educational use permitted. See individual course license for commercial applications.

---

**Ready to optimize?** Click the Colab badge and start exploring! 🚛✨
