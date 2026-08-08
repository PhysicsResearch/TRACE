import os
import tempfile

def get_app_data_dir():
    """
    Returns a writable directory path for TRACE application configuration, debug files, and logs.
    Creates %LOCALAPPDATA%\\TRACE (Windows) or ~/.trace (Linux/macOS) if it doesn't exist.
    """
    local_app_data = os.getenv('LOCALAPPDATA')
    if local_app_data:
        app_dir = os.path.join(local_app_data, 'TRACE')
    else:
        app_dir = os.path.join(os.path.expanduser('~'), '.trace')
    
    try:
        os.makedirs(app_dir, exist_ok=True)
        return app_dir
    except Exception:
        temp_dir = os.path.join(tempfile.gettempdir(), 'TRACE')
        try:
            os.makedirs(temp_dir, exist_ok=True)
            return temp_dir
        except Exception:
            return tempfile.gettempdir()

def get_config_path(filename, for_writing=False):
    """
    Returns the appropriate path for reading or writing a configuration/debug file.
    
    If for_writing is True:
        Returns the path inside the user's writable AppData directory.
    If for_writing is False (reading):
        Checks AppData dir first, then falls back to current working directory or app root.
    """
    user_app_dir = get_app_data_dir()
    user_path = os.path.join(user_app_dir, filename)

    if for_writing:
        return user_path

    if os.path.exists(user_path):
        return user_path

    # Fallback for reading: check CWD or app bundle directory
    cwd_path = os.path.join(os.getcwd(), filename)
    if os.path.exists(cwd_path):
        return cwd_path

    base_dir = os.path.dirname(os.path.abspath(__file__))
    app_root = os.path.abspath(os.path.join(base_dir, ".."))
    bundle_path = os.path.join(app_root, filename)
    if os.path.exists(bundle_path):
        return bundle_path

    return user_path
