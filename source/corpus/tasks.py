import base64
import os
import subprocess
import librosa
import torch
from os.path import exists
from urllib.parse import urlparse

import zmq
import soundfile as sf
import pyloudnorm as pyln
from celery import shared_task
from django.conf import settings
from lingua import Language, LanguageDetectorBuilder

from .models import YoutubeLink, AudioLink, VideoFile, AudioFile, AudioChunk, Utterance
from .utils import get_speech_timestamps, read_audio, save_audio, init_jit_model, wada_snr


WGET_PATH = os.getenv('WGET_PATH', default='/usr/bin/wget')
YOUTUBE_DL = os.getenv('YOUTUBE_DL', default='/usr/local/bin/youtube-dl')
FFMPEG_PATH = os.getenv('FFMPEG_PATH', default='/usr/bin/ffmpeg')

SAMPLE_RATE = 16000

W2V2_SERVER = 'tcp://localhost:5555'

# Fix the number of threads (as it is shown in Silero demo)
torch.set_num_threads(1)

# Init the Silero VAD model
model = init_jit_model(f'{settings.MEDIA_ROOT}/silero_vad.jit')

# Init language detector
lang_detector = LanguageDetectorBuilder.from_languages(*Language.all()).build()


@shared_task
def download_audio(url, row_id):
    row = AudioLink.objects.filter(id=row_id).get()
    print(f'Processing AudioLink ID: {row.id}')

    if row.is_exported:
        print('The row is already exported')
        return

    # Create audios folder
    if not exists(f'{settings.MEDIA_ROOT}/audios'):
        os.makedirs(f'{settings.MEDIA_ROOT}/audios')

    ext = urlparse(row.link).path.split('.')[-1]

    save_as = f'{settings.MEDIA_ROOT}/audios/{row.id}.{ext}'
    save_as_wav = f'{settings.MEDIA_ROOT}/audios/{row.id}.wav'

    # Download audio
    if not exists(save_as):
        output = subprocess.Popen([WGET_PATH, '-O', save_as, url])
        output.communicate()

    # Set the row as exported
    row.is_exported = True
    row.save()

    # Convert M4A into WAV
    if not exists(save_as_wav):
        output = subprocess.Popen([FFMPEG_PATH, '-i', save_as, '-ar', str(SAMPLE_RATE), '-ac', '1', '-acodec', 'pcm_s16le', save_as_wav])
        output.communicate()

    # Remove M4A file
    if exists(save_as):
        os.remove(save_as)

    # Determine the length of the file
    length = librosa.get_duration(filename=save_as_wav)

    # Create a row of audio files
    af = AudioFile()
    af.collection_key = row.collection_key
    af.link = row.link
    af.lang = row.lang
    af.filename = save_as_wav
    af.length = length
    af.save()

    # Now, the filename must be separated into chunks
    split_into_chunks.delay(af.id)


@shared_task
def download_video(url, row_id):
    row = VideoFile.objects.filter(id=row_id).get()
    print(f'Processing VideoFile ID: {row.id}')

    if row.is_exported:
        print('The row is already exported')
        return

    # Create audios folder
    if not exists(f'{settings.MEDIA_ROOT}/audios'):
        os.makedirs(f'{settings.MEDIA_ROOT}/audios')

    ext = urlparse(row.link).path.split('.')[-1]

    save_as = f'{settings.MEDIA_ROOT}/audios/{row.id}.{ext}'
    save_as_aac = f'{settings.MEDIA_ROOT}/audios/{row.id}.aac'
    save_as_wav = f'{settings.MEDIA_ROOT}/audios/{row.id}.wav'

    # Download video
    if not exists(save_as):
        output = subprocess.Popen([WGET_PATH, '-O', save_as, url])
        output.communicate()

    # Set the row as exported
    row.is_exported = True
    row.save()

    # Extract audio stream from the file
    if not exists(save_as_aac):
        output = subprocess.Popen([FFMPEG_PATH, '-i', save_as, '-vn', '-acodec', 'copy', save_as_aac])
        output.communicate()

    # Convert AAC into WAV
    if not exists(save_as_wav):
        output = subprocess.Popen([FFMPEG_PATH, '-i', save_as_aac, '-ar', str(SAMPLE_RATE), '-ac', '1', '-acodec', 'pcm_s16le', save_as_wav])
        output.communicate()

    # Remove the video file and the AAC file
    if exists(save_as):
        os.remove(save_as)
    
    if exists(save_as_aac):
        os.remove(save_as_aac)

    # Determine the length of the file
    length = librosa.get_duration(filename=save_as_wav)

    # Create a row of audio files
    af = AudioFile()
    af.collection_key = row.collection_key
    af.link = row.link
    af.lang = row.lang
    af.filename = save_as_wav
    af.length = length
    af.save()

    # Now, the filename must be separated into chunks
    split_into_chunks.delay(af.id)


