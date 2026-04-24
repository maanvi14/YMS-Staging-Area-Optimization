"""
Ollama/Llama 3 Integration for YMS Staging Optimizer (FINAL STABLE VERSION)
"""

import os
import json
import httpx
from typing import Dict


class OllamaLLMService:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3:latest"):
        self.base_url = base_url
        self.model = model
        self.available = self._check_availability()

        if self.available:
            print(f"✅ Connected to Ollama: {self.model}")
        else:
            print(f"🔶 Ollama not available, using template fallback")

    def _check_availability(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get('models', [])
                names = [m.get('name', m.get('model')) for m in models]
                print(f"   📋 Ollama models found: {names}")

                for m in models:
                    name = m.get('name', m.get('model'))
                    if self.model in name:
                        self.model = name
                        return True
        except Exception:
            pass
        return False

    async def generate_explanation(self, truck_data: Dict, assignment_data: Dict) -> str:
        if not self.available:
            return self._template_explanation(truck_data, assignment_data)

        prompt = self._build_prompt(truck_data, assignment_data)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": "You must always return a 2 sentence explanation. Never return empty output.",
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 300,
                            "top_p": 0.9
                        }
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    print("🧠 FULL OLLAMA RESPONSE:", result)

                    explanation = result.get("response", "").strip()

                    # remove prompt echo if present
                    if prompt in explanation:
                        explanation = explanation.split(prompt)[-1].strip()

                    # ✅ accept ANY non-empty response
                    if explanation:
                        print("✅ USING LLM OUTPUT")
                        return explanation

                print("⚠️ Falling back to template")
                return self._template_explanation(truck_data, assignment_data)

        except Exception as e:
            print("⚠️ LLM ERROR:", e)
            return self._template_explanation(truck_data, assignment_data)

    async def generate_alert_message(self, alert_type: str, details: Dict) -> str:
        return self._template_alert(alert_type, details)

    async def generate_yard_summary(self, metrics: Dict) -> str:
        if not self.available:
            return self._template_summary(metrics)

        prompt = f"""
Summarize yard status:

Trucks: {metrics.get('total_trucks')}
Delay: {metrics.get('avg_delay'):.1f}
Congestion: {metrics.get('congestion_score')}

Give 2-line summary:
"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": "Always return a summary.",
                        "stream": False,
                        "options": {"temperature": 0.4, "num_predict": 120}
                    },
                    timeout=15.0
                )

                if response.status_code == 200:
                    result = response.json()
                    summary = result.get("response", "").strip()
                    if summary:
                        return summary

        except Exception:
            pass

        return self._template_summary(metrics)

    def _build_prompt(self, truck_data: Dict, assignment_data: Dict) -> str:
        return f"""
You are a logistics AI.

Explain WHY this truck is assigned to this dock.

Truck: {truck_data.get('truck_type')} | Priority: {truck_data.get('priority')}
Dock: {assignment_data.get('assigned_dock')}
Distance: {assignment_data.get('route_distance_m')} m
Congestion: {assignment_data.get('congestion_level')}

Answer in 2 sentences.
"""

    def _template_explanation(self, truck_data: Dict, assignment_data: Dict) -> str:
        return f"{truck_data.get('truck_type')} assigned to {assignment_data.get('assigned_dock')} based on system optimization."

    def _template_alert(self, alert_type: str, details: Dict) -> str:
        return f"{alert_type}: {details}"

    def _template_summary(self, metrics: Dict) -> str:
        return f"Yard running with {metrics.get('total_trucks')} trucks and congestion {metrics.get('congestion_score')}/100."


# Singleton
_ollama_service = None

def get_ollama_service():
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaLLMService()
    return _ollama_service
