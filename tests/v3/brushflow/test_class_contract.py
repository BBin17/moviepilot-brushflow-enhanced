import ast
from pathlib import Path


PLUGIN_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "plugins.v3"
    / "brushflow"
    / "__init__.py"
)


def test_all_private_self_calls_have_a_declared_method() -> None:
    """发布前捕获重构中删除定义、仍保留调用的私有方法。"""
    tree = ast.parse(PLUGIN_SOURCE.read_text(encoding="utf-8"))
    plugin_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BrushFlow"
    )
    declared = {
        node.name
        for node in plugin_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    called = {
        node.func.attr
        for node in ast.walk(plugin_class)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr.startswith("_")
    }

    assert called - declared == set()
