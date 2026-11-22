"""List the public names a change adds, removes or changes in a package, as a PR comment.

Usage: python scripts/api_surface.py BASE_REF HEAD_REF [--package erp_framework] [--repo .]
"""

import argparse
import ast

import griffe

SKIPPED_MODULES = {"tests", "migrations"}


def value_kind(value):
    """Kind of an assigned value: dict, list, str, a call such as `DocTypeRegistry()`, or expression."""
    if value is None:
        return "attribute"
    try:
        node = ast.parse(str(value), mode="eval").body
    except SyntaxError:
        return "expression"
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.Call):
        return f"{ast.unparse(node.func)}()"
    return {ast.Dict: "dict", ast.List: "list", ast.Tuple: "tuple", ast.Set: "set"}.get(type(node), "expression")


def describe(obj):
    """One line per public name: its kind plus the signature, bases or value kind that define it."""
    if obj.is_alias:
        return f"re-export of `{obj.target_path}`"
    if obj.is_module:
        return "module"
    labels = "".join(f" @{label}" for label in sorted(obj.labels & {"property", "classmethod", "staticmethod"}))
    if obj.is_class:
        return f"class({', '.join(str(base) for base in obj.bases)})"
    if obj.is_function:
        return f"{'method' if obj.parent.is_class else 'function'}{labels} `{obj.signature()}`"
    annotation = f": {obj.annotation}" if obj.annotation is not None else ""
    scope = "class attribute" if obj.parent.is_class else "constant"
    return f"{scope}{labels}{annotation} ({value_kind(obj.value)})"


def public_surface(obj, surface):
    """Map dotted path to description for every public member under obj, recursing into modules and classes."""
    for name, member in obj.members.items():
        skipped_module = not member.is_alias and member.is_module and (name in SKIPPED_MODULES or name.startswith("test"))
        if name.startswith("_") or skipped_module:
            continue
        if obj.is_module and not member.is_public:
            continue
        surface[member.path] = describe(member)
        if not member.is_alias and (member.is_module or member.is_class):
            public_surface(member, surface)
    return surface


def report(base, head, base_ref, head_ref):
    added = sorted(set(head) - set(base))
    removed = sorted(set(base) - set(head))
    changed = sorted(path for path in set(base) & set(head) if base[path] != head[path])
    if not (added or removed or changed):
        return "No public API changes.\n"
    lines = ["## Public API changes", ""]
    for title, paths, kind in (
        ("Added", added, lambda path: head[path]),
        ("Removed", removed, lambda path: base[path]),
        ("Changed", changed, lambda path: f"{base[path]}<br>→ {head[path]}"),
    ):
        if paths:
            rows = [f"| `{path}` | {kind(path).replace('|', r'\|')} |" for path in paths]
            lines += [f"**{title} ({len(paths)})**", "", "| Name | Kind |", "|---|---|", *rows, ""]
    lines += ["---", f"<sub>Advisory: this report never blocks a merge. `{head_ref}` against `{base_ref}`.</sub>"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_ref")
    parser.add_argument("head_ref")
    parser.add_argument("--package", default="erp_framework")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    base, head = (
        public_surface(griffe.load_git(args.package, ref=ref, repo=args.repo, allow_inspection=False), {})
        for ref in (args.base_ref, args.head_ref)
    )
    print(report(base, head, args.base_ref, args.head_ref), end="")


if __name__ == "__main__":
    main()
