"""Print the interpreter's purelib directory."""
import sysconfig

print(sysconfig.get_paths()["purelib"])
