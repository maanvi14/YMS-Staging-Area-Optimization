YMS Staging Area Optimization System
=================================

Overview
--------
This repository implements a local YMS (Yard Management System) staging area optimizer. It provides:

- A FastAPI service that accepts batches of truck inputs and returns dock assignments and yard metrics.
- A local, rule-based prediction service (no cloud) for ETA and service-time predictions.
- An OR-Tools-based optimization engine for dock assignment and yard routing with a greedy fallback.
- Optional local LLM integration via Ollama for human-friendly explanations and summaries.

Main files
----------
- [yms_staging_optimizer.py](yms_staging_optimizer.py) — Core API, data models, optimization engine, and FastAPI app.
  - Key classes and components:
    - `TruckType`, `Priority`, `TruckState` — enums for truck types and priorities.
    - `TruckInput`, `Dock`, `YardEdge`, `PredictionResult`, `AssignmentResult`, `OptimizationOutput` — Pydantic models/dataclasses used across the system.
    - `MockPredictionService` — Local rule-based ETA & service time predictor.
    - `OptimizationEngine` — OR-Tools model to assign trucks to docks and route them through the yard. Exposes `solve_dock_assignment` and `solve_yard_routing` (Dijkstra-style with congestion costs).
    - `StagingOptimizer` — Orchestrates predictions, assignment, LLM explanations, and produces `OptimizationOutput`.
    - FastAPI app with endpoints:
      - `POST /optimize` — Accepts a list of `TruckInput` and returns `OptimizationOutput`.
      - `GET /yard-status` — Current dock status summary.

- [enhanced_optimizer.py](enhanced_optimizer.py) — Wraps LLM explanation logic and integrates a mock prediction service with the optimization engine.
  - `EnhancedLLMService` — Uses `OllamaLLMService` when available and falls back to deterministic rule-based explanations and alerts.
  - `create_enhanced_optimizer(opt_engine)` — Factory helper that wires `MockPredictionService`, `EnhancedLLMService`, and `StagingOptimizer` together.

- [ollama_service.py](ollama_service.py) — Lightweight wrapper for Ollama/Llama 3.
  - `OllamaLLMService` — Handles connectivity, prompts, and template fallbacks. Methods:
    - `generate_explanation(truck_data, assignment_data)`
    - `generate_alert_message(alert_type, details)`
    - `generate_yard_summary(metrics)`
  - `get_ollama_service()` — Singleton accessor used by `EnhancedLLMService`.

- [demo.py](demo.py) — Simple demo script that posts a sample batch of trucks to the running API and prints formatted results.

How the pieces fit together
---------------------------
1. The FastAPI app (in `yms_staging_optimizer.py`) is started with `uvicorn`.
2. A request to `/optimize` triggers `StagingOptimizer.optimize`.
3. `MockPredictionService` generates predicted arrivals and service times for each truck.
4. `OptimizationEngine.solve_dock_assignment` uses OR-Tools to assign trucks to docks; if OR-Tools fails, a greedy fallback runs.
5. For each assignment, the LLM service (`EnhancedLLMService` → `OllamaLLMService`) produces human-friendly explanations, alerts, and a yard summary.

Run locally (quickstart)
-----------------------
1. Create and activate a Python virtual environment.

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Start the API server (development):

```powershell
uvicorn yms_staging_optimizer:app --reload --port 8001
```

3. In another terminal, run the demo script to send the sample trucks:

```powershell
python demo.py
```

Notes and recommendations
-------------------------
- The repository is intentionally local-first: `MockPredictionService` avoids cloud dependencies and introduces realistic noise.
- `OllamaLLMService` will attempt to connect to a local Ollama instance at `http://localhost:11434`. If not available, the system gracefully falls back to template-based explanations.
- The OR-Tools model uses CP-SAT and is configured with a short time limit; in large or complex yard graphs consider raising `solver.parameters.max_time_in_seconds`.

Suggested next documentation steps (I can implement these if you want):

1. Add module- and function-level docstrings across the Python files for IDE and Sphinx consumption.
2. Generate Sphinx/MkDocs documentation from docstrings and the `DOCUMENTATION.md` file.
3. Add inline examples for `OptimizationEngine.solve_yard_routing` and typical `TruckInput` JSON payload shapes.

Contact / support
-----------------
If you'd like, I can now:
- Add docstrings directly into the code (per function/class).
- Create a `README.md` and a minimal `docs/` site with MkDocs.

Created by the documentation generator.
