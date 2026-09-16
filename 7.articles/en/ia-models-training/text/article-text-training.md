# Training Text Models

To detect **chronicles in radio broadcasts**, we use a **semantic** approach by exploiting the **transcription** of **broadcasts** and **chronicles**.

## Global Overview of Trials

```mermaid
flowchart TD
    A[SRT Transcription] --> B{Detection Strategy}
    B --> C[Classic ML Approach]
    B --> D[Deep Learning Approach]
    B --> E[LLM Approach]

    C --> F[Random Forest]
    F --> G[Features: TF-IDF, stats, duration]

    D --> H[Hybrid CamemBERT + Bi-LSTM + CRF]
    D --> I[CamemBERT Fine-tuning]
    I --> J[5-segment Sliding Window]

    E --> K[Few-Shot Prompting]
    K --> L[Mistral / Qwen]
    K --> M[Claude API / DeepSeek API]
```

## Transcription and Isolation of Chronicles via LLM

This approach relies on the **semantic intelligence** of language models (**LLM**) to identify chronicles from the transcribed text.

### Technical Approach

The approach uses a **Few-Shot Prompting** technique (learning from examples):
1.  Data Extraction: A script loads several **transcriptions** in **SRT** format (**time-stamped text**) which serve as **ground truth**.
2.  Prompt Construction: A **massive prompt** is built containing:
    - The **transcription** of the file to analyze
    - A **series of examples from past broadcasts** with their full transcriptions and the **exact timecodes of their chronicles**
3.  Inference: The model (defaulting to `mistral` via Ollama) **analyzes** these examples to **understand** the **recurring structure of the broadcast** (jingles, introductions, transitions) and applies this **logic** to the new file to **extract chronicle names** and their **timecodes**.

### Observations and Results
> Model score: 0.00/100

## Training Random Forest Model to Detect Chronicles via Transcription

This approach relies on a **chronicle detection** method using a **Random Forest** algorithm.   

### How Random Forest Works
Instead of entrusting the decision to **a single algorithm**, the Random Forest creates a **hundred Decision Trees** (hence the name "Forest").

Each tree examines the **textual features** from the **transcription of a segment** (lexical density, punctuation, sentence length, etc.).  
Each tree gives its **opinion**: "It's a chronicle" or "It's not a chronicle."  
Le **final result** is the one that received the most votes (**majority** wins).

To ensure that the **trees are not all identical**, **randomness** is introduced in two ways:
- On the data: Each tree is trained on a **different sample of the text segments**.
- On the criteria: Each tree only looks at **part of the features** (for example, one tree might focus on punctuation, another on vocabulary).   
  This prevents the algorithm from becoming "obsessed" with a **single misleading detail**.

```mermaid
graph TD
    A[Text Segment /<br>Transcription] --> B[Feature Extraction]
    
    subgraph RandomForest [Random Forest]
        direction TB
        B --> C1[Tree 1]
        B --> C2[Tree 2]
        B --> C3[Tree n...]
        
        C1 --> F1[Lexical Density]
        C2 --> F2[Keywords]
        C3 --> F3[Punctuation]
        
        F1 --> V1{Vote}
        F2 --> V2{Vote}
        F3 --> V3{Vote}
    end
    
    V1 -- Segment --> M[Majority Vote]
    V2 -- Segment --> M
    V3 -- Non-Segment --> M
    
    M --> D[Final Decision:<br>CHRONIC]

    %% Styling to match the original image
    style A fill:#2c2f38,stroke:#555,color:#fff
    style B fill:#2c2f38,stroke:#555,color:#fff
    style C1 fill:#000080,stroke:#555,color:#fff
    style C2 fill:#000080,stroke:#555,color:#fff
    style C3 fill:#000080,stroke:#555,color:#fff
    style F1 fill:#2c2f38,stroke:#555,color:#fff
    style F2 fill:#2c2f38,stroke:#555,color:#fff
    style F3 fill:#2c2f38,stroke:#555,color:#fff
    style V1 fill:#2c2f38,stroke:#555,color:#fff
    style V2 fill:#2c2f38,stroke:#555,color:#fff
    style V3 fill:#2c2f38,stroke:#555,color:#fff
    style M fill:#ff3333,stroke:#555,color:#fff
    style D fill:#2c2f38,stroke:#555,color:#fff
    style RandomForest fill:#1e2129,stroke:#555,color:#fff
```

