"""
Enhanced Optimizer with Ollama LLM Integration
Fully local — no cloud dependencies
"""

from ollama_service import get_ollama_service, OllamaLLMService

from yms_staging_optimizer import (
    TruckInput, PredictionResult, AssignmentResult, OptimizationOutput,
    MockPredictionService, OptimizationEngine, StagingOptimizer
)


class EnhancedLLMService:
    """Wraps Ollama with intelligent fallback to rule-based explanations"""
    
    def __init__(self):
        self.ollama = get_ollama_service()
        self.use_ollama = self.ollama is not None and self.ollama.available
        
        if self.use_ollama:
            print("✅ EnhancedLLMService using Ollama (Llama 3)")
        else:
            print("🔶 EnhancedLLMService using rule-based fallback (Ollama unavailable)")
    
    async def generate_explanation(self, truck: TruckInput, 
                                  prediction: PredictionResult,
                                  assignment: AssignmentResult) -> dict:
        
        # Build rich context for LLM
        truck_data = {
            'truck_id': truck.truck_id,
            'truck_type': truck.truck_type.value,
            'priority': truck.priority.value,
            'cargo_weight': truck.cargo_weight,
            'cargo_hazardous': truck.cargo_hazardous,
            'driver_hours_remaining': truck.driver_hours_remaining
        }
        
        assignment_data = {
            'assigned_dock': assignment.assigned_dock,
            'waiting_time_minutes': assignment.waiting_time_minutes,
            'route': assignment.route,
            'route_distance_m': assignment.route_distance_m,
            'route_time_minutes': assignment.route_time_minutes,
            'congestion_level': assignment.congestion_level
        }
        
        # Try Ollama first, fallback to rule-based
        explanation = None
        if self.use_ollama:
            try:
                explanation = await self.ollama.generate_explanation(truck_data, assignment_data)
            except Exception as e:
                print(f"⚠️ Ollama explanation failed: {e}")
        
        # Fallback: rule-based explanation
        if not explanation:
            if truck.priority.value == "critical":
                explanation = (f"Assigned to {assignment.assigned_dock} with immediate priority due to critical cargo. "
                             f"Route selected to minimize exposure to congestion zones.")
            elif assignment.waiting_time_minutes < 10:
                explanation = (f"Optimal assignment to {assignment.assigned_dock} with minimal waiting time. "
                             f"Efficient routing through low-congestion corridors.")
            else:
                explanation = (f"Assigned to {assignment.assigned_dock} balancing dock availability with truck priority. "
                             f"Expected wait due to current dock utilization.")
        
        # Generate alerts
        alerts = []
        recommendations = []
        
        if assignment.waiting_time_minutes > 30:
            if self.use_ollama:
                try:
                    alert_msg = await self.ollama.generate_alert_message('delay', {
                        'truck_id': truck.truck_id,
                        'delay': assignment.waiting_time_minutes
                    })
                except:
                    alert_msg = f"High waiting time: {assignment.waiting_time_minutes:.0f} minutes"
            else:
                alert_msg = f"High waiting time: {assignment.waiting_time_minutes:.0f} minutes"
            alerts.append(alert_msg)
            recommendations.append("Consider expediting current dock operations or reassigning to alternate dock")
        
        if prediction.delay_probability > 0.6:
            if self.use_ollama:
                try:
                    alert_msg = await self.ollama.generate_alert_message('delay', {
                        'truck_id': truck.truck_id,
                        'probability': prediction.delay_probability
                    })
                except:
                    alert_msg = f"High delay probability ({prediction.delay_probability:.0%}) due to traffic patterns"
            else:
                alert_msg = f"High delay probability ({prediction.delay_probability:.0%}) due to traffic patterns"
            alerts.append(alert_msg)
        
        if truck.driver_hours_remaining < 3:
            if self.use_ollama:
                try:
                    alert_msg = await self.ollama.generate_alert_message('hos', {
                        'truck_id': truck.truck_id,
                        'hours_remaining': truck.driver_hours_remaining
                    })
                except:
                    alert_msg = f"Driver nearing HOS limit ({truck.driver_hours_remaining:.1f}h remaining)"
            else:
                alert_msg = f"Driver nearing HOS limit ({truck.driver_hours_remaining:.1f}h remaining)"
            alerts.append(alert_msg)
            recommendations.append("Prioritize this truck to avoid driver timeout")
        
        if assignment.congestion_level == 'high':
            if self.use_ollama:
                try:
                    alert_msg = await self.ollama.generate_alert_message('congestion', {
                        'truck_id': truck.truck_id,
                        'dock': assignment.assigned_dock
                    })
                except:
                    alert_msg = f"High congestion on route to {assignment.assigned_dock}"
            else:
                alert_msg = f"High congestion on route to {assignment.assigned_dock}"
            alerts.append(alert_msg)
        
        return {
            "explanation": explanation,
            "alerts": alerts,
            "recommendations": recommendations
        }
    
    async def generate_yard_summary(self, output: OptimizationOutput) -> str:
        metrics = {
            'total_trucks': len(output.assignments),
            'avg_delay': output.total_predicted_delay_minutes / max(1, len(output.assignments)),
            'congestion_score': output.yard_congestion_score,
            'active_docks': sum(1 for u in output.dock_utilization.values() if u > 0),
            'total_docks': len(output.dock_utilization)
        }
        
        if self.use_ollama:
            try:
                return await self.ollama.generate_yard_summary(metrics)
            except Exception as e:
                print(f"⚠️ Ollama summary failed: {e}")
        
        # Fallback to rule-based summary
        if not output.assignments:
            return "No assignments to process."
        if output.total_predicted_delay_minutes < 30:
            return (f"Yard operating efficiently. Average delay {output.total_predicted_delay_minutes/len(output.assignments):.1f} min/truck. "
                   f"Congestion score: {output.yard_congestion_score:.0f}/100")
        elif output.yard_congestion_score > 70:
            return (f"Yard experiencing high congestion (score: {output.yard_congestion_score:.0f}). "
                   f"Total predicted delay: {output.total_predicted_delay_minutes:.0f} minutes. "
                   f"Consider activating overflow staging areas.")
        else:
            return (f"Yard operating at moderate capacity. Total delay: {output.total_predicted_delay_minutes:.0f} minutes. "
                   f"Monitor docks with utilization >85%.")


def create_enhanced_optimizer(opt_engine: OptimizationEngine):
    """Factory: Creates optimizer with Llama 3 + local mock predictions"""
    prediction_service = MockPredictionService()
    llm_service = EnhancedLLMService()
    
    return StagingOptimizer(prediction_service, opt_engine, llm_service)
