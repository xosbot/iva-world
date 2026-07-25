"""
Simulation Engine for IVA-World.
Manages agent states, positions on 20x20 grid, and state machine logic.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field, asdict
import time


class AgentStateStatus(Enum):
    """Agent status states."""
    IDLE = "IDLE"
    THINKING = "THINKING"
    COMMUNICATING = "COMMUNICATING"
    USING_TOOL = "USING_TOOL"
    ERROR = "ERROR"


@dataclass
class AgentState:
    """Represents the complete state of an agent."""
    agent_id: str
    name: str
    avatar: str
    status: str
    position_x: int
    position_y: int
    target_x: int
    target_y: int
    message: str = ""
    last_update: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "avatar": self.avatar,
            "status": self.status,
            "position": [self.position_x, self.position_y],
            "target_position": [self.target_x, self.target_y],
            "message": self.message,
            "last_update": self.last_update
        }


# Predefined zones on the 20x20 grid
ZONES = {
    "iva_desk": {"x": 2, "y": 2, "label": "IVA's Desk"},
    "meeting_rug": {"x": 10, "y": 10, "label": "Meeting Rug"},
    "research_lab": {"x": 18, "y": 2, "label": "Research Lab (Luna)"},
    "code_forge": {"x": 15, "y": 5, "label": "Code Forge (Archie)"},
    "coding_station": {"x": 12, "y": 8, "label": "Coding Station (Byte)"},
    "design_studio": {"x": 8, "y": 15, "label": "Design Studio (Pixel)"},
    "security_office": {"x": 5, "y": 18, "label": "Security Office (Guardian)"},
    "bed_zone": {"x": 1, "y": 1, "label": "Bed Zone"},
    "library": {"x": 18, "y": 4, "label": "Library"},
    "computer_desk": {"x": 12, "y": 6, "label": "Computer Desk"}
}


class SimulationEngine:
    """
    Core simulation engine managing all agent states and grid world.
    Broadcasts state changes via callback to WebSocket server.
    """
    
    GRID_SIZE = 20
    
    def __init__(self):
        self.agents: Dict[str, AgentState] = {}
        self.state_callback: Optional[Callable] = None
        self.running = False
        self.broadcast_interval = 0.5  # seconds
        
        # Initialize with default agent positions
        self._initialize_default_agents()
    
    def _initialize_default_agents(self):
        """Initialize all agents with their default positions."""
        default_agents = [
            {"id": "iva_001", "name": "IVA", "avatar": "white_persian", "zone": "iva_desk"},
            {"id": "luna_001", "name": "Luna", "avatar": "siamese", "zone": "research_lab"},
            {"id": "archie_001", "name": "Archie", "avatar": "tabby", "zone": "code_forge"},
            {"id": "byte_001", "name": "Byte", "avatar": "black", "zone": "coding_station"},
            {"id": "pixel_001", "name": "Pixel", "avatar": "calico", "zone": "design_studio"},
            {"id": "guardian_001", "name": "Guardian", "avatar": "sphynx", "zone": "security_office"}
        ]
        
        for agent_info in default_agents:
            zone = ZONES.get(agent_info["zone"], ZONES["iva_desk"])
            self.register_agent(
                agent_id=agent_info["id"],
                name=agent_info["name"],
                avatar=agent_info["avatar"],
                x=zone["x"],
                y=zone["y"]
            )
    
    def register_agent(
        self,
        agent_id: str,
        name: str,
        avatar: str,
        x: int = 0,
        y: int = 0
    ) -> AgentState:
        """Register a new agent in the simulation."""
        agent_state = AgentState(
            agent_id=agent_id,
            name=name,
            avatar=avatar,
            status=AgentStateStatus.IDLE.value,
            position_x=min(max(x, 0), self.GRID_SIZE - 1),
            position_y=min(max(y, 0), self.GRID_SIZE - 1),
            target_x=x,
            target_y=y
        )
        
        self.agents[agent_id] = agent_state
        return agent_state
    
    def unregister_agent(self, agent_id: str):
        """Remove an agent from the simulation."""
        if agent_id in self.agents:
            del self.agents[agent_id]
    
    def set_state_callback(self, callback: Callable):
        """Set callback function for broadcasting state changes."""
        self.state_callback = callback
    
    async def broadcast_state(self):
        """Broadcast all agent states via callback."""
        if not self.state_callback:
            return
        
        states = [agent.to_dict() for agent in self.agents.values()]
        await self.state_callback(states)
    
    def update_agent_status(self, agent_id: str, status: str, message: str = ""):
        """Update an agent's status."""
        if agent_id not in self.agents:
            return
        
        agent = self.agents[agent_id]
        agent.status = status
        agent.message = message
        agent.last_update = time.time()
    
    def move_agent_to(self, agent_id: str, x: int, y: int):
        """Set target position for an agent."""
        if agent_id not in self.agents:
            return
        
        agent = self.agents[agent_id]
        agent.target_x = min(max(x, 0), self.GRID_SIZE - 1)
        agent.target_y = min(max(y, 0), self.GRID_SIZE - 1)
    
    def move_agent_to_zone(self, agent_id: str, zone_name: str):
        """Move agent to a predefined zone."""
        zone = ZONES.get(zone_name)
        if zone:
            self.move_agent_to(agent_id, zone["x"], zone["y"])
    
    def update_positions(self):
        """Update all agent positions toward their targets (simple interpolation)."""
        for agent in self.agents.values():
            if agent.position_x != agent.target_x or agent.position_y != agent.target_y:
                # Move one step toward target
                dx = agent.target_x - agent.position_x
                dy = agent.target_y - agent.position_y
                
                if dx != 0:
                    agent.position_x += 1 if dx > 0 else -1
                if dy != 0:
                    agent.position_y += 1 if dy > 0 else -1
    
    def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a specific agent."""
        agent = self.agents.get(agent_id)
        return agent.to_dict() if agent else None
    
    def get_all_states(self) -> List[Dict[str, Any]]:
        """Get current states of all agents."""
        return [agent.to_dict() for agent in self.agents.values()]
    
    def get_zone_coordinates(self, zone_name: str) -> tuple:
        """Get coordinates for a named zone."""
        zone = ZONES.get(zone_name)
        if zone:
            return (zone["x"], zone["y"])
        return (0, 0)
    
    async def run_simulation_loop(self):
        """Main simulation loop - updates positions and broadcasts state."""
        self.running = True
        
        while self.running:
            # Update positions
            self.update_positions()
            
            # Broadcast state
            await self.broadcast_state()
            
            # Wait for next update
            await asyncio.sleep(self.broadcast_interval)
    
    def stop(self):
        """Stop the simulation loop."""
        self.running = False
    
    def get_zones(self) -> Dict[str, Dict[str, Any]]:
        """Get all defined zones."""
        return ZONES.copy()


# Singleton instance
_engine_instance: Optional[SimulationEngine] = None


def get_simulation_engine() -> SimulationEngine:
    """Get or create the singleton simulation engine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SimulationEngine()
    return _engine_instance
