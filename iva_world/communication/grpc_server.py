"""
gRPC Server for IVA-World agent communication.
Handles task dispatching and inter-agent messaging.
"""

import asyncio
import json
from typing import Dict, Any
from concurrent import futures

import grpc

# Import generated gRPC code
from protos.generated import agent_comms_pb2
from protos.generated import agent_comms_pb2_grpc

# Import agent factory
from core.agent_factory import get_agent_factory, AgentFactory


class AgentCommunicationServicer(agent_comms_pb2_grpc.AgentCommunicationServiceServicer):
    """gRPC servicer for agent communication."""
    
    def __init__(self, agent_factory: AgentFactory):
        self.agent_factory = agent_factory
        self.pending_tasks: Dict[str, Dict[str, Any]] = {}
    
    async def DispatchTask(self, request, context):
        """Handle task dispatch from one agent to another."""
        print(f"[gRPC] DispatchTask: {request.source_agent} -> {request.target_agent}")
        print(f"[gRPC] Task type: {request.task_type}")
        print(f"[gRPC] Description: {request.description}")
        
        try:
            # Parse parameters
            parameters = {}
            if request.parameters:
                parameters = json.loads(request.parameters)
            
            # Get target agent
            agent_name = request.target_agent
            
            # Execute task via agent factory
            task_data = {
                "task_id": request.task_id,
                "task_type": request.task_type,
                "description": request.description,
                "source_agent": request.source_agent,
                **parameters
            }
            
            # Store pending task
            self.pending_tasks[request.task_id] = {
                "request": request,
                "status": "processing"
            }
            
            result = await self.agent_factory.execute_task_for_agent(agent_name, task_data)
            
            # Update pending task status
            self.pending_tasks[request.task_id]["status"] = "completed"
            self.pending_tasks[request.task_id]["result"] = result
            
            # Create response
            success = result.get("success", False)
            
            return agent_comms_pb2.TaskResponse(
                task_id=request.task_id,
                success=success,
                result=json.dumps(result),
                error="" if success else result.get("error", "Unknown error")
            )
            
        except Exception as e:
            print(f"[gRPC] Error executing task: {e}")
            self.pending_tasks.get(request.task_id, {})["status"] = "failed"
            self.pending_tasks.get(request.task_id, {})["error"] = str(e)
            
            return agent_comms_pb2.TaskResponse(
                task_id=request.task_id,
                success=False,
                result="",
                error=str(e)
            )
    
    async def SendMessage(self, request, context):
        """Handle direct message between agents."""
        print(f"[gRPC] Message: {request.sender_id} -> {request.receiver_id}")
        print(f"[gRPC] Content: {request.content}")
        
        # For now, just acknowledge the message
        # In a full implementation, this would route to the receiver's message queue
        
        return agent_comms_pb2.MessageResponse(
            message_id=request.message_id,
            delivered=True,
            timestamp=request.timestamp
        )
    
    async def GetTaskStatus(self, request, context):
        """Get status of a pending task."""
        task_info = self.pending_tasks.get(request.task_id)
        
        if not task_info:
            return agent_comms_pb2.TaskStatusResponse(
                task_id=request.task_id,
                found=False,
                status="unknown"
            )
        
        result = task_info.get("result", {})
        
        return agent_comms_pb2.TaskStatusResponse(
            task_id=request.task_id,
            found=True,
            status=task_info.get("status", "unknown"),
            result=json.dumps(result) if result else ""
        )
    
    async def StreamAgentState(self, request, context):
        """Stream agent state updates to clients."""
        # This would be used for real-time state streaming
        # For now, we use WebSocket for frontend communication
        
        agent_name = request.agent_name
        
        # Send initial state
        agent = self.agent_factory.get_agent(agent_name)
        if agent:
            state = agent_comms_pb2.AgentState(
                agent_id=agent.agent_id,
                name=agent.name,
                status=agent.status,
                position_x=agent.current_position[0],
                position_y=agent.current_position[1],
                message=agent._current_message
            )
            yield agent_comms_pb2.AgentStateResponse(state=state)


class GRPCServer:
    """gRPC server wrapper for IVA-World."""
    
    def __init__(self, host: str = "localhost", port: int = 50051):
        self.host = host
        self.port = port
        self.server = None
        self.agent_factory = get_agent_factory()
    
    async def start(self):
        """Start the gRPC server."""
        # Create server with options
        self.server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ('grpc.max_metadata_size', 4 * 1024 * 1024),
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
            ]
        )
        
        # Add servicer
        servicer = AgentCommunicationServicer(self.agent_factory)
        agent_comms_pb2_grpc.add_AgentCommunicationServiceServicer_to_server(
            servicer, self.server
        )
        
        # Bind to address
        listen_addr = f"{self.host}:{self.port}"
        self.server.add_insecure_port(listen_addr)
        
        # Start server
        await self.server.start()
        
        print(f"[gRPC] Server started on {listen_addr}")
        
        return self.server
    
    async def serve(self):
        """Run the gRPC server until shutdown."""
        if not self.server:
            await self.start()
        
        print("[gRPC] Serving...")
        await self.server.wait_for_termination()
    
    async def stop(self, grace: float = 0):
        """Stop the gRPC server."""
        if self.server:
            await self.server.stop(grace)
            print("[gRPC] Server stopped")


async def run_server(host: str = "localhost", port: int = 50051):
    """Run the gRPC server."""
    server = GRPCServer(host, port)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(run_server())
