from modeltranslation import translator
from .models import Topic, SDG, Skill, FeedPostCategory


@translator.register(Topic)
@translator.register(SDG)
@translator.register(Skill)
class TermTranslationOptions(translator.TranslationOptions):
    fields = ("title",)


@translator.register(FeedPostCategory)
class TermTranslationOptionsWithLabel(translator.TranslationOptions):
    fields = (
        "title",
        "label",
    )
