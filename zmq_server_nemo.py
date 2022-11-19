import os
import base64
import time
import zmq
import torch
import multiprocessing
import logging
import warnings
import nemo.collections.asr as nemo_asr

from loguru import logger
from pyctcdecode import build_ctcdecoder
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
NEMO_MODEL = os.getenv('NEMO_MODEL', default='NeonBohdan/stt_uk_citrinet_512_gamma_0_25')
USE_LM = os.getenv('USE_LM', default='no') == 'yes'
LM_UNIGRAMS_FILE = os.getenv('LM_UNIGRAMS_FILE', default='')
LM_FILE = os.getenv('LM_FILE', default='')

logger.info('Loading the model: NeMo')
ts = time.time()

asr_model = nemo_asr.models.EncDecCTCModel.from_pretrained(NEMO_MODEL, map_location=torch.device('cpu'))

# Load the KenLM model
if USE_LM:
    # Check variables
    if len(LM_UNIGRAMS_FILE) == 0:
        print('LM_UNIGRAMS_FILE is empty')
        exit(1)
    if len(LM_FILE) == 0:
        print('LM_FILE is empty')
        exit(1)

    with open(LM_UNIGRAMS_FILE) as x:
        unigrams = [it.strip() for it in x.readlines()]

    decoder = build_ctcdecoder(
        asr_model.decoder.vocabulary,
        kenlm_model_path=LM_FILE,
        unigrams=unigrams,
        alpha=0.5,
        beta=1.5
    )

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
            if USE_LM:
                logits_list = asr_model.transcribe([filename], logprobs=True)

                with multiprocessing.get_context("fork").Pool() as pool:
                    lm_predictions = decoder.decode_batch(pool, logits_list, beam_width=50)

                predicted = [it.replace('’', "'") for it in lm_predictions]
                text = predicted[0]
            else:
                predictions = asr_model.transcribe([filename])
                predicted = [it.replace('’', "'") for it in predictions]
                text = predicted[0]

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
