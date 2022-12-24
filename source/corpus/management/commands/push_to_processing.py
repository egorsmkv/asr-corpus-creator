from os.path import exists

from django.core.management.base import BaseCommand

from ...tasks import push_folder_to_processing


class Command(BaseCommand):
    help = 'This command pushes new files to the processing from a specified folder'

    def add_arguments(self, parser):
        parser.add_argument('collection_key', type=str)
        parser.add_argument('lang', type=str)
        parser.add_argument('folder', type=str)

    def handle(self, *args, **options):
        collection_key = options['collection_key']
        lang = options['lang']
        folder = options['folder']

        if not exists(folder):
            self.stdout.write(f'The folder {folder} does not exist')
            return

        self.stdout.write(f'Pushing the folder {folder} to the processing')

        push_folder_to_processing.delay(folder, collection_key, lang)

        self.stdout.write(f'The folder {folder} has been pushed')