### Technical Approach
The model analyzes the transcription stream **segment by segment** using:

1.  Feature Extraction:
    - Segment duration and **temporal metadata**.
    - **Textual statistics** (word count, punctuation).
    - TF-IDF: Analysis of **word importance** to identify vocabulary specific to chronicles.

2.  Sliding Window (Contextual Window):   
    For each segment, the model takes into account the **features of adjacent segments** (local context) to improve **detection accuracy**.

3.  Classification:   
    A robust Random Forest classifier that **separates** **chronicles** from the rest of the broadcast.

### Observations and Results 
> Model score: 0.00/100

## Training a Hybrid Model (Random Forest Fine-tuned BERT)

This approach relies on an advanced radio chronicle detection method based on a **Hybrid Deep Learning** architecture analyzing textual transcriptions (SRT).  
This approach is designed to capture both the **deep meaning of speech** and the **sequential structure** of a radio broadcast.

### Technical Approach
The model is based on a **three-tier** architecture:

1.  Semantic Understanding (CamemBERT):
    Each text segment is transformed into rich characteristic **vectors** (embeddings) by the **CamemBERT language model**, allowing for an understanding of the **context** and the **topic discussed**.

2.  Sequential Modeling (Bi-LSTM):
    A **bidirectional recurrent neural network** analyzes the sequence of segments to understand the progression of the broadcast (**the link between segments**) and **identify transitions**.

3.  Temporal Consistency (CRF):
    A **Conditional Random Field** layer ensures that the predicted label sequence is **logically possible** (for example, eliminating chronicles that would last 2 seconds).

```mermaid
graph BT
    A["SRT Segments"] --> B

    subgraph L1 ["Layer 1: Semantic Understanding"]
        B["CamemBERT - Segment<br>Embeddings"]
    end

    B --> C
    subgraph L2 ["Layer 2: Sequential Modeling"]
        C["Bi-LSTM - Bidirectional<br>Flow Analysis"]
    end

    C --> D
    subgraph L3 ["Layer 3: Temporal Coherence"]
        D["CRF Layer - Conditional<br>Random Field"]
    end

    D --> E["Optimized Label<br>Sequence"]

    %% Styles pour correspondre aux couleurs de l'image
    style A fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style B fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style C fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style D fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style E fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    
    style L1 fill:#fffff0,stroke:#bdb76b,stroke-width:2px,color:#333
    style L2 fill:#fffff0,stroke:#bdb76b,stroke-width:2px,color:#333
    style L3 fill:#fffff0,stroke:#bdb76b,stroke-width:2px,color:#333
```

### Observations and Results 
> Model score: 29.61

## Fine-tuning the Semantic BERT Model

This approach relies on using a **CamemBERT model** (BERT for French) to detect chronicles in radio broadcast transcriptions.

### Technical Approach
Chronicle detection relies on a **Transformer** architecture (CamemBERT) specialized in **sequence classification**. The approach breaks down into **three major steps**:  

**1. Semantic Augmentation (Context)**  
An **isolated** transcription segment (often very short, e.g., 2-3 seconds) rarely contains enough information to be classified with certainty.  
- The system uses a **sliding window** (default 5 segments: the target segment + 2 before + 2 after).  
- These segments are **concatenated**, with a special [SEP] token inserted to mark the separation between segments.  
- This allows the model to capture the **structure of the broadcast** (e.g., detecting a transition, a jingle, or a summary announcement).

```mermaid
graph LR
    subgraph FW ["Sliding Window (5 segments)"]
        direction LR
        S1["Segment n-2"] --- SEP1["SEP"]
        SEP1 --- S2["Segment n-1"]
        S2 --- SEP2["SEP"]
        SEP2 --- ST(("Target<br>Segment"))
        ST --- SEP3["SEP"]
        SEP3 --- S3["Segment n+1"]
        S3 --- SEP4["SEP"]
        SEP4 --- S4["Segment n+2"]
    end

    ST --> CLASS["Chronic / Non-<br>Chronic?"]

    style FW fill:#fffff0,stroke:#bdb76b,stroke-width:2px,color:#333
    
    style S1 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style S2 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style S3 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style S4 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    
    style SEP1 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style SEP2 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style SEP3 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    style SEP4 fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
    
    style ST fill:#f4a460,stroke:#333,stroke-width:3px,color:#333
    style CLASS fill:#e6e6fa,stroke:#9370db,stroke-width:2px,color:#333
```

