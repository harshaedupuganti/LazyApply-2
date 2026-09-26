class FormAnalyzer:
    FIELD_LABEL_MAP = {
        # Name fields
        "first name": ("name", "first"), "given name": ("name", "first"),
        "last name": ("name", "last"), "surname": ("name", "last"), "family name": ("name", "last"),
        "full name": ("name", "full"), "your name": ("name", "full"),
        # Contact fields
        "email": ("email", None), "email address": ("email", None),
        "phone": ("phone", None), "mobile": ("phone", None), "contact number": ("phone", None),
        # Profile links
        "linkedin": ("linkedin_url", None), "linkedin profile": ("linkedin_url", None),
        "github": ("github_url", None), "portfolio": ("github_url", None),
        # Experience
        "years of experience": ("years_experience", None), "experience": ("years_experience", None),
        # Documents
        "resume": ("resume_file", None), "cv": ("resume_file", None),
        "upload resume": ("resume_file", None), "upload cv": ("resume_file", None),
        # Location
        "city": ("location", None), "location": ("location", None),
        # Cover letter
        "cover letter": ("cover_letter", None),
    }

    async def analyze_form(self, page) -> list[dict]:
        """Analyze all form fields on the current page."""
        fields = []
        
        try:
            # Find all input elements
            inputs = await page.locator("input:not([type='hidden']), textarea, select").all()
            
            for input_el in inputs:
                try:
                    input_type = await input_el.get_attribute("type") or "text"
                    if input_type in ["hidden", "submit", "button", "reset"]: 
                        continue
                    
                    field_id = await input_el.get_attribute("id") or ""
                    field_name = await input_el.get_attribute("name") or ""
                    placeholder = await input_el.get_attribute("placeholder") or ""
                    aria_label = await input_el.get_attribute("aria-label") or ""
                    
                    # Find associated label
                    label_text = ""
                    if field_id:
                        try:
                            label_locator = page.locator(f"label[for='{field_id}']")
                            if await label_locator.count() > 0:
                                label_text = await label_locator.first.inner_text()
                        except Exception: 
                            pass
                    
                    # Try parent element label
                    if not label_text:
                        try:
                            parent_label = input_el.locator("xpath=ancestor::label")
                            if await parent_label.count() > 0:
                                label_text = await parent_label.first.inner_text()
                        except Exception: 
                            pass
                    
                    # Use placeholder or aria-label as fallback
                    if not label_text:
                        label_text = placeholder or aria_label
                    
                    # Determine what data to fill (Tier 1: label matching)
                    mapping = self._map_label_to_field(label_text.lower())
                    
                    # If no mapping found (Tier 2): try name/id attributes
                    if not mapping:
                        mapping = self._map_label_to_field(field_name.lower()) or \
                                  self._map_label_to_field(field_id.lower())
                    
                    tag_name_str = await input_el.evaluate("el => el.tagName.toLowerCase()")
                    
                    if input_type == "file":
                        final_type = "file"
                    elif tag_name_str == "select":
                        final_type = "select"
                    elif tag_name_str == "textarea":
                        final_type = "textarea"
                    else:
                        final_type = "text"
                        
                    # Build an intelligent selector string to re-find this element later
                    element_selector = None
                    if field_name:
                        element_selector = f"[name='{field_name}']"
                    elif field_id:
                        element_selector = f"[id='{field_id}']"
                    
                    fields.append({
                        "element": input_el,
                        "type": final_type,
                        "label": label_text.strip(),
                        "mapping": mapping,  # (field_key, sub_key) or None
                        "required": await input_el.get_attribute("required") is not None,
                        "selector": element_selector
                    })
                except Exception as e:
                    print(f"Error processing individual form field: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error finding form inputs: {e}")
            
        return fields

    def _map_label_to_field(self, label_lower: str) -> tuple | None:
        if not label_lower:
            return None
            
        for key, value in self.FIELD_LABEL_MAP.items():
            if key in label_lower:
                return value
                
        return None