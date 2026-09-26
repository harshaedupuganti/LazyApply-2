import os
import asyncio
from agents.form_analyzer import FormAnalyzer
from agents.captcha_handler import CaptchaHandler
import core.gemini_client as gm

class IntelligentFormFiller:
    def __init__(self):
        self.form_analyzer = FormAnalyzer()
        self.captcha_handler = CaptchaHandler()

    async def fill(self, page, resume: dict, job: dict, auto_submit: bool = False) -> dict:
        """
        Fill all form fields on the current page using resume data.
        resume dict keys: name, email, phone, linkedin_url, github_url, 
                          years_experience, resume_file_path, cover_letter
        Returns: {success: bool, fields_filled: int, fields_skipped: int, submitted: bool, error: str}
        """
        
        # Step 1: Analyze the form
        fields = await self.form_analyzer.analyze_form(page)
        print(f"   Found {len(fields)} form fields")
        
        filled = 0
        skipped = 0
        
        # Step 2: Fill each field
        for field in fields:
            try:
                value = self._get_value_for_field(field.get("mapping"), resume)
                element = field["element"]
                
                if field["type"] == "file":
                    # Upload resume file
                    file_path = resume.get("resume_file_path")
                    if file_path and os.path.exists(file_path):
                        await element.set_input_files(file_path)
                        print(f"   📎 Uploaded resume to: {field['label']}")
                        filled += 1
                    else:
                        print(f"   ⚠️ Skipping file upload (file not found): {field['label']}")
                        skipped += 1
                
                elif field["type"] == "select":
                    if value:
                        try:
                            await element.select_option(label=str(value))
                            filled += 1
                            print(f"   ✅ Selected '{value}' for: {field['label']}")
                        except Exception:
                            # Try selecting by value text match manually
                            options = await element.locator("option").all()
                            selected = False
                            for opt in options:
                                opt_text = (await opt.inner_text()).lower()
                                if str(value).lower() in opt_text:
                                    # Fallback to selecting by value attribute
                                    opt_val = await opt.get_attribute("value")
                                    if opt_val:
                                        await element.select_option(value=opt_val)
                                        filled += 1
                                        selected = True
                                        print(f"   ✅ Selected '{opt_text}' for: {field['label']}")
                                        break
                            if not selected:
                                skipped += 1
                    else:
                        skipped += 1
                
                elif field["type"] in ["text", "textarea"]:
                    if value:
                        await element.click()
                        await asyncio.sleep(0.3)
                        await element.fill("")
                        # Type with slight delay for human-like feel (press_sequentially replaces deprecated .type)
                        await element.press_sequentially(str(value), delay=50)
                        filled += 1
                        print(f"   ✅ Filled text for: {field['label']}")
                        
                    elif field.get("required"):
                        # Required field with no mapped value — use Gemini as last resort
                        print(f"   🧠 Asking Gemini to fill required field: {field['label']}...")
                        ai_value = await self._ask_gemini_for_field(field["label"], resume, job)
                        if ai_value:
                            await element.fill(ai_value)
                            filled += 1
                            print(f"   ✅ Gemini answered '{ai_value[:30]}...' for: {field['label']}")
                        else:
                            print(f"   ⚠️ Could not fill required field: {field['label']}")
                            skipped += 1
                    else:
                        skipped += 1
                
                await asyncio.sleep(0.5)  # Small pause between fields to mimic human behavior
                
            except Exception as e:
                print(f"   ❌ Error filling field '{field.get('label', '?')}': {e}")
                skipped += 1
        
        # Step 3: Check for CAPTCHA before submitting
        if await self.captcha_handler.solve(page) == False:
            return {"success": False, "error": "CAPTCHA solving failed"}
        
        # Step 4: Handle submission
        submitted = False
        if auto_submit:
            submit_selectors = [
                "button[type='submit']",
                "button:has-text('Submit')", 
                "button:has-text('Apply')",
                "button:has-text('Send Application')",
                "input[type='submit']"
            ]
            for sel in submit_selectors:
                try:
                    submit_btn = page.locator(sel).first
                    if await submit_btn.count() > 0:
                        # Ensure the button is actually visible and clickable
                        if await submit_btn.is_visible():
                            await submit_btn.click()
                            await asyncio.sleep(3)
                            submitted = True
                            print("   ✅ Form submitted!")
                            break
                except Exception:
                    continue
            
            if not submitted:
                print("   ⚠️ Could not find a working submit button.")
        else:
            print("   ⏸️ Form filled but not submitted (AUTO_SUBMIT=false). Review in browser.")
        
        return {
            "success": True,
            "fields_filled": filled,
            "fields_skipped": skipped,
            "submitted": submitted
        }

    def _get_value_for_field(self, mapping, resume: dict) -> str | None:
        if mapping is None:
            return None
            
        field_key, sub_key = mapping
        
        if field_key == "name":
            full_name = str(resume.get("name", ""))
            parts = full_name.strip().split()
            if sub_key == "first": 
                return parts[0] if parts else ""
            if sub_key == "last": 
                return parts[-1] if len(parts) > 1 else ""
            return full_name
            
        value = resume.get(field_key, None)
        return str(value) if value is not None else None

    async def _ask_gemini_for_field(self, label: str, resume: dict, job: dict) -> str | None:
        """Use Gemini ONLY for fields we can't map ourselves."""
        if not gm.gemini: 
            return None
        
        skills_text = str(resume.get('skills', []))[:200]
        prompt = f"""A job application form has this field: "{label}"
Candidate: {resume.get('name', 'Unknown')}, {resume.get('years_experience', 'Unknown')} years experience, skills: {skills_text}
Job: {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}
What is the best short answer (1-2 sentences max) for this field?
Return ONLY the answer text, nothing else."""
        
        try:
            result = await gm.gemini.generate(prompt, max_tokens=150)
            if result:
                return result.strip()
            return None
        except Exception as e:
            print(f"Gemini generation error for field {label}: {e}")
            return None