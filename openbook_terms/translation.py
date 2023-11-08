from modeltranslation import translator
from .models import Topic, InspirationPostCategory, SDG, Skill


@translator.register(Topic)
@translator.register(SDG)
@translator.register(Skill)
@translator.register(InspirationPostCategory)
class TermTranslationOptions(translator.TranslationOptions):
    fields = ("title",)
