# Consumer sketch (not run from this directory alone — use with a project that
# has cuppa on PYTHONPATH and Conan 2 installed).
#
# In the project sconstruct:
#
#   import cuppa
#   cuppa.run(
#       default_variants=['dbg'],
#       default_dependencies=['fmt'],  # discovered via cuppa.dependency.plugins
#   )
#
# In the project sconscript:
#
#   Import('env')
#   env.BuildWith('fmt')   # optional if already in default_dependencies
#   env.Build('hello', 'hello.cpp')
