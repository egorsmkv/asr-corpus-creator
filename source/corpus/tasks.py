import base64
import os
import subprocess
import librosa
import torch
import time
from os.path import exists, getsize
from glob import glob
from urllib.parse import urlparse

import whisper
import zmq
import soundfile as sf
import pyloudnorm as pyln
from pydub import AudioSegment
from celery import shared_task
from django.conf import settings
from pyannote.audio import Pipeline
from lingua import Language, LanguageDetectorBuilder

from .models import YoutubeLink, AudioLink, VideoFile, AudioFile, AudioChunk, Utterance, LocalFolder, YoutubeChannelLink
from .utils import wada_snr
from .srmrpy import srmr

DETECT_AUDIO_LANG = os.getenv('DETECT_AUDIO_LANG', default='no') == 'yes'
WHISPER_MODEL = os.getenv('WHISPER_MODEL', default='base')

WGET_PATH = os.getenv('WGET_PATH', default='/usr/bin/wget')
YOUTUBE_DL = os.getenv('YOUTUBE_DL', default='')
YT_DLP = os.getenv('YT_DLP', default='/usr/local/bin/yt-dlp')
FFMPEG_PATH = os.getenv('FFMPEG_PATH', default='/usr/bin/ffmpeg')

HF_TOKEN = os.getenv('HF_TOKEN', default='')

MIN_UTTERANCE_DURATION = float(os.getenv('MIN_UTTERANCE_DURATION', default=0.5))
MAX_UTTERANCE_DURATION = float(os.getenv('MAX_UTTERANCE_DURATION', default=15))

SAMPLE_RATE = 16000

W2V2_SERVER = 'tcp://localhost:5555'

# Disable using GPU
os.environ['CUDA_VISIBLE_DEVICES'] = ''

# Fix the number of threads (as it is shown in Silero demo)
torch.set_num_threads(1)

# Load PyAnnote VAD model
vad_pipeline = Pipeline.from_pretrained("pyannote/voice-activity-detection", use_auth_token=HF_TOKEN)

# Init language detector
lang_detector = LanguageDetectorBuilder.from_languages(*Language.all()).build()

# Init audio language detector (using Whisper model)
if DETECT_AUDIO_LANG:
    whisper_model = whisper.load_model(WHISPER_MODEL)


@shared_task
def push_folder_to_processing(folder, collection_key, lang):
    print(f'Processing the folder {folder}')

    # Create audios folder
    if not exists(f'{settings.MEDIA_ROOT}/audios'):
        os.makedirs(f'{settings.MEDIA_ROOT}/audios')
    
    # Create a folder for the processing
    ts = time.time()
    processing_folder = f'{settings.MEDIA_ROOT}/audios/processing_{ts}'

    if not exists(processing_folder):
        os.makedirs(processing_folder)

    # Get all files from the source folder
    all_files = os.listdir(folder)

    # Move files into a newly created folder
    for filename in all_files:
        src_path = os.path.join(folder, filename)
        dst_path = os.path.join(processing_folder, filename)

        os.rename(src_path, dst_path)

    n_files = len(all_files)
    print(f'Files are moved, number of files: {n_files}')

    # Now, send the folder to the processing
    lf = LocalFolder()
    lf.path = processing_folder
    lf.collection_key = collection_key
    lf.lang = lang
    lf.save()

    process_local_folder.delay(lf.id)


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
def download_youtube_audio(url, row_id, proxy):
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

    # Download YouTube video via youtube-dl or yt-dlp
    if not exists(save_as_m4a):
        # Use yt-dlp if youtube-dl is not set
        youtube_downloader_cli = ''
        if len(YT_DLP) > 0:
            youtube_downloader_cli = YT_DLP
        else:
            youtube_downloader_cli = YOUTUBE_DL
        
        if proxy != '-':
            output = subprocess.Popen([youtube_downloader_cli, '-x', '--proxy', proxy, '--audio-format', 'm4a', '--audio-quality', '0', '-o', save_as_m4a, url])
        else:
            output = subprocess.Popen([youtube_downloader_cli, '-x', '--audio-format', 'm4a', '--audio-quality', '0', '-o', save_as_m4a, url])

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
def download_youtube_channel(row_id, proxy):
    row = YoutubeChannelLink.objects.filter(id=row_id).get()
    print(f'Processing YoutubeChannelLink ID: {row.id}')

    if row.is_exported:
        print('The row is already exported')
        return

    # Create audios folder
    path = f'{settings.MEDIA_ROOT}/audios'
    if not exists(path):
        os.makedirs(path)

    # Create a folder for the channel
    channel_path = path + f'/channel_{row_id}'
    if not exists(channel_path):
        os.makedirs(channel_path)

    # Use yt-dlp if youtube-dl is not set
    youtube_downloader_cli = ''
    if len(YT_DLP) > 0:
        youtube_downloader_cli = YT_DLP
    else:
        youtube_downloader_cli = YOUTUBE_DL

    if proxy != '-':
        cmd = [youtube_downloader_cli, '-f', 'm4a', '--proxy', proxy, '--audio-quality', '0', '--download-archive', f'/tmp/{row_id}_videos.txt', '-o', f'{channel_path}/%(id)s.%(ext)s', row.channel_url]
    else:
        cmd = [youtube_downloader_cli, '-f', 'm4a', '--audio-quality', '0', '--download-archive', f'/tmp/{row_id}_videos.txt', '-o', f'{channel_path}/%(id)s.%(ext)s', row.channel_url]

    output = subprocess.Popen(cmd)
    output.communicate()

    # Convert audios to the WAV format
    for filename in glob(channel_path + '/*.m4a'):
        save_as_wav = filename.replace('.m4a', '.wav')
        cmd = [FFMPEG_PATH, '-i', filename, '-ar', str(SAMPLE_RATE), '-ac', '1', '-acodec', 'pcm_s16le', save_as_wav]
        output = subprocess.Popen(cmd)
        output.communicate()

        # Remove M4A file
        if exists(filename):
            os.remove(filename)

    # Send the folder with WAV files to the processing
    lf = LocalFolder()
    lf.path = channel_path
    lf.collection_key = row.collection_key
    lf.lang = row.lang
    lf.save()

    process_local_folder.delay(lf.id)

    # Set the row as exported
    row.is_exported = True
    row.save()


