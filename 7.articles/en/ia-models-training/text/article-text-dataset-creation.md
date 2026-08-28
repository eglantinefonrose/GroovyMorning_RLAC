# Dataset Creation
To create the text dataset, it is necessary to transform the audio stream into a faithful transcription and then match
this transcription with the actual timecodes.

## Text Data (Transcription)
### Evolution of Transcription Models
The quality of text detection directly depends on the precision of the Speech-to-Text engine. Several stages have marked our pipeline:
- Whisper (OpenAI): Initial tests with tiny and base models, then switching to the large-v3 model for better textual fidelity.
- Kyutai (Moshi/STT): Final adoption of the kyutai/stt-1b-en_fr model for its performance and processing speed.

### Manual Download and Manual Labeling

Initially, radio broadcasts were manually downloaded from various radio websites, and chronicles were manually detected by humans, in a text file indicating the name of the chronicle as well as the start and end timecodes.

#### Manual Download, Labeling via LLM, and Human Verification
The entirely human-based chronicle detection was later replaced by detection via an LLM (gemini cli), which created the text files with the chronicle timecodes. Human verification was then applied through a Swift macOS interface.

*Visualization of the beginning and ending phrases of the chronicle*
![Visualization of the beginning and ending phrases of the chronicle](../../assets/app-etiquettage-donnees.png)

*Manual editing of the beginning and ending phrases*
![Manual editing of the beginning and ending phrases](../../assets/edit-mode.png)

#### Automatic Download and Detection
The technique currently used is 100% automatic and requires no human intervention.
- **Broadcast Download**: The download of broadcasts and their constituent chronicles is entirely automated by a Python program. However, the program fails to retrieve some chronicles, so not all chronicles are downloaded.
- **Chronicle Detection**: A second program analyzes the full audio and finds the chronicles within it to deduce their position and create the text file providing the chronicle locations in the audio.
- **Text and Audio File Adjustment**: Since some chronicles are missing, they should not be labeled as 'non-chronicle'. A third program deduces the list of missing chronicles from the theoretical list of chronicles present in the broadcast, removes the parts with missing chronicles from the audio, and adjusts the text file accordingly, taking into account the new audio and the missing chronicles.
- **Full Transcription**: The entire broadcast is transcribed using kyutai.

![Explanatory diagram for removing missing chronicles](assets/schema-emission-entiere.png)

#### Extraction of Initial Sentences
We then created a second dataset containing the opening sentences of the chronicles.  
We extract the first 10 seconds of each chronicle, transcribe them, and extract the first sentence of the chronicle (via punctuation analysis).
This first sentence, marking the beginning of the chronicle, constitutes a dataset of chronicle opening sentences.