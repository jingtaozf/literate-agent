import sys
import unittest
from literate_python.reloader import ModuleReloader, extract_imports_from_code
from literate_python.server import process_a_message


class TestExtractImports(unittest.TestCase):
    """Test the import extraction functionality."""

    def test_simple_import(self):
        """Test extraction of simple import statements."""
        code = "import os"
        imports = extract_imports_from_code(code, "test_module")
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].module, "os")
        self.assertEqual(imports[0].definition, "os")
        self.assertFalse(imports[0].is_alias)

    def test_import_with_alias(self):
        """Test extraction of aliased imports."""
        code = "import numpy as np"
        imports = extract_imports_from_code(code, "test_module")
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].module, "numpy")
        self.assertEqual(imports[0].definition, "np")
        self.assertTrue(imports[0].is_alias)

    def test_from_import(self):
        """Test extraction of from imports."""
        code = "from math import sqrt, pi"
        imports = extract_imports_from_code(code, "test_module")
        self.assertEqual(len(imports), 2)
        self.assertEqual(imports[0].module, "math")
        self.assertEqual(imports[0].definition, "sqrt")
        self.assertEqual(imports[0].imported_symbol, "math.sqrt")

    def test_from_import_with_alias(self):
        """Test extraction of from imports with aliases."""
        code = "from collections import defaultdict as dd"
        imports = extract_imports_from_code(code, "test_module")
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].module, "collections")
        self.assertEqual(imports[0].definition, "dd")
        self.assertEqual(imports[0].imported_symbol, "collections.defaultdict")
        self.assertTrue(imports[0].is_alias)

    def test_wildcard_import(self):
        """Test extraction of wildcard imports."""
        code = "from os import *"
        imports = extract_imports_from_code(code, "test_module")
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].module, "os")
        self.assertEqual(imports[0].definition, "*")
        self.assertTrue(imports[0].is_wildcard)


class TestModuleReloader(unittest.TestCase):
    """Test the ModuleReloader class."""

    def setUp(self):
        """Set up test environment."""
        self.reloader = ModuleReloader()
        # Clean up any test modules from sys.modules
        for key in list(sys.modules.keys()):
            if key.startswith("test_module"):
                del sys.modules[key]

    def test_register_module(self):
        """Test module registration."""
        module_info = self.reloader.register_module("test_module_a")
        self.assertEqual(module_info.name, "test_module_a")
        self.assertIn("test_module_a", self.reloader.modules)

    def test_track_module_execution(self):
        """Test tracking module execution with dependencies."""
        # First, create module_a
        code_a = """
def func_a():
    return 'a'
x = 10
"""
        self.reloader.track_module_execution("module_a", code_a, {"func_a", "x"})

        # Create module_b that imports from module_a
        code_b = """
from module_a import func_a, x
import module_a as ma

def func_b():
    return func_a() + str(x)
"""
        self.reloader.track_module_execution("module_b", code_b, {"func_b"})

        # module_b should have imports from module_a
        module_b_info = self.reloader.modules["module_b"]
        self.assertEqual(len(module_b_info.imports), 3)  # func_a, x, and ma

        # module_a should know that module_b imports from it
        module_a_info = self.reloader.modules["module_a"]
        self.assertIn("module_b", module_a_info.imported_by)

    def test_find_dependent_modules(self):
        """Test finding dependent modules."""
        # Set up a dependency chain: module_c -> module_b -> module_a
        self.reloader.track_module_execution("module_a", "x = 1", {"x"})
        self.reloader.track_module_execution(
            "module_b", "from module_a import x", set()
        )
        self.reloader.track_module_execution(
            "module_c", "from module_b import x", set()
        )

        # Find modules dependent on module_a
        dependents = self.reloader.find_dependent_modules("module_a")
        self.assertIn("module_b", dependents)
        self.assertIn("module_c", dependents)  # Transitive dependency

    def test_update_dependent_modules_with_alias(self):
        """Test updating dependent modules with aliased imports."""
        # # Arrange: source module_a with a function and a constant, registered with the reloader.
        # Create actual modules in sys.modules
        import types

        # Create module_a
        module_a = types.ModuleType("module_a")
        module_a.original_func = lambda: "original"
        module_a.value = 100
        sys.modules["module_a"] = module_a

        # Track module_a
        self.reloader.track_module_execution("module_a", "", {"original_func", "value"})

        # # Arrange: dependent module_b that imports both names from module_a under different aliases.
        # Create module_b that imports with alias
        module_b = types.ModuleType("module_b")
        module_b.my_func = (
            module_a.original_func
        )  # Simulating: from module_a import original_func as my_func
        module_b.my_value = (
            module_a.value
        )  # Simulating: from module_a import value as my_value
        sys.modules["module_b"] = module_b

        # Track module_b with aliased imports
        code_b = """
from module_a import original_func as my_func
from module_a import value as my_value
"""
        self.reloader.track_module_execution("module_b", code_b, set())

        # # Act: rebind both names in module_a, then ask the reloader to propagate.
        # Now update module_a
        module_a.original_func = lambda: "updated"
        module_a.value = 200

        # Update dependent modules
        updates = self.reloader.update_dependent_modules("module_a")

        # # Assert: the alias-side names in module_b reflect the new bindings.
        # Check that module_b was updated
        self.assertIn("module_b", updates)
        self.assertIn("my_func", updates["module_b"])
        self.assertIn("my_value", updates["module_b"])

        # Verify the actual updates
        self.assertEqual(module_b.my_func(), "updated")
        self.assertEqual(module_b.my_value, 200)

    def tearDown(self):
        """Clean up after tests."""
        # Remove test modules from sys.modules
        for key in list(sys.modules.keys()):
            if key.startswith("test_module") or key.startswith("module_"):
                del sys.modules[key]


