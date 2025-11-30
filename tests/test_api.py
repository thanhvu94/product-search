import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import json
from main import create_app

# Create the test client using the FastAPI app
app = create_app()
client = TestClient(app)

# -------------------------
# Test search_by_text API
# -------------------------
def test_search_by_text_success():
    payload = {
        "query": "Nike"
    }
    response = client.post("/search_by_text", data=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    
    # 'results' is a list and is NOT empty
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0

def test_search_by_text_missing_query_fails():
    payload = {"top_k": 5}
    response = client.post("/search_by_text", data=payload)
    assert response.status_code == 422

# -------------------------
# Test search_by_image API
# -------------------------
def test_search_by_image_success():
    with open("tests/sample.jpg", "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        response = client.post("/search_by_image", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    
    # 'results' is a list and is NOT empty
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0

def test_search_by_image_missing_image_fails():
    payload = {"top_k": 5}
    response = client.post("/search_by_image", data=payload)
    assert response.status_code == 422

# -------------------------
# Test upsert product API
# -------------------------
def test_upsert_product_success():
    mock_response = {
        "status": "success",
        "id": "1234"
    }

    with patch("main.perform_upsert_product", new_callable=AsyncMock, return_value=mock_response) as mock_fn:
        raw_metadata = {
            "id": "1234",
            "metadata": {"color": "red", "category": "apparel"}
        }
        metadata = json.dumps(raw_metadata)
        files = {"file": ("sample.jpg", b"dummy content", "image/jpeg")}
        data = {"metadata_json": metadata}

        response = client.post("/upsert_product", files=files, data=data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["id"] == "1234"

def test_upsert_product_missing_data_fails():
    response = client.post("/upsert_product")
    
    # Missing file and data
    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(d["loc"][-1] == "file" for d in details)
    assert any(d["loc"][-1] == "metadata_json" for d in details)

def test_upsert_product_missing_image_fails():
    raw_metadata = {
            "id": "1234",
            "metadata": {"color": "red", "category": "apparel"}
        }
    metadata = json.dumps(raw_metadata)        
    data = {"metadata_json": metadata}

    response = client.post("/upsert_product", data=data)

    # Missing image file
    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(d["loc"][-1] == "file" for d in details)

def test_upsert_product_missing_metadata_fails():
    files = {"file": ("sample.jpg", b"dummy content", "text/plain")}

    response = client.post("/upsert_product", files=files)

    # Missing metadata json
    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(d["loc"][-1] == "metadata_json" for d in details)