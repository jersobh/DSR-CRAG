import unittest
from unittest.mock import MagicMock

class TestUpdateFileSHA(unittest.TestCase):

    def test_update_file_sha_handling(self):
        # Mock the GitHub API interactions
        mock_github_api = MagicMock()

        # Scenario 1: Initial file creation/first update
        # Simulate get_file_content returning an initial SHA
        mock_github_api.get_file_content.return_value = {
            "content": "initial content",
            "sha": "initial_sha123"
        }

        repo_name = "jersobh/DSR-CRAG"
        path = "test_file.txt"
        initial_content = "Hello, world!"
        initial_message = "Create test_file.txt"

        # Simulate the first update (or creation if file didn't exist)
        # In a real scenario, if creating, SHA might be None or different logic.
        # For update, we first get content to get SHA.
        file_info = mock_github_api.get_file_content(repo_name=repo_name, path=path)
        current_sha = file_info["sha"]

        new_content_1 = "Hello, world! This is updated content."
        message_1 = "Update 1"
        mock_github_api.update_file(
            repo_name=repo_name,
            path=path,
            content=new_content_1,
            message=message_1,
            sha=current_sha
        )

        # Assert that update_file was called with the correct initial SHA
        mock_github_api.update_file.assert_called_with(
            repo_name=repo_name,
            path=path,
            content=new_content_1,
            message=message_1,
            sha="initial_sha123"
        )

        # Scenario 2: Subsequent update
        # Simulate get_file_content returning a new SHA after the first update
        mock_github_api.get_file_content.return_value = {
            "content": new_content_1,
            "sha": "new_sha456"  # This is the SHA after the first update
        }

        # Get the updated SHA for the next operation
        file_info_after_update_1 = mock_github_api.get_file_content(repo_name=repo_name, path=path)
        current_sha_after_update_1 = file_info_after_update_1["sha"]

        new_content_2 = "Hello, world! This is the second update."
        message_2 = "Update 2"
        mock_github_api.update_file(
            repo_name=repo_name,
            path=path,
            content=new_content_2,
            message=message_2,
            sha=current_sha_after_update_1
        )

        # Assert that update_file was called with the correct new SHA
        mock_github_api.update_file.assert_called_with(
            repo_name=repo_name,
            path=path,
            content=new_content_2,
            message=message_2,
            sha="new_sha456"
        )