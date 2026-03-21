#!/usr/bin/env python3
"""
End-to-end LM DB Schema RAG build flow test (mocked Dify upload).
"""

import sys
import os

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from unittest.mock import patch
from provider.build_lm_db_schema_rag import LmDbSchemaRagProvider
import logging

# Reduce log noise
logging.basicConfig(level=logging.INFO)


def mock_dify_upload(dataset_name, schema_content):
    """Mock Dify upload."""
    print(f"🔄 Mock upload to Dify dataset: {dataset_name}")
    print(f"📄 Schema length: {len(schema_content)} characters")
    if schema_content:
        lines = schema_content.split("\n")
        table_count = len([line for line in lines if line.strip().startswith("# ")])
        print(f"📊 Detected {table_count} table(s)")
    return {"status": "success", "dataset_id": "mock_dataset_123"}


def test_schema_rag_build_process():
    """Run full LM DB Schema RAG build with mocked upload."""

    try:
        test_credentials = {
            "api_uri": "http://localhost/v1",
            "dataset_api_key": "dataset-",
            "db_type": "mssql",
            "db_host": "localhost",
            "db_port": "1433",
            "db_user": "SA",
            "db_password": "Abcd%401234",
            "db_name": "test",
        }

        print("LM DB Schema RAG build test:")
        print("=" * 80)

        provider = LmDbSchemaRagProvider()

        with patch(
            "service.schema_builder.LmDbSchemaRagBuilder.upload_text_to_dify",
            side_effect=mock_dify_upload,
        ):
            with patch(
                "service.schema_builder.LmDbSchemaRagBuilder.close", return_value=None
            ):
                print("🚀 Starting LM DB Schema RAG build...")

                try:
                    ok = provider._build_lm_db_schema_rag(test_credentials)
                    assert ok is True
                    print("✅ LM DB Schema RAG build succeeded!")

                except Exception as e:
                    print(f"❌ LM DB Schema RAG build failed: {e}")
                    raise

        print("=" * 80)

    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Full LM DB Schema RAG build test")
    print("=" * 80)

    try:
        print("1️⃣ Full LM DB Schema RAG build (mocked)")
        test_schema_rag_build_process()

        print("\n🎉 All steps finished!")

    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback

        traceback.print_exc()
