"""Tests for tool classification."""
from context_audit.classifier import classify_tool


class TestClassifyTool:
    def test_read_verbs(self):
        for name in ["get_users", "list_files", "search_messages", "read_file", "fetch_data", "find_user"]:
            result = classify_tool(name)
            assert result.category == "read", f"{name} should be read, got {result.category}"

    def test_write_verbs(self):
        for name in ["create_issue", "update_record", "edit_file", "add_comment", "send_message"]:
            result = classify_tool(name)
            assert result.category == "write", f"{name} should be write, got {result.category}"

    def test_delete_verbs(self):
        for name in ["delete_file", "remove_user", "destroy_resource", "purge_cache", "revoke_token"]:
            result = classify_tool(name)
            assert result.category == "delete", f"{name} should be delete, got {result.category}"

    def test_execute_verbs(self):
        for name in ["execute_query", "run_command", "deploy_service", "restart_server"]:
            result = classify_tool(name)
            assert result.category == "execute", f"{name} should be execute, got {result.category}"

    def test_unknown_tools(self):
        result = classify_tool("foobar")
        assert result.category == "unknown"
        assert result.confidence == "low"

    def test_hyphenated_names(self):
        result = classify_tool("get-user-profile")
        assert result.category == "read"

    def test_slashed_names(self):
        result = classify_tool("github/list_repos")
        assert result.category == "read"

    def test_confidence_levels(self):
        # Direct match = high
        result = classify_tool("list_items")
        assert result.confidence == "high"

        # Unknown = low
        result = classify_tool("xyz_thing")
        assert result.confidence == "low"
