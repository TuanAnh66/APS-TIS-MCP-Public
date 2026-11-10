"""Conservative redaction for credential-shaped text in MCP responses."""
import re

_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----", re.DOTALL),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{15,}\b"),
)


def sensitive_path(path):
    segments = path.lower().split("/")
    name = segments[-1]
    return (
        any(segment in ("credentials", "secrets", ".ssh") for segment in segments)
        or name == ".env" or name.startswith(".env.")
        or name in ("id_rsa", "id_ed25519")
        or name.endswith((".pem", ".key", ".p12", ".pfx"))
    )


def protect(value):
    changed = False

    def visit(node):
        nonlocal changed
        if isinstance(node, str):
            result = node
            for pattern in _PATTERNS:
                result, count = pattern.subn("[REDACTED CREDENTIAL]", result)
                changed = changed or count > 0
            return result
        if isinstance(node, list):
            return [visit(item) for item in node]
        if isinstance(node, dict):
            return {key: visit(item) for key, item in node.items()}
        return node

    output = visit(value)
    if changed and isinstance(output, dict):
        output.setdefault("limitations", []).append("Credential-shaped text was redacted from the MCP response")
        if "complete" in output:
            output["complete"] = False
    return output
