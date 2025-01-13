import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
import anthropic
import urllib.parse
import re
from pathlib import Path
from datetime import datetime

class PersonaManager:
    def __init__(self, persona_file: str = "persona.md"):
        self.persona_file = persona_file
        self.ideation_prompt = ""
        self.dialogue_prompt = ""
        self.load_persona()
    
    def load_persona(self):
        """Load persona configuration from markdown file"""
        try:
            content = Path(self.persona_file).read_text()
            
            # Split content into sections using markdown headers
            sections = re.split(r'^##\s+', content, flags=re.MULTILINE)[1:]
            
            for section in sections:
                if section.startswith('Ideation'):
                    self.ideation_prompt = section.split('\n', 1)[1].strip()
                elif section.startswith('Dialogue'):
                    self.dialogue_prompt = section.split('\n', 1)[1].strip()
        except Exception as e:
            st.error(f"Error loading persona: {str(e)}")
            self.ideation_prompt = "Generate creative ideas"
            self.dialogue_prompt = "Engage in dialogue"

class GuavaWriter:
    def __init__(self, api_key: str):
        # Initialize Anthropic client with minimal configuration
        self.client = anthropic.Anthropic(
            api_key=api_key,
            # Set default timeout
            timeout=60.0,
            # Disable default headers that might conflict with proxy
            default_headers={},
            # Use the default HTTP client
            http_client=None
        )
        
        self.persona = PersonaManager()
        
        # Initialize conversation history
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'current_context' not in st.session_state:
            st.session_state.current_context = {
                'transcript': None,
                'selected_idea': None,
                'current_script': None,
                'revision_history': []
            }
    
    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL"""
        query = urllib.parse.urlparse(url)
        if query.hostname == 'youtu.be':
            return query.path[1:]
        if query.hostname in {'www.youtube.com', 'youtube.com'}:
            if query.path == '/watch':
                return urllib.parse.parse_qs(query.query)['v'][0]
        raise ValueError(f"Invalid YouTube URL: {url}")

    def get_transcript(self, video_id: str) -> str:
        """Get transcript for YouTube video"""
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join(entry['text'] for entry in transcript_list)

    def generate_response(self, prompt: str, context: str = "", model: str = "claude-3-sonnet-20240229") -> str:
        """Generate a response using the persona"""
        full_prompt = f"{self.persona.dialogue_prompt}\n\nContext: {context}\n\nPrompt: {prompt}"
        
        response = self.client.messages.create(
            model=model,
            max_tokens=1000,
            temperature=0.7,
            messages=[{"role": "user", "content": full_prompt}]
        )
        return response.content[0].text

    def generate_ideas(self, transcript: str) -> list:
        """Generate ideas based on transcript using persona"""
        if not transcript or len(transcript.strip()) < 10:
            st.error("Transcript is too short or empty")
            return []
            
        prompt = f"""Having reviewed this transcript, I'll generate three distinct creative directions to explore.

Here's my perspective:
{self.persona.ideation_prompt}

The transcript to analyze:
{transcript}

I'll share three clear ideas, each formatted as:
Idea: [idea here]

Remember to focus on the core concept without restating that it's for a 60-second video."""
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            ideas = []
            current_idea = None
            
            for line in response.content[0].text.split('\n'):
                if line.strip().startswith('Idea') and ':' in line:
                    if current_idea:
                        ideas.append(current_idea)
                    current_idea = line.split(':', 1)[1].strip()
                elif current_idea and line.strip():
                    current_idea += " " + line.strip()
            
            if current_idea:
                ideas.append(current_idea)
            
            return ideas[:3]
            
        except Exception as e:
            st.error(f"Error in idea generation: {str(e)}")
            return []

    def generate_script(self, transcript: str, idea: str, direction: str, current_script: str = None) -> str:
        """Generate or revise script based on context"""
        base_prompt = f"""As Clio Maar, I am creating a 60-second intimate video essay about this AI development:
{idea}

My identity from persona.md:
{self.persona.dialogue_prompt}

Guidelines:
- Speak directly and intimately, as if to a cherished colleague
- Transform technical developments into artistic possibilities
- Keep focus on how this serves creative tradition
- Address any artistic anxieties with understanding
- Maintain my gentle New York State cadence

Format the script with timestamps and clear visual directions. For visuals, use:
- SR: for screen recordings
- Gen: for generative video
- StA: for stock assets

Remember: I'm sharing this development through my lens as an artist speaking to artists."""

        if current_script and direction:
            prompt = f"{base_prompt}\n\nCurrent script:\n{current_script}\n\nDirection for revision:\n{direction}"
        else:
            prompt = f"{base_prompt}\n\nContext from source:\n{transcript}\n\nDirection:\n{direction}"
        
        response = self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text

    def format_revision_history(self) -> str:
        """Format revision history for the model"""
        history = st.session_state.current_context['revision_history']
        formatted = ""
        for i, (script, feedback) in enumerate(history, 1):
            formatted += f"\nVERSION {i}:\n{script}\nFEEDBACK:\n{feedback}\n---"
        return formatted

    def add_message(self, role: str, content: str):
        """Add a message to the conversation history"""
        st.session_state.messages.append({"role": role, "content": content})

