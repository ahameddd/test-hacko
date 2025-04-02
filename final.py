import streamlit as st
import PyPDF2
import pandas as pd
import re
import docx
from io import BytesIO
import json
from datetime import datetime
from difflib import SequenceMatcher

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_requirements" not in st.session_state:
    st.session_state.current_requirements = []
if "clarification_questions" not in st.session_state:
    st.session_state.clarification_questions = []
if "version1_requirements" not in st.session_state:
    st.session_state.version1_requirements = []
if "version2_requirements" not in st.session_state:
    st.session_state.version2_requirements = []

# Function to extract text from different file types
def extract_text(uploaded_file):
    text = ""
    file_type = uploaded_file.name.split(".")[-1].lower()
    
    if file_type == "pdf":
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            st.error(f"Error reading PDF file: {e}")
    
    elif file_type in ["txt", "csv"]:
        text = uploaded_file.read().decode("utf-8")
    
    elif file_type == "docx":
        try:
            doc = docx.Document(uploaded_file)
            text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        except Exception as e:
            st.error(f"Error reading DOCX file: {e}")
    
    else:
        st.error("Unsupported file format. Please upload PDF, DOCX, TXT, or CSV.")
    
    return text

# Function to extract requirements and user stories
def extract_requirements(text):
    requirements = []
    user_stories = []
    capture = False
    
    for line in text.split("\n"):
        line = line.strip()
        
        # Start capturing when we hit Functional/Non-Functional Requirements
        if re.match(r"\d+\.\s*(Functional|Non-Functional) Requirements", line, re.IGNORECASE):
            capture = True
            continue
        
        # Stop capturing when we hit "End of Document" or similar sections
        if re.match(r"\d+\.\s*(Assumptions & Constraints|End of Document)", line, re.IGNORECASE):
            capture = False
            break
        
        if capture and line:
            requirements.append(line)
            if any(kw in line.lower() for kw in ["should", "must", "shall", "require"]):
                user_story = f"As a user, I {line.lower()} so that I can accomplish my goals."
                user_stories.append([user_story])
    
    return "\n".join(requirements), user_stories

# Function to generate clarification questions
def generate_clarification_questions(requirements):
    questions = []
    for req in requirements:
        # Check for ambiguous terms
        if any(term in req.lower() for term in ["should", "may", "can", "could", "might"]):
            questions.append(f"Could you clarify the priority level for: '{req}'?")
        
        # Check for missing details
        if len(req.split()) < 5:
            questions.append(f"Could you provide more details about: '{req}'?")
        
        # Check for technical terms
        if any(term in req.lower() for term in ["system", "interface", "database", "api"]):
            questions.append(f"Could you specify the technical constraints for: '{req}'?")
    
    return questions

# Function to save extracted requirements to a Word document
def save_to_word(requirements_text):
    doc = docx.Document()
    doc.add_heading("Extracted Requirements", level=1)
    doc.add_paragraph(requirements_text)
    
    word_buffer = BytesIO()
    doc.save(word_buffer)
    word_buffer.seek(0)
    return word_buffer

# Function to save user stories to an Excel file
def save_to_excel(user_stories):
    df = pd.DataFrame(user_stories, columns=["User Stories"])
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="User Stories", index=False)
    excel_buffer.seek(0)
    return excel_buffer

# Function to compare requirements
def compare_requirements(req1, req2):
    # Calculate similarity ratio between two requirements
    similarity = SequenceMatcher(None, req1.lower(), req2.lower()).ratio()
    
    # Categorize changes based on similarity
    if similarity > 0.9:
        return "Unchanged", similarity
    elif similarity > 0.7:
        return "Minor Changes", similarity
    elif similarity > 0.3:
        return "Major Changes", similarity
    else:
        return "Completely Different", similarity

# Streamlit UI
st.set_page_config(layout="wide")
st.title("Automated Requirement Extraction with AI Assistant")

# Create tabs for different functionalities
tab1, tab2 = st.tabs(["📄 Single Document Analysis", "🔄 Document Comparison"])

