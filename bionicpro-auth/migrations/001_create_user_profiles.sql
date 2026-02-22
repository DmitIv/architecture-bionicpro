-- Migration: Create user_profiles table
-- Description: Store user profile data from Yandex ID integration

CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    yandex_id VARCHAR(255),
    username VARCHAR(255),
    email VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    display_name VARCHAR(255),
    avatar_url TEXT,
    phone VARCHAR(50),
    birthday DATE,
    gender VARCHAR(10),
    profile_data JSONB,
    consent_given BOOLEAN DEFAULT FALSE,
    consent_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_yandex_id ON user_profiles(yandex_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE user_profiles IS 'Stores user profile data from external identity providers like Yandex ID';
COMMENT ON COLUMN user_profiles.user_id IS 'Keycloak user ID (primary identifier)';
COMMENT ON COLUMN user_profiles.yandex_id IS 'Yandex user ID from identity provider';
COMMENT ON COLUMN user_profiles.username IS 'Username from identity provider';
COMMENT ON COLUMN user_profiles.email IS 'Primary email address';
COMMENT ON COLUMN user_profiles.first_name IS 'User first name';
COMMENT ON COLUMN user_profiles.last_name IS 'User last name';
COMMENT ON COLUMN user_profiles.display_name IS 'Full display name';
COMMENT ON COLUMN user_profiles.avatar_url IS 'URL to user avatar image';
COMMENT ON COLUMN user_profiles.phone IS 'Phone number';
COMMENT ON COLUMN user_profiles.birthday IS 'Date of birth';
COMMENT ON COLUMN user_profiles.gender IS 'Gender (male, female, other)';
COMMENT ON COLUMN user_profiles.profile_data IS 'Complete JSON profile data from identity provider';
COMMENT ON COLUMN user_profiles.consent_given IS 'Whether user consented to data storage';
COMMENT ON COLUMN user_profiles.consent_timestamp IS 'When consent was given';
COMMENT ON COLUMN user_profiles.created_at IS 'Record creation timestamp';
COMMENT ON COLUMN user_profiles.updated_at IS 'Last update timestamp';
