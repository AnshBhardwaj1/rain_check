import streamlit as st
import fitz  # pymupdf
import openai
import os
from fpdf import FPDF
from io import BytesIO
import re

# ─── 1) Page Configuration ────────────────────────────────────────────────
st.set_page_config(page_title="RAIN-CHECK")

# ─── 2) Initialize session state ──────────────────────────────────────────
if "current_movie" not in st.session_state:
    st.session_state["current_movie"] = None
if "history" not in st.session_state:
    st.session_state["history"] = {}  # maps movie_name -> analysis dict

# ─── 3) Set your OpenAI API key from Streamlit secrets ─────────────────────
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ─── 4) Extract text from uploaded PDF ─────────────────────────────────────
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# ─── 5) Call OpenAI for a single prompt ────────────────────────────────────
def call_openai_single(prompt: str, model="gpt-4o-mini", temperature=0.7, max_tokens=1500):
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI chatbot automating script improvements and providing "
                    "data-driven insights (casting, budget, scheduling, marketing) to film producers."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content

# ─── 6) Markdown-cleaning helper ───────────────────────────────────────────
def clean_markdown(text):
    text = re.sub(r"(\*\*|__)", "", text)
    text = re.sub(r"(#+\s*)", "", text)
    text = re.sub(r"`", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ─── 7) Generate PDF report ────────────────────────────────────────────────
def create_pdf_report(data: dict) -> BytesIO:
    pdf = FPDF()
    pdf.add_page()

    font_regular = "DejaVuSans.ttf"
    font_bold = "DejaVuSans-Bold.ttf"

    if not os.path.isfile(font_regular) or not os.path.isfile(font_bold):
        raise FileNotFoundError("Font files not found. Make sure DejaVu fonts are in the app folder.")

    pdf.add_font("DejaVu", "", font_regular, uni=True)
    pdf.add_font("DejaVu", "B", font_bold, uni=True)

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Screenplay Analysis Report", ln=True, align="C")
    pdf.ln(10)

    for section, content in data.items():
        pdf.set_font("DejaVu", "B", 14)
        pdf.cell(0, 10, section, ln=True)
        pdf.ln(2)

        pdf.set_font("DejaVu", "", 12)
        cleaned_content = clean_markdown(content)
        pdf.multi_cell(0, 8, cleaned_content)
        pdf.ln(10)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

# ─── 8) Generate all analyses ──────────────────────────────────────────────
def get_all_analyses_single(screenplay_text: str) -> dict:
    prompts = {
        "Logline": f"""Write a Hollywood-style logline for my screenplay.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Genre": f"""Suggest the genre for the provided screenplay.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Top Keywords": f"""Give the top 10 keywords of the attached movie screenplay without any explanation.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Location Setting": f"""Give the location setting of the attached movie screenplay.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Synopsis": f"""Give only the synopsis of the attached screenplay.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Script Score": f"""Analyze the screenplay and give it a script score out of 10, including multiple components.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Plot Assessment": f"""Analyze the screenplay and give the plot assessment and enhancements.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Character Profiling": f"""Analyze the screenplay and return character profiling for the main characters.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
        "Box Office Collection": f"""Analyze the screenplay and give its box office prediction.\n\nScreenplay:\n\"\"\"{screenplay_text}\"\"\"""",
    }

    results = {}
    for section_name, prompt_text in prompts.items():
        ai_response = call_openai_single(prompt_text, max_tokens=1200)
        results[section_name] = ai_response

    return results

# ─── 9) App UI Styling ─────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        .reportview-container .main { padding: 2rem; }
        .stButton>button, .stDownloadButton>button {
            background-color: #4CAF50;
            color: white;
            font-size: 1.05rem;
            border-radius: 8px;
            padding: 0.5rem 1.2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── 10) Title and History Section ─────────────────────────────────────────
st.markdown("<h1>🎬 RAIN-CHECK: Script Analyzer</h1>", unsafe_allow_html=True)
st.markdown("Upload your screenplay and get detailed insights instantly.")
st.divider()

with st.expander("🕓 View Past Analyses"):
    if st.session_state["history"]:
        selected = st.selectbox(
            "Select a previous screenplay to view results:",
            options=list(st.session_state["history"].keys())
        )
        if selected:
            past_result = st.session_state["history"][selected]
            st.markdown(f"<h3>📜 Analysis for: {selected}</h3>", unsafe_allow_html=True)
            for section, content in past_result.items():
                st.markdown(f"<h4>{section}</h4>", unsafe_allow_html=True)
                st.markdown(f"<div style='margin-bottom: 1rem;'>{clean_markdown(content)}</div>", unsafe_allow_html=True)
    else:
        st.info("No past analyses found in this session.")

# ─── 11) File Upload and New Analysis ──────────────────────────────────────
uploaded_file = st.file_uploader("📄 Upload your movie screenplay (PDF only)", type=["pdf"])

if uploaded_file is not None:
    movie_name = os.path.splitext(uploaded_file.name)[0]

    if "screenplay_text" not in st.session_state or st.session_state["current_movie"] != movie_name:
        with st.spinner("📃 Extracting screenplay..."):
            st.session_state["screenplay_text"] = extract_text_from_pdf(uploaded_file)
        st.session_state["current_movie"] = movie_name
        st.success("✅ Screenplay extracted and ready!")

    if st.button("🚀 Generate Full Analysis"):
        with st.spinner("🤖 Analyzing screenplay…"):
            all_results = get_all_analyses_single(st.session_state["screenplay_text"])

        if all_results:
            st.success("✅ Analysis complete!")
            st.session_state["history"][movie_name] = all_results  # Save to history

            for section, content in all_results.items():
                st.markdown(f"<h3>{section}</h3>", unsafe_allow_html=True)
                st.markdown(f"<div style='margin-bottom: 1.5rem;'>{clean_markdown(content)}</div>", unsafe_allow_html=True)

            pdf_file = create_pdf_report(all_results)
            st.download_button(
                label="📥 Download Report as PDF",
                data=pdf_file,
                file_name=f"{movie_name}-report.pdf",
                mime="application/pdf"
            )
else:
    st.info("📌 Upload a PDF to begin screenplay analysis.")
