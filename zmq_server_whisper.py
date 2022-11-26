import os
import base64
import time
import zmq
import logging
import warnings
import whisper

from loguru import logger
from utils import InterceptHandler, MemoryTempfile

# Configure logging
logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

# Turn off warning messages
warnings.simplefilter('ignore')

# Configure ZeroMQ
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://0.0.0.0:5555")

# Load the model
WHISPER_MODEL = os.getenv('WHISPER_MODEL', default='base')
WHISPER_LANG = os.getenv('WHISPER_LANG', default='')
WHISPER_USE_FP16 = os.getenv('WHISPER_USE_FP16', default='no') == 'yes'

logger.info('Loading the model: Whisper')
ts = time.time()

model = whisper.load_model(WHISPER_MODEL)

logger.info(f'Loaded the model: {time.time() - ts} seconds')
logger.info('---')

while True:
    try:
        # Wait for next request from client
        message = socket.recv()

        logger.info(f"Received a file to recognize with len={len(message)}")

        # Convert to bytes
        data_bytes = base64.b64decode(message)
        text = ''

        # Save in memory
        tf = MemoryTempfile()
        with tf.NamedTemporaryFile('wb') as f:
            f.write(data_bytes)
            filename = f.name

            # Inference
            audio = whisper.load_audio(filename)
            audio = whisper.pad_or_trim(audio)

            mel = whisper.log_mel_spectrogram(audio).to(model.device)

            if WHISPER_LANG:
                options = whisper.DecodingOptions(language=WHISPER_LANG, fp16=WHISPER_USE_FP16)
            else:
                options = whisper.DecodingOptions(fp16=WHISPER_USE_FP16)

            result = whisper.decode(model, mel, options)

            text = result.text
            text = text.strip()

        logger.info(f"Recognized text: {text}")

        # Send a reply with the transcript back to the client
        reply = text
        socket.send(reply.encode('utf-8'))
    except KeyboardInterrupt as e:
        logger.info('Exiting...')

        break
    except Exception as e:
        logger.error(e)

        reply = 'error'
        socket.send(reply.encode('utf-8'))

    logger.info('---')
