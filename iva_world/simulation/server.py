"""
FastAPI Server with WebSocket support for IVA-World.
Serves frontend files and broadcasts agent state changes in real-time.
"""

import asyncio
import json
from typing import Dict, Any, List, Set
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Import simulation engine
from simulation.engine import get_simulation_engine, SimulationEngine


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WebSocket] Client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WebSocket] Client disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast data to all connected clients."""
        message = json.dumps(data)
        
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"[WebSocket] Error sending to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_personal(self, data: Dict[str, Any], websocket: WebSocket):
        """Send data to a specific client."""
        message = json.dumps(data)
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"[WebSocket] Error sending personal message: {e}")
            self.disconnect(websocket)


# Create FastAPI app
app = FastAPI(
    title="IVA-World Simulation Server",
    description="Real-time agent state visualization backend",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection manager
manager = ConnectionManager()

# Get simulation engine
engine = get_simulation_engine()


@app.on_event("startup")
async def startup_event():
    """Initialize on server startup."""
    print("[Server] Starting up...")
    
    # Set up state callback to broadcast via WebSocket
    async def broadcast_states(states: List[Dict[str, Any]]):
        await manager.broadcast({
            "type": "state_update",
            "agents": states,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    engine.set_state_callback(broadcast_states)
    
    # Start simulation loop in background
    asyncio.create_task(run_simulation())
    
    print("[Server] Simulation engine started")


async def run_simulation():
    """Run the simulation loop in background."""
    try:
        await engine.run_simulation_loop()
    except asyncio.CancelledError:
        pass


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on server shutdown."""
    print("[Server] Shutting down...")
    engine.stop()


@app.get("/")
async def root():
    """Serve the main HTML page."""
    frontend_dir = Path(__file__).parent.parent / "frontend"
    index_path = frontend_dir / "index.html"
    
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        return HTMLResponse(
            content="<h1>IVA-World</h1><p>Frontend files not found. Please ensure frontend/ directory exists.</p>",
            status_code=404
        )



@app.get("/3d")
async def root_3d():
    """Serve the 3D visualization HTML page."""
    frontend_dir = Path(__file__).parent.parent / "frontend"
    index_path = frontend_dir / "index3d.html"
    
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        return HTMLResponse(
            content="<h1>IVA-World 3D</h1><p>3D frontend file not found.</p>",
            status_code=404
        )


@app.get("/zones")
async def get_zones():
    """Return all defined zones on the grid."""
    return {"zones": engine.get_zones()}


@app.get("/agents")
async def get_agents():
    """Return current state of all agents."""
    return {"agents": engine.get_all_states()}


@app.get("/agent/{agent_id}")
async def get_agent(agent_id: str):
    """Return state of a specific agent."""
    state = engine.get_agent_state(agent_id)
    if state:
        return {"agent": state}
    else:
        return {"error": f"Agent {agent_id} not found"}, 404


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time state updates."""
    await manager.connect(websocket)
    
    # Send initial state immediately
    initial_data = {
        "type": "initial_state",
        "agents": engine.get_all_states(),
        "zones": engine.get_zones(),
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_personal(initial_data, websocket)
    
    try:
        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            
            # Handle client commands
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "move_agent":
                    agent_id = message.get("agent_id")
                    x = message.get("x")
                    y = message.get("y")
                    
                    if agent_id and x is not None and y is not None:
                        engine.move_agent_to(agent_id, int(x), int(y))
                        await manager.send_personal({
                            "type": "command_ack",
                            "success": True,
                            "message": f"Moved {agent_id} to ({x}, {y})"
                        }, websocket)
                
                elif msg_type == "update_status":
                    agent_id = message.get("agent_id")
                    status = message.get("status")
                    msg = message.get("message", "")
                    
                    if agent_id and status:
                        engine.update_agent_status(agent_id, status, msg)
                        await manager.send_personal({
                            "type": "command_ack",
                            "success": True,
                            "message": f"Updated {agent_id} status to {status}"
                        }, websocket)
                
                elif msg_type == "ping":
                    await manager.send_personal({
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time()
                    }, websocket)
                    
            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"[WebSocket] Error processing message: {e}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket] Connection error: {e}")
        manager.disconnect(websocket)


# Serve static files from frontend directory
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets"), html=True), name="assets")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
