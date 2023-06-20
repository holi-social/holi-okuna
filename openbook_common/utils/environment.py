class InvalidEnvironmentValueError(AttributeError):
    pass


class EmptyEnvironmentValueError(AttributeError):
    pass


class EnvironmentChecker:
    PRODUCTION_VALUE = "production"
    STAGING_VALUE = "staging"
    DEVELOPMENT_VALUE = "development"
    LOCAL_VALUE = "local"
    TEST_VALUE = "test"
    QUICKTEST_VALUE = "quicktest"
    BUILD_VALUE = "build"

    ALLOWED_ENVIRONMENTS = [
        PRODUCTION_VALUE,
        STAGING_VALUE,
        DEVELOPMENT_VALUE,
        LOCAL_VALUE,
        TEST_VALUE,
        QUICKTEST_VALUE,
        BUILD_VALUE,
    ]

    def __init__(self, environment_value):
        self.environment_value = (
            environment_value if self.is_valid_environment_value(environment_value) else self.DEVELOPMENT_VALUE
        )

    def get_environment(self):
        return self.environment_value

    def is_production(self):
        return self.environment_value == self.PRODUCTION_VALUE

    def is_staging(self):
        return self.environment_value == self.STAGING_VALUE

    def is_development(self):
        return self.environment_value == self.DEVELOPMENT_VALUE

    def is_local(self):
        return self.environment_value == self.LOCAL_VALUE

    def is_test(self):
        return self.environment_value == self.TEST_VALUE

    def is_quicktest(self):
        return self.environment_value == self.QUICKTEST_VALUE

    def is_build(self):
        return self.environment_value == self.BUILD_VALUE

    def is_debug(self):
        return self.is_local() or self.is_development()

    def is_valid_environment_value(self, environment_value):
        return environment_value in self.ALLOWED_ENVIRONMENTS