class TestProcessMessageIntegration(unittest.TestCase):
    """Test hot reload integration with process_a_message."""

    def setUp(self):
        """Set up test environment."""
        # Clean up test modules
        for key in list(sys.modules.keys()):
            if key.startswith("test_"):
                del sys.modules[key]

    def test_exec_with_hot_reload(self):
        """Test that exec messages trigger hot reload."""
        # # Arrange — define `test_module_x` with helper() and VALUE via the exec entry point.
        # First, create module_x
        message1 = {
            "type": "exec",
            "module": "test_module_x",
            "module-create-method": "create",
            "code": """
def helper():
    return 42

VALUE = 100
""",
        }
        result1 = process_a_message(message1)
        self.assertEqual(result1["type"], "result")

        # # Arrange — define `test_module_y` that imports both names from x and combines them in use_helper().
        # Create module_y that imports from module_x
        message2 = {
            "type": "exec",
            "module": "test_module_y",
            "module-create-method": "create",
            "code": """
from test_module_x import helper, VALUE

def use_helper():
    return helper() + VALUE
""",
        }
        result2 = process_a_message(message2)
        self.assertEqual(result2["type"], "result")

        # # Verify initial state, then act — re-exec test_module_x with new bindings to trigger hot reload.
        # Verify initial state
        import test_module_y

        self.assertEqual(test_module_y.use_helper(), 142)

        # Update module_x
        message3 = {
            "type": "exec",
            "module": "test_module_x",
            "code": """
def helper():
    return 99

VALUE = 200
""",
        }
        result3 = process_a_message(message3)
        self.assertEqual(result3["type"], "result")

        # # Assert — the response carries hot-reload metadata and module_y now reflects the new bindings.
        # Check that hot reload information is present
        self.assertIn("updated_modules", result3)
        self.assertIn("test_module_y", result3["updated_modules"])

        # Verify that module_y was updated
        self.assertEqual(test_module_y.helper(), 99)
        self.assertEqual(test_module_y.VALUE, 200)
        self.assertEqual(test_module_y.use_helper(), 299)

    def test_exec_with_import_alias(self):
        """Test hot reload with import aliases."""
        # # Arrange — define test_lib with a Calculator class and a compute() function via exec.
        # Create module_lib
        message1 = {
            "type": "exec",
            "module": "test_lib",
            "module-create-method": "create",
            "code": """
class Calculator:
    def add(self, a, b):
        return a + b
        
def compute():
    return 'v1'
""",
        }
        result1 = process_a_message(message1)
        self.assertEqual(result1["type"], "result")

        # # Arrange — define test_app that imports Calculator as Calc and compute as calc_func, exercising both alias forms.
        # Create module_app with aliased imports
        message2 = {
            "type": "exec",
            "module": "test_app",
            "module-create-method": "create",
            "code": """
from test_lib import Calculator as Calc
from test_lib import compute as calc_func

my_calc = Calc()
result = calc_func()
""",
        }
        result2 = process_a_message(message2)
        self.assertEqual(result2["type"], "result")

        # # Verify the pre-update behaviour, then act — re-exec test_lib with new Calculator behaviour and a new compute() return.
        # Verify initial state
        import test_app

        self.assertEqual(test_app.result, "v1")
        self.assertEqual(test_app.my_calc.add(1, 2), 3)

        # Update test_lib
        message3 = {
            "type": "exec",
            "module": "test_lib",
            "code": """
class Calculator:
    def add(self, a, b):
        return (a + b) * 10  # Changed behavior
        
def compute():
    return 'v2'  # Changed return value
""",
        }
        result3 = process_a_message(message3)

        # # Assert — both aliased names appear in the hot-reload report and resolve to the new Calculator / compute behaviour.
        # Check hot reload occurred
        self.assertIn("updated_modules", result3)
        self.assertIn("test_app", result3["updated_modules"])

        # Verify aliased names were updated
        self.assertIn("Calc", result3["updated_modules"]["test_app"])
        self.assertIn("calc_func", result3["updated_modules"]["test_app"])

        # Create new instance with updated class
        new_calc = test_app.Calc()
        self.assertEqual(new_calc.add(1, 2), 30)

        # Verify function alias was updated
        self.assertEqual(test_app.calc_func(), "v2")

    def tearDown(self):
        """Clean up after tests."""
        # Remove test modules
        for key in list(sys.modules.keys()):
            if key.startswith("test_"):
                del sys.modules[key]


def run_all_tests():
    """Run all hot reload tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestExtractImports))
    suite.addTests(loader.loadTestsFromTestCase(TestModuleReloader))
    suite.addTests(loader.loadTestsFromTestCase(TestProcessMessageIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
