"""Assert that jnwb imports from the clean environment, as the build job's tutorial step does."""
import jnwb

assert "clean_env" in jnwb.__file__, f"jnwb resolved outside the clean env: {jnwb.__file__}"
print("Tutorials will run against:", jnwb.__file__)
