from modeltranslation import translator
from .models import Topic, SDG, Skill


@translator.register(Topic)
class TopicTranslationOptions(translator.TranslationOptions):
    fields = ("title",)


@translator.register(SDG)
class SDGTranslationOptions(translator.TranslationOptions):
    fields = ("title",)


@translator.register(Skill)
class SkillTranslationOptions(translator.TranslationOptions):
    fields = ("title",)
