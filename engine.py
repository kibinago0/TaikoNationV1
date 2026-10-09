"""
TaikoNation Inference & Chart Generation Engine
Supports end-to-end audio processing, Mel feature extraction,
PyTorch-based note inference, and .osu/.osz chart generation.
"""

import os
import shutil
import zipfile
import numpy as np
import torch
import torch.nn as nn
import librosa
from convert_weights import TaikoNationNet

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_taiko_model(model_path="output/model/taiko_nation_pytorch.pt"):
    model = TaikoNationNet()
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    state_dict = torch.load(model_path, map_location=DEVICE)
    model.load_state_dict(state_dict)
    model.to(DEVICE)
    model.eval()
    return model

def extract_features_from_audio(audio_path, sample_rate=44100):
    """
    Extracts 80 Mel bands features matching TaikoNation's 23ms chunking.
    In original TaikoNation: 23ms segment = 1014.3 samples at 44.1kHz.
    """
    y, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
    hop_length = int(sr * 0.023) # ~1014 samples (~23ms)
    n_fft = 2048

    # Mel spectrogram (80 bands, 27.5Hz - 16000Hz)
    mel_spec = librosa.feature.melspectrogram(
        y=y,
        sr=sr,
        n_fft=n_fft,
        hop_length=hop_length,
        win_length=1024,
        window='blackmanharris',
        n_mels=80,
        fmin=27.5,
        fmax=16000.0,
        power=2.0
    )

    # Numerically stable log scaling matching DDC/TaikoNation
    log_mel = np.log(mel_spec.T + 1e-16).astype(np.float32)
    return log_mel, sr, len(y) / sr

def generate_taiko_chart(
    model,
    song_features,
    title="Unknown Song",
    artist="Unknown Artist",
    difficulty_name="TaikoNation v1",
    temperature=0.8,
    density_mult=1.0
):
    """
    Runs model inference over song features and produces note selections.
    """
    total_chunks = len(song_features)
    predictions = []
    
    # Process in batches for fast GPU/CPU execution
    batch_size = 128
    with torch.no_grad():
        for start_idx in range(0, total_chunks, batch_size):
            end_idx = min(start_idx + batch_size, total_chunks)
            batch_inputs = []
            
            for j in range(start_idx, end_idx):
                chunk = []
                for i in range(16):
                    idx = j - i
                    if idx < 0:
                        chunk.append(np.zeros(80, dtype=np.float32))
                    else:
                        chunk.append(song_features[idx])
                batch_inputs.append(chunk)

            # [batch, 16, 80]
            batch_tensor = torch.tensor(np.array(batch_inputs), dtype=torch.float32, device=DEVICE)
            encoded = model.encode_song(batch_tensor) # [batch, 8, 16]
            probs = model(encoded) # [batch, 4, 7]
            predictions.extend(probs.cpu().numpy())

    # Note selections combining overlapping window predictions (k+n, 3-n)
    note_selections = []
    for k in range(len(predictions)):
        guess = np.zeros(7, dtype=np.float32)
        for n in range(4):
            if k + n < len(predictions):
                selection = predictions[k + n][3 - n]
                guess += selection
            else:
                break

        # Adjust density: note 0 is silence/rest
        if density_mult != 1.0 and density_mult > 0:
            # lower weight on rest increases note probability
            guess[0] /= density_mult

        # Apply temperature
        if temperature > 0:
            guess = np.power(guess + 1e-8, 1.0 / temperature)

        sum_guess = np.sum(guess)
        if sum_guess > 0:
            prob = guess / sum_guess
        else:
            prob = np.ones(7) / 7.0

        try:
            choice = int(np.random.choice(7, p=prob))
        except Exception:
            choice = int(np.argmax(prob))

        note_selections.append(choice)

    return note_selections

def create_osu_content(note_selections, title="SongTitle", artist="ArtistName", difficulty_name="TaikoNation v1"):
    """
    Creates osu!taiko (Mode 1) beatmap script content.
    """
    osu_lines = [
        "osu file format v14",
        "",
        "[General]",
        "AudioFilename: audio.mp3",
        "AudioLeadIn: 0",
        "PreviewTime: 0",
        "Countdown: 0",
        "SampleSet: Normal",
        "StackLeniency: 0.7",
        "Mode: 1", # Mode 1 = osu!taiko
        "LetterboxInBreaks: 0",
        "WidescreenStoryboard: 0",
        "",
        "[Editor]",
        "DistanceSpacing: 0.8",
        "BeatDivisor: 4",
        "GridSize: 32",
        "TimelineZoom: 3.14",
        "",
        "[Metadata]",
        f"Title:{title}",
        f"TitleUnicode:{title}",
        f"Artist:{artist}",
        f"ArtistUnicode:{artist}",
        "Creator:TaikoNation AI",
        f"Version:{difficulty_name}",
        "Source:TaikoNation",
        "Tags:AI TaikoNation",
        "BeatmapID:-1",
        "BeatmapSetID:-1",
        "",
        "[Difficulty]",
        "HPDrainRate:6",
        "CircleSize:2",
        "OverallDifficulty:6",
        "ApproachRate:10",
        "SliderMultiplier:1.4",
        "SliderTickRate:1",
        "",
        "[TimingPoints]",
        "0,368,4,1,0,40,1,0",
        "",
        "[HitObjects]"
    ]

    current_ms = 0
    last_note_active = False
    hit_objects = []

    for note in note_selections:
        # 1: Red small (Don), 2: Blue small (Kat), 3: Red big, 4: Blue big
        if note == 1 and not last_note_active:
            hit_objects.append(f"256,192,{current_ms},1,0,0:0:0:0:")
            last_note_active = True
        elif note == 2 and not last_note_active:
            hit_objects.append(f"256,192,{current_ms},1,2,0:0:0:0:")
            last_note_active = True
        elif note == 3 and not last_note_active:
            hit_objects.append(f"256,192,{current_ms},1,4,0:0:0:0:")
            last_note_active = True
        elif note == 4 and not last_note_active:
            hit_objects.append(f"256,192,{current_ms},1,6,0:0:0:0:")
            last_note_active = True
        else:
            last_note_active = False
        current_ms += 23

    osu_lines.extend(hit_objects)
    return "\n".join(osu_lines), hit_objects

def package_osz(output_dir, audio_file_path, osu_content, package_name):
    """
    Creates .osu and .osz files in output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)
    osu_file_path = os.path.join(output_dir, "chart.osu")
    with open(osu_file_path, "w", encoding="utf-8") as f:
        f.write(osu_content)

    osz_file_path = os.path.join(output_dir, package_name)
    with zipfile.ZipFile(osz_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(audio_file_path, arcname="audio.mp3")
        zf.write(osu_file_path, arcname="chart.osu")

    return osu_file_path, osz_file_path