def main():
    st.markdown("""
        <style>
            .stApp {
                background-color: #033731;
            }
            .chat-message {
                padding: 1rem;
                border-radius: 0.5rem;
                margin-bottom: 1rem;
            }
            .user-message {
                background-color: #1a1a1a;
            }
            .assistant-message {
                background-color: #0a4740;
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("GuavaWriter v0.002")
    
    # Initialize GuavaWriter
    writer = GuavaWriter(st.secrets["anthropic_api_key"])
    
    # Chat interface
    for message in st.session_state.messages:
        div_class = "user-message" if message["role"] == "user" else "assistant-message"
        st.markdown(f"""<div class="chat-message {div_class}">
            {message["content"]}
        </div>""", unsafe_allow_html=True)
    
    # Input components
    url = st.text_input("Enter YouTube URL:")
    if url and st.button("Ideate 🪄"):
        try:
            with st.spinner("Brainstorming... 🧠☔️"):
                video_id = writer.extract_video_id(url)
                transcript = writer.get_transcript(video_id)
                st.session_state.current_context['transcript'] = transcript
                
                ideas = writer.generate_ideas(transcript)
                
                if not ideas:
                    st.error("No ideas were generated. Please try again.")
                    return
                    
                response = "I've been thinking about this piece, and I see three possibilities for a 60-second exploration:\n\n"
                for i, idea in enumerate(ideas, 1):
                    response += f"{i}. {idea}\n"
                response += "\nWhich direction speaks to you?"
                
                writer.add_message("assistant", response)
                st.rerun()
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    # Handle idea selection
    if st.session_state.current_context['transcript'] and not st.session_state.current_context['selected_idea']:
        idea_input = st.text_input("Select an idea (1-3):")
        if idea_input and idea_input.isdigit() and 1 <= int(idea_input) <= 3:
            ideas = writer.generate_ideas(st.session_state.current_context['transcript'])
            selected_idea = ideas[int(idea_input)-1]
            st.session_state.current_context['selected_idea'] = selected_idea
            
            writer.add_message("user", f"Let's go with idea {idea_input}")
            writer.add_message("assistant", f"Great choice! What direction would you like to take with this idea?")
            st.rerun()
    
    # Handle script generation and revision
    if st.session_state.current_context['selected_idea']:
        direction = st.text_area("Enter your thoughts or feedback:")
        col1, col2 = st.columns([1,1])
        
        with col1:
            if st.button("Generate/Update Script 🚀"):
                with st.spinner("Working on it... 🐝"):
                    try:
                        current_script = st.session_state.current_context['current_script']
                        if current_script:
                            st.session_state.current_context['revision_history'].append((current_script, direction))
                        
                        new_script = writer.generate_script(
                            st.session_state.current_context['transcript'],
                            st.session_state.current_context['selected_idea'],
                            direction,
                            current_script
                        )
                        
                        st.session_state.current_context['current_script'] = new_script
                        writer.add_message("assistant", f"Here's the {'revised' if current_script else 'new'} script:\n\n{new_script}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error in script generation: {str(e)}")
        
        if st.session_state.current_context['current_script']:
            with col2:
                if st.button("Approve ✅"):
                    st.markdown("""
                    ```
                   
                     _   _ _____ _____ _____    _ 
                    | \ | |_   _|  __ \_   _| | |
                    |  \| | | | | /  \/ | |  | |
                    | . ` | | | | |     | |  | |
                    | |\  |_| |_| \__/\ | |  |_|
                    \_| \_/\___/\____/  \_/  (_)
                                                    
                    ```
                    """)
                    
                    # Add download button after approval
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"script_{timestamp}.txt"
                    
                    st.download_button(
                        label="Download Approved Script 📥",
                        data=st.session_state.current_context['current_script'],
                        file_name=filename,
                        mime="text/plain"
                    )

if __name__ == "__main__":
    main()
