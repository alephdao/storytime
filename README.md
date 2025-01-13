# Story Time Magic 🎵✨

A magical Streamlit application that turns any story into an audiobook, with support for multiple languages and voices. This tool uses GPT-4 to adapt stories for different reading levels and AWS Polly for high-quality text-to-speech conversion.

## ✨ Features

* Transform text into engaging audiobooks
* Support for multiple languages and accents
* Customizable reading difficulty levels (5-15 years)
* Adjustable story length
* Interactive voice testing
* Real-time story editing
* Easy audiobook download in MP3 format
* Beautiful, kid-friendly user interface

## 🎯 Key Capabilities

* Story Generation
  * Adapts stories to specified reading levels
  * Maintains original narrative style and voice
  * Preserves important quotes and memorable lines
  * Customizable story length
  
* Voice Customization
  * Multiple language options including:
    * English (UK, US, Australia)
    * Spanish (Spain, Mexico)
    * French (France, Canada)
    * German
    * Italian
    * Portuguese (Brazil)
    * Japanese
    * Korean
    * Chinese (Mandarin)
  * Various voice options per language
  * Voice testing feature
  
* Audio Processing
  * High-quality text-to-speech conversion
  * Automatic chunk processing for long texts
  * Seamless audio combining
  * MP3 format output

## 🛠️ Prerequisites

* Python 3.x
* OpenAI API key
* AWS credentials (Access Key ID and Secret Access Key)
* AWS Polly access

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/alephdao/storytime.git
cd storytime
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your API credentials:
```env
OPENAI_API_KEY=your_openai_api_key
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=your_aws_region
```

## 🚀 Usage

1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. In your web browser:
   * Enter the story title and author
   * Select the desired reading level
   * Choose the story length
   * Pick your preferred language and voice
   * Test the voice with a sample phrase
   * Generate and edit your story
   * Create and download your audiobook

## 💻 Technical Details

### Dependencies

* `streamlit`: Web application framework
* `boto3`: AWS SDK for Python
* `openai`: OpenAI API client
* `pydub`: Audio processing
* `python-dotenv`: Environment variable management

### Key Components

* Story Generation (`generate_full_summary`):
  * Uses GPT-4 for story adaptation
  * Handles chunking for longer content
  * Maintains narrative consistency
  
* Audio Synthesis (`process_file`):
  * Manages text chunking
  * Handles AWS Polly integration
  * Combines audio segments
  
* Voice Management (`get_available_voices`):
  * Fetches available voices from AWS Polly
  * Handles language-specific voice selection
  * Supports multiple dialects and accents

## 🎨 UI Features

* Gradient background with decorative patterns
* Comic Sans MS font for child-friendly appearance
* Animated buttons with hover effects
* Color-coded sections
* Progress indicators
* Downloadable audio output

## 🔐 Security Notes

* Requires secure storage of API keys
* Uses environment variables for sensitive data
* Implements temporary file handling

## 📝 Notes

* Story length is limited for optimal processing
* Audio generation time varies with story length
* Internet connection required for API services
* Some voices may not be available in all languages

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## 📄 License

MIT LICENSE
