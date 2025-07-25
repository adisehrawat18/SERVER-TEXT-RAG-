# -*- coding: utf-8 -*-
"""server video rag

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1J5wlm7yi2hFU1W1pWeYrqVBkrgkP7Cla
"""

!pip install whisper

!pip install chromadb

# Check for GPU
import torch
print("CUDA available:", torch.cuda.is_available())
print("GPU Name:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "No GPU")

!pip show torch

!pip uninstall -y whisper
!pip install git+https://github.com/openai/whisper.git

import os
import whisper
import torch
import chromadb
from chromadb import PersistentClient
from moviepy.editor import VideoFileClip
from sentence_transformers import SentenceTransformer
from transformers import BlipProcessor, BlipForConditionalGeneration, pipeline
import cv2
import numpy as np

# Set device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# === STEP 1: Extract Audio from Video ===
def extract_audio(video_path, audio_output="audio.wav"):
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_output)
    return audio_output

# === STEP 2: Transcribe Audio ===
def transcribe_audio(audio_path):
    model = whisper.load_model("base")  # Automatically uses GPU if available
    result = model.transcribe(audio_path)
    return result['text']

# === STEP 3: Extract and Caption Key Video Frames ===
def extract_key_frames(video_path, frame_interval=5):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_step = int(fps * frame_interval)
    frame_count = 0
    frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % frame_step == 0:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        frame_count += 1
    cap.release()
    return frames

def caption_frames(frames):
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)

    captions = []
    for img in frames:
        inputs = processor(images=img, return_tensors="pt").to(device)
        out = model.generate(**inputs)
        caption = processor.decode(out[0], skip_special_tokens=True)
        captions.append(caption)
    return captions

# === STEP 4: Setup ChromaDB and Embed Knowledge Base ===
def setup_chroma_and_add_docs(collection_name="video_rag_docs"):
    client = PersistentClient(path="./chroma_storage")

    if collection_name in [c.name for c in client.list_collections()]:
        client.delete_collection(name=collection_name)

    collection = client.create_collection(name=collection_name)

    docs = [
        "The Eiffel Tower is in Paris.",
        "Python is a popular programming language for AI.",
        "RAG combines retrieval and generation to enhance answers.",
        "ChromaDB is a fast and easy vector store.",
        "Whisper is used to transcribe speech from audio.",
        "BLIP is used to generate captions from images.",
    ]

    embedder = SentenceTransformer("all-MiniLM-L6-v2", device=device)
    embeddings = embedder.encode(docs).tolist()

    collection.add(
        documents=docs,
        embeddings=embeddings,
        ids=[f"doc{i}" for i in range(len(docs))]
    )

    return collection, embedder

# === STEP 5: Query ChromaDB for Related Knowledge ===
def query_chroma(collection, embedder, query, top_k=3):
    query_embedding = embedder.encode([query])[0].tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    return results['documents'][0]

# === STEP 6: Generate Final Output ===
def generate_rag_output(transcript, captions, related_docs):
    visual_text = "\n".join(captions)
    prompt = f"""You are a helpful assistant. Based on the video content, audio transcript, and related documents, generate a summary or answer.

Audio Transcript:
{transcript}

Visual Captions:
{visual_text}

Relevant Knowledge:
{chr(10).join(related_docs)}

Answer:"""

    gen = pipeline("text-generation", model="gpt2", device=0 if torch.cuda.is_available() else -1)
    output = gen(prompt, max_new_tokens=200)[0]['generated_text']
    return output.split("Answer:")[-1].strip()

# === MAIN FUNCTION ===
def video_to_visual_audio_rag(video_path):
    print("Extracting audio...")
    audio_path = extract_audio(video_path)

    print("Transcribing audio...")
    transcript = transcribe_audio(audio_path)
    print(f"[Transcript]:\n{transcript}")

    print("Extracting key frames...")
    frames = extract_key_frames(video_path)

    print("Generating captions for frames...")
    captions = caption_frames(frames)
    print(f"[Visual Captions]:\n{captions}")

    print("Setting up ChromaDB and embedding documents...")
    collection, embedder = setup_chroma_and_add_docs()

    print("Querying ChromaDB...")
    related_docs = query_chroma(collection, embedder, transcript + " " + " ".join(captions))
    print(f"[Retrieved Docs]:\n{related_docs}")

    print("Generating RAG-augmented output...")
    result = generate_rag_output(transcript, captions, related_docs)
    print(f"\n[Final Output]:\n{result}")

# === RUN ===
if __name__ == "__main__":
    video_file = "/content/Screenrecording_20250709_232529.mp4"  # Replace with your actual video path
    video_to_visual_audio_rag(video_file)

