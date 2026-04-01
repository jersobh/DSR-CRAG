import base64
from default_api import default_api # Import default_api

def robust_update_file(repo_name, path, new_content, message, sha, branch="main"):
    """
    Updates a file in the repository using default_api.robust_update_file.
    This function is designed to be robust by directly using the default_api's
    robust update functionality.

    Args:
        repo_name (str): The full name of the repository (e.g., 'owner/repo').
        path (str): The path to the file in the repository.
        new_content (str): The new content for the file.
        message (str): The commit message.
        sha (str): The SHA of the file to update.
        branch (str): The branch to commit to. Defaults to "main".
    """
    try:
        # Encode the new content to base64 as required by the update_file tool
        encoded_content = base64.b64encode(new_content.encode('utf-8')).decode('utf-8')

        updated_file = default_api.robust_update_file(
            repo_name=repo_name,
            filename=path, # Corrected: use path as filename
            content=encoded_content,
            message=message,
            sha=sha,
            branch=branch
        )
        return {"status": "success", "message": "File updated successfully.", "details": updated_file}
    except Exception as e:
        return {"status": "error", "message": f"Failed to update file: {e}"}

def robust_delete_file(repo_name, path, message, sha, branch="main"):
    """
    Deletes a file from the repository using default_api.delete_file.
    Includes error handling for the known 'NoneType' object has no attribute 'message' bug.

    Args:
        repo_name (str): The full name of the repository (e.g., 'owner/repo').
        path (str): The path to the file in the repository.
        message (str): The commit message.
        sha (str): The blob SHA of the file being deleted.
        branch (str): The branch to commit to. Defaults to "main".
    """
    try:
        # Attempt to delete the file using the default_api tool
        delete_result = default_api.delete_file(
            repo_name=repo_name,
            path=path,
            message=message,
            sha=sha,
            branch=branch
        )
        # If the tool returns None or an empty dict, it might still be an issue
        if delete_result is None or not delete_result:
            return {"status": "error", "message": "File deletion failed: The delete_file tool returned an unexpected empty or None response. This might indicate an underlying issue with the tool."}
        
        return {"status": "success", "message": "File deleted successfully.", "details": delete_result}
    except AttributeError as e:
        if "'NoneType' object has no attribute 'message'" in str(e):
            return {"status": "error", "message": f"File deletion failed due to a known bug in the delete_file tool: {e}. The tool likely returned None where an object with a 'message' attribute was expected."}
        else:
            return {"status": "error", "message": f"An unexpected error occurred during file deletion: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred during file deletion: {e}"}