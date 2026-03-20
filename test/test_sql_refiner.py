"""
SQL Refiner unit tests.

Covers SQL auto-correction scenarios.
"""

import unittest
from unittest.mock import Mock, patch
from service.sql_refiner import SQLRefiner
from sqlalchemy.exc import SQLAlchemyError


class TestSQLRefiner(unittest.TestCase):
    """Tests for SQL Refiner."""

    def setUp(self):
        """Prepare mocks and sample data."""
        # Create mocks
        self.mock_db_service = Mock()
        self.mock_llm_session = Mock()
        self.mock_logger = Mock()

        # Refiner under test
        self.refiner = SQLRefiner(
            db_service=self.mock_db_service,
            llm_session=self.mock_llm_session,
            logger=self.mock_logger
        )

        # Sample schema for tests
        self.test_schema = """
        TABLE: users
        - id (INT, PRIMARY KEY)
        - username (VARCHAR)
        - email (VARCHAR)
        - created_at (DATETIME)

        TABLE: orders
        - id (INT, PRIMARY KEY)
        - user_id (INT, FOREIGN KEY)
        - total_amount (DECIMAL)
        - status (VARCHAR)
        """

        self.test_question = "Count orders per user"
        self.test_dialect = "mysql"
        self.test_db_config = {
            'db_type': 'mysql',
            'host': 'localhost',
            'port': 3306,
            'user': 'test',
            'password': 'test',
            'dbname': 'testdb'
        }

    def test_clean_sql_with_markdown(self):
        """Strip markdown fences from SQL."""
        sql_with_markdown = """
        ```sql
        SELECT * FROM users WHERE id = 1;
        ```
        """

        cleaned = self.refiner._clean_sql(sql_with_markdown)
        self.assertEqual(cleaned, "SELECT * FROM users WHERE id = 1;")

    def test_clean_sql_without_markdown(self):
        """Clean SQL that has no markdown."""
        sql = "SELECT * FROM users WHERE id = 1;"
        cleaned = self.refiner._clean_sql(sql)
        self.assertEqual(cleaned, "SELECT * FROM users WHERE id = 1;")

    def test_add_limit_for_validation_select(self):
        """Add LIMIT for SELECT validation."""
        sql = "SELECT * FROM users"
        result = self.refiner._add_limit_for_validation(sql)
        self.assertTrue("LIMIT 0" in result)

    def test_add_limit_for_validation_with_existing_limit(self):
        """Do not add LIMIT when one already exists."""
        sql = "SELECT * FROM users LIMIT 10"
        result = self.refiner._add_limit_for_validation(sql)
        self.assertEqual(result, sql)

    def test_add_limit_for_validation_non_select(self):
        """Non-SELECT statements are unchanged."""
        sql = "UPDATE users SET status = 'active'"
        result = self.refiner._add_limit_for_validation(sql)
        self.assertEqual(result, sql)

    def test_validate_sql_success(self):
        """Validation succeeds when execute_query works."""
        # Successful execution
        self.mock_db_service.execute_query.return_value = ([], [])

        test_sql = "SELECT * FROM users"
        is_valid, error_msg = self.refiner._validate_sql(test_sql, self.test_db_config)

        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "")

    def test_validate_sql_failure(self):
        """Validation fails when execute_query raises."""
        # Failed execution
        error_message = "Column 'invalid_column' doesn't exist"
        self.mock_db_service.execute_query.side_effect = SQLAlchemyError(error_message)

        test_sql = "SELECT invalid_column FROM users"
        is_valid, error_msg = self.refiner._validate_sql(test_sql, self.test_db_config)

        self.assertFalse(is_valid)
        self.assertIn("invalid_column", error_msg)

    def test_refine_sql_success_first_attempt(self):
        """Refinement succeeds on second validation after one failure."""
        # First validation fails, second succeeds
        validation_results = [
            (False, "Column 'name' doesn't exist"),  # first attempt
            (True, "")  # second attempt
        ]
        self.refiner._validate_sql = Mock(side_effect=validation_results)

        # LLM returns corrected SQL
        mock_response = Mock()
        mock_response.message.content = "SELECT username FROM users"
        self.mock_llm_session.model.llm.invoke.return_value = mock_response

        failed_sql = "SELECT name FROM users"
        mock_llm_model = Mock()

        refined_sql, success, error_history = self.refiner.refine_sql(
            original_sql=failed_sql,
            schema_info=self.test_schema,
            question=self.test_question,
            dialect=self.test_dialect,
            db_config=self.test_db_config,
            llm_model=mock_llm_model,
            max_iterations=3
        )

        self.assertTrue(success)
        self.assertEqual(len(error_history), 1)
        self.assertIn("username", refined_sql)

    def test_refine_sql_max_iterations_reached(self):
        """Stop after max iterations when validation keeps failing."""
        # All validations fail
        self.refiner._validate_sql = Mock(return_value=(False, "Syntax error"))

        # LLM always returns invalid SQL
        mock_response = Mock()
        mock_response.message.content = "SELECT * FROM invalid_table"
        self.mock_llm_session.model.llm.invoke.return_value = mock_response

        failed_sql = "SELECT * FROM nonexistent"
        mock_llm_model = Mock()

        refined_sql, success, error_history = self.refiner.refine_sql(
            original_sql=failed_sql,
            schema_info=self.test_schema,
            question=self.test_question,
            dialect=self.test_dialect,
            db_config=self.test_db_config,
            llm_model=mock_llm_model,
            max_iterations=3
        )

        self.assertFalse(success)
        self.assertEqual(len(error_history), 3)

    def test_refine_sql_llm_returns_empty(self):
        """Handle empty LLM response."""
        # Validation fails once
        self.refiner._validate_sql = Mock(return_value=(False, "Column error"))

        # LLM returns empty content
        mock_response = Mock()
        mock_response.message.content = ""
        self.mock_llm_session.model.llm.invoke.return_value = mock_response

        failed_sql = "SELECT invalid FROM users"
        mock_llm_model = Mock()

        refined_sql, success, error_history = self.refiner.refine_sql(
            original_sql=failed_sql,
            schema_info=self.test_schema,
            question=self.test_question,
            dialect=self.test_dialect,
            db_config=self.test_db_config,
            llm_model=mock_llm_model,
            max_iterations=3
        )

        self.assertFalse(success)
        self.assertEqual(len(error_history), 1)

    def test_format_refiner_result_success(self):
        """Format successful refinement report."""
        original_sql = "SELECT name FROM users"
        refined_sql = "SELECT username FROM users"
        error_history = [
            {"iteration": 1, "sql": original_sql, "error": "Column 'name' doesn't exist"}
        ]

        report = self.refiner.format_refiner_result(
            original_sql=original_sql,
            refined_sql=refined_sql,
            success=True,
            error_history=error_history,
            iterations=1
        )

        self.assertIn("succeeded", report)
        self.assertIn("iteration", report)
        self.assertIn(refined_sql, report)

    def test_format_refiner_result_failure(self):
        """Format failed refinement report."""
        original_sql = "SELECT invalid FROM users"
        refined_sql = "SELECT still_invalid FROM users"
        error_history = [
            {"iteration": 1, "sql": original_sql, "error": "Column 'invalid' doesn't exist"},
            {"iteration": 2, "sql": refined_sql, "error": "Column 'still_invalid' doesn't exist"}
        ]

        report = self.refiner.format_refiner_result(
            original_sql=original_sql,
            refined_sql=refined_sql,
            success=False,
            error_history=error_history,
            iterations=2
        )

        self.assertIn("failed", report)
        self.assertIn("attempt", report)
        self.assertIn("Error history", report)


class TestSQLRefinerIntegration(unittest.TestCase):
    """Integration-style tests for SQL Refiner."""

    @patch('service.sql_refiner.SQLRefiner._validate_sql')
    @patch('service.sql_refiner.SQLRefiner._generate_refined_sql')
    def test_column_name_correction(self, mock_generate, mock_validate):
        """Correct wrong column name via refinement loop."""
        # Wrong column 'name' should become 'username'
        mock_db_service = Mock()
        mock_llm_session = Mock()

        refiner = SQLRefiner(mock_db_service, mock_llm_session)

        # First validation fails, second succeeds after fix
        mock_validate.side_effect = [
            (False, "Unknown column 'name' in 'field list'"),
            (True, "")
        ]

        mock_generate.return_value = "SELECT username FROM users"

        failed_sql = "SELECT name FROM users"
        schema_info = "TABLE users: id, username, email"

        refined_sql, success, _ = refiner.refine_sql(
            original_sql=failed_sql,
            schema_info=schema_info,
            question="Get usernames",
            dialect="mysql",
            db_config={},
            llm_model=Mock(),
            max_iterations=3
        )

        self.assertTrue(success)
        self.assertIn("username", refined_sql)


if __name__ == '__main__':
    unittest.main()