**2. Semantic Classification**  
The contextualized text is passed through a **fine-tuned CamemBERT (or DistilCamemBERT) model**.    

Input: The **tokens of the 5 merged segments**.   
Output: A **probability (0 to 1)** that the central segment belongs to a chronicle.

The model learns to recognize not only **thematic vocabulary** but also **politeness formulas** and **typical discourse structures** of chronicle launches.

**3. Post-processing & Smoothing**  
Raw predictions can be **discontinuous** (e.g., a silent segment in the middle of a chronicle). The inference script applies **consistency filters**:  

Smoothing: Single-segment "holes" within a detection block are **automatically filled**.   
Duration Filter: Only **continuous blocks of more than 30 seconds** are kept, thus eliminating **false positives** on brief interventions or headlines.

### Observations and Results
> Model score: **2.8/100**

## Fine-tuning the Semantic BERT Model to Detect the Start of a Chronicle

This approach uses a **CamemBERT** model (via Hugging Face Transformers) to automatically detect the **start of chronicles** within radio broadcast transcriptions (STT).

### Model Training
The *train_camembert.py* script allows for training the model on our **own data**.

Data: The script retrieves .txt files containing the transcription of the **first 10 seconds of chronicles** and extracts the **first sentence** (words until the first period).  
Output: The trained model is saved in the ./camembert_chronicle_start folder.

### Inference
The script displays a **numbered list** of **sentences** identified as being **chronicle starts**.

**Improvement**   
At the time of inference, we choose to display the **first 3 sentences of the chronicle** instead of only the first sentence. We observe that detection is often made **slightly too early**.

### Observations and Results
> Model score: **28.2/100**

**Improvement 2**
- Transition Management: The model finally learns to handle the **transition from one segment to another**. We generate **mixed examples** (e.g., [Last sentence of chronicle A, Transition sentence, First sentence of chronicle B]) labeled as chronicle start.
- Length Bias Removal: All examples now consist of **exactly 3 sentences**. The model can no longer **cheat** by associating "short text" with "chronicle start."
- Data Leakage Elimination: We no longer ask the model to detect chronicles in broadcasts that were **part of its training**. The model can no longer *memorize* a transition it would find in validation in an **almost identical form**.
- Inclusion of the **full transcription of the broadcast** to integrate more **negative** examples (non-chronicle starts).

NB: Training sessions were done by **improving an already trained model** (with the first improvements); a model was not re-generated from scratch.

### Observations and Results
> Model score: **22.4/100**

## Using an LLM to Detect Just the Start of Chronicles
After discovering that Claude can **perfectly extract chronicle opening sentences**, Qwen is used to try to extract chronicle opening sentences.

### Model Training
Qwen is asked to detect sentences corresponding to the start of chronicles. It sees sentences **one by one** (as in a live stream).  
**Few-shot prompting** is used to give examples directly in the prompt (examples of chronicle opening sentences).

### Inference
The script **observes the stream** and **signals** when it detects the start of a chronicle.

> Since results were not conclusive, another LLM was tried.

## Using Claude to Detect Just the Start of Chronicles

### Model Training
The **Claude API** is called to detect sentences corresponding to the start of chronicles, providing the **list of chronicles to detect** (in order). It sees the **sentences one by one** (as in a live stream).   
**Few-shot prompting** is used to give examples directly in the prompt (examples of chronicle opening sentences).

### Inference
The script **observes the stream** and **signals** when it detects the start of a chronicle and its name.

## Using DeepSeek to Detect Just the Start of Chronicles
For **performance** and **economic** reasons, the **DeepSeek API** is used to detect chronicles in the live stream.

