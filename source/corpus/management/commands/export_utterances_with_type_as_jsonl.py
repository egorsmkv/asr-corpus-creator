import os
import json
import time
from django.core.management.base import BaseCommand

from ...models import Utterance

FILES_DIR = os.getenv('FILES_DIR', '/opt/asr-corpus-creator/source/content/media/audios/')


class Command(BaseCommand):
    help = 'This command exports utternaces found by a collection key in JSONL format'

    def add_arguments(self, parser):
        parser.add_argument('collection_key', type=str)
        parser.add_argument('audio_type', type=str)

    def handle(self, *args, **options):
        collection_key = options['collection_key']
        audio_type = options['audio_type']

        utternaces = Utterance.objects.filter(collection_key=collection_key, audio_type=audio_type).all()

        for utternace in utternaces:
            data = {
                'id': str(time.time()),
                'file': utternace.filename.replace(FILES_DIR, ''),
                'text': utternace.label,
                'duration': str(utternace.length),
                'wada_snr': str(utternace.snr),
            }
            jsonl_str = json.dumps(data)

            self.stdout.write(jsonl_str)
