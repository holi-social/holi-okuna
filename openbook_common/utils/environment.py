class InvalidEnvironmentValueError(AttributeError):
    pass


class EmptyEnvironmentValueError(AttributeError):
    pass


class EnvironmentChecker:
    PRODUCTION_VALUE = "production"
    STAGING_VALUE = "staging"
    DEVELOPMENT_VALUE = "development"
    TEST_VALUE = "test"
    QUICKTEST_VALUE = "quicktest"
    BUILD_VALUE = "build"

    ALLOWED_ENVIRONMENTS = [
        BUILD_VALUE,
        TEST_VALUE,
        QUICKTEST_VALUE,
        PRODUCTION_VALUE,
        DEVELOPMENT_VALUE,
        STAGING_VALUE,
    ]

    def __init__(self, environment_value):
        if not self.is_valid_environment_value(environment_value):
            raise InvalidEnvironmentValueError

        self.environment_value = environment_value

    def is_production(self):
        return self.environment_value == self.PRODUCTION_VALUE

    def is_development(self):
        return self.environment_value == self.DEVELOPMENT_VALUE

    def is_staging(self):
        return self.environment_value == self.STAGING_VALUE

    def is_test(self):
        return self.environment_value == self.TEST_VALUE

    def is_build(self):
        return self.environment_value == self.BUILD_VALUE

    def is_debug(self):
        return self.is_development() or self.is_staging()

    def is_valid_environment_value(self, environment_value):
        return environment_value in self.ALLOWED_ENVIRONMENTS

    def is_quicktest(self):
        return self.environment_value == self.QUICKTEST_VALUE
