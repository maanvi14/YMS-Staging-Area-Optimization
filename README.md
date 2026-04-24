# YMS-Staging-Area-Optimization

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![OR-Tools](https://img.shields.io/badge/OR--Tools-CP--SAT-orange)
![Graph](https://img.shields.io/badge/Graph-Dijkstra-purple)
![NumPy](https://img.shields.io/badge/NumPy-Scientific%20Computing-yellow)
![Ollama](https://img.shields.io/badge/Ollama-Llama3%20Local%20LLM-black)
![Optimization](https://img.shields.io/badge/Optimization-Constraint%20Solver-blue)
![Status](https://img.shields.io/badge/Status-Active-success)

YMS Staging Area Optimization System is an optimization-first logistics engine that integrates prediction, constraint-based scheduling, and graph routing to drive real-time, efficient yard operations.

It functions as a decision-support system, ensuring optimal dock assignments, smooth yard movement, and reduced operational delays under real-world constraints.

---

## 🚀 Overview

Logistics yard operations are often complex and constraint-heavy:

Dock assignments are made manually and often suboptimal
Congestion builds up due to poor routing decisions
High-priority shipments get delayed behind lower-priority ones
Multiple constraints (capacity, compatibility, HOS) interact and cause conflicts

YMS Staging Area Optimization System solves this by integrating:

📊 Predictive Estimation → arrival time, service time, delay probability
⚙️ Constraint Optimization (CP-SAT) → dock assignment under real-world constraints
🛣️ Graph-Based Routing → congestion-aware path planning (Dijkstra)
💬 Explainable AI Layer → human-readable decision insights
---

## 🧠 Key Features

## Prediction Layer
Estimates arrival time, service time, and delay probability
Based on:
Truck type, weight, priority
Time of day (traffic patterns)
Hazardous status
Adds controlled noise to simulate real-world uncertainty

## Optimization Layer (CP-SAT)
Models dock assignment as a constraint optimization problem

Constraints:
One truck → one dock
Dock compatibility (type, hazardous handling)
Capacity limits (weight constraints)
No overlapping schedules (time-based constraints)
Driver HOS (Hours of Service) limits

## Objective:
## Minimize:
Waiting time
Priority-based delays
Travel distance (staging → dock)

Reliability: Fallback to greedy priority-based assignment if solver fails

## Routing Layer (Graph-Based)
Models yard as a weighted graph:
Nodes → gates, staging areas, docks
Edges → roads connecting locations

## Edge attributes:
Distance
Speed
Congestion factor
Width

Routing logic: Uses Dijkstra’s algorithm to compute optimal path
Applies penalty for oversized trucks on narrow paths
## Explanation Layer
Uses LLaMA3 via Ollama (local LLM)
Generates human-readable explanations for decisions

Example:
“Truck assigned to Dock B due to compatibility and lower congestion.”

Reliability: Rule-based fallback if LLM is unavailable
## Orchestration Engine

Coordinates the full pipeline:
Runs prediction → optimization → routing sequentially
Aggregates outputs into a unified decision context
Ensures smooth data flow across layers
## 🏗️ System Architecture
Truck Input
Prediction Layer
Optimization Layer (CP-SAT)
Routing Layer (Dijkstra)
Context Aggregation
Explanation Layer (LLaMA3 via Ollama)
Final Output (Assignment + Route + Explanation)


LLM	Llama3 (Ollama – Local)
| Layer | Technology |
|------|-----------|
| Backend API | FastAPI |
| LLM | Llama3 (Ollama – Local) |
| Routing	|Dijkstra (Graph) |



Data Models	Pydantic
