import json
from os.path import exists

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'This command parses a JSONL file and print data in the CSV format'

    def add_arguments(self, parser):
        parser.add_argument('jsonl_file', type=str)

    def handle(self, *args, **options):
        jsonl_file = options['jsonl_file']

        if not exists(jsonl_file):
            self.stdout.write(f'The file {jsonl_file} does not exist')
            return

        with open(jsonl_file) as f:
            rows = [json.loads(it.strip()) for it in f.readlines()]
        
        self.stdout.write('path,text')
        for row in rows:
            self.stdout.write(f'{row["file"]},{row["text"]}')
