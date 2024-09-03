## storytime overview
This is an app that will turn any story that you give it into an audiobook. It is specifically trying to work with public domain stories like Cinderella, The Prince and the Pauper, any classic story.

The idea is you can give it the story and then specify the target age for the story as well as the length of the story, and then it'll generate the story for you.

You can review the story, edit it, and then you can click "Generate Audio." When you generate audio, it'll give you the audiobook version of that spoken.

## Setup

- You're going to need to set up an ID with the OpenAI API.
- You're going to need an Amazon Polly secret and ID. I'll include instructions for how to do that.
- You're going to need to just download this repo.
- Install the requirements, and it'll create the Streamlit app, and then you can go from there. Very simple setup, should be super, super simple.

So this is a Streamlit app, which just makes it easy to have a simple front end. Once you're all installed with all the requirements, you'll be in really good shape and have really high quality audiobooks. 

## Customizing

You can switch the parameters. I have it set to limit to 10,000 characters, but you can change that. You can switch the age target, and you know you could hook this up to different voice APIs, right? It'd be pretty easy to adjust this code to use a different voice API. 

Let's say you want to use ElevenLabs because you like their voices, you could do that. You could create custom voices. Tortoise has some really good libraries that I'm going to be playing around with for creating custom voices. yeah and you could also play around with how the story is abridged and edited and I hope this is useful
