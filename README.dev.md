
# Developer Documentation

## Admin Setup Verification (`verify_admin_setup.py`)

The `verify_admin_setup.py` script is a developer tool to ensure that the admin environment is correctly configured. It performs the following checks:

1.  **Configuration Files**: Verifies the existence of `.env.admin`.
2.  **Gitignore Protection**: Checks that `.env.admin` is included in `.gitignore` to prevent accidental commits of sensitive data.
3.  **Admin Authentication**: Tests the `AdminAuthenticator` and verifies that admin credentials can be loaded.

### Environment Variable Loading

The script now includes a helper function, `parse_env_file`, to safely parse `.env` files.

**Warning Mechanism**:

To prevent silent configuration overrides, the script will now print a warning if it detects that an environment variable it is about to set from `.env.admin` is already present in the environment. This is crucial for debugging, as it makes developers aware of potential conflicts where a system-level environment variable might be overriding a project-specific one.


