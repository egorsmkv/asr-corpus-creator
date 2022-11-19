import os
import base64
import time
import zmq
import torch
import torchaudio
import logging
import warnings

from loguru import logger
from transformers import Wav2Vec2ProcessorWithLM, Wav2Vec2Processor, Wav2Vec2ForCTC
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
USE_LM = os.getenv('USE_LM', default='no') == 'yes'
WAV2VEC2_MODEL = os.getenv('WAV2VEC2_MODEL', default='Yehor/wav2vec2-xls-r-300m-uk-with-small-lm')

logger.info('Loading the model: wav2vec2')
ts = time.time()

if USE_LM:
    processor = Wav2Vec2ProcessorWithLM.from_pretrained(WAV2VEC2_MODEL, cache_dir='./all-models')
else:
    processor = Wav2Vec2Processor.from_pretrained(WAV2VEC2_MODEL, cache_dir='./all-models')

model = Wav2Vec2ForCTC.from_pretrained(WAV2VEC2_MODEL, cache_dir='./all-models')
model.to('cpu')
logger.info(f'Loaded the model: {time.time() - ts} seconds')
logger.info('---')

while True:
    try:
        # Wait for a next request from the client
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

            # Convert the data to the tensor
            waveform, sample_rate = torchaudio.load(filename)
            speech = waveform.squeeze().numpy()

            # Inference
            input_values = processor(speech, sampling_rate=16000, return_tensors='pt', padding='longest').input_values
            with torch.no_grad():
                logits = model(input_values).logits

            if USE_LM:
                prediction = processor.batch_decode(logits.numpy()).text
                text = prediction[0]
            else:
                predicted_ids = torch.argmax(logits, dim=-1)
                prediction = processor.batch_decode(predicted_ids)
                text = prediction[0]

        logger.info(f"Recognized transcript: {text}")

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
