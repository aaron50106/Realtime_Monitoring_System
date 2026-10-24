from pathlib import Path
# mask secretestr type str object printed to "***"
# validating tools for the database URL
from pydantic import SecretStr, field_validator 

# for configuring Pydantic settings
from pydantic_settings import BaseSettings, SettingsConfigDict 
from sqlalchemy.engine import make_url # for parsing and validating the database URL
from sqlalchemy.exc import ArgumentError # for handling invalid database URLs


class Settings(BaseSettings): # declares the Pydantic settings class for the application
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", # path to the .env file 
        env_file_encoding="utf-8",
        extra="ignore", # if extra environment variables are present, ignore them
        hide_input_in_errors=True,
    )
    # declares the database URL setting for the application
    database_url: SecretStr

    # declares the JWT settings for the application
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # system bot password for internal system operations(for data generation)
    system_bot_password: SecretStr

    # whether the realtime service should automatically start when the application starts
    realtime_auto_start: bool = False

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("DATABASE_URL must be a valid mysql+asyncmy URL") from None
        if url.drivername != "mysql+asyncmy":
            raise ValueError("DATABASE_URL must use mysql+asyncmy")
        return value

    @field_validator("system_bot_password")
    @classmethod
    def validate_system_bot_password(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("SYSTEM_BOT_PASSWORD must not be empty")
        return value
