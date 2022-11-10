from modeltranslation import translator
from .models import Topic, SDG, Skill


@translator.register(Topic)
@translator.register(SDG)
@translator.register(Skill)
class TermTranslationOptions(translator.TranslationOptions):
    fields = ("title",)
