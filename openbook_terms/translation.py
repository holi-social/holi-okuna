from modeltranslation.translator import register, TranslationOptions
from .models import Topic, SDG, Skill


@register(Topic)
class TopicTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(SDG)
class SDGTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(Skill)
class SkillTranslationOptions(TranslationOptions):
    fields = ("title",)
