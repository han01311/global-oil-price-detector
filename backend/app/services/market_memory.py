import logging
import chromadb
from app.schemas.news import ClassifiedArticle

# Configure logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

class MarketMemory:
    """ChromaDB-based vector search system for historical market events."""

    COLLECTION_NAME = "oil_market_events"

    def __init__(self, db_path: str = "backend/data/chromadb"):
        try:
            self._client = chromadb.PersistentClient(path=db_path)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client at path {db_path}: {e}")
            self._client = None
            self._collection = None

    def is_available(self) -> bool:
        """Check if the ChromaDB connection is available."""
        return self._collection is not None

    async def store_event(self, classified_article: dict, price_change: dict):
        """
        Stores a classified article and its corresponding price change in the vector DB.
        """
        if not self.is_available():
            logger.warning("MarketMemory is not available. Skipping store_event.")
            return

        try:
            # Using Pydantic model for validation and easier access
            article_model = ClassifiedArticle(**classified_article)
            article_info = article_model.article

            document = f"Title: {article_info.title}\nSummary: {article_model.impact_summary}"
            
            metadata = {
                "category": article_model.category,
                "impact_score": article_model.impact_score,
                "confidence": article_model.confidence,
                "date": article_info.published_at.split('T')[0],
                "source": article_info.source or "Unknown",
                "url": article_info.url,
                **price_change
            }
            # Ensure all metadata values are of supported types
            for key, value in metadata.items():
                if value is None:
                    metadata[key] = -1.0 # ChromaDB doesn't like None
                elif isinstance(value, (int, float, str, bool)):
                    continue
                else:
                    metadata[key] = str(value)


            self._collection.upsert(
                ids=[article_info.id],
                documents=[document],
                metadatas=[metadata]
            )
        except Exception as e:
            logger.error(f"Failed to store event {classified_article.get('article', {}).get('id')}: {e}")

    async def search_similar(self, query: str, category: str = None, n_results: int = 5) -> list[dict]:
        """
        Searches for similar historical events.
        """
        if not self.is_available():
            logger.warning("MarketMemory is not available. Skipping search_similar.")
            return []

        try:
            where_clause = {}
            if category:
                where_clause["category"] = category

            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause if where_clause else None
            )

            # Process and format results
            formatted_results = []
            if not results or not results.get('ids') or not results['ids'][0]:
                return []

            for i, event_id in enumerate(results['ids'][0]):
                formatted_results.append({
                    "id": event_id,
                    "document": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search for similar events with query '{query}': {e}")
            return []

    async def get_category_stats(self) -> dict:
        """
        Calculates and returns statistics for each category in the collection.
        """
        if not self.is_available():
            logger.warning("MarketMemory is not available. Skipping get_category_stats.")
            return {}

        try:
            # Get all items from the collection
            all_events = self._collection.get(include=["metadatas"])
            
            if not all_events or not all_events['metadatas']:
                return {}

            stats = {}
            for metadata in all_events['metadatas']:
                category = metadata.get('category')
                impact_score = metadata.get('impact_score')
                
                if category:
                    if category not in stats:
                        stats[category] = {'count': 0, 'total_impact': 0}
                    stats[category]['count'] += 1
                    if isinstance(impact_score, (int, float)):
                        stats[category]['total_impact'] += impact_score
            
            # Calculate average impact
            for category, data in stats.items():
                if data['count'] > 0:
                    stats[category]['average_impact'] = data['total_impact'] / data['count']
                else:
                    stats[category]['average_impact'] = 0
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get category stats: {e}")
            return {}
