# Explicit namespace package declaration for jnwb subpackages
__path__ = __import__('pkgutil').extend_path(__path__, __name__)
