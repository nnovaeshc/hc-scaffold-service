#!/usr/bin/env python3
"""
Stub MCP server for testing hc-scaffold-service skill.
Implements stdio JSON-RPC protocol with no external dependencies.
"""
import json
import os
import sys
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SCENARIO = os.environ.get("STUB_SCENARIO", "default")


def parse_metadata(content, fallback_name):
    """Extract name/title/description/tags from the top-level `metadata:` block
    only. Scanning the whole file would pick up the LAST `name:`/`title:`
    anywhere - step names, nested property titles - instead of the entity's."""
    meta = {"name": fallback_name, "title": None, "description": None, "tags": []}
    in_metadata = False
    in_tags = False

    for raw_line in content.split('\n'):
        if not raw_line.strip() or raw_line.lstrip().startswith('#'):
            continue

        # A non-indented key ends the metadata block.
        if not raw_line[0].isspace():
            in_metadata = raw_line.strip().startswith('metadata:')
            in_tags = False
            continue
        if not in_metadata:
            continue

        stripped = raw_line.strip()
        if in_tags:
            if stripped.startswith('- '):
                meta["tags"].append(stripped[2:].strip())
                continue
            in_tags = False

        key, sep, val = stripped.partition(':')
        if not sep:
            continue
        key, val = key.strip(), val.strip()
        if key == 'tags':
            in_tags = not val
        elif key in ('name', 'title', 'description'):
            meta[key] = val

    return meta


def load_templates():
    """Load all template fixtures."""
    templates_dir = FIXTURES_DIR / "templates"
    templates = []

    for yaml_file in sorted(templates_dir.glob("*.yaml")):
        with open(yaml_file) as f:
            content = f.read()

        meta = parse_metadata(content, yaml_file.stem)

        templates.append({
            "metadata": {
                "name": meta["name"],
                "title": meta["title"] or meta["name"],
                "description": meta["description"] or "",
                "tags": meta["tags"]
            },
            "spec": {
                "type": "service",
                "parameters": []  # Full spec loaded on demand
            },
            "_yaml": content
        })

    return templates


def load_groups():
    """Load all group fixtures."""
    groups_dir = FIXTURES_DIR / "groups"
    groups = []

    for yaml_file in sorted(groups_dir.glob("*.yaml")):
        with open(yaml_file) as f:
            content = f.read()

        meta = parse_metadata(content, yaml_file.stem)

        groups.append({
            "metadata": {
                "name": meta["name"],
                "title": meta["title"] or meta["name"],
                "description": meta["description"] or ""
            },
            "spec": {
                "type": "team"
            }
        })

    return groups


def load_task_logs(log_type="success"):
    """Load task log fixtures."""
    log_file = FIXTURES_DIR / "task-logs" / f"{log_type}.json"
    if log_file.exists():
        with open(log_file) as f:
            return json.load(f)
    return []


def get_tool_names():
    """Get tool names based on scenario."""
    if SCENARIO == "prefixed_tool_names":
        return [
            "backstage.catalog.query-catalog-entities",
            "backstage.catalog.get-catalog-entity",
            "backstage.scaffolder.execute-template",
            "backstage.scaffolder.get-scaffolder-task-logs"
        ]
    elif SCENARIO == "catalog_only":
        return [
            "catalog.query-catalog-entities",
            "catalog.get-catalog-entity"
        ]
    elif SCENARIO == "no_backstage_tools":
        return [
            "unrelated.tool-one",
            "unrelated.tool-two"
        ]
    else:
        return [
            "catalog.query-catalog-entities",
            "catalog.get-catalog-entity",
            "scaffolder.execute-template",
            "scaffolder.get-scaffolder-task-logs"
        ]


def get_base_tool_name(full_name):
    """Extract base tool name, handling prefixes."""
    # Remove common prefixes
    for prefix in ["backstage.catalog.", "backstage.scaffolder.", "catalog.", "scaffolder."]:
        if full_name.startswith(prefix):
            return full_name[len(prefix):]
    return full_name


def query_catalog_entities(arguments):
    """Handle catalog.query-catalog-entities."""
    if SCENARIO == "denied_first_call":
        return {
            "error": {
                "code": -32001,
                "message": "Authorization denied: insufficient permissions to query catalog"
            }
        }

    if SCENARIO == "empty_catalog":
        return {"result": {"items": []}}

    # Parse filter
    filter_obj = arguments.get("filter", {})
    kind = filter_obj.get("kind", "")
    fields = arguments.get("fields", [])
    limit = arguments.get("limit", 100)

    if kind == "Template":
        templates = load_templates()

        # Apply fields projection
        if fields:
            projected = []
            for t in templates:
                item = {}
                for field in fields:
                    parts = field.split('.')
                    val = t
                    for part in parts:
                        val = val.get(part, {})
                    # Set nested value
                    current = item
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = val
                projected.append(item)
            templates = projected

        return {"result": {"items": templates[:limit]}}

    elif kind == "Group":
        groups = load_groups()
        return {"result": {"items": groups[:limit]}}

    return {"result": {"items": []}}


