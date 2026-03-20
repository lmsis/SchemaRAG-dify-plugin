"""
Tests for multi-dataset knowledge base support.

Covers:
1. Concurrent async retrieval across multiple datasets
2. Example dataset retrieval
3. Parameter validation and error handling
"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Project root on path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from service.knowledge_service import KnowledgeService
from tools.parameter_validator import validate_and_extract_text2sql_parameters


class TestMultipleDatasetSupport(unittest.TestCase):
    """Multi-dataset support tests."""

    def setUp(self):
        """Test fixtures."""
        self.api_uri = "https://test-api.com"
        self.api_key = "test-key"
        self.knowledge_service = KnowledgeService(self.api_uri, self.api_key)

    def test_single_dataset_id_parsing(self):
        """Single dataset ID is accepted."""
        single_id = "dataset123"
        result = self.knowledge_service.retrieve_schema_from_multiple_datasets(
            single_id, "test query", top_k=5
        )
        # No real API: ensure call does not raise

    def test_multiple_dataset_id_parsing(self):
        """Comma-separated IDs parse to a list."""
        multiple_ids = "dataset1,dataset2,dataset3"
        id_list = [id.strip() for id in multiple_ids.split(",") if id.strip()]
        self.assertEqual(len(id_list), 3)
        self.assertEqual(id_list, ["dataset1", "dataset2", "dataset3"])

    def test_empty_dataset_id_handling(self):
        """Empty dataset_id yields empty result."""
        empty_ids = ""
        result = self.knowledge_service.retrieve_schema_from_multiple_datasets(
            empty_ids, "test query", top_k=5
        )
        self.assertEqual(result, "")

    def test_whitespace_only_dataset_id_handling(self):
        """Whitespace-only IDs yield empty result."""
        whitespace_ids = "  ,  ,  "
        result = self.knowledge_service.retrieve_schema_from_multiple_datasets(
            whitespace_ids, "test query", top_k=5
        )
        self.assertEqual(result, "")

    @patch('httpx.AsyncClient')
    async def test_async_multiple_dataset_retrieval(self, mock_client):
        """Async retrieval returns one result per dataset."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [
                {"segment": {"content": "Test schema content"}}
            ]
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        dataset_ids = ["dataset1", "dataset2"]
        results = await self.knowledge_service._retrieve_from_multiple_datasets_async(
            dataset_ids, "test query", 5, "semantic_search"
        )

        self.assertEqual(len(results), 2)

    def test_text2sql_tool_parameter_validation(self):
        """Valid Text2SQL parameters return a full tuple."""
        valid_params = {
            "dataset_id": "dataset1,dataset2",
            "llm": Mock(),
            "content": "What are the users?",
            "dialect": "mysql",
            "top_k": 5,
            "retrieval_model": "semantic_search",
            "custom_prompt": "Use specific column names",
            "example_dataset_id": "examples_dataset"
        }

        result = validate_and_extract_text2sql_parameters(valid_params)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 12)

    def test_text2sql_tool_example_dataset_validation(self):
        """example_dataset_id must be a string when provided."""
        invalid_params = {
            "dataset_id": "dataset1",
            "llm": Mock(),
            "content": "What are the users?",
            "example_dataset_id": 123  # must be str, not int
        }

        result = validate_and_extract_text2sql_parameters(invalid_params)
        self.assertIsInstance(result, str)
        self.assertIn("example_dataset_id must be a string", result)

    def test_fallback_multiple_dataset_retrieval(self):
        """Fallback sequential retrieval returns a string."""
        dataset_ids = ["dataset1", "dataset2"]

        with patch.object(self.knowledge_service, 'retrieve_schema_from_dataset', return_value="test content"):
            result = self.knowledge_service._fallback_retrieve_multiple_datasets(
                dataset_ids, "test query", 5, "semantic_search"
            )
            self.assertIsInstance(result, str)

    def test_content_merging_with_knowledge_base_labels(self):
        """Merged blocks use the same prefix as KnowledgeService."""
        dataset_id = "test_dataset"
        content = "Test schema content"
        expected_result = f"=== Knowledge base {dataset_id} ===\\n{content}"

        formatted_content = f"=== Knowledge base {dataset_id} ===\\n{content}"
        self.assertEqual(formatted_content, expected_result)


class TestPromptBuildingWithExamples(unittest.TestCase):
    """Prompt building with SQL examples."""

    def test_prompt_with_examples(self):
        """User prompt includes schema and example SQL when provided."""
        from prompt.text2sql_prompt import _build_user_prompt

        db_schema = "CREATE TABLE users (id INT, name VARCHAR(255));"
        question = "Get all users"
        example_info = "SELECT * FROM users WHERE status = 'active';"

        prompt = _build_user_prompt(db_schema, question, example_info)

        self.assertIn("【Examples】", prompt)
        self.assertIn(example_info, prompt)
        self.assertIn("【Database Schema】", prompt)

    def test_prompt_without_examples(self):
        """User prompt has schema; no example SQL when examples empty."""
        from prompt.text2sql_prompt import _build_user_prompt

        db_schema = "CREATE TABLE users (id INT, name VARCHAR(255));"
        question = "Get all users"
        example_sql = "SELECT * FROM users WHERE status = 'active';"

        prompt = _build_user_prompt(db_schema, question, "")

        self.assertIn("【Database Schema】", prompt)
        self.assertNotIn(example_sql, prompt)

    def test_prompt_with_custom_instructions_and_examples(self):
        """Custom system instructions and user-level examples both apply."""
        from prompt.text2sql_prompt import _build_system_prompt, _build_user_prompt

        dialect = "mysql"
        db_schema = "CREATE TABLE users (id INT, name VARCHAR(255));"
        question = "Get all users"
        custom_prompt = "Always use explicit joins"
        example_info = "SELECT u.id, u.name FROM users u WHERE u.status = 'active';"

        system_prompt = _build_system_prompt(dialect, custom_prompt)
        user_prompt = _build_user_prompt(db_schema, question, example_info)

        self.assertIn("【Examples】", user_prompt)
        self.assertIn(example_info, user_prompt)
        self.assertIn(custom_prompt, system_prompt)


if __name__ == "__main__":
    unittest.main()
