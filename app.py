
from pathlib import Path
from openai import OpenAI
import time
import streamlit as st
from PIL import Image
import threading
import pydub
from pydub.playback import play
import os



root_dir = os.getcwd()
video_file = "video.mp4"
image1_file = "2.png"
image2_file = "new.png"

def main():

    
    st.set_page_config(
        page_title="Cigna AI Assistant",
        page_icon="📚",
        layout="wide"
    )
         
    video_path = os.path.join(root_dir,video_file)
    st.video(video_path,start_time=0)
    
    image_path = os.path.join(root_dir,image1_file)
    st.sidebar.image(image_path, caption='')
    

    # Add a selectbox to the sidebar:
    add_selectbox = st.sidebar.selectbox(
    'How would you like to be contacted?',
    ('Email', 'Home phone', 'Mobile phone')
    )
    
    add_selectbox = st.sidebar.selectbox(
    'How often would you like to be contacted?',
    ('Daily', 'Weekly', 'Monthly','Never')
    )
    

    slider_value = st.sidebar.slider("How satisfied out of 10 were you with your last Cigna interaction?", 0, 5, 10)
    
    image_path = os.path.join(root_dir,image2_file)
    st.sidebar.image(image_path, caption='')
    

    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]

    # Initiate st.session_state
    st.session_state.client = OpenAI(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "start_chat" not in st.session_state:
        st.session_state.start_chat = False

    if st.session_state.client:
        st.session_state.start_chat = True

    if st.session_state.start_chat:
        # Display existing messages in the chat
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

                # Accept user input
        if prompt := st.chat_input("Hello how can I help?"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            # Display user message in chat message container
            with st.chat_message("user"):
                st.markdown(prompt)

            # Create a thread
            st.session_state.thread = st.session_state.client.beta.threads.create()

            # Add a Message to the thread
            st.session_state.client.beta.threads.messages.create(
                thread_id=st.session_state.thread.id,
                role="user",
                content=prompt,
            )

            # As of now, assistant and thread are not associated to eash other
            # You need to create a run in order to tell the assistant at which thread to look at
            run = st.session_state.client.beta.threads.runs.create(
                thread_id=st.session_state.thread.id,
                assistant_id=assistant_id,
            )

            # with while loop continuously check the status of a run until it neither 'queued' nor 'in progress'
            def wait_for_complete(run, thread):
                while run.status == "queued" or run.status == "in_progress":
                    run = st.session_state.client.beta.threads.runs.retrieve(
                        thread_id=thread.id,
                        run_id=run.id,
                    )
                    time.sleep(0.5)
                return run

            run = wait_for_complete(run, st.session_state.thread)

            # once the run has completed, list the messages in the thread -> they are ordered in reverse chronological order
            replies = st.session_state.client.beta.threads.messages.list(
                thread_id=st.session_state.thread.id
            )

            # This function will parse citations and make them readable
            def process_replies(replies):
                citations = []

                # Iterate over all replies
                for r in replies:
                    if r.role == "assistant":
                        message_content = r.content[0].text
                        annotations = message_content.annotations

                        # Iterate over the annotations and add footnotes
                        for index, annotation in enumerate(annotations):
                            # Replace the text with a footnote
                            message_content.value = message_content.value.replace(
                                annotation.text, f" [{index}]"
                            )

                            # Gather citations based on annotation attributes
                            if file_citation := getattr(
                                annotation, "file_citation", None
                            ):
                                cited_file = st.session_state.client.files.retrieve(
                                    file_citation.file_id
                                )
                                citations.append(
                                    f"[{index}] {file_citation.quote} from {cited_file.filename}"
                                )
                            elif file_path := getattr(annotation, "file_path", None):
                                cited_file = st.session_state.client.files.retrieve(
                                    file_path.file_id
                                )
                                citations.append(
                                    f"[{index}] Click <here> to download {cited_file.filename}"
                                )

                # Combine message content and citations
                full_response = message_content.value + "\n" + "\n".join(citations)
                return full_response

            # Add the processed response to session state
            processed_response = process_replies(replies)
            st.session_state.messages.append(
                {"role": "assistant", "content": processed_response}
            )
            
            speech_file_path = Path(__file__).parent / "speech.mp3"

# Delete the previous recorded file if it exists
            if speech_file_path.is_file():
                speech_file_path.unlink()

# Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(processed_response, unsafe_allow_html=True)
    
            client = st.session_state.client

# Request the API to create the audio file
            response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=processed_response
            )

# Save the new audio file
            with open(speech_file_path, "wb") as audio_file:
                audio_file.write(response.content)

# Play the most recent audio file
            st.audio(speech_file_path.read_bytes())

if __name__ == "__main__":
    main()
