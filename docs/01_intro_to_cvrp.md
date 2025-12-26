# Introduction to Constrained Vehicle Routing Problems (CVRP)

## What is Vehicle Routing?
Vehicle Routing Problems (VRP) involve finding optimal routes for a fleet of vehicles to serve a set of customers. The goal is typically to minimize total distance or cost while satisfying constraints.

## What Makes CVRP "Constrained"?
CVRP adds capacity constraints:
- **Pallets**: Maximum number of pallet spaces per vehicle
- **Weight**: Maximum weight capacity per vehicle
- **Time Windows**: Delivery time restrictions (optional)

Unlike standard VRP, CVRP doesn't specify the number of vehicles upfront. The fleet size emerges from the constraints.

## Real-World Applications
- **Logistics**: Delivering goods from warehouses to stores
- **Delivery Services**: Meal/food delivery with weight limits
- **Waste Collection**: Trucks with capacity limits
- **Field Service**: Technicians visiting customers with time constraints

## Problem Formulation
- **Depot**: Central starting/ending point
- **Customers**: Points requiring service
- **Vehicles**: Fleet with capacity limits
- **Routes**: Sequences of customers per vehicle

## Challenges
- **NP-Hard**: Computationally expensive for large instances
- **Capacity Balancing**: Avoid overloading vehicles
- **Route Optimization**: Minimize total distance/cost

## Solution Approaches
- **Exact Methods**: Branch & bound, cutting planes (small instances)
- **Heuristics**: Construction heuristics, local search
- **Metaheuristics**: Simulated annealing, tabu search, **ACO**

Next: [ACO Algorithm Explained](../docs/02_aco_algorithm.md)
