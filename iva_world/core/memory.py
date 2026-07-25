"""
core/memory.py
Persistent vector memory for agents using ChromaDB.
Allows agents to recall past research, code snippets, and decisions.
Includes fallback to simple in-memory storage when disk space is limited.
"""
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

# Try to import chromadb, fall back to simple memory if not available
try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class SimpleVectorMemory:
    """Simple in-memory vector storage fallback when ChromaDB is unavailable."""
    
    def __init__(self):
        self.documents: List[str] = []
        self.metadatas: List[Dict] = []
        self.ids: List[str] = []
    
    def add(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        self.documents.extend(documents)
        self.metadatas.extend(metadatas)
        self.ids.extend(ids)
    
    def query(self, query_texts: List[str], n_results: int = 3):
        # Simple keyword-based retrieval (no embeddings)
        query = query_texts[0].lower()
        scores = []
        for i, doc in enumerate(self.documents):
            score = sum(1 for word in query.split() if word in doc.lower())
            scores.append((score, i))
        
        scores.sort(reverse=True)
        top_indices = [idx for _, idx in scores[:n_results]]
        
        return {
            'documents': [[self.documents[i] for i in top_indices]],
            'metadatas': [[self.metadatas[i] for i in top_indices]],
            'distances': [[1.0 - (s / 10.0) for s, _ in scores[:n_results]]]
        }
    
    def get(self, include=None, limit=None):
        limit = limit or len(self.documents)
        return {
            'documents': self.documents[-limit:],
            'metadatas': self.metadatas[-limit:]
        }


class AgentMemory:
    def __init__(self, agent_name: str, persist_directory: str = "./sandbox/memory_db"):
        self.agent_name = agent_name
        
        if CHROMA_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=persist_directory)
                self.collection = self.client.get_or_create_collection(
                    name=f"memory_{agent_name}",
                    metadata={"description": f"Long-term memory for {agent_name}"}
                )
                self.use_chroma = True
            except Exception as e:
                print(f"[Memory] ChromaDB failed ({e}), using simple memory fallback")
                self.collection = SimpleVectorMemory()
                self.use_chroma = False
        else:
            self.collection = SimpleVectorMemory()
            self.use_chroma = False

    def save_context(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Save a new memory entry."""
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name
        })

        self.collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )
        return True

    def search_context(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant memories based on a query."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        memories = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                memories.append({
                    "content": doc,
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if results.get('distances') else 0.0
                })
        return memories

    def get_recent_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most recent memory entries."""
        all_data = self.collection.get(include=["documents", "metadatas"], limit=limit)
        
        history = []
        if all_data['documents']:
            for i, doc in enumerate(all_data['documents']):
                history.append({
                    "content": doc,
                    "metadata": all_data['metadatas'][i]
                })
        return history

# Singleton manager for easy access
class MemoryManager:
    def __init__(self):
        self.memories: Dict[str, AgentMemory] = {}

    def get_memory(self, agent_name: str) -> AgentMemory:
        if agent_name not in self.memories:
            self.memories[agent_name] = AgentMemory(agent_name)
        return self.memories[agent_name]

global_memory_manager = MemoryManager()
