"""Vector database operations for company knowledge bases"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Try to import Pinecone, fallback to placeholder if not available
try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False


class VectorDBClient:
    """Client for vector database operations with company namespace isolation"""
    
    def __init__(self):
        self.db_type = os.getenv("VECTOR_DB_TYPE", "pinecone").lower()
        
        if self.db_type == "pinecone":
            if not PINECONE_AVAILABLE:
                raise ImportError("pinecone not installed. Install with: pip install pinecone")
            
            api_key = os.getenv("PINECONE_API_KEY")
            self.index_name = os.getenv("PINECONE_INDEX_NAME", "mcp-server")
            
            if api_key:
                # Initialize Pinecone client (new SDK v5+)
                self.pc = Pinecone(api_key=api_key)
                # Connect to index
                try:
                    self.index = self.pc.Index(self.index_name)
                except Exception as e:
                    # Index might not exist, will be created when needed
                    print(f"Warning: Could not connect to index {self.index_name}: {e}")
                    self.index = None
            else:
                self.index = None
                self.pc = None
        else:
            raise ValueError(f"Unsupported vector database type: {self.db_type}")
    
    def create_namespace(self, namespace: str) -> bool:
        """Create a namespace for a company (Pinecone uses namespaces)"""
        # In Pinecone, namespaces are created automatically when data is added
        # Just verify the index exists
        if self.index is None:
            return False
        return True
    
    def upsert_documents(
        self,
        namespace: str,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> bool:
        """Upsert documents with embeddings into a company namespace"""
        if self.index is None:
            return False
        
        if len(documents) != len(embeddings):
            raise ValueError("Documents and embeddings must have the same length")
        
        # Prepare vectors for Pinecone (new SDK format)
        vectors = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            vector_id = f"{namespace}_{i}_{datetime.utcnow().timestamp()}"
            metadata = {
                "text": doc.get("text", ""),
                "question": doc.get("question", ""),
                "answer": doc.get("answer", ""),
            }
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            })
        
        # Upsert to Pinecone with namespace (new SDK format)
        self.index.upsert(vectors=vectors, namespace=namespace)
        return True
    
    def search(
        self,
        namespace: str,
        query_embedding: List[float],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search for similar documents in a company namespace"""
        if self.index is None:
            return []
        
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        
        # New SDK returns results.matches as a list
        return [
            {
                "id": match.get("id", ""),
                "score": match.get("score", 0.0),
                "text": match.get("metadata", {}).get("text", ""),
                "question": match.get("metadata", {}).get("question", ""),
                "answer": match.get("metadata", {}).get("answer", ""),
            }
            for match in results.get("matches", [])
        ]
    
    def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """Get statistics for a namespace"""
        if self.index is None:
            return {"total_entries": 0, "last_updated": None}
        
        try:
            stats = self.index.describe_index_stats()
            # New SDK returns stats as a dict
            namespace_stats = stats.get("namespaces", {}).get(namespace, {})
            return {
                "total_entries": namespace_stats.get("vector_count", 0),
                "last_updated": datetime.utcnow().isoformat()
            }
        except Exception:
            return {"total_entries": 0, "last_updated": None}
    
    def delete_namespace(self, namespace: str) -> bool:
        """Delete all vectors in a namespace"""
        if self.index is None:
            return False
        
        try:
            # Delete all vectors in namespace
            self.index.delete(delete_all=True, namespace=namespace)
            return True
        except Exception:
            return False
    
    def list_vectors(self, namespace: str, limit: int = 10000) -> List[Dict[str, Any]]:
        """List all vectors in a namespace
        
        Note: Pinecone doesn't have a direct "list all" API. This method uses
        a workaround by querying with a zero vector. For better performance with
        large datasets, consider storing vector IDs in a separate database.
        """
        if self.index is None:
            return []
        
        try:
            # Get namespace stats to check if there are any vectors
            stats = self.index.describe_index_stats()
            namespace_stats = stats.get("namespaces", {}).get(namespace, {})
            vector_count = namespace_stats.get("vector_count", 0)
            
            if vector_count == 0:
                return []
            
            # Get dimension from index stats
            dimension = stats.get("dimension", 384)
            
            # Query with a zero vector to retrieve vectors
            # Pinecone max top_k is 10000, so we'll use that as the limit
            top_k = min(limit, vector_count, 10000)
            
            # Use a zero vector for querying (this will return vectors, though order may vary)
            zero_vector = [0.0] * dimension
            
            results = self.index.query(
                vector=zero_vector,
                top_k=top_k,
                namespace=namespace,
                include_metadata=True,
                include_values=False  # Don't include vector values to save bandwidth
            )
            
            matches = results.get("matches", [])
            all_vectors = []
            for match in matches:
                metadata = match.get("metadata", {})
                all_vectors.append({
                    "id": match.get("id", ""),
                    "question": metadata.get("question", ""),
                    "answer": metadata.get("answer", ""),
                    "text": metadata.get("text", ""),
                    "score": match.get("score", 0.0)
                })
            
            return all_vectors
        except Exception as e:
            print(f"Error listing vectors: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def delete_vectors(self, namespace: str, vector_ids: List[str]) -> bool:
        """Delete specific vectors by IDs"""
        if self.index is None:
            return False
        
        try:
            # Delete vectors by IDs
            self.index.delete(ids=vector_ids, namespace=namespace)
            return True
        except Exception:
            return False