@shared_task
def process_local_folder(row_id):
    row = LocalFolder.objects.filter(id=row_id).get()
    print(f'Processing LocalFolder ID: {row.id}')

    if row.is_exported:
        print('The row is already exported')
        return

    # Create audios folder
    if not exists(f'{settings.MEDIA_ROOT}/audios'):
        os.makedirs(f'{settings.MEDIA_ROOT}/audios')

    for filename in glob(row.path + '/*.wav'):
        print(f'Sending a file: {filename}')

        # Determine the length of the file
        length = librosa.get_duration(filename=filename)

        # Create a row of audio files
        af = AudioFile()
        af.collection_key = row.collection_key
        af.link = '-'
        af.lang = row.lang
        af.filename = filename
        af.length = length
        af.save()

        # Now, the filename must be separated into chunks
        split_into_chunks.delay(af.id)

    # Set the row as exported
    row.is_exported = True
    row.save()


@shared_task
def split_into_chunks(audio_file_id):
    audio = AudioFile.objects.filter(id=audio_file_id).get()
    print(f'Processing AudioFile ID: {audio.id}')

    if not exists(audio.filename):
        print(f'The {audio.filename} does not exist')
        return

    # Get WAV
    wav = AudioSegment.from_wav(audio.filename)

    # Detect speech segments by VAD
    output = vad_pipeline(audio.filename)

    for n, speech in enumerate(output.get_timeline().support()):
        # Start and end of speech in seconds
        ts_start = speech.start
        ts_end = speech.end

        print(f'Chunk: {ts_start} - {ts_end}')

        # Check duration limits
        if speech.duration < MIN_UTTERANCE_DURATION or speech.duration > MAX_UTTERANCE_DURATION:
            continue

        # Get the detected speech
        chunk = wav[ts_start * 1000 : ts_end * 1000]

        # Create a subfolder for chunks
        original_filename = audio.filename.split('/')[-1].replace('.wav', '')
        new_folder = f'{settings.MEDIA_ROOT}/audios/chunks/{original_filename}'

        if not exists(new_folder):
            os.makedirs(new_folder)

        # Save the chunk
        filename = f'{new_folder}/{original_filename}__chunk_{n}.wav'
        if not exists(filename):
            chunk.export(filename, format="wav")

            ac = AudioChunk()
            ac.filename = filename
            ac.length = speech.duration
            ac.audio = audio
            ac.save()

            print(f'Chunk #{n} is saved as {filename}')
        else:
            print(f'Chunk #{n} is already saved as {filename}')

    # Remove the filename
    if exists(audio.filename):
        os.remove(audio.filename)

    # Send chunks to recognition
    recognize_chunks.delay(audio.id)


@shared_task
def recognize_chunks(audio_file_id):
    audio = AudioFile.objects.filter(id=audio_file_id).get()
    print(f'Processing chunks of AudioFile ID: {audio.id}')

    chunks = AudioChunk.objects.filter(audio__id=audio_file_id).all()
    for chunk in chunks:
        print(chunk)

        # Check duration limits
        if chunk.length < MIN_UTTERANCE_DURATION or chunk.length > MAX_UTTERANCE_DURATION:
            print(chunk, 'is long')
            continue
        
        # Check existence of an utterance
        exists = Utterance.objects.filter(audio=audio, filename=chunk.filename).exists()
        if exists:
            print(chunk, 'exists in utternaces, skipping')
            continue

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
        wav, sr = librosa.load(chunk.filename)
        snr = wada_snr(wav)

        label_lang = '--'
        audio_lang = '--'
        loudness = 0

        # Detect label's language
        guess_lang = lang_detector.detect_language_of(text)
        if guess_lang:
            label_lang = guess_lang.iso_code_639_1.name

        # Detect loudness
        file_data, rate = sf.read(chunk.filename)
        meter = pyln.Meter(rate) # create BS.1770 meter
        try:
            loudness = meter.integrated_loudness(file_data)
        except ValueError: # Intercept an exception: Audio must have length greater than the block size.
            loudness = 0

        # Detect SRMR ratio
        srmr_ratio, _ = srmr(wav, sr)

        # Detect audio language
        if DETECT_AUDIO_LANG:
            chunk_audio = whisper.load_audio(chunk.filename)
            chunk_audio = whisper.pad_or_trim(chunk_audio)

            mel = whisper.log_mel_spectrogram(chunk_audio).to(whisper_model.device)
            _, probs = whisper_model.detect_language(mel)
            audio_lang = max(probs, key=probs.get)
            if isinstance(audio_lang, str):
                audio_lang = audio_lang.upper()

        # Get the filesize
        filesize = getsize(chunk.filename)

        # Save the utterance and delete the chunk row (in database)
        utt = Utterance()
        utt.collection_key = audio.collection_key
        utt.label = text
        utt.label_lang = label_lang
        utt.audio_lang = audio_lang
        utt.loudness = loudness
        utt.srmr_ratio = srmr_ratio
        utt.filename = chunk.filename
        utt.filesize = filesize
        utt.length = chunk.length
        utt.lang = audio.lang
        utt.snr = snr
        utt.audio = audio
        utt.save()