### Model Training
The **DeepSeek API** (*deepseek-v4-flash*) is called to detect sentences corresponding to the **start of chronicles**, providing the **list of chronicles to detect** (in order). It sees sentences **one by one** (as in a live stream).   
**Few-shot prompting** is used to give examples directly in the prompt (examples of chronicle opening sentences).

### Inference
The script **observes the stream** and **signals** when it detects the start of a chronicle and its name.

### Observations and Results  
> Model score: **67.10**

### Improvements  
To avoid **gross errors**, chronicles are compared with their **theoretical schedule**. A detected chronicle that has **already passed** is also **ignored**.

```mermaid
sequenceDiagram
    participant FT as Transcription Stream
    participant PR as Prompt (Few-Shot +<br>Chronicle List)
    participant API as LLM API (DeepSeek-v4)
    participant FC as Coherence Filter
    participant U as User

    FT->>PR: New sentence detected
    PR->>API: Sentence analysis
    
    API-->>FC: "Start of chronicle X"
    
    FC->>FC: Theoretical time comparison
    FC->>FC: Check "Already passed?"
    
    FC-->>U: Chronicle start notification
```

## Chronicle Detection from Transcription and Audio of Radio Broadcasts

### Using Multiple Approaches

```mermaid
graph TD
    A["Radio Audio Stream"] --> B["Audio Detection<br>Musical Stinger"]
    A --> C["Diarization<br>Speaker Change"]
    A --> D["Streaming STT<br>Local Whisper (M1)"]
    
    D --> E["Semantic Analysis<br>Generic Markers"]
    
    B --> F["Fusion & Decision<br>Audio + Semantic Break"]
    C --> F
    E --> F
    
    F --> G["Chronicle Start Detected"]

    %% Styles pour correspondre aux couleurs de l'image
    style A fill:#f0f0eb,stroke:#b0b0a0,stroke-width:2px,color:#333
    style B fill:#e0f2f1,stroke:#4db6ac,stroke-width:2px,color:#004d40
    style C fill:#fbe9e7,stroke:#ff8a65,stroke-width:2px,color:#bf360c
    style D fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#0d47a1
    style E fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#0d47a1
    style F fill:#e8eaf6,stroke:#7986cb,stroke-width:2px,color:#1a237e
    style G fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#1b5e20
```

A "multi-modal" approach is used to detect the start of radio chronicles in real-time. Instead of relying on a single criterion, it merges several types of analyses to make a more robust decision.

Here are the main steps of the method:

**1. Capture and Preprocessing**   
   The system retrieves the **audio stream** (either from a file or a live stream like France Inter) and cuts it into small segments (chunks) to analyze them on the fly.

**2. The "Fast Path" (Acoustic Fingerprinting)**  
   Before launching heavy computations, the system checks if the audio segment **resembles a known jingle**.
- It generates a **digital fingerprint** (fingerprint) of the sound.
- If there is a match in its **database** (e.g., the specific jingle of a show), it triggers **immediate detection**.

**3. Parallel Sensors (Multi-Approach)**   
   If it's not a known jingle, it activates **4 different sensors**:
* **Acoustic** (Novelty): It detects **abrupt changes** in the sound texture (rhythm break, change in atmosphere).
* **Audio Events**: It searches for the **presence of music** (often used for transitions) vs. speech.
* **Diarization**: It detects if the **speaker changes** (transition from presenter to chronicler).
* **Semantic (LLM)**: The system **transcribes** the audio into text via Whisper (STT) and sends the text to a **language model** (like Llama 3) via Ollama. L'IA analyzes if the **words used** resemble a chronicle introduction (e.g., "Hello everyone, today we're going to talk about...").

**4. Score Fusion**   
   Each sensor gives a **score**. The system makes a **weighted average**:
- **Semantics** (IA) has the most weight (**40%**).
- The **other criteria** (acoustic, music, speaker) share the rest (**20% each**).

**5. Learning (Feedback Loop)**  
   As soon as a chronicle is detected with **certainty**, the system records the **sound fingerprint** of that moment. If it was a jingle, it will recognize it even faster next time thanks to the *Fast Path*.

> Model score: **0.00/100**

[Version Française](../../../fr/ia-models-training/text/ARTICLE_TEXT_TRAINING.md)
