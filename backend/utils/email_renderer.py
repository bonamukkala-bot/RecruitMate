import html
import re

ALLOWED_TEMPLATE_VARS = {
    "candidate_name",
    "job_title",
    "company_name",
    "next_step",
    "date"
}

_VAR_PATTERN = re.compile(r"\{([^{}]+)\}")

def validate_template_variables(text: str) -> tuple[bool, str]:
    """
    Validates that any placeholders in the text are in ALLOWED_TEMPLATE_VARS.
    Returns (True, "") or (False, "error message").
    """
    if not text:
        return True, ""
    
    found_vars = _VAR_PATTERN.findall(text)
    for raw_var in found_vars:
        var = raw_var.strip()
        if var not in ALLOWED_TEMPLATE_VARS:
            allowed_list = ", ".join(f"{{{v}}}" for v in sorted(ALLOWED_TEMPLATE_VARS))
            return False, f"Unknown template variable '{{{raw_var}}}'. Allowed variables: {allowed_list}"
    
    return True, ""

def render_template(template_str: str, context: dict, escape_html: bool = False) -> str:
    """
    Safely substitutes allowed variables into template_str.
    Values are escaped with html.escape if escape_html is True.
    Does NOT use eval or str.format with arbitrary attributes.
    """
    if not template_str:
        return ""
    
    result = template_str
    for var in ALLOWED_TEMPLATE_VARS:
        val = context.get(var, "")
        if val is None:
            val = ""
        val_str = str(val)
        if escape_html:
            val_str = html.escape(val_str)
        result = result.replace(f"{{{var}}}", val_str)
    
    return result

def build_email_html(
    rendered_body: str,
    company_name: str,
    footer_note: str = "",
    button_text: str = None,
    button_url: str = None,
    details_box: list[tuple[str, str]] = None
) -> str:
    """
    Constructs a styled HTML email layout wrapping the rendered body text.
    """
    escaped_company = html.escape(company_name or "RecruitMate AI")
    escaped_footer = html.escape(footer_note) if footer_note else f"This email was sent by {escaped_company}. Please do not reply directly."
    
    # Format line breaks in body
    paragraphs = rendered_body.strip().split("\n\n")
    body_html_parts = []
    for para in paragraphs:
        cleaned_para = para.strip().replace("\n", "<br/>")
        if cleaned_para:
            body_html_parts.append(f'<p style="color: #374151; font-size: 15px; line-height: 1.7; margin: 0 0 16px 0;">{cleaned_para}</p>')
    body_html = "".join(body_html_parts)

    cta_html = ""
    if button_text and button_url:
        escaped_btn_text = html.escape(button_text)
        escaped_btn_url = html.escape(button_url)
        cta_html = f"""
        <div style="text-align: center; margin: 28px 0;">
            <a href="{escaped_btn_url}" style="background-color: #2563eb; color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block;">
                {escaped_btn_text}
            </a>
        </div>
        <p style="color: #6b7280; font-size: 13px; line-height: 1.6; text-align: center;">
            Or copy this link into your browser:<br/>
            <span style="color: #2563eb; word-break: break-all;">{escaped_btn_url}</span>
        </p>
        """

    details_html = ""
    if details_box:
        rows = "".join(
            f'<p style="margin: 4px 0; color: #374151;"><strong>{html.escape(k)}:</strong> {html.escape(v)}</p>'
            for k, v in details_box
        )
        details_html = f"""
        <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 20px; margin: 24px 0;">
            {rows}
        </div>
        """

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 24px auto; padding: 32px; border: 1px solid #e5e7eb; border-radius: 12px; background-color: #ffffff;">
        <div style="margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #f3f4f6;">
            <span style="font-size: 18px; font-weight: 700; color: #111827;">{escaped_company}</span>
        </div>
        {body_html}
        {details_html}
        {cta_html}
        <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
            <p style="color: #4b5563; font-weight: 600; margin: 0 0 6px 0;">{escaped_company} Talent Acquisition</p>
            <p style="font-size: 12px; color: #9ca3af; margin: 0; line-height: 1.5;">{escaped_footer}</p>
        </div>
    </div>
    """
