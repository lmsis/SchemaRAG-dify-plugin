"""
Context manager tests for multi-turn conversation memory.
"""

import sys
import os

# Project root on Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from service.context import ContextManager, Conversation


def test_basic_context_operations():
    """Basic add / window / reset behavior."""
    print("=" * 50)
    print("Basic context operations")
    print("=" * 50)

    cm = ContextManager()

    test_user_id = "test_user_123"

    cm.add_conversation(
        query="List all users",
        sql="SELECT * FROM users",
        user_id=test_user_id,
        metadata={"dialect": "mysql"}
    )

    cm.add_conversation(
        query="Orders from last month",
        sql="SELECT * FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH)",
        user_id=test_user_id,
        metadata={"dialect": "mysql"}
    )

    cm.add_conversation(
        query="Count by region",
        sql="SELECT region, COUNT(*) FROM orders GROUP BY region",
        user_id=test_user_id,
        metadata={"dialect": "mysql"}
    )

    print(f"\n✓ Added 3 conversation turns")

    history = cm.get_conversation_history(user_id=test_user_id, window_size=2)

    print(f"\n✓ Last 2 turns:")
    for i, conv in enumerate(history, 1):
        print(f"  {i}. Query: {conv['query']}")
        print(f"     SQL: {conv['sql'][:50]}...")

    full_history = cm.get_conversation_history(user_id=test_user_id, window_size=10)
    print(f"\n✓ Total turns: {len(full_history)}")

    cm.reset_memory(user_id=test_user_id)
    print(f"\n✓ Memory reset for user")

    after_reset = cm.get_conversation_history(user_id=test_user_id, window_size=10)
    print(f"✓ Turns after reset: {len(after_reset)}")

    assert len(after_reset) == 0, "Expected no history after reset"

    print("\n" + "=" * 50)
    print("✓ Basic tests passed")
    print("=" * 50)


def test_multiple_users():
    """History is isolated per user."""
    print("\n" + "=" * 50)
    print("Multi-user isolation")
    print("=" * 50)

    cm = ContextManager()

    cm.add_conversation(
        query="User A question 1",
        sql="SELECT * FROM table_a",
        user_id="user_a"
    )

    cm.add_conversation(
        query="User A question 2",
        sql="SELECT * FROM table_a WHERE id > 10",
        user_id="user_a"
    )

    cm.add_conversation(
        query="User B question 1",
        sql="SELECT * FROM table_b",
        user_id="user_b"
    )

    history_a = cm.get_conversation_history(user_id="user_a")
    history_b = cm.get_conversation_history(user_id="user_b")

    print(f"\n✓ User A turns: {len(history_a)}")
    print(f"✓ User B turns: {len(history_b)}")

    assert len(history_a) == 2, "User A should have 2 turns"
    assert len(history_b) == 1, "User B should have 1 turn"

    print("\n" + "=" * 50)
    print("✓ Multi-user isolation passed")
    print("=" * 50)


def test_window_size():
    """Window size limits returned history length."""
    print("\n" + "=" * 50)
    print("Memory window size")
    print("=" * 50)

    cm = ContextManager()
    user_id = "window_test_user"

    for i in range(1, 11):
        cm.add_conversation(
            query=f"Question {i}",
            sql=f"SELECT * FROM table{i}",
            user_id=user_id
        )

    print(f"\n✓ Added 10 turns")

    for window_size in [1, 3, 5, 10]:
        history = cm.get_conversation_history(user_id=user_id, window_size=window_size)
        print(f"✓ Window {window_size}: got {len(history)} turn(s)")
        assert len(history) == window_size, f"Window {window_size} should return {window_size} turns"

    print("\n" + "=" * 50)
    print("✓ Window size tests passed")
    print("=" * 50)


def test_conversation_model():
    """Conversation model round-trip dict."""
    print("\n" + "=" * 50)
    print("Conversation model")
    print("=" * 50)

    conv = Conversation(
        query="Test question",
        sql="SELECT * FROM test",
        metadata={"dialect": "mysql", "dataset_id": "test_dataset"}
    )

    print(f"\n✓ Created Conversation")
    print(f"  Query: {conv.query}")
    print(f"  SQL: {conv.sql}")
    print(f"  Metadata: {conv.metadata}")

    conv_dict = conv.to_dict()
    print(f"\n✓ Serialized to dict")

    conv_restored = Conversation.from_dict(conv_dict)
    print(f"✓ Restored from dict")

    assert conv_restored.query == conv.query, "Query should match after round-trip"
    assert conv_restored.sql == conv.sql, "SQL should match after round-trip"

    print("\n" + "=" * 50)
    print("✓ Model tests passed")
    print("=" * 50)


if __name__ == "__main__":
    try:
        test_basic_context_operations()
        test_multiple_users()
        test_window_size()
        test_conversation_model()

        print("\n" + "=" * 60)
        print("🎉 All tests passed — context manager OK")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
