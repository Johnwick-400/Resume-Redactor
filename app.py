    import os
    import io
    import json
    import fitz
    import streamlit as st
    import requests
    import re
    from typing import List, Dict, Any
    from pydantic import BaseModel
    from dotenv import load_dotenv

    load_dotenv()

    st.set_page_config(
        page_title="PDF Resume Redactor",
        page_icon="🔒",
        layout="wide",
    )

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "enter your api key ")
    OPENAI_MODEL = "gpt-4o-mini"

    STOP_WORDS = {
        'in', 'at', 'on', 'of', 'the', 'and', 'or', 'but', 'a', 'an', 'to', 'for', 
        'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you',
        'he', 'she', 'it', 'we', 'him', 'her', 'us', 'them', 'my',
        'your', 'his', 'her', 'its', 'our', 'their'
    }

    class PersonalInfo(BaseModel):
        emails: List[str] = []
        phone_numbers: List[str] = []
        names: List[str] = []
        addresses: List[str] = []
        linkedin_urls: List[str] = []
        github_urls: List[str] = []
        other_urls: List[str] = []
        locations: List[str] = []

    class EducationInfo(BaseModel):
        institutions: List[str] = []
        degrees: List[str] = []
        graduation_years: List[str] = []
        gpa_scores: List[str] = []
        certifications: List[str] = []

    class ExperienceInfo(BaseModel):
        companies: List[str] = []
        job_titles: List[str] = []
        project_titles: List[str] = []
        employment_dates: List[str] = []
        achievements: List[str] = []
        responsibilities: List[str] = []

    class ResumeData(BaseModel):
        personal_info: PersonalInfo = PersonalInfo()
        education: EducationInfo = EducationInfo()
        experience: ExperienceInfo = ExperienceInfo()

    class PDFRedactor:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.api_url = "https://api.openai.com/v1/chat/completions"
            self.headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}

        @staticmethod
        def extract_text(pdf_bytes: bytes) -> str:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = []
            for pg in doc:
                text.append(pg.get_text())
            doc.close()
            return "\n".join(text)

        def flatten_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
            flattened = {}
            for section, section_data in data.items():
                if isinstance(section_data, dict):
                    flattened[section] = {}
                    for key, value in section_data.items():
                        if isinstance(value, list):
                            flat_list = []
                            for item in value:
                                if isinstance(item, dict):
                                    flat_list.extend([str(v) for v in item.values() if v and str(v).strip()])
                                elif isinstance(item, str) and item.strip():
                                    flat_list.append(item.strip())
                                elif item and str(item).strip():
                                    flat_list.append(str(item).strip())
                            flattened[section][key] = flat_list
                        else:
                            flattened[section][key] = []
                else:
                    flattened[section] = section_data if section_data else {}
            return flattened

        def detect_resume_info(self, text: str) -> ResumeData:
            prompt = f"""
            Extract information from the resume text and return ONLY valid JSON with exactly this structure:
            {{
                "personal_info": {{
                    "emails": [],
                    "phone_numbers": [],
                    "names": [],
                    "addresses": [],
                    "date_of_birth": "",
                    "languages": [common languages],
                    "linkedin_urls": [],
                    "github_urls": [],
                    "other_urls": [],
                    "locations": []
                }},
                "education": {{
                    "institutions": [],
                    "graduation_years": []
                }},
                "experience": {{
                    "companies": [],
                    "project_titles": []
                
                }}
            }}
            Resume text:
            {text}
            """
            payload = {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "Return strictly valid JSON with flat string arrays only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
            }
            try:
                response = requests.post(self.api_url, headers=self.headers, json=payload)
                if response.status_code != 200:
                    st.error(f"OpenAI API Error: {response.status_code} - {response.text}")
                    return ResumeData()
                content = response.json()['choices'][0]['message']['content'].strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    json_start = -1
                    json_end = -1
                    for i, line in enumerate(lines):
                        if line.strip().startswith("{"):
                            json_start = i
                            break
                    for i in range(len(lines) - 1, -1, -1):
                        if lines[i].strip().endswith("}"):
                            json_end = i
                            break
                    if json_start != -1 and json_end != -1:
                        content = "\n".join(lines[json_start:json_end + 1])
                data = json.loads(content)
                flattened_data = self.flatten_extracted_data(data)
                return ResumeData.model_validate(flattened_data)
            except Exception as e:
                st.error(f"Error: {e}")
                return ResumeData()

        @staticmethod
        def find_images(pdf_bytes: bytes) -> List[Dict[str, Any]]:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            images = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img if isinstance(img, (list, tuple)) else img
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha < 4:
                            img_data = pix.tobytes("png")
                            bbox = page.get_image_bbox(img)
                            images.append({
                                "page": page_num,
                                "index": img_index,
                                "xref": xref,
                                "data": img_data,
                                "bbox": bbox,
                                "width": pix.width,
                                "height": pix.height,
                                "size": len(img_data)
                            })
                        pix = None
                    except:
                        continue
            doc.close()
            return images

        @staticmethod
        def is_valid_redaction_term(term: str, term_type: str = "general", min_length: int = 3) -> bool:
            term = term.strip()
            if len(term) < min_length:
                return False
            if term.lower() in STOP_WORDS and term_type not in ["email", "phone", "url"]:
                return False
            if len(term) == 1:
                return False
            if term.isdigit() and len(term) < 4 and term_type not in ["phone", "date", "year"]:
                return False
            generic_terms = {
                'university', 'college', 'school', 'degree', 'bachelor', 'master',
                'phd', 'doctorate', 'certificate', 'diploma', 'science', 'arts',
                'engineering', 'technology', 'management', 'business', 'computer',
                'information', 'systems', 'software', 'development'
            }
            if term.lower() in generic_terms and term_type not in ["institution", "company"]:
                return False
            return True

        @staticmethod
        def generate_smart_search_terms(term: str, term_type: str = "general") -> List[str]:
            if not term or len(term.strip()) < 2:
                return []
            term = term.strip()
            search_terms = []
            if PDFRedactor.is_valid_redaction_term(term, term_type):
                search_terms.append(term)
            if term_type == "email":
                search_terms.extend([term.lower(), term.upper()])
            elif term_type == "phone":
                digits_only = re.sub(r'[^\d+]', '', term)
                if len(digits_only) >= 10:
                    search_terms.append(digits_only)
                    if len(digits_only) == 10:
                        search_terms.extend([
                            f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}",
                            f"{digits_only[:3]}-{digits_only[3:6]}-{digits_only[6:]}",
                            f"{digits_only[:3]}.{digits_only[3:6]}.{digits_only[6:]}"
                        ])
                    elif len(digits_only) == 11 and digits_only.startswith('1'):
                        clean_num = digits_only[1:]
                        search_terms.extend([
                            f"({clean_num[:3]}) {clean_num[3:6]}-{clean_num[6:]}",
                            f"1-{clean_num[:3]}-{clean_num[3:6]}-{clean_num[6:]}"
                        ])
            elif term_type == "name":
                search_terms.extend([term.lower(), term.upper(), term.title()])
                parts = [p.strip() for p in term.split() if p.strip()]
                if len(parts) == 2:
                    first, last = parts
                    if (len(first) > 2 and len(last) > 2 and
                        first.isalpha() and last.isalpha() and
                        first.lower() not in STOP_WORDS and last.lower() not in STOP_WORDS):
                        search_terms.extend([first, last, first.title(), last.title()])
            elif term_type == "url":
                search_terms.append(term.lower())
                if term.startswith(('http://', 'https://')):
                    clean_url = term.split('://', 1)[1]
                    search_terms.append(clean_url)
            elif term_type == "institution":
                search_terms.extend([term.lower(), term.upper(), term.title()])
                if "university" in term.lower() and len(term.split()) > 2:
                    words = term.split()
                    if len(words) >= 3:
                        abbrev = ''.join([w.upper() for w in words[:3] if len(w) > 3])
                        if len(abbrev) >= 2:
                            search_terms.append(abbrev)
            elif term_type == "company":
                search_terms.extend([term.lower(), term.upper(), term.title()])
                business_suffixes = ['Inc.', 'LLC', 'Corp.', 'Ltd.', 'Co.', 'Company', 'Corporation']
                clean_term = term
                for suffix in business_suffixes:
                    if clean_term.endswith(suffix):
                        clean_term = clean_term[:-len(suffix)].strip()
                        if len(clean_term) > 3:
                            search_terms.append(clean_term)
            elif term_type == "degree":
                search_terms.extend([term.lower(), term.upper(), term.title()])
            elif term_type == "date" or term_type == "year":
                search_terms.append(term)
            else:
                search_terms.extend([term.lower(), term.upper(), term.title()])
            valid_terms = []
            seen = set()
            for search_term in search_terms:
                clean_term = search_term.strip()
                if (clean_term and clean_term not in seen and
                    PDFRedactor.is_valid_redaction_term(clean_term, term_type)):
                    seen.add(clean_term)
                    valid_terms.append(clean_term)
            return valid_terms

        @staticmethod
        def determine_term_type(item: str, category: str) -> str:
            item = item.lower()
            if '@' in item and '.' in item:
                return "email"
            elif any(c.isdigit() for c in item) and any(c in item for c in ['-', '(', ')', '+', ' ', '.']):
                digit_count = sum(1 for c in item if c.isdigit())
                if digit_count >= 7:
                    return "phone"
            elif item.startswith(('http://', 'https://', 'www.')):
                return "url"
            elif category == "personal_info":
                if any(c.isalpha() for c in item) and not any(c.isdigit() for c in item):
                    return "name"
            elif category == "education":
                if "university" in item or "college" in item or "institute" in item:
                    return "institution"
                elif any(word in item for word in ["bachelor", "master", "phd", "degree", "diploma"]):
                    return "degree"
                elif item.isdigit() and len(item) == 4:
                    return "year"
            elif category == "experience":
                if any(word in item for word in ["inc", "corp", "llc", "ltd", "company", "technologies"]):
                    return "company"
                elif re.match(r'^\d{4}', item) or '-' in item:
                    return "date"
                elif "project" in item or "system" in item or len(item.split()) >= 2:
                    return "project"
            return "general"

        @staticmethod
        def validate_match_context(page, rect, term: str) -> bool:
            if len(term) <= 2:
                return False
            if term.lower() in STOP_WORDS:
                return False
            return True

        @staticmethod
        def merge_overlapping_rects(rects: List) -> List:
            if not rects:
                return []
            merged = []
            for rect in rects:
                merged_with_existing = False
                for i, existing_rect in enumerate(merged):
                    if rect.intersects(existing_rect):
                        merged[i] = rect | existing_rect
                        merged_with_existing = True
                        break
                if not merged_with_existing:
                    merged.append(rect)
            return merged

        @staticmethod
        def redact_pdf_section_wise(pdf_bytes: bytes, resume_data: ResumeData,
                                selected_sections: Dict[str, bool],
                                redact_images: bool = False,
                                selected_items: Dict[str, List[str]] = None) -> bytes:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            section_terms = {'personal_info': [], 'education': [], 'experience': []}
            if selected_items:
                for category, items in selected_items.items():
                    for item in items:
                        if item.strip():
                            term_type = PDFRedactor.determine_term_type(item, category)
                            terms = PDFRedactor.generate_smart_search_terms(item, term_type)
                            section_terms[category].extend(terms)
            else:
                personal = resume_data.personal_info
                education = resume_data.education
                experience = resume_data.experience
                if selected_sections.get("personal_info", False):
                    for email in personal.emails:
                        section_terms['personal_info'].extend(PDFRedactor.generate_smart_search_terms(email, "email"))
                    for phone in personal.phone_numbers:
                        section_terms['personal_info'].extend(PDFRedactor.generate_smart_search_terms(phone, "phone"))
                    for name in personal.names:
                        section_terms['personal_info'].extend(PDFRedactor.generate_smart_search_terms(name, "name"))
                    for addr in personal.addresses:
                        section_terms['personal_info'].extend(PDFRedactor.generate_smart_search_terms(addr, "general"))
                    for url in personal.linkedin_urls + personal.github_urls + personal.other_urls:
                        section_terms['personal_info'].extend(PDFRedactor.generate_smart_search_terms(url, "url"))
                    for loc in personal.locations:
                        section_terms['personal_info'].extend(PDFRedactor.generate_smart_search_terms(loc, "general"))
                if selected_sections.get("education", False):
                    for inst in education.institutions:
                        section_terms['education'].extend(PDFRedactor.generate_smart_search_terms(inst, "institution"))
                    for degree in education.degrees:
                        section_terms['education'].extend(PDFRedactor.generate_smart_search_terms(degree, "degree"))
                    for year in education.graduation_years:
                        section_terms['education'].extend(PDFRedactor.generate_smart_search_terms(year, "year"))
                    for gpa in education.gpa_scores:
                        section_terms['education'].extend(PDFRedactor.generate_smart_search_terms(gpa, "general"))
                    for cert in education.certifications:
                        section_terms['education'].extend(PDFRedactor.generate_smart_search_terms(cert, "general"))
                if selected_sections.get("experience", False):
                    for company in experience.companies:
                        section_terms['experience'].extend(PDFRedactor.generate_smart_search_terms(company, "company"))
                    for title in experience.job_titles:
                        section_terms['experience'].extend(PDFRedactor.generate_smart_search_terms(title, "general"))
                    for proj in experience.project_titles:
                        section_terms['experience'].extend(PDFRedactor.generate_smart_search_terms(proj, "project"))
                    for date in experience.employment_dates:
                        section_terms['experience'].extend(PDFRedactor.generate_smart_search_terms(date, "date"))
                    for achievement in experience.achievements:
                        section_terms['experience'].extend(PDFRedactor.generate_smart_search_terms(achievement, "general"))
                    for resp in experience.responsibilities:
                        section_terms['experience'].extend(PDFRedactor.generate_smart_search_terms(resp, "general"))
            for page_num, page in enumerate(doc):
                redaction_rects = []
                for section, terms in section_terms.items():
                    for term in terms:
                        try:
                            matches = page.search_for(term)
                            for rect in matches:
                                if PDFRedactor.validate_match_context(page, rect, term):
                                    redaction_rects.append(rect + (-0.5, -0.5, 0.5, 0.5))
                        except Exception:
                            pass
                merged_regular_rects = PDFRedactor.merge_overlapping_rects(redaction_rects)
                for rect in merged_regular_rects:
                    try:
                        annot = page.add_redact_annot(rect)
                        annot.set_colors(stroke=None, fill=(0, 0, 0))
                        annot.update()
                    except Exception:
                        pass
                if redact_images:
                    try:
                        image_list = page.get_images(full=True)
                        for img in image_list:
                            try:
                                bbox = page.get_image_bbox(img)
                                if bbox and bbox.is_valid:
                                    annot = page.add_redact_annot(bbox)
                                    annot.set_colors(stroke=None, fill=(0, 0, 0))
                                    annot.update()
                            except Exception:
                                pass
                    except Exception:
                        pass
                try:
                    page.apply_redactions()
                except Exception:
                    pass
            try:
                redacted_bytes = doc.write()
                doc.close()
                return redacted_bytes
            except Exception:
                doc.close()
                return pdf_bytes

    st.markdown("## 🔒 Enhanced PDF Resume Redactor")
    st.markdown("**Protect your privacy with intelligent, section-wise redaction**")
    st.markdown("---")

    with st.sidebar:
        st.header("🔧 Configuration")
        api_key_input = st.text_input(
            "OpenAI API Key", 
            value=OPENAI_API_KEY if OPENAI_API_KEY.startswith("sk-") else "",
            type="password"
        )
        if api_key_input:
            OPENAI_API_KEY = api_key_input
        st.markdown("---")
        st.markdown("### 📋 Features:")
        st.markdown("""
        ✅ **Intelligent Matching**  
        ✅ **Section-wise Redaction**  
        ✅ **Individual Item Selection**  
        ✅ **Context-aware Processing**  
        ✅ **Image Redaction**  
        """)

    uploaded_file = st.file_uploader("📄 Upload Resume PDF", type="pdf")

    if uploaded_file and OPENAI_API_KEY:
        if uploaded_file.type != "application/pdf":
            st.error("❌ Please upload a valid PDF file.")
        else:
            redactor = PDFRedactor(OPENAI_API_KEY)
            pdf_bytes = uploaded_file.read()
            with st.spinner("🔍 Extracting text..."):
                resume_text = redactor.extract_text(pdf_bytes)
            if not resume_text.strip():
                st.error("❌ Could not extract text from PDF.")
                st.stop()
            with st.spinner("🤖 Analyzing resume..."):
                resume_data = redactor.detect_resume_info(resume_text)
            with st.spinner("🖼️ Detecting images..."):
                images = redactor.find_images(pdf_bytes)
            col1, col2 = st.columns([3, 4])  # ← This was the missing fix!
            with col1:
                st.subheader("🎯 Select Information to Redact")
                tab1, tab2, tab3 = st.tabs(["👤 Personal", "🎓 Education", "💼 Experience"])
                selected_items = {}
                with tab1:
                    personal_data = resume_data.personal_info.model_dump()
                    selected_personal = []
                    for field, items in personal_data.items():
                        if items:
                            st.write(f"*{field.replace('_', ' ').title()}:*")
                            for idx, item in enumerate(items):
                                if st.checkbox(f"{item}", key=f"personal_{field}_{idx}_{hash(item)}"):
                                    selected_personal.append(item)
                    if selected_personal:
                        selected_items["personal_info"] = selected_personal
                with tab2:
                    education_data = resume_data.education.model_dump()
                    selected_education = []
                    for field, items in education_data.items():
                        if items:
                            st.write(f"*{field.replace('_', ' ').title()}:*")
                            for idx, item in enumerate(items):
                                if st.checkbox(f"{item}", key=f"education_{field}_{idx}_{hash(item)}"):
                                    selected_education.append(item)
                    if selected_education:
                        selected_items["education"] = selected_education
                with tab3:
                    experience_data = resume_data.experience.model_dump()
                    selected_experience = []
                    for field, items in experience_data.items():
                        if items:
                            st.write(f"*{field.replace('_', ' ').title()}:*")
                            for idx, item in enumerate(items):
                                if st.checkbox(f"{item}", key=f"experience_{field}_{idx}_{hash(item)}"):
                                    selected_experience.append(item)
                    if selected_experience:
                        selected_items["experience"] = selected_experience
            with col2:
                st.subheader("🔒 Redaction Options")
                selected_sections = {
                    "personal_info": st.checkbox("Redact Personal Information", value=True),
                    "education": st.checkbox("Redact Education Information", value=True),
                    "experience": st.checkbox("Redact Experience Information", value=True)
                }
                redact_images = st.checkbox("Redact Profile Photos and Images", value=True)
                if st.button("🔴 Redact PDF"):
                    with st.spinner("🛠️ Processing redactions..."):
                        redacted_pdf_bytes = redactor.redact_pdf_section_wise(
                            pdf_bytes,
                            resume_data,
                            selected_sections,
                            redact_images,
                            selected_items
                        )
                    st.success("✅ Redaction complete! Download your redacted PDF below:")
                    st.download_button(
                        "Download Redacted PDF",
                        data=redacted_pdf_bytes,
                        file_name="redacted_resume.pdf",
                        mime="application/pdf"
                    )
