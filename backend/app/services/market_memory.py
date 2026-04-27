from __future__ import annotations
import logging
from pathlib import Path
import chromadb
from datetime import datetime, timezone
from app.schemas.news import ClassifiedArticle, NewsArticle, CrudeImpact

# Configure logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

CRUDE_TYPES = ["dubai", "brent", "wti"]

class MarketMemory:
    """ChromaDB-based vector search system for historical market events."""

    COLLECTION_NAME = "oil_market_events"

    @staticmethod
    def _default_db_path() -> str:
        backend_dir = Path(__file__).resolve().parents[2]
        candidates = [
            backend_dir / "data" / "chromadb",
            backend_dir / "backend" / "data" / "chromadb",
        ]
        for candidate in candidates:
            db_file = candidate / "chroma.sqlite3"
            if db_file.exists() and db_file.stat().st_size > 1024 * 1024:
                return str(candidate)
        return str(candidates[0])

    def __init__(self, db_path: str | None = None):
        try:
            self._client = chromadb.PersistentClient(path=db_path or self._default_db_path())
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
        Includes per-crude impact scores and price changes in metadata.
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
                "translated_title": article_model.translated_title or "",
            }

            # Store per-crude impact scores
            for crude in CRUDE_TYPES:
                if article_model.impact_by_crude and crude in article_model.impact_by_crude:
                    impact = article_model.impact_by_crude[crude]
                    metadata[f"{crude}_score"] = impact.score
                    metadata[f"{crude}_direction"] = impact.direction
                else:
                    # Fallback to overall score
                    metadata[f"{crude}_score"] = article_model.impact_score
                    metadata[f"{crude}_direction"] = "neutral"

            # Store per-crude price changes
            for crude in CRUDE_TYPES:
                for period in ["1d", "7d", "30d"]:
                    key = f"{crude}_change_{period}"
                    metadata[key] = price_change.get(key, price_change.get(f"wti_change_{period}", 0.0))

            # Also keep legacy wti_change_* for backward compatibility
            for key in ["wti_change_1d", "wti_change_7d", "wti_change_30d"]:
                if key in price_change:
                    metadata[key] = price_change[key]

            # Ensure all metadata values are of supported types
            for key, value in metadata.items():
                if value is None:
                    metadata[key] = -1.0  # ChromaDB doesn't like None
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

    async def search_similar(self, query: str, category: str = None,
                             crude_type: str = None, n_results: int = 5) -> list[dict]:
        """
        Searches for similar historical events.
        When crude_type is specified, filters for events that had significant impact on that crude type.
        """
        if not self.is_available():
            logger.warning("MarketMemory is not available. Skipping search_similar.")
            return []

        try:
            where_clauses = []
            if category:
                where_clauses.append({"category": category})
            if crude_type and crude_type in CRUDE_TYPES:
                # Filter for events that had at least moderate impact on this crude type
                where_clauses.append({f"{crude_type}_score": {"$gte": 1}})

            # Build final where clause
            where = None
            if len(where_clauses) == 1:
                where = where_clauses[0]
            elif len(where_clauses) > 1:
                where = {"$and": where_clauses}

            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where
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

    def get_recent_classified_articles(self, limit: int = 50) -> list[ClassifiedArticle]:
        """Return already-classified articles from ChromaDB without invoking the LLM."""
        if not self.is_available():
            return []

        try:
            result = self._collection.get(limit=limit, include=["documents", "metadatas"])
        except Exception as e:
            logger.error(f"Failed to load cached classified articles: {e}")
            return []

        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        articles: list[ClassifiedArticle] = []

        for article_id, document, metadata in zip(ids, documents, metadatas):
            try:
                title = ""
                summary = ""
                for line in (document or "").splitlines():
                    if line.startswith("Title: "):
                        title = line.replace("Title: ", "", 1)
                    elif line.startswith("Summary: "):
                        summary = line.replace("Summary: ", "", 1)

                impact_by_crude = {}
                for crude in CRUDE_TYPES:
                    impact_by_crude[crude] = CrudeImpact(
                        direction=metadata.get(f"{crude}_direction", "neutral"),
                        score=int(metadata.get(f"{crude}_score", metadata.get("impact_score", 0)) or 0),
                        rationale="",
                    )

                news_article = NewsArticle(
                    id=article_id,
                    title=title or metadata.get("translated_title") or "Untitled",
                    description=summary or None,
                    source=metadata.get("source"),
                    url=metadata.get("url") or "",
                    published_at=f"{metadata.get('date') or datetime.now(timezone.utc).date().isoformat()}T00:00:00Z",
                    content_snippet=summary or None,
                    data_source="market_memory",
                )

                articles.append(ClassifiedArticle(
                    article=news_article,
                    is_relevant=True,
                    category=metadata.get("category", "unknown"),
                    sub_categories=[],
                    impact_score=int(metadata.get("impact_score", 0) or 0),
                    impact_summary=summary or "",
                    confidence=float(metadata.get("confidence", 0.8) or 0.8),
                    classified_at=datetime.now(timezone.utc).isoformat(),
                    translated_title=metadata.get("translated_title") or None,
                    impact_by_crude=impact_by_crude,
                ))
            except Exception as e:
                logger.warning(f"Failed to reconstruct cached article {article_id}: {e}")

        articles.sort(key=lambda item: item.article.published_at, reverse=True)
        return articles
