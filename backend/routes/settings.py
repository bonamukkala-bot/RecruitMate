import copy
import traceback
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from utils.auth_helper import jwt_required, get_current_company
from utils.db import company_settings_collection
from utils.settings import (
    DEFAULT_SETTINGS,
    VALID_SECTIONS,
    get_settings,
    validate_section,
    assert_safe_db
)

settings_bp = Blueprint("settings", __name__)

# ── GET /api/settings ─────────────────────────────────────────────────────────
@settings_bp.route("", methods=["GET"])
@jwt_required
def get_all_settings():
    """
    Get all company settings, deep-merged with DEFAULT_SETTINGS.
    Always returns complete structure even if no settings document exists yet.
    """
    try:
        assert_safe_db()
        company = get_current_company()
        company_id = company.get("company_id")
        if not company_id:
            return jsonify({"success": False, "error": "Company ID missing from token"}), 400

        settings = get_settings(company_id)
        return jsonify({"success": True, "settings": settings}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to fetch settings: {str(e)}"}), 500

# ── PUT /api/settings/<section> ───────────────────────────────────────────────
@settings_bp.route("/<section>", methods=["PUT"])
@jwt_required
def update_section(section: str):
    """
    Update a single settings section for the authenticated company.
    Validates input schema and performs deep validation.
    """
    try:
        assert_safe_db()
        company = get_current_company()
        company_id = company.get("company_id")
        if not company_id:
            return jsonify({"success": False, "error": "Company ID missing from token"}), 400

        if section not in VALID_SECTIONS:
            return jsonify({
                "success": False,
                "error": f"Invalid section '{section}'. Allowed sections: {sorted(list(VALID_SECTIONS))}"
            }), 400

        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"success": False, "error": "Invalid JSON or missing request body"}), 400

        is_valid, validated_or_err = validate_section(section, payload)
        if not is_valid:
            return jsonify({"success": False, "error": validated_or_err}), 400

        now_utc = datetime.now(timezone.utc)
        updater_email = company.get("email", "unknown")

        company_settings_collection.update_one(
            {"company_id": str(company_id)},
            {
                "$set": {
                    section: validated_or_err,
                    "updated_at": now_utc,
                    "updated_by": updater_email
                }
            },
            upsert=True
        )

        return jsonify({
            "success": True,
            "message": f"{section.capitalize()} settings updated successfully",
            "section": section,
            "data": validated_or_err
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to update {section} settings: {str(e)}"}), 500

# ── POST /api/settings/<section>/reset ────────────────────────────────────────
@settings_bp.route("/<section>/reset", methods=["POST"])
@jwt_required
def reset_section(section: str):
    """
    Reset a specific settings section back to its default configuration.
    """
    try:
        assert_safe_db()
        company = get_current_company()
        company_id = company.get("company_id")
        if not company_id:
            return jsonify({"success": False, "error": "Company ID missing from token"}), 400

        if section not in VALID_SECTIONS:
            return jsonify({
                "success": False,
                "error": f"Invalid section '{section}'. Allowed sections: {sorted(list(VALID_SECTIONS))}"
            }), 400

        default_data = copy.deepcopy(DEFAULT_SETTINGS[section])
        now_utc = datetime.now(timezone.utc)
        updater_email = company.get("email", "unknown")

        company_settings_collection.update_one(
            {"company_id": str(company_id)},
            {
                "$set": {
                    section: default_data,
                    "updated_at": now_utc,
                    "updated_by": updater_email
                }
            },
            upsert=True
        )

        return jsonify({
            "success": True,
            "message": f"{section.capitalize()} settings reset to defaults",
            "section": section,
            "data": default_data
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to reset {section} settings: {str(e)}"}), 500
