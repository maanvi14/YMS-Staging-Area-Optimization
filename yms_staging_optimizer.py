"""
YMS Staging Area Optimization System
Tech Stack: FastAPI, OR-Tools, Llama 3 (via Ollama)
Fully local — $0 cloud costs
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from contextlib import asynccontextmanager
import numpy as np
import json
import asyncio
import heapq
from dataclasses import dataclass

# ─── DATA MODELS ─────────────────────────────────────────────────────────────

class TruckType(str, Enum):
    FLATBED = "flatbed"
    REFRIGERATED = "refrigerated"
    TANKER = "tanker"
    CONTAINER = "container"
    DRY_VAN = "dry_van"
    OVERSIZE = "oversize"

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    STANDARD = "standard"
    LOW = "low"

class TruckState(str, Enum):
    EN_ROUTE = "en_route"
    AT_GATE = "at_gate"
    IN_STAGING = "in_staging"
    ASSIGNED = "assigned"
    AT_DOCK = "at_dock"
    SERVICING = "servicing"
    COMPLETED = "completed"

@dataclass
class Position:
    x: float
    y: float
    zone: str

class TruckInput(BaseModel):
    truck_id: str
    truck_type: TruckType
    priority: Priority
    estimated_arrival: datetime
    cargo_weight: float = Field(..., ge=0, le=80000)
    cargo_hazardous: bool = False
    driver_hours_remaining: float = Field(..., ge=0, le=11)
    preferred_docks: Optional[List[str]] = None
    appointment_id: Optional[str] = None

class Dock(BaseModel):
    dock_id: str
    position: Dict[str, float]
    supported_types: List[TruckType]
    capacity_kg: float
    has_refrigeration: bool
    has_hazard_handling: bool
    current_truck: Optional[str] = None
    estimated_release: Optional[datetime] = None
    maintenance_window: Optional[Tuple[datetime, datetime]] = None
    queue: List[str] = []

class YardEdge(BaseModel):
    from_node: str
    to_node: str
    distance_m: float
    speed_limit_kmh: float
    bidirectional: bool = True
    width_m: float = 4.0
    congestion_factor: float = 1.0

class PredictionResult(BaseModel):
    truck_id: str
    predicted_arrival: datetime
    predicted_service_minutes: float
    confidence_interval: Tuple[float, float]
    delay_probability: float
    weather_impact_factor: float = 1.0

class AssignmentResult(BaseModel):
    truck_id: str
    assigned_dock: str
    expected_start: datetime
    expected_completion: datetime
    waiting_time_minutes: float
    route: List[str]
    route_distance_m: float
    route_time_minutes: float
    congestion_level: str
    explanation: str
    alerts: List[str]

class OptimizationOutput(BaseModel):
    timestamp: datetime
    assignments: List[AssignmentResult]
    yard_congestion_score: float
    total_predicted_delay_minutes: float
    dock_utilization: Dict[str, float]
    ai_summary: str
    recommended_actions: List[str]

# ─── MOCK PREDICTION SERVICE (NO CLOUD) ─────────────────────────────────────

class MockPredictionService:
    """
    Pure local prediction service — rule-based with realistic noise.
    Zero cloud dependencies, zero cost.
    """
    
    def __init__(self):
        self.historical_avg = {
            TruckType.FLATBED: 45,
            TruckType.REFRIGERATED: 60,
            TruckType.TANKER: 75,
            TruckType.CONTAINER: 50,
            TruckType.DRY_VAN: 40,
            TruckType.OVERSIZE: 90
        }
        print("✅ MockPredictionService initialized (local — $0 cloud costs)")
    
    async def predict_eta_and_service(self, truck: TruckInput, 
                                     current_time: datetime,
                                     weather_delay_factor: float = 1.0) -> PredictionResult:
        base_service = self.historical_avg[truck.truck_type]
        
        hour = truck.estimated_arrival.hour
        if 8 <= hour <= 10 or 16 <= hour <= 18:
            traffic_factor = 1.3
        elif 22 <= hour or hour <= 5:
            traffic_factor = 0.9
        else:
            traffic_factor = 1.0
        
        priority_factor = {
            Priority.CRITICAL: 0.85,
            Priority.HIGH: 0.9,
            Priority.STANDARD: 1.0,
            Priority.LOW: 1.1
        }[truck.priority]
        
        weight_factor = 1 + (truck.cargo_weight - 20000) / 100000
        hazard_factor = 1.2 if truck.cargo_hazardous else 1.0
        
        predicted_service = (base_service * traffic_factor * priority_factor * 
                           weight_factor * hazard_factor * weather_delay_factor)
        
        noise = np.random.normal(0, predicted_service * 0.1)
        predicted_service = max(15, predicted_service + noise)
        
        arrival_noise = np.random.normal(0, 12)
        predicted_arrival = truck.estimated_arrival + timedelta(minutes=arrival_noise)
        
        ci_width = predicted_service * 0.2
        delay_prob = min(1.0, max(0.0, arrival_noise / 30 + 0.2))
        
        return PredictionResult(
            truck_id=truck.truck_id,
            predicted_arrival=predicted_arrival,
            predicted_service_minutes=predicted_service,
            confidence_interval=(max(15, predicted_service - ci_width), 
                               predicted_service + ci_width),
            delay_probability=delay_prob,
            weather_impact_factor=weather_delay_factor
        )

# ─── OR-TOOLS OPTIMIZATION ENGINE ────────────────────────────────────────────

from ortools.sat.python import cp_model

class OptimizationEngine:
    def __init__(self, yard_graph: List[YardEdge], docks: List[Dock]):
        self.yard_graph = self._build_graph(yard_graph)
        self.docks = {d.dock_id: d for d in docks}
        self.staging_areas = ["staging_north", "staging_south", "staging_east", "staging_west"]
    
    def _build_graph(self, edges: List[YardEdge]) -> Dict:
        graph = {}
        for edge in edges:
            if edge.from_node not in graph:
                graph[edge.from_node] = []
            graph[edge.from_node].append((edge.to_node, edge.distance_m, edge.speed_limit_kmh, 
                                        edge.congestion_factor, edge.width_m))
            if edge.bidirectional:
                if edge.to_node not in graph:
                    graph[edge.to_node] = []
                graph[edge.to_node].append((edge.from_node, edge.distance_m, edge.speed_limit_kmh,
                                          edge.congestion_factor, edge.width_m))
        return graph
    
    def solve_dock_assignment(self, trucks: List[TruckInput], 
                             predictions: List[PredictionResult],
                             current_time: datetime) -> Dict[str, str]:
        model = cp_model.CpModel()
        
        truck_ids = [t.truck_id for t in trucks]
        dock_ids = list(self.docks.keys())
        
        assignment = {}
        for t in truck_ids:
            assignment[t] = {}
            for d in dock_ids:
                assignment[t][d] = model.NewBoolVar(f"assign_{t}_{d}")
        
        start_time = {t: model.NewIntVar(0, 1440, f"start_{t}") for t in truck_ids}
        
        for t in truck_ids:
            model.Add(sum(assignment[t][d] for d in dock_ids) == 1)
        
        for t_idx, truck in enumerate(trucks):
            for d in dock_ids:
                if truck.truck_type not in self.docks[d].supported_types:
                    model.Add(assignment[truck.truck_id][d] == 0)
        
        for d in dock_ids:
            for t_idx, truck in enumerate(trucks):
                if truck.cargo_weight > self.docks[d].capacity_kg:
                    model.Add(assignment[truck.truck_id][d] == 0)
        
        for t_idx, truck in enumerate(trucks):
            if truck.cargo_hazardous:
                for d in dock_ids:
                    if not self.docks[d].has_hazard_handling:
                        model.Add(assignment[truck.truck_id][d] == 0)
        
        for d in dock_ids:
            intervals = []
            for t_idx, truck in enumerate(trucks):
                pred = predictions[t_idx]
                duration = int(pred.predicted_service_minutes)
                is_assigned = assignment[truck.truck_id][d]
                interval = model.NewOptionalIntervalVar(
                    start_time[truck.truck_id],
                    duration,
                    start_time[truck.truck_id] + duration,
                    is_assigned,
                    f"interval_{truck.truck_id}_{d}"
                )
                intervals.append(interval)
            model.AddNoOverlap(intervals)
        
        for t_idx, truck in enumerate(trucks):
            pred = predictions[t_idx]
            arrival_minutes = int((pred.predicted_arrival - current_time).total_seconds() / 60)
            arrival_minutes = max(0, arrival_minutes)
            model.Add(start_time[truck.truck_id] >= arrival_minutes)
        
        for t_idx, truck in enumerate(trucks):
            pred = predictions[t_idx]
            max_duration = int(truck.driver_hours_remaining * 60)
            model.Add(start_time[truck.truck_id] + int(pred.predicted_service_minutes) <= max_duration)
        
        priority_weights = {
            Priority.CRITICAL: 10,
            Priority.HIGH: 5,
            Priority.STANDARD: 2,
            Priority.LOW: 1
        }
        
        total_cost = []
        for t_idx, truck in enumerate(trucks):
            pred = predictions[t_idx]
            arrival_minutes = int((pred.predicted_arrival - current_time).total_seconds() / 60)
            arrival_minutes = max(0, arrival_minutes)
            weight = priority_weights[truck.priority]
            wait_var = model.NewIntVar(0, 1440, f"wait_{truck.truck_id}")
            model.Add(wait_var == start_time[truck.truck_id] - arrival_minutes)
            weighted_wait = model.NewIntVar(0, 14400, f"wwait_{truck.truck_id}")
            model.AddMultiplicationEquality(weighted_wait, [wait_var, weight])
            total_cost.append(weighted_wait)
            
            for d in dock_ids:
                dock_pos = self.docks[d].position
                staging_pos = {"x": 0, "y": 0}
                dist = int(np.sqrt((dock_pos["x"] - staging_pos["x"])**2 + 
                                 (dock_pos["y"] - staging_pos["y"])**2))
                travel_cost = model.NewIntVar(0, 10000, f"travel_{truck.truck_id}_{d}")
                model.Add(travel_cost == dist * assignment[truck.truck_id][d])
                total_cost.append(travel_cost)
        
        model.Minimize(sum(total_cost))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        solver.parameters.num_search_workers = 8
        
        status = solver.Solve(model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            assignments = {}
            for t in truck_ids:
                for d in dock_ids:
                    if solver.Value(assignment[t][d]) == 1:
                        assignments[t] = d
                        break
            return assignments
        else:
            return self._greedy_fallback(trucks, predictions, current_time)
    
    def _greedy_fallback(self, trucks, predictions, current_time):
        sorted_trucks = sorted(zip(trucks, predictions), 
                             key=lambda x: (x[0].priority.value != "critical", 
                                          x[1].predicted_arrival))
        assignments = {}
        dock_release = {d: current_time for d in self.docks}
        
        for truck, pred in sorted_trucks:
            best_dock = None
            best_wait = float('inf')
            for d_id, dock in self.docks.items():
                if (truck.truck_type in dock.supported_types and 
                    truck.cargo_weight <= dock.capacity_kg and
                    (not truck.cargo_hazardous or dock.has_hazard_handling)):
                    wait = max(0, (dock_release[d_id] - pred.predicted_arrival).total_seconds() / 60)
                    if wait < best_wait:
                        best_wait = wait
                        best_dock = d_id
            if best_dock:
                assignments[truck.truck_id] = best_dock
                dock_release[best_dock] = max(dock_release[best_dock], pred.predicted_arrival) + \
                                         timedelta(minutes=pred.predicted_service_minutes)
        return assignments
    
    def solve_yard_routing(self, truck_id: str, start_node: str, 
                          target_dock: str, truck_type: TruckType) -> Tuple[List[str], float, float]:
        """Find optimal path through yard with congestion-aware Dijkstra"""
        
        def edge_cost(edge, is_oversize):
            to_node, dist, speed, congestion, width = edge
            speed_mpm = (speed * 1000) / 60.0
            base_cost = (dist / speed_mpm) * congestion
            if is_oversize and width < 5.0:
                base_cost *= 3.0
            return base_cost
        
        is_oversize = (truck_type == TruckType.OVERSIZE)
        
        if start_node == target_dock:
            return [start_node], 0.0, 0.0
        
        dist_map = {node: float('inf') for node in self.yard_graph}
        prev_map = {node: None for node in self.yard_graph}
        dist_map[start_node] = 0
        pq = [(0, start_node)]
        visited = set()
        
        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)
            if u == target_dock:
                break
            for edge in self.yard_graph.get(u, []):
                v = edge[0]
                cost = edge_cost(edge, is_oversize)
                if d + cost < dist_map[v]:
                    dist_map[v] = d + cost
                    prev_map[v] = u
                    heapq.heappush(pq, (d + cost, v))
        
        path = []
        curr = target_dock
        while curr is not None:
            path.append(curr)
            curr = prev_map[curr]
        path.reverse()
        
        if dist_map[target_dock] == float('inf') or len(path) < 2:
            return [start_node, target_dock], 100.0, 2.0
        
        total_distance = 0
        for i in range(len(path) - 1):
            for edge in self.yard_graph.get(path[i], []):
                if edge[0] == path[i+1]:
                    total_distance += edge[1]
                    break
        
        total_time = dist_map[target_dock]
        if total_time == float('inf'):
            total_time = 999.0
            
        return path, total_distance, round(total_time, 1)

# ─── MAIN ORCHESTRATOR ───────────────────────────────────────────────────────

class StagingOptimizer:
    def __init__(self, prediction_service: MockPredictionService,
                 opt_engine: OptimizationEngine,
                 llm_service):
        self.predictor = prediction_service
        self.opt = opt_engine
        self.llm = llm_service
        self.current_time = datetime.now()
    
    async def optimize(self, trucks: List[TruckInput]) -> OptimizationOutput:
        self.current_time = datetime.now()
        
        predictions = []
        for truck in trucks:
            pred = await self.predictor.predict_eta_and_service(truck, self.current_time)
            predictions.append(pred)
        
        assignments = self.opt.solve_dock_assignment(trucks, predictions, self.current_time)
        
        results = []
        total_delay = 0
        dock_usage = {d: 0 for d in self.opt.docks}
        
        for truck, pred in zip(trucks, predictions):
            dock_id = assignments.get(truck.truck_id)
            if not dock_id:
                continue
            
            dock = self.opt.docks[dock_id]
            
            arrival_min = (pred.predicted_arrival - self.current_time).total_seconds() / 60
            
            if arrival_min > 0:
                wait_time = 0.0
                expected_start = pred.predicted_arrival
            else:
                wait_time = 0.0
                expected_start = self.current_time
            
            staging = self._select_staging_area(dock_id, truck.truck_type)
            route, dist, route_time = self.opt.solve_yard_routing(
                truck.truck_id, staging, dock_id, truck.truck_type
            )
            
            congestion = self._assess_congestion(route)
            expected_end = expected_start + timedelta(minutes=pred.predicted_service_minutes)
            
            assignment = AssignmentResult(
                truck_id=truck.truck_id,
                assigned_dock=dock_id,
                expected_start=expected_start,
                expected_completion=expected_end,
                waiting_time_minutes=round(wait_time, 1),
                route=route,
                route_distance_m=dist,
                route_time_minutes=route_time,
                congestion_level=congestion,
                explanation="",
                alerts=[]
            )
            
            explanation = await self.llm.generate_explanation(truck, pred, assignment)
            assignment.explanation = explanation["explanation"]
            assignment.alerts = explanation["alerts"]
            
            results.append(assignment)
            total_delay += wait_time
            dock_usage[dock_id] += pred.predicted_service_minutes / 60
        
        congestion_score = self._calculate_yard_congestion(results)
        utilization = {d: min(100, u / 8 * 100) for d, u in dock_usage.items()}
        
        output = OptimizationOutput(
            timestamp=self.current_time,
            assignments=results,
            yard_congestion_score=congestion_score,
            total_predicted_delay_minutes=round(total_delay, 1),
            dock_utilization=utilization,
            ai_summary="",
            recommended_actions=[]
        )
        
        output.ai_summary = await self.llm.generate_yard_summary(output)
        
        if congestion_score > 70:
            output.recommended_actions.append("Activate overflow staging area")
        if total_delay > 120:
            output.recommended_actions.append("Call additional dock workers")
        
        return output
    
    def _select_staging_area(self, dock_id: str, truck_type: TruckType) -> str:
        dock_pos = self.opt.docks[dock_id].position
        
        best_staging = "staging_west"
        best_dist = float('inf')
        
        for staging in self.opt.staging_areas:
            if staging in self.opt.yard_graph:
                route, dist, time = self.opt.solve_yard_routing("test", staging, dock_id, truck_type)
                if dist < best_dist and dist != float('inf'):
                    best_dist = dist
                    best_staging = staging
        
        return best_staging
    
    def _assess_congestion(self, route: List[str]) -> str:
        if len(route) < 2:
            return "low"
        total_congestion = 0
        edges_count = 0
        for i in range(len(route) - 1):
            found = False
            for edge in self.opt.yard_graph.get(route[i], []):
                if edge[0] == route[i+1]:
                    total_congestion += edge[3]
                    edges_count += 1
                    found = True
                    break
            if not found:
                continue
        
        if edges_count == 0:
            return "low"
        avg = total_congestion / edges_count
        if avg > 1.5:
            return "high"
        elif avg > 1.2:
            return "medium"
        return "low"
    
    def _calculate_yard_congestion(self, assignments: List[AssignmentResult]) -> float:
        if not assignments:
            return 0
        high_count = sum(1 for a in assignments if a.congestion_level == "high")
        med_count = sum(1 for a in assignments if a.congestion_level == "medium")
        score = (high_count * 30 + med_count * 15) / len(assignments)
        return min(100, score)

# ─── FASTAPI APPLICATION ─────────────────────────────────────────────────────

optimizer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global optimizer
    
    # Import here to avoid circular dependency
    from enhanced_optimizer import create_enhanced_optimizer
    
    yard_edges = [
        YardEdge(from_node="gate_main", to_node="staging_north", distance_m=150, speed_limit_kmh=15, congestion_factor=1.0),
        YardEdge(from_node="gate_main", to_node="staging_south", distance_m=180, speed_limit_kmh=15, congestion_factor=1.1),
        YardEdge(from_node="gate_secondary", to_node="staging_east", distance_m=120, speed_limit_kmh=15, congestion_factor=0.9),
        YardEdge(from_node="staging_north", to_node="corridor_north", distance_m=200, speed_limit_kmh=10, congestion_factor=1.2),
        YardEdge(from_node="staging_south", to_node="corridor_south", distance_m=220, speed_limit_kmh=10, congestion_factor=1.0),
        YardEdge(from_node="staging_east", to_node="corridor_east", distance_m=180, speed_limit_kmh=10, congestion_factor=1.3),
        YardEdge(from_node="corridor_north", to_node="dock_zone_A", distance_m=100, speed_limit_kmh=8, congestion_factor=1.1),
        YardEdge(from_node="corridor_north", to_node="dock_zone_B", distance_m=150, speed_limit_kmh=8, congestion_factor=1.4),
        YardEdge(from_node="corridor_south", to_node="dock_zone_C", distance_m=120, speed_limit_kmh=8, congestion_factor=1.0),
        YardEdge(from_node="corridor_east", to_node="dock_zone_D", distance_m=140, speed_limit_kmh=8, congestion_factor=1.2),
        YardEdge(from_node="dock_zone_A", to_node="D-01", distance_m=30, speed_limit_kmh=5, congestion_factor=1.0),
        YardEdge(from_node="dock_zone_A", to_node="D-02", distance_m=35, speed_limit_kmh=5, congestion_factor=1.0),
        YardEdge(from_node="dock_zone_B", to_node="D-03", distance_m=40, speed_limit_kmh=5, congestion_factor=1.5),
        YardEdge(from_node="dock_zone_C", to_node="D-04", distance_m=35, speed_limit_kmh=5, congestion_factor=1.0, width_m=6.0),
        YardEdge(from_node="dock_zone_D", to_node="D-05", distance_m=30, speed_limit_kmh=5, congestion_factor=1.1),
        YardEdge(from_node="dock_zone_D", to_node="D-06", distance_m=35, speed_limit_kmh=5, congestion_factor=1.1),
        YardEdge(from_node="corridor_north", to_node="corridor_east", distance_m=250, speed_limit_kmh=10, congestion_factor=1.3),
        YardEdge(from_node="corridor_south", to_node="corridor_east", distance_m=200, speed_limit_kmh=10, congestion_factor=1.2),
        YardEdge(from_node="dock_zone_A", to_node="dock_zone_B", distance_m=80, speed_limit_kmh=5, congestion_factor=1.6),
    ]
    
    docks = [
        Dock(dock_id="D-01", position={"x": 450, "y": 150}, 
             supported_types=[TruckType.DRY_VAN, TruckType.CONTAINER],
             capacity_kg=30000, has_refrigeration=False, has_hazard_handling=False),
        Dock(dock_id="D-02", position={"x": 480, "y": 180},
             supported_types=[TruckType.DRY_VAN, TruckType.FLATBED],
             capacity_kg=40000, has_refrigeration=False, has_hazard_handling=False),
        Dock(dock_id="D-03", position={"x": 500, "y": 200},
             supported_types=[TruckType.TANKER],
             capacity_kg=50000, has_refrigeration=False, has_hazard_handling=True),
        Dock(dock_id="D-04", position={"x": 700, "y": 400},
             supported_types=[TruckType.CONTAINER, TruckType.OVERSIZE],
             capacity_kg=80000, has_refrigeration=False, has_hazard_handling=True),
        Dock(dock_id="D-05", position={"x": 720, "y": 420},
             supported_types=[TruckType.FLATBED, TruckType.OVERSIZE],
             capacity_kg=75000, has_refrigeration=False, has_hazard_handling=False),
        Dock(dock_id="D-06", position={"x": 350, "y": 300},
             supported_types=[TruckType.REFRIGERATED],
             capacity_kg=35000, has_refrigeration=True, has_hazard_handling=True),
    ]
    
    opt_engine = OptimizationEngine(yard_edges, docks)
    optimizer = create_enhanced_optimizer(opt_engine)
    
    print("✅ Optimizer initialized successfully (100% local — $0 cloud costs)")
    yield
    print("🛑 Shutting down optimizer")

app = FastAPI(title="YMS Staging Optimizer", version="2.0.0", lifespan=lifespan)

@app.post("/optimize", response_model=OptimizationOutput)
async def optimize_staging(trucks: List[TruckInput]):
    if not optimizer:
        raise HTTPException(status_code=503, detail="System initializing")
    if len(trucks) > 50:
        raise HTTPException(status_code=400, detail="Batch size limited to 50 trucks")
    result = await optimizer.optimize(trucks)
    return result

@app.get("/yard-status")
async def yard_status():
    if not optimizer:
        raise HTTPException(status_code=503, detail="System initializing")
    return {
        "timestamp": datetime.now(),
        "dock_status": {
            dock_id: {
                "status": "available" if not dock.current_truck else "occupied",
                "queue_length": len(dock.queue),
                "next_available": dock.estimated_release
            }
            for dock_id, dock in optimizer.opt.docks.items()
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)