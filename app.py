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

def get_available_voices(language_code='en-GB'):
    try:
        response = polly.describe_voices(LanguageCode=language_code)
        voices = response['Voices']
        
        def get_country(language_code):
            country_map = {
                'en-US': 'US', 'en-GB': 'England', 'en-AU': 'Australia',
                'en-NZ': 'New Zealand', 'en-ZA': 'South Africa',
                'en-IE': 'Ireland', 'en-GB-WLS': 'Wales'
                # Add more mappings for other languages as needed
            }
            return country_map.get(language_code, language_code)
        
        return {f"{voice['Name']} - {get_country(voice['LanguageCode'])}": voice['Id'] for voice in voices}
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

def generate_summary_chunk(book_title, reading_difficulty, total_char_count, chunk_number, total_chunks, language_code, previous_chunk=""):
    chunk_char_count = math.ceil(total_char_count / total_chunks)
    start_percentage = (chunk_number - 1) / total_chunks * 100
    end_percentage = chunk_number / total_chunks * 100

    prompt = f"""Create a part of an abridged version of {book_title} (which was published pre 1924 and is in the public domain) in {language_code}. 
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

    Begin the abridged text for this section now in {language_code}:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are a skilled writer specializing in children's literature adaptations. You are fluent in {language_code} and will generate the story in this language."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )

    return response.choices[0].message.content.strip()

def generate_full_summary(book_title, reading_difficulty, char_count, language_code):
    chunks = []
    total_chunks = math.ceil(char_count / 3000)
    overlap = 500

    previous_chunk = ""
    for i in range(1, total_chunks + 1):
        chunk = generate_summary_chunk(book_title, reading_difficulty, char_count, i, total_chunks, language_code, previous_chunk[-overlap:])
        chunks.append(chunk)
        previous_chunk = chunk

    generated_content = " ".join(chunks)
    full_summary = f"{book_title}\n\n{generated_content}"

    return full_summary

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

# Story Generation Inputs
st.markdown("### 📚 Let's Pick The Story!")
book_title = st.text_input("What's the title and author of the story?", value="The Dragon and the Raven by GA Henty")
reading_difficulty = st.slider("What reading level should we aim for? (in years)", 5, 15, 8)
char_count = st.slider("How long should your story be? (in characters)", 400, 10000, 1000)

# Language selection (moved up and default set to English UK)
st.markdown("### 🌍 Choose Your Language")
languages = {
    "English (UK)": "en-GB",
    "English (US)": "en-US",
    "English (Australia)": "en-AU",
    "Spanish (Spain)": "es-ES",
    "Spanish (Mexico)": "es-MX",
    "French (France)": "fr-FR",
    "French (Canada)": "fr-CA",
    "German": "de-DE",
    "Italian": "it-IT",
    "Portuguese (Brazil)": "pt-BR",
    "Japanese": "ja-JP",
    "Korean": "ko-KR",
    "Chinese (Mandarin)": "cmn-CN"
    # Add more languages as needed
}
selected_language = st.selectbox("Select a language:", list(languages.keys()), index=0)  # Default to English (UK)
language_code = languages[selected_language]

# Voice selection based on chosen language
st.markdown("### 🎭 Pick Your Storyteller's Voice")
voices = get_available_voices(language_code)
if voices:
    # Find the index of Brian for en-GB, otherwise default to 0
    default_voice_index = next((i for i, v in enumerate(voices.keys()) if 'Brian' in v), 0) if language_code == 'en-GB' else 0
    selected_voice = st.selectbox("Who should tell your story?", 
                                  list(voices.keys()), 
                                  index=default_voice_index,
                                  key="voice_selection")
    voice_id = voices[selected_voice]
else:
    st.error(f"No voices available for the selected language: {selected_language}")
    st.stop()

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
        # Generate the story in the selected language
        story = generate_full_summary(book_title, reading_difficulty, char_count, language_code)
        
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
