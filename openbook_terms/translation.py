from modeltranslation import translator
from .models import Topic, InspirationPostCategory, SDG, Skill, FeedPostCategory


@translator.register(Topic)
@translator.register(SDG)
@translator.register(Skill)
@translator.register(InspirationPostCategory)
@translator.register(FeedPostCategory)
class TermTranslationOptions(translator.TranslationOptions):
    fields = ("title",)
