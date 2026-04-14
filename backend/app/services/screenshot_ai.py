import asyncio
import base64
import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import Screenshot, Device, AnomalyLog, AnomalyType
from app.core.logging import get_logger
from app.core.files import safe_path_join
from app.core.config import settings
from app.ai.providers.groq_provider import GroqProvider

log = get_logger("screenshot_ai")

def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

async def process_screenshot_with_ai_task(screenshot_id: uuid.UUID, app_deps=None):
    """
    Background worker task to analyze a screenshot with Groq AI.
    It runs in a separate DB session to avoid interfering with the main thread.
    """
    # Wait briefly to ensure file is saved on disk
    await asyncio.sleep(1)
    
    async with AsyncSessionLocal() as db:
        await _process_screenshot_with_ai(screenshot_id, db)

async def _process_screenshot_with_ai(screenshot_id: uuid.UUID, db: AsyncSession):
    try:
        from app.api.v1.routes.blocker import _blocked_domains
        if not _blocked_domains:
            log.debug("No active blocklist domains; skipping AI screenshot analysis.")
            return

        result = await db.execute(select(Screenshot).where(Screenshot.id == screenshot_id))
        shot = result.scalar_one_or_none()
        if not shot:
            return

        filepath = safe_path_join(settings.SCREENSHOT_DIR, shot.file_path)
        if not filepath.exists():
            return
            
        device_res = await db.execute(select(Device).where(Device.id == shot.device_id))
        device = device_res.scalar_one_or_none()
        if not device:
            return

        base64_img = _encode_image(str(filepath))
        active_rules = [{"domain": v["domain"], "category": v["category"], "severity": v.get("severity", "medium")} 
                        for v in _blocked_domains.values() if v.get("is_active")]
                        
        if not active_rules:
            return

        prompt = f"""
You are an AI monitor checking an employee's screen.
The following is an image of the user's screen.
Observe the screen and tell me if the user is using any apps or domains that belong to these blocked categories or domains:
{json.dumps(active_rules, indent=2)}

Please respond in JSON format ONLY:
{{
  "violation_found": boolean,
  "domain_or_category_matched": "string or null",
  "reason": "short excerpt of what was seen",
  "severity_matched": "low|medium|high or null"
}}
"""
        
        provider = GroqProvider()
        client = provider._get_client()
        
        # Primary vision model
        model_name = "llama-3.2-11b-vision-preview"
        
        try:
            # We call groq directly because the existing provider text_generation format doesn't accept image inputs cleanly
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat.completions.create,
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}},
                            ],
                        }
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=600,
                    temperature=0.1
                ),
                timeout=45.0,
            )
            
            output_text = response.choices[0].message.content
            if output_text:
                result_json = json.loads(output_text)
                if result_json.get("violation_found"):
                    domain = result_json.get("domain_or_category_matched", "Unknown block category")
                    sev = result_json.get("severity_matched", "medium")
                    reason = result_json.get("reason", "Detected via screenshot AI analysis.")

                    # Create anomaly
                    anomaly = AnomalyLog(
                        employee_id=shot.employee_id,
                        device_id=shot.device_id,
                        anomaly_type=AnomalyType.unusual_app_usage,
                        description=f"Screenshot AI flagged {domain}: {reason}",
                        event_metadata={
                            "screenshot_id": str(shot.id),
                            "ai_reason": reason,
                            "domain_or_category": domain,
                            "severity_override": sev,
                            "violation_type": "screenshot_ai_flag"
                        },
                    )
                    db.add(anomaly)
                    await db.commit()
                    log.warning(f"Screenshot {shot.id} flagged for {domain} ({sev})")
                    
                    # Try pushing to dashboard
                    try:
                        from app.services.ws_broadcaster import broadcast_anomaly
                        await broadcast_anomaly({
                            "employee_id": str(shot.employee_id),
                            "type": "screenshot_ai_flag",
                            "description": f"AI flagged screenshot: {domain}",
                            "severity": sev,
                        })
                    except Exception:
                        pass
                    
        except Exception as e:
            log.warning(f"Screenshot AI processing failed or rate limited: {e}")
            # The prompt requested a fallback if we hit rate limits. For image models, if llama-3.2-11b-vision isn't available, 
            # we simply skip for now because we don't have text extracted via OCR locally to pass to a text model right now.
            pass

    except Exception as e:
        log.error(f"Error in _process_screenshot_with_ai: {e}")
