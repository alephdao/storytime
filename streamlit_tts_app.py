import streamlit as st
import boto3
import os
from dotenv import load_dotenv
from pydub import AudioSegment
import botocore
import re
import tempfile
from openai import OpenAI
import math
import sqlite3
import hashlib

# Load environment variables
load_dotenv()

# Initialize Polly client
polly = boto3.client('polly',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Database functions
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_password = hash_password(password)
    try:
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        return result[0] == hash_password(password)
    return False

# Existing functions
def remove_markdown(text):
    text = re.sub(r'^\s*#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    return text.strip()

def split_into_chunks(text, max_chars=3000):
    chunks = []
    current_chunk = ""
    
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += sentence + " "
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def get_voice_details(voice_id):
    response = polly.describe_voices()
    for voice in response['Voices']:
        if voice['Id'] == voice_id:
            return voice
    return None

def select_engine_and_language(voice_id):
    voice_details = get_voice_details(voice_id)
    if voice_details:
        supported_engines = voice_details['SupportedEngines']
        if 'neural' in supported_engines:
            return 'neural', voice_details['LanguageCode']
        else:
            return 'standard', voice_details['LanguageCode']
    return 'standard', 'en-US'  # default fallback

def synthesize_speech(text, output_filename, voice_id):
    engine, language_code = select_engine_and_language(voice_id)
    
    response = polly.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId=voice_id,
        Engine=engine,
        LanguageCode=language_code
    )
    
    with open(output_filename, 'wb') as file:
        file.write(response['AudioStream'].read())

def process_file(file_content, output_dir, voice_id, file_extension):
    os.makedirs(output_dir, exist_ok=True)
    
    if file_extension.lower() == '.md':
        text = remove_markdown(file_content)
    else:
        text = file_content

    text = text[:10000]
    chunks = split_into_chunks(text)

    chunk_files = []
    for i, chunk in enumerate(chunks):
        chunk_filename = os.path.join(output_dir, f"chunk_{i}.mp3")
        synthesize_speech(chunk, chunk_filename, voice_id)
        chunk_files.append(chunk_filename)

    combined = AudioSegment.empty()
    for chunk_file in chunk_files:
        chunk_audio = AudioSegment.from_mp3(chunk_file)
        combined += chunk_audio

    output_filename = os.path.join(output_dir, 'output.mp3')
    combined.export(output_filename, format="mp3")

    for chunk_file in chunk_files:
        os.remove(chunk_file)

    return output_filename

def get_available_voices():
    try:
        response = polly.describe_voices()
        voices = response['Voices']
        english_voices = [
            voice for voice in voices
            if voice['LanguageCode'].startswith('en-') and 'en-IN' not in voice['LanguageCode']
        ]
        
        def get_country(language_code):
            country_map = {
                'en-US': 'US',
                'en-GB': 'England',
                'en-AU': 'Australia',
                'en-NZ': 'New Zealand',
                'en-ZA': 'South Africa',
                'en-IE': 'Ireland',
                'en-GB-WLS': 'Wales'
            }
            return country_map.get(language_code, language_code)
        
        return {f"{voice['Name']} - {get_country(voice['LanguageCode'])}": voice['Id'] for voice in english_voices}
    except botocore.exceptions.ClientError as error:
        st.error(f"An error occurred while fetching voices: {error}")
        return {}

def generate_test_audio(text, voice_id):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
        synthesize_speech(text, temp_file.name, voice_id)
        with open(temp_file.name, "rb") as file:
            audio_bytes = file.read()
    os.unlink(temp_file.name)
    return audio_bytes

def generate_summary_chunk(book_title, reading_difficulty, total_char_count, chunk_number, total_chunks, previous_chunk=""):
    chunk_char_count = math.ceil(total_char_count / total_chunks)
    start_percentage = (chunk_number - 1) / total_chunks * 100
    end_percentage = chunk_number / total_chunks * 100

    prompt = f"""Create a part of an abridged version of {book_title} (which was published pre 1924 and is in the public domain). 
    This abridgement should:
    1. Maintain the original voice, style, and narrative perspective of the book.
    2. Be suitable for a {reading_difficulty}-year-old listener, but use vocabulary appropriate for a {reading_difficulty}-year-old reading level.
    3. Cover approximately from {start_percentage:.0f}% to {end_percentage:.0f}% of the book's content.
    4. Be about {chunk_char_count} characters long (the entire abridged version will be approximately {total_char_count} characters).

    Guidelines:
    - Do not summarize or change the narrative voice. Instead, shorten the original text by removing less critical passages while keeping key scenes and dialogue.
    - Preserve important quotes and memorable lines from the original text whenever possible.
    - Maintain the author's writing style, including any distinctive narrative techniques or language patterns.
    - Focus on the main plot points and key character developments, but present them as the author would.
    - Use simple sentence structures when needed to engage young listeners, but don't oversimplify to the point of losing the book's essence.
    - Ensure this part can smoothly connect with the previous and next parts of the abridged version.
    - Do not add any explanations or commentary that aren't in the original text.
    {"" if chunk_number == 1 else f"Previous chunk (for context, do not repeat):\n{previous_chunk}\n\nContinue the story from where this left off, ensuring smooth flow:"}
    {"" if chunk_number != total_chunks else "This is the final chunk. Ensure that the story reaches a satisfying conclusion, covering all major plot points and character arcs."}

    {"If this is the first chunk, begin the story immediately after the title. Do not repeat the title in the text." if chunk_number == 1 else ""}

    Begin the abridged text for this section now:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a skilled writer specializing in children's literature adaptations."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )

    return response.choices[0].message.content.strip()

def generate_full_summary(book_title, reading_difficulty, char_count):
    chunks = []
    total_chunks = math.ceil(char_count / 3000)
    overlap = 500

    previous_chunk = ""
    for i in range(1, total_chunks + 1):
        chunk = generate_summary_chunk(book_title, reading_difficulty, char_count, i, total_chunks, previous_chunk[-overlap:])
        chunks.append(chunk)
        previous_chunk = chunk

    generated_content = " ".join(chunks)
    full_summary = f"{book_title}\n\n{generated_content}"

    return full_summary

# Initialize database
init_db()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Streamlit app
st.set_page_config(page_title="Story Time Magic", page_icon="🎵")

# Define custom CSS
st.markdown("""
<style>
    body {
        background: linear-gradient(120deg, #FFD1DC, #87CEFA);
        background-image: url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M11 18l-5-5 5-5 5 5-5 5zm60 60l-5-5 5-5 5 5-5 5zM59 78l-5-5 5-5 5 5-5 5zM82 30l-5-5 5-5 5 5-5 5z' fill='%23ffffff' fill-opacity='0.2'/%3E%3C/svg%3E");
    }
    body, .stButton button, .stSelectbox, .stTextInput>div>div>input {
        font-family: 'Comic Sans MS', cursive, sans-serif;
    }
    .stButton button, .stFileUploader>div>button, .stDownloadButton>button {
        background-color: #1E90FF;
        color: #FFFFFF;
        border: 2px solid #808080;
        border-radius: 20px;
        padding: 10px 20px;
        transition: all 0.3s;
    }
    .stButton button:hover, .stFileUploader>div>button:hover, .stDownloadButton>button:hover {
        transform: scale(1.1);
        background-color: #4169E1;
    }
    .custom-title {
        font-size: 3em;
        color: #1E90FF;
        text-shadow: 2px 2px #FFD700;
        text-align: center;
        margin-bottom: 30px;
    }
    .stSelectbox>div>div {
        background-color: #F0F0F0;
        border: 2px solid #1E90FF;
        border-radius: 15px;
        color: #333333;
    }
    .stTextInput>div>div>input {
        background-color: #F0F0F0;
        border: 2px solid #1E90FF;
        border-radius: 15px;
        color: #333333;
    }
    .stFileUploader>div>button {
        background-color: #98FB98;
        color: #1E90FF;
        border: 2px dashed #FF69B4;
        border-radius: 15px;
    }
    .stAudio>div {
        background-color: #FFD700;
        border-radius: 15px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Custom title
st.markdown("<h1 class='custom-title'>🎵 Story Time Magic: Turn Any Story Into An Audiobook! 🌈</h1>", unsafe_allow_html=True)

# Authentication
if not st.session_state.logged_in:
    st.markdown("### 👤 Login or Register")
    auth_option = st.radio("Choose an option:", ["Login", "Register"])

    if auth_option == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    elif auth_option == "Register":
        new_username = st.text_input("Choose a username")
        new_password = st.text_input("Choose a password", type="password")
        if st.button("Register"):
            if register_user(new_username, new_password):
                st.success("Registration successful! Please login.")
            else:
                st.error("Username already exists")

else:
    st.markdown(f"### Welcome, {st.session_state.username}! 👋")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()

    # Story Generation Inputs
    st.markdown("### 📚 Let's Pick The Story!")
    book_title = st.text_input("What's the title and author of the story?", value="The Dragon and the Raven by GA Henty")
    reading_difficulty = st.slider("What reading level should we aim for? (in years)", 5, 15, 8)
    char_count = st.slider("How long should your story be? (in characters)", 400, 10000, 1000)

    # Language and voice selection
    st.markdown("### 🎭 Pick Your Storyteller's Voice")
    voices = get_available_voices()
    default_voice = next((key for key, value in voices.items() if value == 'Brian'), list(voices.keys())[0])
    selected_voice = st.selectbox("Who should tell your story?", 
                                   list(voices.keys()), 
                                   index=list(voices.keys()).index(default_voice),
                                   key="voice_selection")  # Add this unique key
    voice_id = voices[selected_voice]

    # Test phrase input and audio generation
    st.markdown("### 🔊 Let's Test the Storyteller's Voice!")
    test_phrase = st.text_input("Type a fun phrase to hear narrator's voice (up to 200 letters)", 
                                value="Once upon a time, in a land far away, there lived a kind and gentle soul who though small in stature, possessed a heart brimming with courage.", 
                                max_chars=200)
    if st.button("Listen to narration! 🪄"):
        with st.spinner("Bibbidi-Bobbidi-Boo... Making your audio!"):
            test_audio = generate_test_audio(test_phrase, voice_id)
        st.audio(test_audio, format='audio/mp3')

    if st.button("Generate My Story! 📝"):
        with st.spinner("Waving our magic wand... Your story is coming to life!"):
            # Generate the story
            story = generate_full_summary(book_title, reading_difficulty, char_count)
            
            # Store the generated story in session state
            st.session_state.generated_story = story

        st.success("Your story has been generated! 🎉")

    # Display and allow editing of the generated story
    if 'generated_story' in st.session_state:
        st.markdown("### Your Generated Story:")
        
        # Allow editing of the generated story
        edited_story = st.text_area("Edit your story here:", value=st.session_state.generated_story, height=300)
        
        # Update the session state with the edited story
        st.session_state.generated_story = edited_story

        if st.button("Create My Audiobook! ✨"):
            with st.spinner("Turning your story into an audiobook... 🎵"):
                # Convert story to audio
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_file = process_file(edited_story, temp_dir, voice_id, '.txt')
                    
                    # Read the generated audio file
                    with open(output_file, 'rb') as file:
                        audio_bytes = file.read()

            st.success("Hooray! Your audiobook is ready! 🎉")
            st.audio(audio_bytes, format='audio/mp3')
            
            # Provide download link
            st.download_button(
                label="Download Your Free Audiobook!",
                data=audio_bytes,
                file_name=f"{book_title}.mp3",
                mime="audio/mp3"
            )

# Add a fun footer
st.markdown("---")
st.markdown("Brought to life with a little dash of pixie dust")
