"""
gRPC Client for IVA-World agent communication.
Provides client utilities for dispatching tasks between agents.
"""

import asyncio
import json
from typing import Optional, Dict, Any

import grpc

# Import generated gRPC code
from protos.generated import agent_comms_pb2
from protos.generated import agent_comms_pb2_grpc


class GRPCClient:
    """gRPC client for agent communication."""
    
    def __init__(self, host: str = "localhost", port: int = 50051):
        self.host = host
        self.port = port
        self.channel = None
        self.stub = None
    
    async def connect(self):
        """Establish connection to gRPC server."""
        address = f"{self.host}:{self.port}"
        self.channel = grpc.aio.insecure_channel(address)
        self.stub = agent_comms_pb2_grpc.AgentCommunicationStub(self.channel)
        print(f"[gRPC Client] Connected to {address}")
    
    async def disconnect(self):
        """Close connection to gRPC server."""
        if self.channel:
            await self.channel.close()
            print("[gRPC Client] Disconnected")
    
    async def dispatch_task(
        self,
        task_id: str,
        source_agent: str,
        target_agent: str,
        task_type: str,
        description: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Dispatch a task to another agent."""
        if not self.stub:
            await self.connect()
        
        request = agent_comms_pb2.TaskRequest(
            task_id=task_id,
            source_agent=source_agent,
            target_agent=target_agent,
            task_type=task_type,
            description=description,
            parameters=json.dumps(parameters) if parameters else ""
        )
        
        try:
            response = await self.stub.DispatchTask(request)
            
            return {
                "task_id": response.task_id,
                "success": response.success,
                "result": json.loads(response.result) if response.result else {},
                "error": response.error
            }
        except grpc.RpcError as e:
            return {
                "task_id": task_id,
                "success": False,
                "error": f"gRPC error: {e.code()} - {e.details()}"
            }
    
    async def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        content: str,
        message_type: str = "text"
    ) -> Dict[str, Any]:
        """Send a direct message between agents."""
        if not self.stub:
            await self.connect()
        
        import time
        timestamp = str(int(time.time()))
        
        request = agent_comms_pb2.MessageRequest(
            message_id=f"msg_{timestamp}",
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
            timestamp=timestamp
        )
        
        try:
            response = await self.stub.SendMessage(request)
            
            return {
                "message_id": response.message_id,
                "delivered": response.delivered,
                "timestamp": response.timestamp
            }
        except grpc.RpcError as e:
            return {
                "delivered": False,
                "error": f"gRPC error: {e.code()} - {e.details()}"
            }
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a pending task."""
        if not self.stub:
            await self.connect()
        
        request = agent_comms_pb2.TaskStatusRequest(task_id=task_id)
        
        try:
            response = await self.stub.GetTaskStatus(request)
            
            return {
                "task_id": response.task_id,
                "found": response.found,
                "status": response.status,
                "result": json.loads(response.result) if response.result else None
            }
        except grpc.RpcError as e:
            return {
                "found": False,
                "error": f"gRPC error: {e.code()} - {e.details()}"
            }
    
    async def stream_agent_state(self, agent_name: str):
        """Stream state updates for an agent."""
        if not self.stub:
            await self.connect()
        
        request = agent_comms_pb2.AgentStateRequest(agent_name=agent_name)
        
        try:
            responses = self.stub.StreamAgentState(request)
            
            async for response in responses:
                state = response.state
                yield {
                    "agent_id": state.agent_id,
                    "name": state.name,
                    "status": state.status,
                    "position": (state.position_x, state.position_y),
                    "message": state.message
                }
        except grpc.RpcError as e:
            print(f"gRPC streaming error: {e.code()} - {e.details()}")


async def test_client():
    """Test the gRPC client."""
    client = GRPCClient()
    
    try:
        await client.connect()
        
        # Test dispatch task
        result = await client.dispatch_task(
            task_id="test_001",
            source_agent="iva_001",
            target_agent="luna",
            task_type="research",
            description="Test research task",
            parameters={"query": "test"}
        )
        
        print(f"Task result: {result}")
        
        # Test send message
        msg_result = await client.send_message(
            sender_id="iva_001",
            receiver_id="luna_001",
            content="Hello Luna!"
        )
        
        print(f"Message result: {msg_result}")
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_client())
