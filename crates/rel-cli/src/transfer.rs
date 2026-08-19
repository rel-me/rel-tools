use rel_client::{ImageBlockingMode, Profile, ProfileCreateRequest, Proxy, ProxyCreateRequest};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};

pub(crate) const PROFILE_TRANSFER_FORMAT: &str = "rel.profile";
pub(crate) const PROXY_TRANSFER_FORMAT: &str = "rel.proxy";
pub(crate) const TRANSFER_FORMAT_VERSION: u32 = 1;

const MAX_TRANSFER_FILE_BYTES: u64 = 1_048_576;
const MAX_IMAGE_SIZE_LIMIT_KB: i64 = 1_048_576;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub(crate) struct ProfileTransferDocument {
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
    pub(crate) fn from_profile(profile: &Profile) -> Self {
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

    pub(crate) fn into_create_request(
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

    pub(crate) fn default_filename(&self) -> String {
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
        if !(1..=MAX_IMAGE_SIZE_LIMIT_KB).contains(&self.profile.image_size_limit_kb) {
            return Err(format!(
                "Profile transfer image_size_limit_kb must be between 1 and {MAX_IMAGE_SIZE_LIMIT_KB}"
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub(crate) struct ProxyTransferDocument {
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
    pub(crate) fn from_public_proxy(proxy: &Proxy) -> Self {
        let oxylabs = proxy.oxylabs.as_ref();
        Self {
            format: PROXY_TRANSFER_FORMAT.to_string(),
            version: TRANSFER_FORMAT_VERSION,
            secrets_included: !proxy.password_set,
            proxy: ProxyTransferPayload {
                alias: proxy.alias.clone(),
                upstream_host: proxy.upstream_host.clone(),
                upstream_port: proxy.upstream_port,
                username: proxy.username.clone(),
                password: None,
                oxylabs_enabled: oxylabs.is_some_and(|options| options.enabled),
                oxylabs_location_parameter: oxylabs
                    .and_then(|options| options.location_parameter.clone()),
                oxylabs_location_value: oxylabs.and_then(|options| options.location_value.clone()),
            },
        }
    }

    pub(crate) fn into_create_request(
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

    pub(crate) fn default_filename(&self) -> String {
        transfer_filename(&self.proxy.alias, "relproxy", "Proxy")
    }

    pub(crate) fn secrets_included(&self) -> bool {
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
        if self.proxy.upstream_host.trim().is_empty() {
            return Err("Proxy transfer upstream_host must not be empty".to_string());
        }
        if self.proxy.upstream_port == 0 {
            return Err("Proxy transfer upstream_port must be between 1 and 65535".to_string());
        }
        Ok(())
    }
}

pub(crate) fn read_transfer_document<T: DeserializeOwned>(path: &Path) -> Result<T, String> {
    let metadata = fs::metadata(path).map_err(|error| {
        format!(
            "Could not inspect transfer file {}: {error}",
            path.display()
        )
    })?;
    if !metadata.is_file() {
        return Err(format!("Transfer path {} is not a file", path.display()));
    }
    if metadata.len() > MAX_TRANSFER_FILE_BYTES {
        return Err(format!(
            "Transfer file {} exceeds the {} byte limit",
            path.display(),
            MAX_TRANSFER_FILE_BYTES
        ));
    }
    let data = fs::read(path)
        .map_err(|error| format!("Could not read transfer file {}: {error}", path.display()))?;
    serde_json::from_slice(&data)
        .map_err(|error| format!("Invalid transfer file {}: {error}", path.display()))
}

pub(crate) fn write_transfer_document(
    document: &impl Serialize,
    output: Option<PathBuf>,
    default_filename: &str,
) -> Result<PathBuf, String> {
    let requested_path = output.unwrap_or_else(|| PathBuf::from(default_filename));
    let path = if requested_path.is_absolute() {
        requested_path
    } else {
        std::env::current_dir()
            .map_err(|error| format!("Could not resolve the current directory: {error}"))?
            .join(requested_path)
    };
    let mut data = serde_json::to_vec_pretty(document)
        .map_err(|error| format!("Could not encode transfer file: {error}"))?;
    data.push(b'\n');

    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&path)
        .map_err(|error| format!("Could not create transfer file {}: {error}", path.display()))?;
    if let Err(error) = file.write_all(&data).and_then(|()| file.flush()) {
        drop(file);
        let _ = fs::remove_file(&path);
        return Err(format!(
            "Could not write transfer file {}: {error}",
            path.display()
        ));
    }
    Ok(path)
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
    use rel_client::OxylabsProxy;
    use serde_json::json;
    use std::os::unix::fs::PermissionsExt;
    use uuid::Uuid;

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
        let value = serde_json::to_value(&document).unwrap();
        assert_eq!(value["format"], PROFILE_TRANSFER_FORMAT);
        assert_eq!(value["version"], TRANSFER_FORMAT_VERSION);
        assert_eq!(value["browser_data"]["included"], false);
        assert_eq!(value["browser_data"]["source_includes_cookies"], true);

        let request = document
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
        let document: ProfileTransferDocument = serde_json::from_value(value.clone()).unwrap();
        assert!(document.into_create_request(None).is_ok());

        value["version"] = json!(2);
        let document: ProfileTransferDocument = serde_json::from_value(value.clone()).unwrap();
        assert!(document
            .into_create_request(None)
            .unwrap_err()
            .contains("not supported"));

        value["version"] = json!(1);
        value["browser_data"]["included"] = json!(true);
        let document: ProfileTransferDocument = serde_json::from_value(value).unwrap();
        assert!(document
            .into_create_request(None)
            .unwrap_err()
            .contains("browser data"));
    }

    #[test]
    fn public_proxy_transfer_marks_omitted_password_and_restores_routing() {
        let document = ProxyTransferDocument::from_public_proxy(&proxy());
        assert!(!document.secrets_included());
        assert_eq!(document.default_filename(), "office.relproxy");
        let value = serde_json::to_value(&document).unwrap();
        assert!(value["proxy"].get("password").is_none());
        assert!(value["proxy"]["oxylabs_session_id"].is_null());

        let request = document
            .into_create_request(Some("imported".to_string()))
            .unwrap();
        assert_eq!(request.alias, "imported");
        assert_eq!(request.username.as_deref(), Some("account"));
        assert_eq!(request.password, None);
        assert_eq!(request.oxylabs_enabled, Some(true));
        assert_eq!(
            request.oxylabs_location_parameter.as_deref(),
            Some("country")
        );
    }

    #[test]
    fn transfer_files_are_private_bounded_and_never_overwritten() {
        let directory = std::env::temp_dir().join(format!("rel-transfer-test-{}", Uuid::new_v4()));
        fs::create_dir(&directory).unwrap();
        let path = directory.join("profile.relprofile");
        let document = ProfileTransferDocument::from_profile(&profile());

        let written = write_transfer_document(&document, Some(path.clone()), "unused").unwrap();
        assert_eq!(written, path);
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        let decoded: ProfileTransferDocument = read_transfer_document(&path).unwrap();
        assert_eq!(decoded, document);
        assert!(write_transfer_document(&document, Some(path.clone()), "unused").is_err());

        fs::remove_file(path).unwrap();
        fs::remove_dir(directory).unwrap();
    }
}
