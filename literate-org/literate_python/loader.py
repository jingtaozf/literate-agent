import sys
import types
import importlib
import importlib.abc
import importlib.machinery
import logging
import orgparse

logger = logging.getLogger(__name__)

if "inMemoryModules" not in globals():
    inMemoryModules = {}


def register_literate_modules(module_spec_list: list) -> None:
    for module_spec in module_spec_list:
        inMemoryModules[module_spec["name"]] = module_spec


def _get_module_spec(fullname: str) -> bool:
    return inMemoryModules.get(fullname) or inMemoryModules.get(fullname + ".__init__")


class LiterateImporter(object):
    def find_module(self, fullname: str, _path=None):
        if _get_module_spec(fullname):
            logger.debug(f"Found literate module {fullname}")
            return self
        else:
            return None

    def load_module(self, fullname: str):
        """Create a new module object."""
        mod_spec = _get_module_spec(fullname)
        mod = types.ModuleType(fullname)
        mod.__loader__ = self
        mod.__file__ = mod_spec.get("filepath", "")
        # Set module path - get filepath and keep only the path until filename
        mod.__path__ = ["/".join(mod.__file__.split("/")[:-1]) + "/"]
        mod.__package__ = fullname
        sys.modules[fullname] = mod
        # Execute the module/package code into the Module object
        logger.debug(f"Load literate module {fullname}")
        exec(mod_spec["content"], mod.__dict__)
        return mod


class LiterateModuleFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, _path, _target=None):
        if _get_module_spec(fullname):
            logger.debug(f"Found literate module {fullname}")
            return importlib.machinery.ModuleSpec(fullname, LiterateImporter())
        return None


def register_literate_module_finder():
    sys.meta_path = [
        f for f in sys.meta_path if not isinstance(f, LiterateModuleFinder)
    ]
    print("Register literate importer.\n")
    sys.meta_path.append(LiterateModuleFinder())


def load_literate_modules_from_org_file(org_file: str) -> None:
    orgparse.load(org_file)


def load_literate_modules_from_org_node(node: orgparse.OrgNode) -> None:
    # root_module = LITERATE_ORG_ROOT_MODULE
    pass


def build_org_model_from_local_python_package(_package_path: str) -> str:
    pass
