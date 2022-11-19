import kenlm
import functools


from django.core.management.base import BaseCommand

from ...models import Utterance


def score(lm, word, context):
    new_context = kenlm.State()
    full_score = lm.BaseFullScore(context, word, new_context)
    if full_score.oov:
        return -42, new_context
    return full_score.log_prob, new_context


@functools.lru_cache(maxsize=2**10)
def segment(lm, text, context=None, maxlen=20):
    if context is None:
        context = kenlm.State()
        lm.NullContextWrite(context)

    if not text:
        return 0.0, []

    textlen = min(len(text), maxlen)
    splits = [(text[:i + 1], text[i + 1:]) for i in range(textlen)]

    candidates = []
    for word, remain_word in splits:
        first_prob, new_context = score(lm, word, context)
        remain_prob, remain_word = segment(lm, remain_word, new_context)

        candidates.append((first_prob + remain_prob, [word] + remain_word))

    return max(candidates)


class Command(BaseCommand):
    help = 'This command fixes glued utternaces found by a collection key'

    def add_arguments(self, parser):
        parser.add_argument('lm_path', type=str)
        parser.add_argument('collection_key', type=str)

    def fix(self, utternace, fixed_label=''):
        utternace.label = fixed_label
        utternace.save()

    def handle(self, *args, **options):
        lm_path = options['lm_path']
        collection_key = options['collection_key']

        lm = kenlm.LanguageModel(lm_path)

        utternaces = Utterance.objects.filter(collection_key=collection_key).all()

        for utternace in utternaces:
            label = utternace.label.replace(' ', '')
            _, fixed_label_chunks = segment(lm, label)
            fixed_label = ' '.join(fixed_label_chunks)

            self.fix(utternace, fixed_label)

            self.stdout.write(utternace.label)
            self.stdout.write(fixed_label)
            self.stdout.write('---')
