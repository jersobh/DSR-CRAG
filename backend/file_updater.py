import base64

def update_file_with_sha(repo_name, path, new_content, message, branch="main", get_file_content_func=None, update_file_func=None):
    """
    Updates a file in the repository by first fetching its current SHA.
    This ensures that the update_file tool is used with the correct SHA,
    preventing issues with stale SHAs.

    Args:
        repo_name (str): The full name of the repository (e.g., 'owner/repo').
        path (str): The path to the file in the repository.
        new_content (str): The new content for the file.
        message (str): The commit message.
        branch (str): The branch to commit to. Defaults to "main".
        get_file_content_func (callable): Function to get file content (e.g., default_api.get_file_content).
        update_file_func (callable): Function to update file (e.g., default_api.update_file).
    """
    if get_file_content_func is None or update_file_func is None:
        raise ValueError("get_file_content_func and update_file_func must be provided.")

    try:
        # Get the current file content to retrieve its SHA
        file_details = get_file_content_func(repo_name=repo_name, path=path, ref=branch)
        current_sha = file_details['sha']

        # Encode the new content to base64 as required by the update_file tool
        encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')

        # Update the file with the new content and the fetched SHA
        updated_file = update_file_func(
            repo_name=repo_name,
            path=path,
            content=encoded_content,
            message=message,
            sha=current_sha,
            branch=branch
        )
        return {"status": "success", "message": "File updated successfully.", "details": updated_file}
    except Exception as e:
        return {"status": "error", "message": f"Failed to update file: {e}"}