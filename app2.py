# app.py
import streamlit as st
import fitz  # PyMuPDF
import openai
import json
import os
import re
from fpdf import FPDF
from io import BytesIO

# ────────────────────────────────────────────────────────────────────────────────
# 1) OPENAI API KEY
# ────────────────────────────────────────────────────────────────────────────────
# Make sure you've set OPENAI_API_KEY in your Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]


# ────────────────────────────────────────────────────────────────────────────────
# 2) GLOBAL CSS INJECTION (Gemini Dark Theme + Hide Streamlit Chrome)
# ────────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAIN-CHECK",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    /* Hide default Streamlit header, footer, and menu */
    header, footer, #MainMenu { visibility: hidden; }

    /* Overall page background */
    .css-1lcbmhc.e1fqkh3o2 { background-color: #202124; }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
      background-color: #202124;
      color: #E8EAED;
    }
    .stSidebar .css-1d391kg:hover {
      background-color: #303134;
    }

    /* Main content background and text */
    .main .block-container {
      background-color: #202124;
      color: #E8EAED;
      padding-top: 2rem;
    }

    /* Greeting styles */
    .greeting {
      text-align: center;
      font-size: 3rem;
      margin-bottom: 2rem;
    }
    .greeting .blue { color: #8AB4F8; }
    .greeting .red  { color: #F28B82; }

    /* File uploader centering override */
    .css-1r6slb0.e1fqkh3o3 { justify-content: center; }

    /* Hide default text_input label */
    .stTextInput>label { display: none; }

    /* Style the bottom input bar */
    .input-bar {
      position: fixed;
      bottom: 16px;
      left: 240px;   /* match sidebar width */
      right: 16px;
      background-color: #303134;
      border-radius: 32px;
      padding: 8px 16px;
      display: flex;
      align-items: center;
      z-index: 999;
    }
    .input-bar .icon-btn {
      background: none;
      border: none;
      color: #E8EAED;
      font-size: 1.25rem;
      margin: 0 12px;
      cursor: pointer;
    }

    /* Style the text_input inside the input-bar */
    .input-bar .css-174j9nr.e1fqkh3o6>div>div>input {
      background-color: #303134 !important;
      color: #E8EAED !important;
      border: none !important;
      border-radius: 24px !important;
      height: 48px !important;
      padding: 0 1rem !important;
      font-size: 1rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ────────────────────────────────────────────────────────────────────────────────
# 3) FUNCTIONS
#    - PDF text extraction
#    - OpenAI call
#    - Batch analyses
#    - Markdown cleanup
#    - PDF report creation
# ────────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_file):
    """
    Read an uploaded PDF (as a stream) and extract all text.
    """
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    all_text = []
    for page in doc:
        all_text.append(page.get_text())
    return "\n".join(all_text)


def call_openai(prompt: str,
                model: str = "gpt-4o-mini",
                temperature: float = 0.7,
                max_tokens: int = 1000) -> str:
    """
    Call the OpenAI Chat Completions API.
    """
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI chatbot automating script improvements and "
                    "providing data-driven insights (casting, budget, scheduling, marketing) "
                    "to film producers."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content


def get_all_analyses(screenplay_text: str) -> dict:
    """
    Run a suite of analyses on the screenplay text and return a dict of results.
    """
    prompts = {
        "Logline": f"""Write a Hollywood-style logline for my screenplay. It should only contain the logline, making it engaging and high-concept.

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Genre": f"""Suggest the genre for the provided screenplay. By genre, we mean a particular type or style of literature, art, film, or music recognizable by its special characteristics.

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Top Keywords": f"""Give the top 10 keywords of the attached movie screenplay without any explanation.

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Location Setting": f"""Give the location setting of the attached movie screenplay, considering only the primary location.

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Synopsis": f"""Give only the synopsis of the attached screenplay.

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Script Score": f"""Analyze the attached screenplay and give it a script score out of 10, including:
- Character development score (out of 10) with 1-2 lines explanation
- Plot construction (out of 10) with 1-2 lines explanation
- Dialogue (out of 10) with 1-2 lines explanation
- Originality (out of 10) with 1-2 lines explanation
- Emotional engagement (out of 10) with 1-2 lines explanation
- Theme and message (out of 10) with 1-2 lines explanation
- Overall rating out of 10 with explanation

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Plot Assessment": f"""Analyze the attached screenplay and give the plot assessment and enhancement, including:
- 5 points of what is working well (positive aspects)
- 5 points where the screenplay lacks
- 5 points of improvements that may be made
- An overall review of the screenplay

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Character Profiling": f"""Analyze the attached screenplay and return character profiling for the main characters, including:
- Brief description of each main character
- What is working well for each character
- Areas for improvement
- The archetype for each

Screenplay:
\"\"\"{screenplay_text}\"\"\"
""",

        "Box Office Collection": f"""Analyze the attached screenplay and give its box office prediction with the following fields:
- Opening day (global and local)
- Opening week (global and local)
- Opening month (global and local)

Screenplay:
\"\"\"{screenplay_text}\"\"\"
"""
    }

    results = {}
    for section, prompt in prompts.items():
        # Use shorter token limit for small answers
        limit = 200 if section in ["Genre", "Top Keywords", "Location Setting"] else 700
        results[section] = call_openai(prompt, max_tokens=limit)

    return results


def clean_markdown(text: str) -> str:
    """
    Strip out common Markdown syntax for a cleaner PDF layout.
    """
    text = re.sub(r"(\*\*|__)", "", text)           # bold
    text = re.sub(r"(#+\s*)", "", text)             # headings
    text = re.sub(r"`", "", text)                   # inline code
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links
    text = re.sub(r"\n{3,}", "\n\n", text)           # excessive newlines
    return text.strip()


def create_pdf_report(data: dict) -> BytesIO:
    """
    Generate a PDF report from the analysis dict and return a BytesIO buffer.
    """
    pdf = FPDF()
    pdf.add_page()

    # Load fonts (make sure these .ttf files are in your working directory)
    font_regular = "DejaVuSans.ttf"
    font_bold = "DejaVuSans-Bold.ttf"
    if not os.path.isfile(font_regular) or not os.path.isfile(font_bold):
        raise FileNotFoundError("DejaVu font files not found in working directory.")

    pdf.add_font("DejaVu", "", font_regular, uni=True)
    pdf.add_font("DejaVu", "B", font_bold, uni=True)

    # Title
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Screenplay Analysis Report", ln=True, align="C")
    pdf.ln(10)

    # Sections
    for section, content in data.items():
        pdf.set_font("DejaVu", "B", 14)
        pdf.cell(0, 10, section, ln=True)
        pdf.ln(2)

        pdf.set_font("DejaVu", "", 12)
        cleaned = clean_markdown(content)
        pdf.multi_cell(0, 8, cleaned)
        pdf.ln(8)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer


# ────────────────────────────────────────────────────────────────────────────────
# 4) SIDEBAR NAV (Gemini Style)
# ────────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:#E8EAED;margin-bottom:0'>Gemini</h2>", unsafe_allow_html=True)
    st.selectbox("", ["2.0 Flash", "2.0 Advanced"], key="model_select", label_visibility="collapsed")
    st.markdown("---")
    st.button("➕  New chat", key="new_chat")
    st.button("💎  Explore Gems", key="explore_gems")
    st.markdown("**Recent**")
    for item in [
        "Optics Lecture Notes Break…",
        "Enhance Deep Learning De…",
        "Improving Project Assistant…",
        "Create Google Sheet CGPA…",
        "Single Period Inquiry"
    ]:
        st.markdown(f"- {item}")
    st.markdown("---")
    st.markdown("⚙️  Settings & help")


# ────────────────────────────────────────────────────────────────────────────────
# 5) MAIN CONTENT AREA
# ────────────────────────────────────────────────────────────────────────────────

# 5.1 Greeting
user_name = "Ansh"
st.markdown(
    f"<div class='greeting'><span class='blue'>Hello, </span>"
    f"<span class='red'>{user_name}</span></div>",
    unsafe_allow_html=True
)

# 5.2 File uploader (PDF screenplay)
uploaded_file = st.file_uploader("Upload a movie screenplay (PDF)", type=["pdf"])
movie_name = None

if uploaded_file:
    movie_name = os.path.splitext(uploaded_file.name)[0]

    if "screenplay_text" not in st.session_state:
        with st.spinner("Extracting screenplay…"):
            text = extract_text_from_pdf(uploaded_file)
            st.session_state["screenplay_text"] = text
        st.success("✅ Screenplay extracted and ready!")

    # 5.3 Generate analysis report
    if st.button("Generate Report"):
        with st.spinner("Analyzing screenplay (this may take a while)…"):
            analyses = get_all_analyses(st.session_state["screenplay_text"])
        pdf_buf = create_pdf_report(analyses)
        st.success("📝 Analysis complete!")

        st.download_button(
            label="📄 Download Analysis Report as PDF",
            data=pdf_buf,
            file_name=f"{movie_name}-report.pdf",
            mime="application/pdf"
        )
else:
    st.info("Please upload a PDF screenplay to get started.")


# ────────────────────────────────────────────────────────────────────────────────
# 6) FIXED BOTTOM INPUT BAR
# ────────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="input-bar">
      <button class="icon-btn">＋</button>
      <div style="flex:1"></div>
      <button class="icon-btn">🧐</button>
      <button class="icon-btn">🖼️</button>
      <button class="icon-btn">🎤</button>
    </div>
    """,
    unsafe_allow_html=True,
)

# The actual text input — styled via our CSS above
query = st.text_input("Ask Gemini…", key="gemini_query")

# (Optionally, you can now hook `query` into your analysis pipeline or chat loop.)