@shared_task
def download_youtube_audio(url, row_id):
    row = YoutubeLink.objects.filter(id=row_id).get()
    print(f'Processing YoutubeLink ID: {row.id}')

    if row.is_exported:
        print('The row is already exported')
        return
    
    # Create audios folder
    if not exists(f'{settings.MEDIA_ROOT}/audios'):
        os.makedirs(f'{settings.MEDIA_ROOT}/audios')

    save_as_m4a = f'{settings.MEDIA_ROOT}/audios/{row.id}.m4a'
    save_as_wav = f'{settings.MEDIA_ROOT}/audios/{row.id}.wav'

    # Download YouTube video via youtube-dl
    if not exists(save_as_m4a):
        output = subprocess.Popen([YOUTUBE_DL, '-x', '--audio-format', 'm4a', '--audio-quality', '0', '-o', save_as_m4a, url])
        output.communicate()

    # Set the row as exported
    row.is_exported = True
    row.save()

    # Convert M4A into WAV
    if not exists(save_as_wav):
        output = subprocess.Popen([FFMPEG_PATH, '-i', save_as_m4a, '-ar', str(SAMPLE_RATE), '-ac', '1', '-acodec', 'pcm_s16le', save_as_wav])
        output.communicate()

    # Remove M4A file
    if exists(save_as_m4a):
        os.remove(save_as_m4a)

    # Determine the length of the file
    length = librosa.get_duration(filename=save_as_wav)

    # Create a row of audio files
    af = AudioFile()
    af.collection_key = row.collection_key
    af.link = row.link
    af.lang = row.lang
    af.filename = save_as_wav
    af.length = length
    af.save()

    # Now, the filename must be separated into chunks
    split_into_chunks.delay(af.id)


@shared_task
def split_into_chunks(audio_file_id):
    audio = AudioFile.objects.filter(id=audio_file_id).get()
    print(f'Processing AudioFile ID: {audio.id}')

    if not exists(audio.filename):
        print(f'The {audio.filename} does not exist')
        return

    # Read the file and retreive speeches
    wav = read_audio(audio.filename, sampling_rate=SAMPLE_RATE)
    speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=SAMPLE_RATE, window_size_samples=512)

    for n, c in enumerate(speech_timestamps):
        # Start and end of speech in seconds
        ts_start = round(c['start'] / SAMPLE_RATE, 1)
        ts_end = round(c['end'] / SAMPLE_RATE, 1)

        print(f'Chunk: {ts_start} - {ts_end}')

        # Get the detected speech
        chunk = wav[c['start']: c['end']]
        original_filename = audio.filename.split('/')[-1].replace('.wav', '')
        new_folder = f'{settings.MEDIA_ROOT}/audios/chunks/{original_filename}'
        
        if not exists(new_folder):
            os.makedirs(new_folder)

        # Save the chunk
        filename = f'{new_folder}/{original_filename}__chunk_{n}.wav'
        if not exists(filename):
            save_audio(filename, chunk, SAMPLE_RATE)

            # Determine the length of the file
            length = librosa.get_duration(filename=filename)

            ac = AudioChunk()
            ac.filename = filename
            ac.length = length
            ac.audio = audio
            ac.save()

            print(f'Chunk #{n} is saved as {filename}')
        else:
            print(f'Chunk #{n} is already saved as {filename}')

    # Remove the filename
    if exists(audio.filename):
        os.remove(audio.filename)

    # Send chunks into recognition
    recognize_chunks.delay(audio.id)


@shared_task
def recognize_chunks(audio_file_id):
    audio = AudioFile.objects.filter(id=audio_file_id).get()
    print(f'Processing chunks of AudioFile ID: {audio.id}')

    chunks = AudioChunk.objects.filter(audio__id=audio_file_id).all()
    for chunk in chunks:
        print(chunk)

        # Encode the file into base64
        with open(chunk.filename, 'rb') as f:
            out_data = f.read()
            out_data_base64 = base64.b64encode(out_data) # it's bytes

        print(f'Encoded a file with len={len(out_data_base64)}')

        # Send to the ZeroMQ server
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(W2V2_SERVER)
        socket.send(out_data_base64)

        # Receive the transcription
        text_bin = socket.recv()
        text = text_bin.decode('utf-8')

        # Close the ZeroMQ connection
        socket.close()

        # Nothing is recognized
        if len(text) == 0:
            continue

        # Determine the SNR value
        wav, _ = librosa.load(chunk.filename)
        snr = wada_snr(wav)

        label_lang = '--'
        loudness = 0

        # Detect label's language
        guess_lang = lang_detector.detect_language_of(text)
        if guess_lang:
            label_lang = guess_lang.iso_code_639_1.name
        
        # Detect loudness
        file_data, rate = sf.read(chunk.filename)
        meter = pyln.Meter(rate) # create BS.1770 meter
        loudness = meter.integrated_loudness(file_data)

        # Save the utterance and delete the chunk row (in database)
        utt = Utterance()
        utt.collection_key = audio.collection_key
        utt.label = text
        utt.label_lang = label_lang
        utt.loudness = loudness
        utt.filename = chunk.filename
        utt.length = chunk.length
        utt.lang = audio.lang
        utt.snr = snr
        utt.audio = audio
        utt.save()
