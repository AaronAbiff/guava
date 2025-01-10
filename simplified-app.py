# app.py
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
import anthropic
import urllib.parse
import re

# Initialize Anthropic client
if 'client' not in st.session_state:
    st.session_state.client = anthropic.Anthropic(api_key=st.secrets["anthropic_api_key"])

# Initialize session states
if 'transcript' not in st.session_state:
    st.session_state.transcript = None
if 'ideas' not in st.session_state:
    st.session_state.ideas = None
if 'selected_idea' not in st.session_state:
    st.session_state.selected_idea = None
if 'current_script' not in st.session_state:
    st.session_state.current_script = None
if 'revision_history' not in st.session_state:
    st.session_state.revision_history = []  # List of (script, feedback) tuples

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    query = urllib.parse.urlparse(url)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in {'www.youtube.com', 'youtube.com'}:
        if query.path == '/watch':
            return urllib.parse.parse_qs(query.query)['v'][0]
    raise ValueError(f"Invalid YouTube URL: {url}")

def get_transcript(video_id):
    """Get transcript for YouTube video"""
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    return ' '.join(entry['text'] for entry in transcript_list)

def generate_ideas(transcript):
    """Generate three ideas based on transcript"""
    response = st.session_state.client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=500,
        temperature=0.7,
        messages=[{
            "role": "user",
            "content": f"Based on this transcript, generate exactly 3 clear, concrete ideas for 60-second videos explaining AI developments. Each idea should start with 'Idea: '.\n\nTranscript:\n{transcript}"
        }]
    )
    ideas = []
    for line in response.content[0].text.split('\n'):
        if line.startswith('Idea:'):
            ideas.append(line[5:].strip())
    return ideas[:3]

def format_history(history):
    """Format revision history for the model"""
    formatted = ""
    for i, (script, feedback) in enumerate(history, 1):
        formatted += f"\nVERSION {i}:\n{script}\nFEEDBACK:\n{feedback}\n---"
    return formatted

def generate_script(transcript, idea, direction, current_script=None):
    """Generate or revise script based on context"""
    history = format_history(st.session_state.revision_history) if st.session_state.revision_history else ""
    
    if current_script and direction:
        prompt = f"Revise this script based on the feedback and revision history:\n{history}\nCURRENT SCRIPT:\n{current_script}\nNEW FEEDBACK:\n{direction}"
    else:
        prompt = f"Create a 60-second video script about this AI development:\n\n{idea}\n\nDirection:\n{direction}\n\nContext:\n{transcript}"
    
    response = st.session_state.client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1000,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Main UI
st.markdown("""
    <style>
        .stApp {
            background-color: #033731;
        }
    </style>
""", unsafe_allow_html=True)
st.title("Guava Writer v0.001")

# URL Input
url = st.text_input("Enter YouTube URL:")
if url and st.button("Ideate ✨"):
    try:
        with st.spinner("Brainstorming 🧠☔️"):
            video_id = extract_video_id(url)
            st.session_state.transcript = get_transcript(video_id)
            st.session_state.ideas = generate_ideas(st.session_state.transcript)
            st.rerun()
    except Exception as e:
        st.error(f"Error: {str(e)}")

# Display ideas and get selection
if st.session_state.ideas:
    st.subheader("One of these?")
    options = [""] + st.session_state.ideas
    selected = st.radio("Choose one idea:", options, index=0)
    if selected:  # Only update if non-empty selection
        st.session_state.selected_idea = selected
    st.session_state.selected_idea = selected

# Get direction and generate script
if st.session_state.selected_idea:
    direction = st.text_area("Enter additional direction:")
    if st.button("Crack On 🚀"):
        with st.spinner("Working on it..."):
            st.session_state.current_script = generate_script(
                st.session_state.transcript,
                st.session_state.selected_idea,
                direction
            )

# Display and iterate on script
if st.session_state.current_script:
    st.subheader("Working Draft")
    st.text_area("Current Script:", st.session_state.current_script, height=400)
    
    new_direction = st.text_area("Enter feedback for script revision:")
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Update Script"):
            with st.spinner("✨ Revising your script..."):
                # Store current version before updating
                st.session_state.revision_history.append((st.session_state.current_script, new_direction))
                revised_script = generate_script(
                    st.session_state.transcript,
                    st.session_state.selected_idea,
                    new_direction,
                    st.session_state.current_script
                )
                st.session_state.current_script = revised_script
                st.rerun()
    with col2:
        if st.button("Approved"):
            st.markdown("""
            ```
           
             _   _ _____ _____ _____    _ 
            | \ | |_   _|  __ \_   __| | |
            |  \| | | | | /  \/ | |__  | |
            | . ` | | | | |     |  __| | |
            | |\  |_| |_| \__/\ |  __  |_|
            \_| \_/\___/\____/  \____/ (_)
                                                    
            ```
            """)