# Tab 1 - Original functionality
with tab1:
    # Create two columns for the main layout
    left_col, right_col = st.columns([1, 1])

    # Left column - File upload and requirements
    with left_col:
        st.subheader("📄 Document Upload")
        uploaded_file = st.file_uploader("Upload a File", type=["pdf", "docx", "txt", "csv"])
        
        if uploaded_file is not None:
            text = extract_text(uploaded_file)
            
            if text.strip():
                requirements_text, user_stories = extract_requirements(text)
                st.session_state.current_requirements = requirements_text.split("\n")
                
                # Display requirements in an expander
                with st.expander("📋 View Extracted Requirements", expanded=True):
                    st.text_area("", requirements_text, height=200)
                
                # Download buttons in a container
                with st.container():
                    st.subheader("📥 Download Options")
                    word_file = save_to_word(requirements_text)
                    excel_file = save_to_excel(user_stories)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button("📄 Download Requirements", word_file, "requirements.docx", 
                                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    with col2:
                        st.download_button("📊 Download User Stories", excel_file, "user_stories.xlsx", 
                                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.warning("No valid text extracted from the uploaded file. Please check the format.")

    # Right column - Chat interface
    with right_col:
        st.subheader("🤖 AI Assistant")
        
        # Chat container with custom styling
        chat_container = st.container()
        with chat_container:
            # Display chat messages
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
            
            # Generate and display clarification questions
            if uploaded_file is not None and text.strip():
                if not st.session_state.clarification_questions:
                    st.session_state.clarification_questions = generate_clarification_questions(st.session_state.current_requirements)
                
                if st.session_state.clarification_questions:
                    with st.expander("💡 Suggested Questions", expanded=True):
                        for question in st.session_state.clarification_questions:
                            if st.button(question):
                                st.session_state.messages.append({"role": "assistant", "content": question})
                                st.rerun()
            
            # Chat input at the bottom
            if prompt := st.chat_input("Ask questions about the requirements"):
                # Add user message to chat history
                st.session_state.messages.append({"role": "user", "content": prompt})
                
                # Generate AI response
                response = f"I understand you're asking about: '{prompt}'. Let me help clarify that requirement."
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # Rerun to update chat display
                st.rerun()

# Tab 2 - Document Comparison
with tab2:
    st.subheader("🔄 Compare Document Versions")
    
    # Create two columns for document uploads
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("Version 1")
        version1_file = st.file_uploader("Upload Version 1", type=["pdf", "docx", "txt", "csv"], key="v1")
    
    with col2:
        st.write("Version 2")
        version2_file = st.file_uploader("Upload Version 2", type=["pdf", "docx", "txt", "csv"], key="v2")
    
    if version1_file is not None and version2_file is not None:
        # Extract text from both versions
        text1 = extract_text(version1_file)
        text2 = extract_text(version2_file)
        
        if text1.strip() and text2.strip():
            # Extract requirements from both versions
            req1_text, _ = extract_requirements(text1)
            req2_text, _ = extract_requirements(text2)
            
            req1_list = req1_text.split("\n")
            req2_list = req2_text.split("\n")
            
            # Store requirements in session state
            st.session_state.version1_requirements = req1_list
            st.session_state.version2_requirements = req2_list
            
            # Display comparison results
            st.subheader("📊 Comparison Results")
            
            # Create tabs for different comparison views
            comp_tab1, comp_tab2 = st.tabs(["Detailed Comparison", "Summary"])
            
            with comp_tab1:
                # Create a DataFrame for comparison
                comparison_data = []
                for req1 in req1_list:
                    best_match = None
                    best_similarity = 0
                    for req2 in req2_list:
                        status, similarity = compare_requirements(req1, req2)
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_match = (req2, status, similarity)
                    
                    if best_match:
                        comparison_data.append({
                            "Version 1": req1,
                            "Version 2": best_match[0],
                            "Status": best_match[1],
                            "Similarity": f"{best_match[2]*100:.1f}%"
                        })
                
                # Display comparison table
                df = pd.DataFrame(comparison_data)
                st.dataframe(df, use_container_width=True)
            
            with comp_tab2:
                # Calculate statistics
                total_reqs = len(req1_list)
                unchanged = sum(1 for req in comparison_data if req["Status"] == "Unchanged")
                minor_changes = sum(1 for req in comparison_data if req["Status"] == "Minor Changes")
                major_changes = sum(1 for req in comparison_data if req["Status"] == "Major Changes")
                completely_different = sum(1 for req in comparison_data if req["Status"] == "Completely Different")
                
                # Display summary statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Unchanged", unchanged)
                with col2:
                    st.metric("Minor Changes", minor_changes)
                with col3:
                    st.metric("Major Changes", major_changes)
                with col4:
                    st.metric("Completely Different", completely_different)
                
                # Display pie chart
                import plotly.express as px
                fig = px.pie(values=[unchanged, minor_changes, major_changes, completely_different],
                           names=["Unchanged", "Minor Changes", "Major Changes", "Completely Different"],
                           title="Requirement Changes Distribution")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Please ensure both documents contain valid text.")
