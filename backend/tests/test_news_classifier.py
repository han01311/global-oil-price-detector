import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock, ANY
import json

from pydantic import ValidationError

from app.services.news_classifier import NewsClassifier
from app.schemas.news import NewsArticle, ClassifiedArticle

# Fixtures for articles
@pytest.fixture
def sample_article_dict():
    return { "id": "test-id-1", "title": "OPEC+ Agrees to Deepen Oil Production Cuts", "description": "The group of oil-producing nations decided to cut production by an additional 500,000 barrels per day.", "source": "Reuters", "url": "http://example.com/opec-cuts", "published_at": "2024-01-01T12:00:00Z", "content_snippet": "In a surprise move, OPEC+ announced deeper cuts...", "data_source": "newsapi" }

@pytest.fixture
def irrelevant_article_dict():
    return { "id": "test-id-2", "title": "Tesla Stock Surges on New EV Model", "description": "Shares of the electric vehicle maker jumped 10%.", "source": "Bloomberg", "url": "http://example.com/tesla-stock", "published_at": "2024-01-01T13:00:00Z", "content_snippet": "Tesla's new model has excited investors...", "data_source": "newsapi" }

# Fixtures for mock Gemini responses
@pytest.fixture
def mock_gemini_response_success():
    mock_response = MagicMock()
    mock_response.text = json.dumps({ "is_relevant": True, "category": "supply", "sub_categories": ["geopolitics"], "impact_score": 3, "impact_summary": "OPEC+의 추가 감산 결정은 원유 공급 감소로 이어져 유가 상승 압력으로 작용할 것입니다.", "confidence": 0.95 })
    return asyncio.sleep(0.01, result=mock_response)

@pytest.fixture
def mock_gemini_response_irrelevant():
    mock_response = MagicMock()
    mock_response.text = json.dumps({ "is_relevant": False, "category": "demand", "sub_categories": [], "impact_score": 0, "impact_summary": "이 기사는 유가와 직접적인 관련이 없습니다.", "confidence": 0.98 })
    return asyncio.sleep(0.01, result=mock_response)

@pytest.fixture
def mock_gemini_response_invalid_json():
    mock_response = MagicMock()
    mock_response.text = '{"is_relevant": true, ...'
    return asyncio.sleep(0.01, result=mock_response)

@pytest.fixture
def mock_gemini_response_invalid_data():
    mock_response = MagicMock()
    mock_response.text = json.dumps({ "is_relevant": True, "category": "supply", "sub_categories": [], "impact_score": 10, "impact_summary": "Summary", "confidence": 0.9 })
    return asyncio.sleep(0.01, result=mock_response)

# Main fixture for the classifier, with genai patched
@pytest.fixture
def classifier(monkeypatch):
    monkeypatch.setattr("google.generativeai.configure", MagicMock())
    monkeypatch.setattr("google.generativeai.GenerativeModel", MagicMock())
    return NewsClassifier(api_key="DUMMY_API_KEY")

# --- Tests ---

def test_init_with_key(monkeypatch):
    """Test that the classifier initializes correctly with an API key."""
    mock_configure = MagicMock()
    mock_model = MagicMock()
    monkeypatch.setattr("google.generativeai.configure", mock_configure)
    monkeypatch.setattr("google.generativeai.GenerativeModel", mock_model)
    
    classifier = NewsClassifier(api_key="TEST_KEY")
    
    mock_configure.assert_called_once_with(api_key="TEST_KEY")
    mock_model.assert_called_with('gemini-1.5-flash', generation_config=ANY)
    assert classifier.model is not None

def test_init_no_key(monkeypatch):
    """Test that the classifier handles a missing API key gracefully."""
    monkeypatch.setattr("app.core.config.settings.GEMINI_API_KEY", None)
    classifier = NewsClassifier()
    assert classifier.model is None

def test_build_prompt(classifier, sample_article_dict):
    """Test if the prompt is constructed correctly."""
    article = NewsArticle(**sample_article_dict)
    content = f"Title: {article.title}\nDescription: {article.description}\nContent Snippet: {article.content_snippet}"
    prompt = classifier._build_classification_prompt(content)
    
    assert "You are an expert financial analyst" in prompt
    assert "geopolitics" in prompt
    assert "impact_score" in prompt
    assert content in prompt

@pytest.mark.asyncio
async def test_classify_article_success(classifier, sample_article_dict, mock_gemini_response_success):
    """Test successful classification of a single article."""
    classifier.model.generate_content_async = AsyncMock(return_value=await mock_gemini_response_success)
    
    result = await classifier.classify_article(sample_article_dict)
    
    classifier.model.generate_content_async.assert_awaited_once()
    assert isinstance(result, ClassifiedArticle)
    assert result.is_relevant is True
    assert result.category == "supply"
    assert result.impact_score == 3
    assert result.article.id == sample_article_dict["id"]

@pytest.mark.asyncio
async def test_classify_article_irrelevant(classifier, irrelevant_article_dict, mock_gemini_response_irrelevant):
    """Test classification of an irrelevant article."""
    classifier.model.generate_content_async = AsyncMock(return_value=await mock_gemini_response_irrelevant)
    
    result = await classifier.classify_article(irrelevant_article_dict)
    
    assert result is not None
    assert result.is_relevant is False

@pytest.mark.asyncio
async def test_classify_article_invalid_json(classifier, sample_article_dict, mock_gemini_response_invalid_json):
    """Test fallback for invalid JSON response."""
    classifier.model.generate_content_async = AsyncMock(return_value=await mock_gemini_response_invalid_json)
    result = await classifier.classify_article(sample_article_dict)
    assert result is None

@pytest.mark.asyncio
async def test_classify_article_validation_error(classifier, sample_article_dict, mock_gemini_response_invalid_data):
    """Test fallback for Pydantic validation error."""
    classifier.model.generate_content_async = AsyncMock(return_value=await mock_gemini_response_invalid_data)
    result = await classifier.classify_article(sample_article_dict)
    assert result is None

@pytest.mark.asyncio
async def test_classify_batch(classifier, sample_article_dict, irrelevant_article_dict):
    """Test batch classification."""
    classified_relevant = ClassifiedArticle(article=NewsArticle(**sample_article_dict), is_relevant=True, category="supply", impact_score=3, impact_summary="s", confidence=0.9, classified_at="t")
    classified_irrelevant = ClassifiedArticle(article=NewsArticle(**irrelevant_article_dict), is_relevant=False, category="demand", impact_score=0, impact_summary="s", confidence=0.9, classified_at="t")
    
    async def side_effect(article_dict):
        if article_dict['id'] == 'test-id-1': return classified_relevant
        if article_dict['id'] == 'test-id-2': return classified_irrelevant
        return None
    
    with patch.object(classifier, 'classify_article', side_effect=side_effect, autospec=True) as mock_classify:
        articles_to_classify = [
            sample_article_dict,
            irrelevant_article_dict,
            {"id": "fail-id", "title": "Fail", "url": "u", "published_at": "p", "data_source": "d", "description": None, "source": None, "content_snippet": None}
        ]
        
        results = await classifier.classify_batch(articles_to_classify)
        
        assert mock_classify.call_count == 3
        assert len(results) == 2
        assert any(r.article.id == 'test-id-1' for r in results)
        assert any(r.article.id == 'test-id-2' for r in results)