def get_catalog_entity(arguments):
    """Handle catalog.get-catalog-entity."""
    entity_ref = arguments.get("entityRef", "")

    # Parse entity ref (format: kind:namespace/name or template:default/name)
    parts = entity_ref.split(":")
    if len(parts) < 2:
        return {"error": {"code": -32602, "message": "Invalid entityRef format"}}

    kind = parts[0].lower()
    name_part = parts[1].split("/")[-1] if "/" in parts[1] else parts[1]

    if kind == "template":
        templates = load_templates()
        for t in templates:
            if t["metadata"]["name"] == name_part:
                # Return full template with YAML spec
                return {"result": {
                    "metadata": t["metadata"],
                    "spec": {
                        "type": t["spec"]["type"],
                        "parameters": t["_yaml"]  # Return raw YAML as spec
                    }
                }}

    elif kind == "group":
        groups = load_groups()
        for g in groups:
            if g["metadata"]["name"] == name_part:
                return {"result": g}

    return {"error": {"code": -32001, "message": f"Entity not found: {entity_ref}"}}


def execute_template(arguments):
    """Handle scaffolder.execute-template."""
    if SCENARIO == "task_failure":
        return {"result": {"taskId": "task-456"}}

    return {"result": {"taskId": "task-123"}}


def get_scaffolder_task_logs(arguments):
    """Handle scaffolder.get-scaffolder-task-logs."""
    task_id = arguments.get("taskId", "")
    after = arguments.get("after")

    if SCENARIO == "task_failure":
        logs = load_task_logs("failure")
    else:
        logs = load_task_logs("success")

    # Filter by after cursor
    if after:
        filtered = [log for log in logs if log["id"] > after]
        return {"result": {"logs": filtered}}

    return {"result": {"logs": logs}}


def handle_tools_list():
    """Handle tools/list request."""
    tool_names = get_tool_names()

    tools = []
    for name in tool_names:
        base_name = get_base_tool_name(name)

        if "query-catalog-entities" in base_name:
            tools.append({
                "name": name,
                "description": "Query catalog entities with filters and projections",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "object"},
                        "fields": {"type": "array"},
                        "limit": {"type": "integer"}
                    }
                }
            })
        elif "get-catalog-entity" in base_name:
            tools.append({
                "name": name,
                "description": "Get a specific catalog entity by reference",
                "inputSchema": {
                    "type": "object",
                    "required": ["entityRef"],
                    "properties": {
                        "entityRef": {"type": "string"}
                    }
                }
            })
        elif "execute-template" in base_name:
            tools.append({
                "name": name,
                "description": "Execute a scaffolder template",
                "inputSchema": {
                    "type": "object",
                    "required": ["templateRef", "values"],
                    "properties": {
                        "templateRef": {"type": "string"},
                        "values": {"type": "object"}
                    }
                }
            })
        elif "get-scaffolder-task-logs" in base_name:
            tools.append({
                "name": name,
                "description": "Get scaffolder task logs",
                "inputSchema": {
                    "type": "object",
                    "required": ["taskId"],
                    "properties": {
                        "taskId": {"type": "string"},
                        "after": {"type": "string"}
                    }
                }
            })
        else:
            # Unrelated tool
            tools.append({
                "name": name,
                "description": "Unrelated tool for testing",
                "inputSchema": {"type": "object"}
            })

    return {"tools": tools}


def handle_tools_call(name, arguments):
    """Handle tools/call request."""
    base_name = get_base_tool_name(name)

    if "query-catalog-entities" in base_name:
        return query_catalog_entities(arguments or {})
    elif "get-catalog-entity" in base_name:
        return get_catalog_entity(arguments or {})
    elif "execute-template" in base_name:
        return execute_template(arguments or {})
    elif "get-scaffolder-task-logs" in base_name:
        return get_scaffolder_task_logs(arguments or {})

    return {"error": {"code": -32601, "message": f"Unknown tool: {name}"}}


def handle_request(request):
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        response = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "backstage-stub",
                "version": "1.0.0"
            }
        }
    elif method == "tools/list":
        response = handle_tools_list()
    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        call_result = handle_tools_call(name, arguments)

        if "error" in call_result:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": call_result["error"]
            }

        # MCP requires tools/call results to carry a `content` block list.
        # Returning the bare payload reads as "completed with no output".
        payload = call_result.get("result", call_result)
        response = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    elif method.startswith("notifications/"):
        return None  # notifications carry no id and take no response
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": response
    }


def main():
    """Main stdio loop."""
    sys.stderr.write(f"Stub MCP server started with scenario: {SCENARIO}\n")
    sys.stderr.flush()

    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = handle_request(request)
            if response is not None:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"JSON decode error: {e}\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"Error handling request: {e}\n")
            sys.stderr.flush()
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
