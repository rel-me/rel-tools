use crate::{ImageBlockingMode, Profile, ProfileCreateRequest, Proxy, ProxyCreateRequest};
use serde::{Deserialize, Serialize};

pub const PROFILE_TRANSFER_FORMAT: &str = "rel.profile";
pub const PROXY_TRANSFER_FORMAT: &str = "rel.proxy";
pub const TRANSFER_FORMAT_VERSION: u32 = 1;
pub const MAX_TRANSFER_FILE_BYTES: usize = 1_048_576;

const MAX_IMAGE_SIZE_LIMIT_KB: i64 = 1_048_576;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ProfileTransferDocument {
    format: String,
    version: u32,
    profile: ProfileTransferPayload,
    browser_data: ProfileBrowserData,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
struct ProfileTransferPayload {
    name: String,
    proxy_alias: Option<String>,
    adblock_enabled: bool,
    image_blocking_mode: ImageBlockingMode,
    image_size_limit_kb: i64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
struct ProfileBrowserData {
    included: bool,
    source_includes_cookies: bool,
    source_includes_passwords: bool,
}

impl ProfileTransferDocument {
    pub fn from_profile(profile: &Profile) -> Self {
        Self {
            format: PROFILE_TRANSFER_FORMAT.to_string(),
            version: TRANSFER_FORMAT_VERSION,
            profile: ProfileTransferPayload {
                name: profile.name.clone(),
                proxy_alias: profile.proxy_alias.clone(),
                adblock_enabled: profile.adblock_enabled,
                image_blocking_mode: profile.image_blocking_mode,
                image_size_limit_kb: profile.image_size_limit_kb,
            },
            browser_data: ProfileBrowserData {
                included: false,
                source_includes_cookies: profile.includes_cookies,
                source_includes_passwords: profile.includes_passwords,
            },
        }
    }

    pub fn decode(data: &[u8]) -> Result<Self, String> {
        validate_size(data)?;
        let document: Self = serde_json::from_slice(data)
            .map_err(|error| format!("Invalid profile transfer JSON: {error}"))?;
        document.validate()?;
        Ok(document)
    }

    pub fn encode(&self) -> Result<Vec<u8>, String> {
        self.validate()?;
        encode_document(self)
    }

    pub fn into_create_request(
        self,
        name_override: Option<String>,
    ) -> Result<ProfileCreateRequest, String> {
        self.validate()?;
        let name = name_override.unwrap_or(self.profile.name);
        if name.trim().is_empty() {
            return Err("Profile transfer name must not be empty".to_string());
        }
        Ok(ProfileCreateRequest {
            name,
            proxy_alias: self.profile.proxy_alias,
            adblock_enabled: Some(self.profile.adblock_enabled),
            image_blocking_mode: Some(self.profile.image_blocking_mode),
            image_size_limit_kb: Some(self.profile.image_size_limit_kb),
            includes_cookies: Some(false),
            includes_passwords: Some(false),
        })
    }

    pub fn default_filename(&self) -> String {
        transfer_filename(&self.profile.name, "relprofile", "Profile")
    }

    fn validate(&self) -> Result<(), String> {
        validate_header(&self.format, PROFILE_TRANSFER_FORMAT, self.version)?;
        if self.browser_data.included {
            return Err(
                "This profile transfer includes browser data that this REL version cannot import"
                    .to_string(),
            );
        }
        if self.profile.name.trim().is_empty() {
            return Err("Profile transfer name must not be empty".to_string());
        }
        if !(1..=MAX_IMAGE_SIZE_LIMIT_KB).contains(&self.profile.image_size_limit_kb) {
            return Err(format!(
                "Profile transfer image_size_limit_kb must be between 1 and {MAX_IMAGE_SIZE_LIMIT_KB}"
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ProxyTransferDocument {
    format: String,
    version: u32,
    secrets_included: bool,
    proxy: ProxyTransferPayload,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
struct ProxyTransferPayload {
    alias: String,
    upstream_host: String,
    upstream_port: u16,
    username: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    password: Option<String>,
    oxylabs_enabled: bool,
    oxylabs_location_parameter: Option<String>,
    oxylabs_location_value: Option<String>,
}

impl ProxyTransferDocument {
    pub fn from_proxy(proxy: &Proxy, password: Option<String>) -> Self {
        let oxylabs = proxy.oxylabs.as_ref();
        let secrets_included = !proxy.password_set || password.is_some();
        Self {
            format: PROXY_TRANSFER_FORMAT.to_string(),
            version: TRANSFER_FORMAT_VERSION,
            secrets_included,
            proxy: ProxyTransferPayload {
                alias: proxy.alias.clone(),
                upstream_host: proxy.upstream_host.clone(),
                upstream_port: proxy.upstream_port,
                username: proxy.username.clone(),
                password,
                oxylabs_enabled: oxylabs.is_some_and(|options| options.enabled),
                oxylabs_location_parameter: oxylabs
                    .and_then(|options| options.location_parameter.clone()),
                oxylabs_location_value: oxylabs.and_then(|options| options.location_value.clone()),
            },
        }
    }

    pub fn from_public_proxy(proxy: &Proxy) -> Self {
        Self::from_proxy(proxy, None)
    }

    pub fn decode(data: &[u8]) -> Result<Self, String> {
        validate_size(data)?;
        let document: Self = serde_json::from_slice(data)
            .map_err(|error| format!("Invalid proxy transfer JSON: {error}"))?;
        document.validate()?;
        Ok(document)
    }

    pub fn encode(&self) -> Result<Vec<u8>, String> {
        self.validate()?;
        encode_document(self)
    }

    pub fn into_create_request(
        self,
        alias_override: Option<String>,
    ) -> Result<ProxyCreateRequest, String> {
        self.validate()?;
        let alias = alias_override.unwrap_or(self.proxy.alias);
        if alias.trim().is_empty() {
            return Err("Proxy transfer alias must not be empty".to_string());
        }
        Ok(ProxyCreateRequest {
            alias,
            upstream_host: self.proxy.upstream_host,
            upstream_port: self.proxy.upstream_port,
            username: self.proxy.username,
            password: self.proxy.password,
            oxylabs_enabled: Some(self.proxy.oxylabs_enabled),
            oxylabs_location_parameter: self.proxy.oxylabs_location_parameter,
            oxylabs_location_value: self.proxy.oxylabs_location_value,
        })
    }

    pub fn default_filename(&self) -> String {
        transfer_filename(&self.proxy.alias, "relproxy", "Proxy")
    }

    pub fn secrets_included(&self) -> bool {
        self.secrets_included
    }

    fn validate(&self) -> Result<(), String> {
        validate_header(&self.format, PROXY_TRANSFER_FORMAT, self.version)?;
        if !self.secrets_included && self.proxy.password.is_some() {
            return Err(
                "Proxy transfer cannot contain a password when secrets_included is false"
                    .to_string(),
            );
        }
        if self.proxy.alias.trim().is_empty() {
            return Err("Proxy transfer alias must not be empty".to_string());
        }
        if self.proxy.upstream_host.trim().is_empty() {
            return Err("Proxy transfer upstream_host must not be empty".to_string());
        }
        if self.proxy.upstream_port == 0 {
            return Err("Proxy transfer upstream_port must be between 1 and 65535".to_string());
        }
        Ok(())
    }
}

fn encode_document(document: &impl Serialize) -> Result<Vec<u8>, String> {
    let mut data = serde_json::to_vec_pretty(document)
        .map_err(|error| format!("Could not encode transfer file: {error}"))?;
    data.push(b'\n');
    validate_size(&data)?;
    Ok(data)
}

fn validate_size(data: &[u8]) -> Result<(), String> {
    if data.len() > MAX_TRANSFER_FILE_BYTES {
        return Err(format!(
            "Transfer file exceeds the {MAX_TRANSFER_FILE_BYTES} byte limit"
        ));
    }
    Ok(())
}

fn validate_header(format: &str, expected: &str, version: u32) -> Result<(), String> {
    if format != expected {
        return Err(format!(
            "Transfer format must be {expected:?}, found {format:?}"
        ));
    }
    if version != TRANSFER_FORMAT_VERSION {
        return Err(format!(
            "Transfer version {version} is not supported; this REL version supports {TRANSFER_FORMAT_VERSION}"
        ));
    }
    Ok(())
}

fn transfer_filename(name: &str, extension: &str, fallback: &str) -> String {
    let stem = name
        .chars()
        .map(|character| {
            if character == '/' || character == ':' || character.is_control() {
                '-'
            } else {
                character
            }
        })
        .collect::<String>();
    let stem = stem.trim().trim_matches('.');
    let stem = if stem.is_empty() { fallback } else { stem };
    format!("{stem}.{extension}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::OxylabsProxy;
    use serde_json::json;

    fn profile() -> Profile {
        Profile {
            id: "profile-id".to_string(),
            name: "Research/Primary".to_string(),
            proxy_alias: Some("office".to_string()),
            adblock_enabled: true,
            image_blocking_mode: ImageBlockingMode::OverLimit,
            image_size_limit_kb: 250,
            includes_cookies: true,
            includes_passwords: true,
            is_builtin: false,
            created_at: 1,
        }
    }

    fn proxy() -> Proxy {
        Proxy {
            alias: "office".to_string(),
            upstream_host: "proxy.example.com".to_string(),
            upstream_port: 8000,
            username: Some("account".to_string()),
            password_set: true,
            oxylabs: Some(OxylabsProxy {
                enabled: true,
                session_id: Some("generated-session".to_string()),
                location_parameter: Some("country".to_string()),
                location_value: Some("US".to_string()),
            }),
        }
    }

    #[test]
    fn profile_transfer_round_trips_settings_without_browser_data() {
        let document = ProfileTransferDocument::from_profile(&profile());
        assert_eq!(document.default_filename(), "Research-Primary.relprofile");
        let data = document.encode().unwrap();
        let value: serde_json::Value = serde_json::from_slice(&data).unwrap();
        assert_eq!(value["format"], PROFILE_TRANSFER_FORMAT);
        assert_eq!(value["version"], TRANSFER_FORMAT_VERSION);
        assert_eq!(value["browser_data"]["included"], false);
        assert_eq!(value["browser_data"]["source_includes_cookies"], true);

        let request = ProfileTransferDocument::decode(&data)
            .unwrap()
            .into_create_request(Some("Imported".to_string()))
            .unwrap();
        assert_eq!(request.name, "Imported");
        assert_eq!(request.proxy_alias.as_deref(), Some("office"));
        assert_eq!(request.adblock_enabled, Some(true));
        assert_eq!(
            request.image_blocking_mode,
            Some(ImageBlockingMode::OverLimit)
        );
        assert_eq!(request.image_size_limit_kb, Some(250));
        assert_eq!(request.includes_cookies, Some(false));
        assert_eq!(request.includes_passwords, Some(false));
    }

    #[test]
    fn additive_fields_are_ignored_but_versions_and_browser_data_are_strict() {
        let mut value =
            serde_json::to_value(ProfileTransferDocument::from_profile(&profile())).unwrap();
        value["future_top_level"] = json!({"value": true});
        value["profile"]["future_setting"] = json!(42);
        let data = serde_json::to_vec(&value).unwrap();
        assert!(ProfileTransferDocument::decode(&data).is_ok());

        value["version"] = json!(2);
        let error =
            ProfileTransferDocument::decode(&serde_json::to_vec(&value).unwrap()).unwrap_err();
        assert!(error.contains("not supported"));

        value["version"] = json!(1);
        value["browser_data"]["included"] = json!(true);
        let error =
            ProfileTransferDocument::decode(&serde_json::to_vec(&value).unwrap()).unwrap_err();
        assert!(error.contains("browser data"));
    }

    #[test]
    fn proxy_transfer_can_include_or_omit_password() {
        let public = ProxyTransferDocument::from_public_proxy(&proxy());
        assert!(!public.secrets_included());
        assert_eq!(public.default_filename(), "office.relproxy");
        let public_value: serde_json::Value =
            serde_json::from_slice(&public.encode().unwrap()).unwrap();
        assert!(public_value["proxy"].get("password").is_none());

        let complete = ProxyTransferDocument::from_proxy(&proxy(), Some("secret".to_string()));
        assert!(complete.secrets_included());
        let request = ProxyTransferDocument::decode(&complete.encode().unwrap())
            .unwrap()
            .into_create_request(Some("imported".to_string()))
            .unwrap();
        assert_eq!(request.alias, "imported");
        assert_eq!(request.username.as_deref(), Some("account"));
        assert_eq!(request.password.as_deref(), Some("secret"));
        assert_eq!(request.oxylabs_enabled, Some(true));
        assert_eq!(
            request.oxylabs_location_parameter.as_deref(),
            Some("country")
        );
    }

    #[test]
    fn transfer_files_are_bounded() {
        let data = vec![b' '; MAX_TRANSFER_FILE_BYTES + 1];
        assert!(ProfileTransferDocument::decode(&data)
            .unwrap_err()
            .contains("byte limit"));
    }
}
