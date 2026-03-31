import unittest
import os
from unittest.mock import MagicMock

# Assume default_api is available in the environment where this test runs
# For the purpose of this test, we'll mock it.
class MockDefaultApi:
    def __init__(self):
        self.files = {} # Stores file content and sha

    def create_file(self, repo_name, path, content, message, branch=None):
        if path in self.files:
            raise Exception("File already exists for creation test")
        sha = f"sha_for_{path}_{len(self.files) + 1}"
        self.files[path] = {"content": content, "sha": sha}
        return {"content": content, "path": path, "sha": sha}

    def get_file_content(self, repo_name, path, ref=None):
        if path not in self.files:
            raise Exception("File not found for get_file_content test")
        return {"content": self.files[path]["content"], "sha": self.files[path]["sha"]}

    def update_file(self, repo_name, path, content, message, sha, branch=None):
        if path not in self.files:
            raise Exception("File not found for update test")
        if self.files[path]["sha"] != sha:
            raise Exception("SHA mismatch for update test")
        new_sha = f"sha_for_{path}_updated_{len(self.files) + 1}"
        self.files[path]["content"] = content
        self.files[path]["sha"] = new_sha
        return {"content": content, "path": path, "sha": new_sha}

class TestAgentUpdateFile(unittest.TestCase):

    def setUp(self):
        self.mock_api = MockDefaultApi()
        self.repo_name = "jersobh/DSR-CRAG"
        self.test_file_path = "backend/tests/temp_test_file.txt"
        self.branch_name = "fix/update-file-tool-usage"

    def test_agent_correct_update_file_usage(self):
        # 1. Create a new file
        initial_content = "This is the initial content."
        create_response = self.mock_api.create_file(
            repo_name=self.repo_name,
            path=self.test_file_path,
            content=initial_content,
            message="Create temp_test_file.txt",
            branch=self.branch_name
        )
        self.assertIsNotNone(create_response)
        self.assertEqual(create_response["content"], initial_content)

        # 2. Get the content of the newly created file to obtain its sha
        file_info = self.mock_api.get_file_content(
            repo_name=self.repo_name,
            path=self.test_file_path,
            ref=self.branch_name
        )
        current_sha = file_info["sha"]
        self.assertEqual(file_info["content"], initial_content)

        # 3. Update the file using the retrieved sha
        updated_content = "This is the updated content."
        update_response = self.mock_api.update_file(
            repo_name=self.repo_name,
            path=self.test_file_path,
            content=updated_content,
            message="Update temp_test_file.txt",
            sha=current_sha,
            branch=self.branch_name
        )
        self.assertIsNotNone(update_response)
        self.assertEqual(update_response["content"], updated_content)

        # 4. Get the content again to verify the update
        verified_file_info = self.mock_api.get_file_content(
            repo_name=self.repo_name,
            path=self.test_file_path,
            ref=self.branch_name
        )
        self.assertEqual(verified_file_info["content"], updated_content)
        self.assertNotEqual(verified_file_info["sha"], current_sha) # SHA should change after update

if __name__ == '__main__':
    unittest.main()