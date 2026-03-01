"""Rules CRUD API routes."""

from flask import jsonify, request

from ..errors import error_response


def register_rules_routes(app, _meta):
    """Register /api/rules* routes. Requires _meta (MetaAccessor)."""
    @app.route("/api/rules")
    def api_rules_list():
        rules = _meta.get_all_rules()
        return jsonify({"rules": rules})

    @app.route("/api/rules", methods=["POST"])
    def api_rules_add():
        data = request.get_json() or {}
        pattern = (data.get("pattern") or "").strip()
        tag = (data.get("tag") or "").strip()
        if not pattern or not tag:
            return error_response("PATTERN_AND_TAG_REQUIRED", "pattern and tag required", 400)
        _meta.add_rule_tag(pattern, tag)
        return jsonify({"pattern": pattern, "tag": tag, "rules": _meta.get_all_rules()})

    @app.route("/api/rules", methods=["DELETE"])
    def api_rules_remove():
        pattern = (request.args.get("pattern") or "").strip()
        tag = (request.args.get("tag") or "").strip()
        if not pattern:
            return error_response("PATTERN_REQUIRED", "pattern required", 400)
        if tag:
            _meta.remove_rule_tag(pattern, tag)
        else:
            _meta.remove_rule_pattern(pattern)
        return jsonify({"pattern": pattern, "tag": tag or None, "rules": _meta.get_all_rules()})

    @app.route("/api/rules", methods=["PATCH"])
    def api_rules_update_pattern():
        data = request.get_json() or {}
        old_pattern = (data.get("old_pattern") or data.get("pattern") or "").strip()
        new_pattern = (data.get("new_pattern") or "").strip()
        if not old_pattern or not new_pattern:
            return error_response("OLD_AND_NEW_PATTERN_REQUIRED", "old_pattern and new_pattern required", 400)
        if old_pattern == new_pattern:
            return jsonify({"rules": _meta.get_all_rules()})
        _meta.update_rule_pattern(old_pattern, new_pattern)
        return jsonify({"old_pattern": old_pattern, "new_pattern": new_pattern, "rules": _meta.get_all_rules()})
