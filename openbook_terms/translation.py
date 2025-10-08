from modeltranslation import translator
from .models import SDG, FeedPostCategory


@translator.register(SDG)
class TermTranslationOptions(translator.TranslationOptions):
    fields = ("title",)


@translator.register(FeedPostCategory)
class TermTranslationOptionsWithLabel(translator.TranslationOptions):
    fields = (
        "title",
        "label",
    )
