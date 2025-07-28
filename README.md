# Resume Redactor 🔒

An AI-powered Streamlit application to intelligently find and redact sensitive information from PDF resumes, giving you full control over your privacy.

---

## ✨ Features

-   **AI-Powered PII Detection**: Uses OpenAI (GPT-4o-mini) to automatically identify names, emails, phone numbers, addresses, URLs, company names, and educational institutions.
-   **Interactive & Granular Control**: A user-friendly interface to review all detected information and select specific items for redaction.
-   **Smart Text Matching**: Goes beyond simple string matching by generating and searching for multiple variations of a term (e.g., different capitalizations, formats, and abbreviations) to ensure comprehensive redaction.
-   **Image Redaction**: Option to automatically find and black out embedded images like profile photos.
-   **Section-Wise Redaction**: Organize redaction choices by "Personal," "Education," and "Experience" categories.
-   **Secure & Validated Data**: Utilizes Pydantic models to structure and validate the data extracted by the AI, ensuring robust processing.
-   **Instant Download**: Get your anonymized, secure PDF with a single click.

---

## 🔧 Tech Stack

-   **Frontend**: Streamlit
-   **Backend**: Python
-   **AI Engine**: OpenAI (GPT-4o-mini)
-   **PDF Processing**: PyMuPDF (`fitz`)
-   **Data Validation**: Pydantic
-   **Configuration**: `python-dotenv`

---

## ⚙️ Setup and Installation

Follow these steps to set up and run the project on your local machine.

### 1. Clone the Repository

```bash
git clone https://github.com/Johnwick-400/Resume-Redactor
cd Resume-redactor
