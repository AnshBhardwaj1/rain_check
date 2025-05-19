import streamlit as st
import fitz  # pymupdf
import openai
import json

# Set your OpenAI API key from Streamlit secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Function to extract text from uploaded PDF
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# Function to call OpenAI API with a prompt
# Updated for openai>=1.0.0

def call_openai(prompt, model="gpt-4o-mini", temperature=0.7, max_tokens=1000):
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an AI chatbot automating script improvements and providing data-driven insights (casting, budget, scheduling, marketing) to film producers."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content

# Function to run all analyses
def get_all_analyses(screenplay_text):
    results = {}

    # Each prompt uses your exact detailed instructions
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

    "Box Office Collection": f"""Analyze the attached screenplay and give its box office prediction  with the following fields:
- Opening day (global and local)
- Opening week (global and local)
- Opening month (global and local)

Screenplay:
\"\"\"{screenplay_text}\"\"\"
"""
}



    for key, prompt in prompts.items():
        results[key] = call_openai(prompt, max_tokens=700 if key not in ["Top Keywords", "Location Setting", "Genre"] else 200)

    return results

# PDF generation function
from fpdf import FPDF
from io import BytesIO
import os

def clean_markdown(text):
    # Remove common Markdown characters
    text = re.sub(r"(\*\*|__)", "", text)         # bold
    text = re.sub(r"(#+\s*)", "", text)           # headings like #, ##, ###
    text = re.sub(r"`", "", text)                 # inline code
    text = re.sub(r"\n{3,}", "\n\n", text)        # excessive line breaks
    return text.strip()

def create_pdf_report(data):
    pdf = FPDF()
    pdf.add_page()

    font_regular = "DejaVuSans.ttf"
    font_bold = "DejaVuSans-Bold.ttf"

    if not os.path.isfile(font_regular) or not os.path.isfile(font_bold):
        raise FileNotFoundError("Font files not found.")

    pdf.add_font("DejaVu", "", font_regular, uni=True)
    pdf.add_font("DejaVu", "B", font_bold, uni=True)

    pdf.set_font("DejaVu", 'B', 16)
    pdf.cell(0, 10, "Screenplay Analysis Report", ln=True, align="C")
    pdf.ln(10)

    for section, content in data.items():
        pdf.set_font("DejaVu", 'B', 14)
        pdf.cell(0, 10, section, ln=True)
        pdf.ln(2)

        pdf.set_font("DejaVu", '', 12)
        cleaned_content = clean_markdown(content)
        pdf.multi_cell(0, 8, cleaned_content)

        pdf.ln(10)

    # Save to BytesIO
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer
import re






# Streamlit UI
st.set_page_config(page_title="RAIN-CHECK")
st.title("🎬 RAIN-CHECK")
import os
uploaded_file = st.file_uploader("Upload a movie screenplay (PDF)", type=["pdf"])
if uploaded_file is not None:
    movie_name = os.path.splitext(uploaded_file.name)[0]
if uploaded_file is not None:
    if "screenplay_text" not in st.session_state:
        with st.spinner("Extracting screenplay..."):
            st.session_state["screenplay_text"] = extract_text_from_pdf(uploaded_file)
        st.success("✅ Screenplay extracted and ready!")

    if st.button("Generate Report"):
        with st.spinner("Analyzing screenplay (this may take a while)..."):
            all_results = get_all_analyses(st.session_state["screenplay_text"])

        # Generate PDF report
        pdf_file = create_pdf_report(all_results)

        st.success("Analysis complete!")
        st.download_button(
            label="📄 Download Analysis Report as PDF",
            data=pdf_file,
            file_name=f"{movie_name}-report.pdf",
            mime="application/pdf"
        )
else:
    st.info("Please upload a PDF screenplay to get started.")
