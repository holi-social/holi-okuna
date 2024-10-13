from openbook_translation.strategies.base import (
    BaseTranslationStrategy,
    UnsupportedLanguagePairError,
    MaxTextLengthExceededError,
)


class MockAmazonTranslate(BaseTranslationStrategy):
    # Both methods are hardcoded to respond to the tests

    def get_detected_language_code(self, text):
        if text == "Ik ben en man 😀. Jij bent en vrouw.":
            return "nl"
        else:
            return "no"

    def get_default_translation_language_code(self):
        return "en"

    def get_supported_translation_language_code(self, language_code):
        return "en"

    def translate_text(self, text, source_language_code, target_language_code):

        if len(text) > self.text_max_length:
            raise MaxTextLengthExceededError("MaxTextLengthExceededError")

        if target_language_code == "en" and source_language_code == "nl":
            return {"translated_text": "I am a man 😀. You're a woman."}

        if target_language_code == "ar" and source_language_code == "no":
            raise UnsupportedLanguagePairError
