"""
SQL Refiner Service - automatic SQL error correction

Implements LLM-based SQL error repair via iterative feedback, correcting syntax and logic errors.
"""

import re
import logging
from typing import Tuple, List, Dict, Any, Optional
from sqlalchemy.exc import SQLAlchemyError
from prompt import sql_refiner_prompt
from dify_plugin.entities.model.message import SystemPromptMessage, UserPromptMessage


class SQLRefiner:
    """
    Automatic SQL corrector.

    Repairs SQL errors through an LLM feedback loop, supporting:
    - Syntax error fixes
    - Column/table name mapping
    - Type casting corrections
    - JOIN logic improvements
    """
    
    def __init__(
        self, 
        db_service, 
        llm_session, 
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize SQL Refiner.

        Args:
            db_service: Database service instance
            llm_session: Dify LLM session object
            logger: Logger instance
        """
        self.db_service = db_service
        self.llm_session = llm_session
        self.logger = logger or logging.getLogger(__name__)
        
    def refine_sql(
        self,
        original_sql: str,
        schema_info: str,
        question: str,
        dialect: str,
        db_config: Dict[str, Any],
        llm_model: Any,
        max_iterations: int = 3
    ) -> Tuple[str, bool, List[Dict]]:
        """
        Iteratively repair SQL errors.

        Args:
            original_sql: Originally generated SQL
            schema_info: Database schema information
            question: Original user question
            dialect: SQL dialect
            db_config: Database configuration dict
            llm_model: LLM model configuration
            max_iterations: Maximum number of iterations

        Returns:
            (repaired SQL, success flag, error history list)
        """
        self.logger.info(f"Starting SQL auto-repair, max iterations: {max_iterations}")
        
        current_sql = original_sql
        error_history = []
        
        for iteration in range(1, max_iterations + 1):
            self.logger.info(f"SQL repair iteration {iteration}/{max_iterations}")
            
            # Validate whether SQL can execute
            is_valid, error_message = self._validate_sql(current_sql, db_config)
            
            if is_valid:
                self.logger.info(f"SQL repair succeeded after {iteration} iteration(s)")
                return current_sql, True, error_history
            
            # Record error history
            error_record = {
                "iteration": iteration,
                "sql": current_sql,
                "error": error_message
            }
            error_history.append(error_record)
            
            self.logger.warning(f"Attempt {iteration} failed: {error_message[:200]}")
            
            # Stop if max iterations reached
            if iteration >= max_iterations:
                self.logger.error(f"Max iterations ({max_iterations}) reached; SQL repair failed")
                return current_sql, False, error_history
            
            # Use LLM to produce repaired SQL
            try:
                refined_sql = self._generate_refined_sql(
                    schema_info=schema_info,
                    question=question,
                    failed_sql=current_sql,
                    error_message=error_message,
                    dialect=dialect,
                    iteration=iteration,
                    error_history=error_history[:-1],  # exclude current error from history passed to LLM
                    llm_model=llm_model
                )
                
                if not refined_sql or refined_sql.strip() == "":
                    self.logger.error("LLM returned empty repaired SQL")
                    return current_sql, False, error_history
                
                # Clean SQL
                refined_sql = self._clean_sql(refined_sql)
                
                if refined_sql == current_sql:
                    self.logger.warning("LLM returned the same SQL as before; possible loop")
                    return current_sql, False, error_history
                
                current_sql = refined_sql
                self.logger.info(f"Generated new repaired SQL, length: {len(current_sql)}")
                
            except Exception as e:
                self.logger.error(f"Exception while generating repaired SQL: {str(e)}")
                return current_sql, False, error_history
        
        return current_sql, False, error_history
    
    def _validate_sql(
        self, 
        sql: str, 
        db_config: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Check whether SQL can execute successfully (uses LIMIT 0 to avoid large result sets).

        Args:
            sql: SQL to validate
            db_config: Database configuration

        Returns:
            (is_valid, error_message)
        """
        try:
            # Add LIMIT 0 for SELECT queries for quick validation
            validation_sql = self._add_limit_for_validation(sql)
            
            # Run validation query
            _, _ = self.db_service.execute_query(
                db_type=db_config['db_type'],
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                dbname=db_config['dbname'],
                query=validation_sql
            )
            
            return True, ""
            
        except SQLAlchemyError as e:
            error_msg = str(e)
            self.logger.debug(f"SQL validation failed: {error_msg[:300]}")
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Unknown error during SQL validation: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def _add_limit_for_validation(self, sql: str) -> str:
        """
        Append LIMIT 0 to SELECT queries for validation (avoids large result sets).

        Args:
            sql: Original SQL

        Returns:
            SQL with LIMIT applied where appropriate
        """
        sql_lower = sql.lower().strip()
        
        # Only add LIMIT for SELECT queries
        if not sql_lower.startswith('select'):
            return sql
        
        # Do not add if LIMIT already present
        if 'limit' in sql_lower:
            return sql
        
        # Strip trailing semicolon
        sql = sql.rstrip(';').strip()
        
        # Append LIMIT 0
        return f"{sql} LIMIT 0"
    
    def _generate_refined_sql(
        self,
        schema_info: str,
        question: str,
        failed_sql: str,
        error_message: str,
        dialect: str,
        iteration: int,
        error_history: List[Dict],
        llm_model: Any
    ) -> str:
        """
        Use LLM to generate repaired SQL.

        Args:
            schema_info: Schema information
            question: User question
            failed_sql: Failed SQL
            error_message: Error message from the database
            dialect: SQL dialect
            iteration: Current iteration number
            error_history: Prior error records
            llm_model: LLM model configuration

        Returns:
            Repaired SQL string
        """
        # Build prompts
        system_prompt = sql_refiner_prompt._build_refiner_system_prompt(dialect)
        user_prompt = sql_refiner_prompt._build_refiner_user_prompt(
            schema_info=schema_info,
            question=question,
            failed_sql=failed_sql,
            error_message=error_message,
            dialect=dialect,
            iteration=iteration,
            error_history=error_history
        )
        
        self.logger.debug(f"Invoking LLM for SQL repair, iteration: {iteration}")
        
        # Invoke LLM
        response = self.llm_session.model.llm.invoke(
            model_config=llm_model,
            prompt_messages=[
                SystemPromptMessage(content=system_prompt),
                UserPromptMessage(content=user_prompt),
            ],
            stream=False,
        )
        
        # Extract SQL from response
        refined_sql = ""
        if hasattr(response, "message") and response.message:
            refined_sql = response.message.content.strip() if response.message.content else ""
        
        if not refined_sql:
            raise ValueError("LLM returned empty repaired SQL")
        
        return refined_sql
    
    def _clean_sql(self, sql: str) -> str:
        """
        Clean SQL text (remove markdown fences, etc.).

        Args:
            sql: Raw SQL text

        Returns:
            Cleaned SQL
        """
        if not sql:
            return ""
        
        # Remove markdown code fences
        markdown_pattern = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
        match = markdown_pattern.search(sql)
        
        if match:
            cleaned_sql = match.group(1).strip()
        else:
            cleaned_sql = sql.strip()
        
        # Collapse extra whitespace
        cleaned_sql = re.sub(r"\s+", " ", cleaned_sql).strip()
        
        return cleaned_sql
    
    def format_refiner_result(
        self,
        original_sql: str,
        refined_sql: str,
        success: bool,
        error_history: List[Dict],
        iterations: int
    ) -> str:
        """
        Format refiner output as a human-readable report.

        Args:
            original_sql: Original SQL
            refined_sql: Repaired SQL
            success: Whether repair succeeded
            error_history: Error history
            iterations: Number of iterations performed

        Returns:
            Formatted report string
        """
        if success:
            report = f"""
[SQL auto-repair succeeded]

After {iterations} iteration(s), the SQL was repaired successfully.

Repaired SQL:
{refined_sql}
"""
        else:
            report = f"""
[SQL auto-repair failed]

After {iterations} attempt(s), the SQL could not be repaired.

Error history:
"""
            for idx, err in enumerate(error_history, 1):
                report += f"\nAttempt {idx}:\nError: {err.get('error', 'N/A')[:200]}\n"
        
        return report.strip()
