# API Reference

## Core Modules

### parser

::: c2py23.parser
    options:
      members:
        - load_c2py
        - from_c2py_dict
        - ModuleDef
        - FuncDef
        - COverload
        - CVariant
        - PyParam
        - CParam

### generator

::: c2py23.generator
    options:
      members:
        - generate
        - CBuilder

### cli

::: c2py23.cli

### c2py_loader

::: c2py23.c2py_loader
    options:
      members:
        - load_native

### perf

::: c2py23.perf

### invariant_checker

::: c2py23.invariant_checker

## Tools

### convert_c2py_to_dict

::: tools.convert_c2py_to_dict

Converts `.c2py` files from legacy YAML to Python dict format.  YAML is no longer supported by c2py23 with default dependencies.  This script is only needed for migration.  Run with:

```bash
python3 -m tools.convert_c2py_to_dict path/to/file.c2py
```
