//! Typed Rust client for REL RPC v1.
//!
//! This module contains no desktop-app lifecycle or local-file behavior. It can
//! therefore be used by other Rust programs without adopting the bundled CLI's
//! macOS-specific conveniences.

use base64::{engine::general_purpose::STANDARD as BASE64_STANDARD, Engine as _};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize, Serializer};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::io::{self, BufRead, BufReader, Lines, Read};
use std::time::Duration;

pub mod transfer;

const DEFAULT_AGENT_PORT: u16 = 17_319;
const DEFAULT_REQUEST_TIMEOUT: Duration = Duration::from_secs(10);
const DEFAULT_PAGE_READ_MAX_CHARS: usize = 12_000;
const MIN_PAGE_READ_MAX_CHARS: usize = 512;
const MAX_PAGE_READ_MAX_CHARS: usize = 32_768;
const DEFAULT_PAGE_READ_MAX_SECTIONS: usize = 24;
const MAX_PAGE_READ_MAX_SECTIONS: usize = 100;

/// Stable application error codes for REL RPC v1.
///
/// Codes begin at 10,000 so they cannot be mistaken for HTTP transport
/// statuses. String error IDs remain available for readable diagnostics.
pub mod rpc_error_codes {
    pub const MINIMUM: u32 = 10_000;

    pub const INVALID_REQUEST: u32 = 10_000;
    pub const ROUTE_NOT_FOUND: u32 = 10_001;
    pub const METHOD_NOT_ALLOWED: u32 = 10_002;
    pub const PAYLOAD_TOO_LARGE: u32 = 10_003;
    pub const UNSUPPORTED_MEDIA_TYPE: u32 = 10_004;
    pub const VALIDATION_FAILED: u32 = 10_005;
    pub const UNSUPPORTED_MODALITY: u32 = 10_006;
    pub const OBSERVATION_TOO_LARGE: u32 = 10_007;

    pub const SESSION_NOT_FOUND: u32 = 10_100;
    pub const PAGE_NOT_FOUND: u32 = 10_101;
    pub const PAGE_MISMATCH: u32 = 10_102;
    pub const PROXY_NOT_FOUND: u32 = 10_103;
    pub const ACTIVE_PAGE_NOT_FOUND: u32 = 10_104;

    pub const CONFLICT: u32 = 10_200;
    pub const BROWSER_BUSY: u32 = 10_201;
    pub const NETWORK_PAUSED: u32 = 10_202;
    pub const ACTION_TARGET_NOT_FOUND: u32 = 10_203;
    pub const REQUEST_CANCELLED: u32 = 10_204;
    pub const RATE_LIMITED: u32 = 10_205;
    pub const ACTION_TIMEOUT: u32 = 10_206;
    pub const OBSERVATION_STALE: u32 = 10_207;
    pub const PRO_REQUIRED: u32 = 10_208;

    pub const UPSTREAM_UNAVAILABLE: u32 = 10_300;
    pub const BROWSER_UNAVAILABLE: u32 = 10_301;
    pub const AGENT_UNHEALTHY: u32 = 10_302;
    pub const TIMEOUT: u32 = 10_303;
    pub const PROXY_CONFIGURATION_FAILED: u32 = 10_304;
    pub const BROWSER_CREATION_FAILED: u32 = 10_305;
    pub const SEMANTIC_EXTRACTION_FAILED: u32 = 10_306;

    pub const INTERNAL_ERROR: u32 = 10_999;

    pub fn for_id(id: &str) -> u32 {
        match id {
            "INVALID_REQUEST" => INVALID_REQUEST,
            "ROUTE_NOT_FOUND" => ROUTE_NOT_FOUND,
            "METHOD_NOT_ALLOWED" => METHOD_NOT_ALLOWED,
            "PAYLOAD_TOO_LARGE" => PAYLOAD_TOO_LARGE,
            "UNSUPPORTED_MEDIA_TYPE" => UNSUPPORTED_MEDIA_TYPE,
            "VALIDATION_FAILED" => VALIDATION_FAILED,
            "UNSUPPORTED_MODALITY" => UNSUPPORTED_MODALITY,
            "OBSERVATION_TOO_LARGE" => OBSERVATION_TOO_LARGE,
            "SESSION_NOT_FOUND" => SESSION_NOT_FOUND,
            "PAGE_NOT_FOUND" => PAGE_NOT_FOUND,
            "PAGE_MISMATCH" => PAGE_MISMATCH,
            "PROXY_NOT_FOUND" => PROXY_NOT_FOUND,
            "ACTIVE_PAGE_NOT_FOUND" => ACTIVE_PAGE_NOT_FOUND,
            "CONFLICT" => CONFLICT,
            "BROWSER_BUSY" => BROWSER_BUSY,
            "NETWORK_PAUSED" => NETWORK_PAUSED,
            "ACTION_TARGET_NOT_FOUND" => ACTION_TARGET_NOT_FOUND,
            "REQUEST_CANCELLED" => REQUEST_CANCELLED,
            "RATE_LIMITED" => RATE_LIMITED,
            "ACTION_TIMEOUT" => ACTION_TIMEOUT,
            "OBSERVATION_STALE" => OBSERVATION_STALE,
            "PRO_REQUIRED" => PRO_REQUIRED,
            "UPSTREAM_UNAVAILABLE" => UPSTREAM_UNAVAILABLE,
            "BROWSER_UNAVAILABLE" => BROWSER_UNAVAILABLE,
            "AGENT_UNHEALTHY" => AGENT_UNHEALTHY,
            "TIMEOUT" => TIMEOUT,
            "PROXY_CONFIGURATION_FAILED" => PROXY_CONFIGURATION_FAILED,
            "BROWSER_CREATION_FAILED" => BROWSER_CREATION_FAILED,
            "SEMANTIC_EXTRACTION_FAILED" => SEMANTIC_EXTRACTION_FAILED,
            _ => INTERNAL_ERROR,
        }
    }

    pub fn is_valid(id: &str, code: u32) -> bool {
        if code < MINIMUM {
            return false;
        }
        let expected = for_id(id);
        (expected == INTERNAL_ERROR && id != "INTERNAL_ERROR") || code == expected
    }
}

#[derive(Clone, Debug)]
pub struct RelClient {
    base_url: String,
    request_timeout: Duration,
}

impl RelClient {
    /// Connect to the standard loopback REL RPC v1 endpoint.
    pub fn local() -> Self {
        let port = std::env::var("REL_AGENT_PORT")
            .ok()
            .and_then(|value| value.parse::<u16>().ok())
            .filter(|port| *port > 0)
            .unwrap_or(DEFAULT_AGENT_PORT);
        Self::new(format!("http://127.0.0.1:{port}/v1"))
    }

    /// Connect to an explicit RPC v1 base URL, such as
    /// `http://127.0.0.1:17319/v1`.
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into().trim_end_matches('/').to_string(),
            request_timeout: DEFAULT_REQUEST_TIMEOUT,
        }
    }

    pub fn with_request_timeout(mut self, timeout: Duration) -> Self {
        self.request_timeout = timeout;
        self
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn health(&self) -> Result<RpcResponse<Health>, ClientError> {
        self.request::<Health, Value>("GET", "/health", None)
    }

    pub fn status(&self) -> Result<RpcResponse<StatusReport>, ClientError> {
        self.request::<StatusReport, Value>("GET", "/status", None)
    }

    /// List the bounded in-memory queue of website notifications that the user
    /// explicitly opted in to share with agents.
    pub fn list_notifications(
        &self,
    ) -> Result<RpcResponse<BrowserNotificationListData>, ClientError> {
        self.request::<BrowserNotificationListData, Value>("GET", "/notifications", None)
    }

    pub fn capture(&self, request: &CaptureRequest) -> Result<CaptureStream, ClientError> {
        let timeout = capture_request_timeout(request);
        let response = self.send("POST", "/captures", Some(request), timeout)?;
        match response {
            SentResponse::Success(response) => CaptureStream::from_response(response),
            SentResponse::Failure { status, response } => Err(parse_rpc_failure(status, response)),
        }
    }

    pub fn navigate(
        &self,
        request: &NavigateRequest,
    ) -> Result<RpcResponse<PageOperationData>, ClientError> {
        self.request_with_timeout(
            "POST",
            "/navigate",
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    pub fn perform(
        &self,
        request: &PerformRequest,
    ) -> Result<RpcResponse<PageOperationData>, ClientError> {
        self.request_with_timeout(
            "POST",
            "/perform",
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    pub fn capture_current_page(
        &self,
        request: &PageCaptureRequest,
    ) -> Result<RpcResponse<PageOperationData>, ClientError> {
        self.request_with_timeout(
            "POST",
            "/capture",
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    pub fn screenshot_current_page(
        &self,
        request: &ScreenshotRequest,
    ) -> Result<RpcResponse<ScreenshotOperationData>, ClientError> {
        self.request_with_timeout(
            "POST",
            "/screenshot",
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    /// Observe the current shorthand page using compact rendered semantics and,
    /// for hybrid or visual mode, a synchronized viewport screenshot.
    pub fn observe_current_page(
        &self,
        request: &ObservationRequest,
    ) -> Result<RpcResponse<ObservationOperationData>, ClientError> {
        self.request_with_timeout(
            "POST",
            "/observe",
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    /// Navigate in embedded Chromium and return the first synchronized page
    /// observation without requiring a separate observe request.
    pub fn navigate_and_observe(
        &self,
        request: &NavigateObservationRequest,
    ) -> Result<RpcResponse<ObservationOperationData>, ClientError> {
        self.request_with_timeout(
            "POST",
            "/navigate/observe",
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    /// Read either a URL or the current shorthand page as bounded,
    /// query-directed Markdown. This is a semantic-only convenience over the
    /// canonical `/navigate/observe` and `/observe` RPC v1 operations.
    pub fn read_page(
        &self,
        request: &PageReadRequest,
    ) -> Result<RpcResponse<PageReadData>, ClientError> {
        let (max_chars, max_sections) = page_read_limits(request.max_chars, request.max_sections)?;

        let response = if let Some(url) = request.url.as_deref() {
            self.navigate_and_observe(&NavigateObservationRequest {
                url: Some(url.to_string()),
                session_id: request.session_id.clone(),
                profile: request.profile.clone(),
                proxy: request.proxy.clone(),
                mode: Some(ObservationMode::Semantic),
                timeout: request.timeout,
                wait: request.wait,
                ..NavigateObservationRequest::default()
            })?
        } else {
            if request.profile.is_some() || request.proxy.is_some() {
                return Err(ClientError::Protocol(
                    "profile and proxy require a URL when reading a page".to_string(),
                ));
            }
            self.observe_current_page(&ObservationRequest {
                session_id: request.session_id.clone(),
                mode: Some(ObservationMode::Semantic),
                timeout: request.timeout,
                wait: request.wait,
            })?
        };

        let RpcResponse {
            status,
            request_id,
            data,
        } = response;
        Ok(RpcResponse {
            status,
            request_id,
            data: page_read_data(data, request.query.as_deref(), max_chars, max_sections),
        })
    }

    /// Return one retained public semantic observation. Interaction references
    /// may be stale after navigation; use this operation only for reading.
    pub fn get_observation(
        &self,
        observation_id: &str,
    ) -> Result<RpcResponse<ObservationOperationData>, ClientError> {
        self.request::<ObservationOperationData, Value>(
            "GET",
            &format!("/observations/{}", encode_path_segment(observation_id)),
            None,
        )
    }

    /// Re-read one retained public observation as bounded, query-directed
    /// Markdown without navigating the browser again.
    pub fn read_observation(
        &self,
        observation_id: &str,
        request: &ObservationReadRequest,
    ) -> Result<RpcResponse<PageReadData>, ClientError> {
        let (max_chars, max_sections) = page_read_limits(request.max_chars, request.max_sections)?;
        let RpcResponse {
            status,
            request_id,
            data,
        } = self.get_observation(observation_id)?;
        Ok(RpcResponse {
            status,
            request_id,
            data: page_read_data(data, request.query.as_deref(), max_chars, max_sections),
        })
    }

    pub fn attach_page(
        &self,
        request: &PageAttachRequest,
    ) -> Result<RpcResponse<PageOperationData>, ClientError> {
        self.request_with_timeout(
            "POST",
            "/pages",
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    pub fn perform_page_action(
        &self,
        page_id: &str,
        request: &PageActionRequest,
    ) -> Result<RpcResponse<PageOperationData>, ClientError> {
        let path = format!("/pages/{}/actions", encode_path_segment(page_id));
        self.request_with_timeout(
            "POST",
            &path,
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    pub fn take_page_screenshot(
        &self,
        page_id: &str,
        request: &PageScreenshotRequest,
    ) -> Result<RpcResponse<ScreenshotOperationData>, ClientError> {
        let path = format!("/pages/{}/screenshot", encode_path_segment(page_id));
        self.request_with_timeout(
            "POST",
            &path,
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    /// Observe an attached page.
    pub fn observe_page(
        &self,
        page_id: &str,
        request: &PageObservationRequest,
    ) -> Result<RpcResponse<ObservationOperationData>, ClientError> {
        let path = format!("/pages/{}/observe", encode_path_segment(page_id));
        self.request_with_timeout(
            "POST",
            &path,
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    /// Perform an allowlisted action through a reference from one observation.
    /// The response always contains a new post-action observation.
    pub fn perform_observation_action(
        &self,
        observation_id: &str,
        request: &ObservationActionRequest,
    ) -> Result<RpcResponse<ObservationOperationData>, ClientError> {
        let path = format!(
            "/observations/{}/actions",
            encode_path_segment(observation_id)
        );
        self.request_with_timeout(
            "POST",
            &path,
            Some(request),
            page_request_timeout(request.timeout, request.wait),
        )
    }

    /// Search one stored observation's public semantic snapshot.
    pub fn find_in_observation(
        &self,
        observation_id: &str,
        request: &ObservationFindRequest,
    ) -> Result<RpcResponse<ObservationFindData>, ClientError> {
        let path = format!("/observations/{}/find", encode_path_segment(observation_id));
        self.request("POST", &path, Some(request))
    }

    pub fn list_proxies(&self) -> Result<RpcResponse<ProxyListData>, ClientError> {
        self.request::<ProxyListData, Value>("GET", "/proxies", None)
    }

    pub fn get_proxy(&self, alias: &str) -> Result<RpcResponse<ProxyData>, ClientError> {
        self.request::<ProxyData, Value>(
            "GET",
            &format!("/proxies/{}", encode_path_segment(alias)),
            None,
        )
    }

    pub fn create_proxy(
        &self,
        request: &ProxyCreateRequest,
    ) -> Result<RpcResponse<ProxyData>, ClientError> {
        self.request("POST", "/proxies", Some(request))
    }

    pub fn update_proxy(
        &self,
        alias: &str,
        request: &ProxyUpdateRequest,
    ) -> Result<RpcResponse<ProxyData>, ClientError> {
        self.request(
            "PATCH",
            &format!("/proxies/{}", encode_path_segment(alias)),
            Some(request),
        )
    }

    pub fn delete_proxy(&self, alias: &str) -> Result<RpcResponse<ProxyDeletedData>, ClientError> {
        self.request::<ProxyDeletedData, Value>(
            "DELETE",
            &format!("/proxies/{}", encode_path_segment(alias)),
            None,
        )
    }

    pub fn rotate_proxy_session(&self, alias: &str) -> Result<RpcResponse<ProxyData>, ClientError> {
        self.request::<ProxyData, Value>(
            "POST",
            &format!("/proxies/{}/rotate-session", encode_path_segment(alias)),
            None,
        )
    }

    pub fn export_proxy_transfer(
        &self,
        request: &ProxyTransferExportRequest,
    ) -> Result<RpcResponse<TransferExportData>, ClientError> {
        self.request("POST", "/proxy-transfers/export", Some(request))
    }

    pub fn import_proxy_transfer(
        &self,
        request: &ProxyTransferImportRequest,
    ) -> Result<RpcResponse<ProxyData>, ClientError> {
        self.request("POST", "/proxy-transfers/import", Some(request))
    }

    pub fn list_sessions(&self) -> Result<RpcResponse<SessionListData>, ClientError> {
        self.request::<SessionListData, Value>("GET", "/sessions", None)
    }

    pub fn get_session(&self, id: &str) -> Result<RpcResponse<SessionData>, ClientError> {
        self.request::<SessionData, Value>(
            "GET",
            &format!("/sessions/{}", encode_path_segment(id)),
            None,
        )
    }

    /// Refresh a session's inactivity timer without performing browser work.
    pub fn ping_session(&self, id: &str) -> Result<RpcResponse<SessionData>, ClientError> {
        self.request(
            "POST",
            &format!("/sessions/{}/ping", encode_path_segment(id)),
            Some(&serde_json::json!({})),
        )
    }

    pub fn create_session(
        &self,
        request: &SessionCreateRequest,
    ) -> Result<RpcResponse<SessionData>, ClientError> {
        self.request("POST", "/sessions", Some(request))
    }

    pub fn list_profiles(&self) -> Result<RpcResponse<ProfileListData>, ClientError> {
        self.request::<ProfileListData, Value>("GET", "/profiles", None)
    }

    pub fn create_profile(
        &self,
        request: &ProfileCreateRequest,
    ) -> Result<RpcResponse<ProfileData>, ClientError> {
        self.request("POST", "/profiles", Some(request))
    }

    pub fn update_profile_data(
        &self,
        id: &str,
        request: &ProfileDataUpdateRequest,
    ) -> Result<RpcResponse<ProfileData>, ClientError> {
        self.request(
            "PATCH",
            &format!("/profiles/{}", encode_path_segment(id)),
            Some(request),
        )
    }

    pub fn delete_profile(&self, id: &str) -> Result<RpcResponse<DeletedData>, ClientError> {
        self.request::<DeletedData, Value>(
            "DELETE",
            &format!("/profiles/{}", encode_path_segment(id)),
            None,
        )
    }

    pub fn export_profile_transfer(
        &self,
        request: &ProfileTransferExportRequest,
    ) -> Result<RpcResponse<TransferExportData>, ClientError> {
        self.request("POST", "/profile-transfers/export", Some(request))
    }

    pub fn import_profile_transfer(
        &self,
        request: &ProfileTransferImportRequest,
    ) -> Result<RpcResponse<ProfileData>, ClientError> {
        self.request("POST", "/profile-transfers/import", Some(request))
    }

    pub fn update_session(
        &self,
        id: &str,
        request: &SessionUpdateRequest,
    ) -> Result<RpcResponse<SessionData>, ClientError> {
        self.request(
            "PATCH",
            &format!("/sessions/{}", encode_path_segment(id)),
            Some(request),
        )
    }

    /// Pause all network activity in a persistent browser session.
    pub fn pause_session(
        &self,
        id: &str,
    ) -> Result<RpcResponse<SessionNetworkStateData>, ClientError> {
        self.request::<SessionNetworkStateData, Value>(
            "POST",
            &format!("/sessions/{}/pause", encode_path_segment(id)),
            None,
        )
    }

    /// Resume network activity and reload the current page when needed.
    pub fn play_session(
        &self,
        id: &str,
    ) -> Result<RpcResponse<SessionNetworkStateData>, ClientError> {
        self.request::<SessionNetworkStateData, Value>(
            "POST",
            &format!("/sessions/{}/play", encode_path_segment(id)),
            None,
        )
    }

    pub fn delete_session(&self, id: &str) -> Result<RpcResponse<DeletedData>, ClientError> {
        self.request::<DeletedData, Value>(
            "DELETE",
            &format!("/sessions/{}", encode_path_segment(id)),
            None,
        )
    }

    pub fn close_session_group(
        &self,
        group: &str,
    ) -> Result<RpcResponse<ClosedSessionGroupData>, ClientError> {
        self.request(
            "POST",
            "/sessions/close",
            Some(&SessionGroupCloseRequest { group }),
        )
    }

    fn request<T, B>(
        &self,
        method: &str,
        path: &str,
        body: Option<&B>,
    ) -> Result<RpcResponse<T>, ClientError>
    where
        T: DeserializeOwned,
        B: Serialize + ?Sized,
    {
        self.request_with_timeout(method, path, body, self.request_timeout)
    }

    fn request_with_timeout<T, B>(
        &self,
        method: &str,
        path: &str,
        body: Option<&B>,
        timeout: Duration,
    ) -> Result<RpcResponse<T>, ClientError>
    where
        T: DeserializeOwned,
        B: Serialize + ?Sized,
    {
        match self.send(method, path, body, timeout)? {
            SentResponse::Success(response) => parse_rpc_success(response),
            SentResponse::Failure { status, response } => Err(parse_rpc_failure(status, response)),
        }
    }

    fn send<B>(
        &self,
        method: &str,
        path: &str,
        body: Option<&B>,
        timeout: Duration,
    ) -> Result<SentResponse, ClientError>
    where
        B: Serialize + ?Sized,
    {
        if self.base_url.is_empty() {
            return Err(ClientError::Protocol(
                "REL RPC base URL cannot be empty".to_string(),
            ));
        }
        let url = format!("{}{}", self.base_url, path);
        let request = ureq::request(method, &url)
            .set("Accept", "application/json, application/x-ndjson")
            .timeout(timeout);
        let result = match body {
            Some(body) => {
                let body = serde_json::to_string(body).map_err(ClientError::Json)?;
                request
                    .set("Content-Type", "application/json")
                    .send_string(&body)
            }
            None => request.call(),
        };
        match result {
            Ok(response) => Ok(SentResponse::Success(response)),
            Err(ureq::Error::Status(status, response)) => {
                Ok(SentResponse::Failure { status, response })
            }
            Err(ureq::Error::Transport(error)) => Err(ClientError::Transport(error.to_string())),
        }
    }
}

enum SentResponse {
    Success(ureq::Response),
    Failure {
        status: u16,
        response: ureq::Response,
    },
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct RpcResponse<T> {
    pub status: String,
    pub request_id: String,
    pub data: T,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct RpcFailure {
    pub status: String,
    pub request_id: String,
    pub error: RpcError,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct RpcError {
    pub id: String,
    pub code: u32,
    pub message: String,
    pub retryable: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<Value>,
}

impl fmt::Display for RpcError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}: {}", self.id, self.message)
    }
}

impl std::error::Error for RpcError {}

#[derive(Debug)]
pub enum ClientError {
    Transport(String),
    Protocol(String),
    Rpc(Box<RpcFailure>),
    Io(io::Error),
    Json(serde_json::Error),
}

impl ClientError {
    pub fn rpc_failure(&self) -> Option<&RpcFailure> {
        match self {
            Self::Rpc(failure) => Some(failure),
            _ => None,
        }
    }
}

impl fmt::Display for ClientError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Transport(message) | Self::Protocol(message) => formatter.write_str(message),
            Self::Rpc(failure) => failure.error.fmt(formatter),
            Self::Io(error) => error.fmt(formatter),
            Self::Json(error) => error.fmt(formatter),
        }
    }
}

impl std::error::Error for ClientError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Rpc(failure) => Some(&failure.error),
            Self::Io(error) => Some(error),
            Self::Json(error) => Some(error),
            Self::Transport(_) | Self::Protocol(_) => None,
        }
    }
}

impl From<io::Error> for ClientError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

fn parse_rpc_success<T: DeserializeOwned>(
    response: ureq::Response,
) -> Result<RpcResponse<T>, ClientError> {
    validate_json_content_type(&response)?;
    let header_request_id = response.header("X-Request-Id").map(str::to_string);
    let body = response.into_string().map_err(ClientError::Io)?;
    let envelope = serde_json::from_str::<RpcResponse<T>>(&body).map_err(ClientError::Json)?;
    if envelope.status != "ok" {
        return Err(ClientError::Protocol(format!(
            "REL RPC success response has status {:?}",
            envelope.status
        )));
    }
    validate_request_id(header_request_id.as_deref(), &envelope.request_id)?;
    Ok(envelope)
}

fn parse_rpc_failure(status: u16, response: ureq::Response) -> ClientError {
    if let Err(error) = validate_json_content_type(&response) {
        return error;
    }
    let header_request_id = response.header("X-Request-Id").map(str::to_string);
    let body = match response.into_string() {
        Ok(body) => body,
        Err(error) => return ClientError::Io(error),
    };
    let failure = match serde_json::from_str::<RpcFailure>(&body) {
        Ok(failure) => failure,
        Err(error) => {
            return ClientError::Protocol(format!(
                "REL RPC returned HTTP {status} with an invalid error envelope: {error}"
            ))
        }
    };
    if failure.status != "error" {
        return ClientError::Protocol(format!(
            "REL RPC error response has status {:?}",
            failure.status
        ));
    }
    if let Err(error) = validate_request_id(header_request_id.as_deref(), &failure.request_id) {
        return error;
    }
    if failure.error.id.trim().is_empty()
        || !rpc_error_codes::is_valid(&failure.error.id, failure.error.code)
        || failure.error.message.trim().is_empty()
    {
        return ClientError::Protocol(
            "REL RPC error response has an incomplete error object".to_string(),
        );
    }
    if failure
        .error
        .details
        .as_ref()
        .is_some_and(|details| !details.is_object())
    {
        return ClientError::Protocol("REL RPC error details must be a JSON object".to_string());
    }
    ClientError::Rpc(Box::new(failure))
}

fn validate_json_content_type(response: &ureq::Response) -> Result<(), ClientError> {
    let content_type = response.header("Content-Type").unwrap_or_default();
    if content_type
        .to_ascii_lowercase()
        .starts_with("application/json")
    {
        Ok(())
    } else {
        Err(ClientError::Protocol(format!(
            "REL RPC returned unsupported Content-Type {content_type:?}"
        )))
    }
}

fn validate_request_id(header: Option<&str>, body: &str) -> Result<(), ClientError> {
    if body.trim().is_empty() {
        return Err(ClientError::Protocol(
            "REL RPC response is missing request_id".to_string(),
        ));
    }
    match header {
        Some(header) if header == body => Ok(()),
        Some(header) => Err(ClientError::Protocol(format!(
            "REL RPC request ID mismatch: header {header:?}, body {body:?}"
        ))),
        None => Err(ClientError::Protocol(
            "REL RPC response is missing X-Request-Id".to_string(),
        )),
    }
}

type ResponseReader = Box<dyn Read + Send + Sync + 'static>;

pub struct CaptureStream {
    request_id: String,
    lines: Lines<BufReader<ResponseReader>>,
    exit_code: Option<i32>,
    finished: bool,
}

impl CaptureStream {
    fn from_response(response: ureq::Response) -> Result<Self, ClientError> {
        let content_type = response.header("Content-Type").unwrap_or_default();
        if !content_type
            .to_ascii_lowercase()
            .starts_with("application/x-ndjson")
        {
            return Err(ClientError::Protocol(format!(
                "REL capture returned unsupported Content-Type {content_type:?}"
            )));
        }
        let request_id = response
            .header("X-Request-Id")
            .filter(|value| !value.trim().is_empty())
            .ok_or_else(|| {
                ClientError::Protocol("REL capture response is missing X-Request-Id".to_string())
            })?
            .to_string();
        Ok(Self {
            request_id,
            lines: BufReader::new(response.into_reader()).lines(),
            exit_code: None,
            finished: false,
        })
    }

    pub fn request_id(&self) -> &str {
        &self.request_id
    }

    /// Available after `capture.finished` has been read.
    pub fn exit_code(&self) -> Option<i32> {
        self.exit_code
    }

    pub fn is_finished(&self) -> bool {
        self.finished
    }
}

impl Iterator for CaptureStream {
    type Item = Result<CaptureEvent, ClientError>;

    fn next(&mut self) -> Option<Self::Item> {
        let line = loop {
            match self.lines.next()? {
                Ok(line) if line.trim().is_empty() => continue,
                Ok(line) => break line,
                Err(error) => return Some(Err(ClientError::Io(error))),
            }
        };
        let event = match serde_json::from_str::<CaptureEvent>(&line) {
            Ok(event) => event,
            Err(error) => return Some(Err(ClientError::Json(error))),
        };
        if event.request_id != self.request_id {
            return Some(Err(ClientError::Protocol(format!(
                "REL capture request ID mismatch: header {:?}, event {:?}",
                self.request_id, event.request_id
            ))));
        }
        if event.event.trim().is_empty() {
            return Some(Err(ClientError::Protocol(
                "REL capture event is missing its event name".to_string(),
            )));
        }
        match event.status.as_str() {
            "ok" if event.data.is_some() && event.error.is_none() => {}
            "error"
                if event.error.as_ref().is_some_and(|error| {
                    !error.id.trim().is_empty()
                        && rpc_error_codes::is_valid(&error.id, error.code)
                        && !error.message.trim().is_empty()
                }) => {}
            _ => {
                return Some(Err(ClientError::Protocol(format!(
                    "REL capture event {:?} has an invalid envelope",
                    event.event
                ))))
            }
        }
        if event.event == "capture.finished" {
            let exit_code = event
                .data
                .as_ref()
                .and_then(|data| data.get("exit_code"))
                .and_then(Value::as_i64)
                .and_then(|code| i32::try_from(code).ok());
            let Some(exit_code) = exit_code else {
                return Some(Err(ClientError::Protocol(
                    "REL capture.finished event is missing a valid exit_code".to_string(),
                )));
            };
            self.exit_code = Some(exit_code);
            self.finished = true;
        }
        Some(Ok(event))
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct CaptureEvent {
    pub status: String,
    pub request_id: String,
    pub event: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<RpcError>,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct CaptureRequest {
    pub url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub actions: Vec<Action>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retry: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retry_delay: Option<f64>,
}

impl CaptureRequest {
    pub fn new(url: impl Into<String>) -> Self {
        Self {
            url: url.into(),
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct NavigateRequest {
    pub url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

impl NavigateRequest {
    pub fn new(url: impl Into<String>) -> Self {
        Self {
            url: url.into(),
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(tag = "action", rename_all = "kebab-case")]
pub enum Action {
    Click {
        selector: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        mouse_move: Option<bool>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        scroll: Option<bool>,
    },
    WaitFor {
        selector: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        timeout: Option<f64>,
    },
    Type {
        selector: String,
        text: String,
    },
    Clear {
        selector: String,
    },
    Press {
        selector: String,
        key: String,
    },
    Select {
        selector: String,
        value: String,
    },
    ClickLink {
        link: String,
        #[serde(rename = "match")]
        match_rule: FuzzyLinkMatch,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        mouse_move: Option<bool>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        scroll: Option<bool>,
    },
    Wait {
        seconds: f64,
    },
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct FuzzyLinkMatch {
    #[serde(rename = "type")]
    kind: FuzzyLinkMatchType,
    pub threshold: f64,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
enum FuzzyLinkMatchType {
    #[serde(rename = "fuzzy-link")]
    FuzzyLink,
}

impl FuzzyLinkMatch {
    pub fn new(threshold: f64) -> Self {
        Self {
            kind: FuzzyLinkMatchType::FuzzyLink,
            threshold,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct PageAttachRequest {
    pub url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

impl PageAttachRequest {
    pub fn new(url: impl Into<String>) -> Self {
        Self {
            url: url.into(),
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct PageActionRequest {
    pub action: Action,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

impl PageActionRequest {
    pub fn new(action: Action) -> Self {
        Self {
            action,
            output: None,
            timeout: None,
            wait: None,
        }
    }
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct PerformRequest {
    pub actions: Vec<Action>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

impl PerformRequest {
    pub fn new(actions: Vec<Action>) -> Self {
        Self {
            actions,
            session_id: None,
            output: None,
            timeout: None,
            wait: None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct PageCaptureRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct PageOperationData {
    pub page: Page,
    pub capture: PageCapture,
    #[serde(default)]
    pub closed_session_ids: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Page {
    pub id: String,
    pub session_id: String,
    pub url: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct PageCapture {
    pub output_path: String,
    pub bytesize: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_http_status: Option<u16>,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ScreenshotFormat {
    Png,
    Jpeg,
    Webp,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct ScreenshotRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<ScreenshotFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub quality: Option<u8>,
    #[serde(default)]
    pub full_page: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct PageScreenshotRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<ScreenshotFormat>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub quality: Option<u8>,
    #[serde(default)]
    pub full_page: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ScreenshotOperationData {
    pub page: Page,
    pub screenshot: ScreenshotCapture,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ScreenshotCapture {
    pub output_path: String,
    pub bytesize: usize,
    pub format: ScreenshotFormat,
    pub mime_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub width: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<u32>,
}

/// Public observation modalities. `auto` is intentionally an AI-harness
/// policy and is not accepted by RPC v1.
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ObservationMode {
    #[default]
    Semantic,
    Hybrid,
    Visual,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct ObservationRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<ObservationMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct NavigateObservationRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub navigation: Option<ObservationNavigation>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<ObservationMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

impl NavigateObservationRequest {
    pub fn new(url: impl Into<String>) -> Self {
        Self {
            url: Some(url.into()),
            ..Self::default()
        }
    }
}

/// Parameters for a bounded semantic read of either a URL or the current
/// shorthand page.
#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct PageReadRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_chars: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_sections: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct ObservationReadRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_chars: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_sections: Option<usize>,
}

impl PageReadRequest {
    pub fn new(url: impl Into<String>) -> Self {
        Self {
            url: Some(url.into()),
            ..Self::default()
        }
    }
}

/// A compact page representation intended for research and reading rather
/// than interaction. Use an observation when action references are needed.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct PageReadData {
    pub page: Page,
    pub observation_id: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query: Option<String>,
    pub markdown: String,
    pub selected_outline_count: usize,
    pub selected_content_count: usize,
    pub selected_link_count: usize,
    pub available_content_count: usize,
    pub available_link_count: usize,
    pub source_truncated: bool,
    pub truncated: bool,
    pub matched_query: bool,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ObservationNavigation {
    Url,
    Back,
    Forward,
    Reload,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct PageObservationRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<ObservationMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum ObservationActionKind {
    Click,
    Type,
    Clear,
    Press,
    Select,
    Hover,
    Scroll,
    Wait,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct ObservationAction {
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "ref")]
    pub element_ref: Option<String>,
    pub action: ObservationActionKind,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mouse_move: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scroll: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Native horizontal wheel delta. Negative scrolls right; positive scrolls left.
    pub delta_x: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    /// Native vertical wheel delta. Negative scrolls down; positive scrolls up.
    pub delta_y: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seconds: Option<f64>,
}

impl ObservationAction {
    pub fn new(element_ref: impl Into<String>, action: ObservationActionKind) -> Self {
        Self {
            element_ref: Some(element_ref.into()),
            action,
            text: None,
            key: None,
            value: None,
            mouse_move: None,
            scroll: None,
            delta_x: None,
            delta_y: None,
            seconds: None,
        }
    }

    pub fn scroll(delta_x: i32, delta_y: i32) -> Self {
        Self {
            element_ref: None,
            action: ObservationActionKind::Scroll,
            text: None,
            key: None,
            value: None,
            mouse_move: None,
            scroll: None,
            delta_x: Some(delta_x),
            delta_y: Some(delta_y),
            seconds: None,
        }
    }

    pub fn wait(seconds: f64) -> Self {
        Self {
            element_ref: None,
            action: ObservationActionKind::Wait,
            text: None,
            key: None,
            value: None,
            mouse_move: None,
            scroll: None,
            delta_x: None,
            delta_y: None,
            seconds: Some(seconds),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationActionRequest {
    pub actions: Vec<ObservationAction>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<ObservationMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timeout: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub wait: Option<f64>,
}

impl ObservationActionRequest {
    pub fn new(element_ref: impl Into<String>, action: ObservationActionKind) -> Self {
        Self {
            actions: vec![ObservationAction::new(element_ref, action)],
            mode: None,
            timeout: None,
            wait: None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct ObservationFindRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<usize>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationFindData {
    pub observation_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    pub matches: Vec<ObservationFindMatch>,
    pub total_matches: usize,
    pub truncated: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ObservationFindMatch {
    Content {
        index: usize,
        content: ObservationContent,
    },
    Element {
        element: ObservationElement,
    },
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationOperationData {
    pub page: Page,
    pub observation: PageObservation,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct PageObservation {
    pub id: String,
    pub mode: ObservationMode,
    pub document_sequence: u64,
    pub captured_at: String,
    pub title: String,
    pub truncated: bool,
    pub omitted_node_count: usize,
    pub clipped_text_count: usize,
    pub visited_node_count: usize,
    pub semantic_bytes: usize,
    pub viewport: ObservationViewport,
    pub content: Vec<ObservationContent>,
    pub elements: Vec<ObservationElement>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub screenshot: Option<ObservationScreenshot>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationViewport {
    pub css_width: u32,
    pub css_height: u32,
    pub scroll_x: u32,
    pub scroll_y: u32,
    pub document_width: u32,
    pub document_height: u32,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationContent {
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub level: Option<u8>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub context: Option<String>,
    pub text: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationElement {
    #[serde(rename = "ref")]
    pub element_ref: String,
    pub role: String,
    pub name: String,
    pub states: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub destination: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub context: Option<String>,
    pub in_viewport: bool,
    pub bounds: ObservationBounds,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationBounds {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ObservationScreenshot {
    pub output_path: String,
    pub bytesize: usize,
    pub format: ScreenshotFormat,
    pub mime_type: String,
    pub width: u32,
    pub height: u32,
    pub css_to_image_scale_x: f64,
    pub css_to_image_scale_y: f64,
}

fn page_read_data(
    data: ObservationOperationData,
    query: Option<&str>,
    max_chars: usize,
    max_sections: usize,
) -> PageReadData {
    let ObservationOperationData { page, observation } = data;
    let normalized_query = query.map(str::trim).filter(|value| !value.is_empty());
    let terms = page_read_query_terms(normalized_query.unwrap_or_default());
    let query_active = normalized_query.is_some();

    let scored_content = observation
        .content
        .iter()
        .enumerate()
        .map(|(index, item)| {
            let mut score =
                page_read_match_score(&item.text, normalized_query, &terms, item.kind == "heading")
                    .max(page_read_named_context_score(
                        item.context.as_deref(),
                        normalized_query,
                    ));
            if page_read_query_requests_ratings(&terms) && page_read_text_is_rating(&item.text) {
                score = score.max(2);
            }
            (index, score)
        })
        .collect::<Vec<_>>();
    let content_matched = query_active && scored_content.iter().any(|(_, score)| *score > 0);
    let mut content = if content_matched {
        let mut ranked = scored_content
            .iter()
            .copied()
            .filter(|(_, score)| *score > 0)
            .collect::<Vec<_>>();
        ranked.sort_by_key(|(index, score)| (std::cmp::Reverse(*score), *index));
        page_read_matched_content_with_context(&observation.content, &ranked)
    } else if !query_active {
        page_read_coverage_content(&observation.content, max_sections)
    } else {
        Vec::new()
    };
    let available_content_count = if query_active {
        content.len()
    } else {
        observation.content.len()
    };
    if !query_active {
        content.truncate(max_sections);
    }

    let mut links = page_read_unique_links(&observation.elements, normalized_query, &terms);
    let links_matched = query_active && links.iter().any(|link| link.score > 0);
    if links_matched {
        links.retain(|link| link.score > 0);
        links.sort_by_key(|link| (std::cmp::Reverse(link.score), link.index));
    } else if content_matched {
        links.clear();
    }
    let available_link_count = links.len();
    links.truncate(max_sections);

    let mut markdown = String::new();
    let title = observation.title.trim().to_string();
    let heading = if title.is_empty() {
        page.url.as_str()
    } else {
        title.as_str()
    };
    push_page_read_block(
        &mut markdown,
        &format!("# {}", escape_markdown_text(heading)),
        max_chars,
    );
    push_page_read_block(
        &mut markdown,
        &format!("Source: <{}>", escape_markdown_url(&page.url)),
        max_chars,
    );
    if let Some(query) = normalized_query {
        push_page_read_block(
            &mut markdown,
            &format!("Query: {}", escape_markdown_text(query)),
            max_chars,
        );
    }

    if query_active {
        push_page_read_block(&mut markdown,
            &format!("Query scope: {} candidate blocks of {} captured blocks. Counts describe matches and structural context, not whole-page coverage.", available_content_count, observation.content.len()), max_chars);
    }

    let viewport = &observation.viewport;
    push_page_read_block(
        &mut markdown,
        &format!(
            "Snapshot: {} / document {}. Viewport: {}×{} at {},{} of {}×{}.",
            escape_markdown_text(&observation.captured_at),
            observation.document_sequence,
            viewport.css_width,
            viewport.css_height,
            viewport.scroll_x,
            viewport.scroll_y,
            viewport.document_width,
            viewport.document_height,
        ),
        max_chars,
    );

    if query_active {
        // Budget the ranked windows before arranging their retained blocks for
        // reading. Otherwise early weak matches can exhaust either limit before
        // a precise match near the end of the document is ever rendered.
        let mut remaining_chars = max_chars.saturating_sub(markdown.chars().count());
        let mut retained = 0;
        content.retain(|(index, _)| {
            if retained == max_sections {
                return false;
            }
            let item = &observation.content[*index];
            let (body, _) = page_read_content_body(item, &observation.elements, &links, max_chars);
            let context = page_read_context(item.context.as_deref());
            // Charge every block for a context transition, including a reset to
            // unspecified context. Document-order rendering can only cost less.
            let previous = context.is_none().then_some("previous context");
            let block = page_read_with_context(&body, context, previous);
            let (block, _) = page_read_bounded_content_block(block, max_chars);
            let cost = block.chars().count() + 2;
            if cost > remaining_chars {
                return false;
            }
            remaining_chars -= cost;
            retained += 1;
            true
        });
        content.sort_by_key(|(index, _)| *index);
    }

    let mut selected_content_count = 0;
    let mut selected_link_count = 0;
    let mut emitted_links = BTreeSet::new();
    let mut emitted_headings = BTreeSet::new();
    let mut last_context = None;
    let mut output_truncated = false;
    for (index, _) in &content {
        let item = &observation.content[*index];
        let context = page_read_context(item.context.as_deref());
        let (mut body, mut inline) =
            page_read_content_body(item, &observation.elements, &links, max_chars);
        if inline.is_some_and(|index| emitted_links.contains(&index)) {
            body = page_read_content_markdown(item);
            inline = None;
        }
        let block = page_read_with_context(&body, context, last_context);
        let (block, block_clipped) = page_read_bounded_content_block(block, max_chars);
        let (added, clipped) = push_page_read_excerpt(&mut markdown, &block, max_chars);
        output_truncated |= block_clipped || clipped;
        if added {
            selected_content_count += 1;
            last_context = context;
            if !block_clipped && !clipped {
                if item.kind == "heading" {
                    emitted_headings.insert(*index);
                }
                if let Some(index) = inline {
                    emitted_links.insert(index);
                    selected_link_count += 1;
                }
            }
        }
    }

    // A selected heading already supplies its outline information. Render only
    // additional headings, after content so an outline cannot crowd out prose.
    let outline = page_read_outline(&observation.content, max_sections.min(16))
        .into_iter()
        .filter(|index| !emitted_headings.contains(index))
        .collect::<Vec<_>>();
    let mut selected_outline_count = 0;
    if !outline.is_empty()
        && push_page_read_block(&mut markdown, "## Other page headings", max_chars)
    {
        for index in outline {
            let heading = &observation.content[index];
            let indent = "  ".repeat(heading.level.unwrap_or(2).saturating_sub(2) as usize);
            let block = format!("{indent}- {}", escape_markdown_text(heading.text.trim()));
            if push_page_read_block(&mut markdown, &block, max_chars) {
                selected_outline_count += 1;
            } else {
                break;
            }
        }
    }

    let remaining_links = links
        .iter()
        .filter(|link| !emitted_links.contains(&link.index))
        .collect::<Vec<_>>();
    if !remaining_links.is_empty() && push_page_read_block(&mut markdown, "## Links", max_chars) {
        last_context = None;
        for link in remaining_links {
            let element = &observation.elements[link.index];
            let context = page_read_context(element.context.as_deref());
            let block = page_read_with_context(
                &format!("- {}", page_read_link_markdown(element, link.in_viewport)),
                context,
                last_context,
            );
            if push_page_read_block(&mut markdown, &block, max_chars) {
                selected_link_count += 1;
                last_context = context;
            } else {
                output_truncated = true;
                break;
            }
        }
    } else if !remaining_links.is_empty() {
        output_truncated = true;
    }

    let content_was_limited = available_content_count > selected_content_count;
    let links_were_limited = available_link_count > selected_link_count;

    PageReadData {
        page,
        observation_id: observation.id,
        title,
        query: normalized_query.map(str::to_string),
        markdown,
        selected_outline_count,
        selected_content_count,
        selected_link_count,
        available_content_count,
        available_link_count,
        source_truncated: observation.truncated,
        truncated: content_was_limited || links_were_limited || output_truncated,
        matched_query: content_matched || links_matched,
    }
}

fn page_read_matched_content_with_context(
    content: &[ObservationContent],
    ranked: &[(usize, usize)],
) -> Vec<(usize, usize)> {
    let mut seen = BTreeSet::new();
    let mut selected = Vec::new();
    for (index, score) in ranked {
        let mut retain = |candidate| {
            if seen.insert(candidate) {
                selected.push((candidate, *score));
            }
        };
        // The match and its context remain together in relevance order until
        // the caller has applied both budgets. Only then use document order.
        retain(*index);
        if *index > 0
            && !matches!(content[*index].kind.as_str(), "heading" | "landmark")
            && content[*index - 1].kind == "text"
            && page_read_context(content[*index - 1].context.as_deref())
                == page_read_context(content[*index].context.as_deref())
        {
            // A definition body may be the lexical hit while the immediately
            // preceding text record supplies its label or API signature.
            retain(*index - 1);
        }
        if let Some(heading) = (0..=*index).rev().find(|candidate| {
            content[*candidate].kind == "heading"
                && page_read_contexts_overlap(
                    content[*candidate].context.as_deref(),
                    content[*index].context.as_deref(),
                )
        }) {
            retain(heading);
        }
        // Labels/headings often name a value whose own words do not match the
        // query. Retain two following blocks, then any continuing prose/list
        // description. This includes definition bodies and platform caveats,
        // stopping before the next text label/signature, heading or landmark.
        // The caller bounds the retained window by characters and sections.
        for (next, neighbor) in content.iter().enumerate().skip(*index + 1) {
            let changes_region = matches!(
                (page_read_context(neighbor.context.as_deref()),
                 page_read_context(content[*index].context.as_deref())),
                (Some(next), Some(current)) if next != current
            );
            if changes_region
                || matches!(neighbor.kind.as_str(), "heading" | "landmark")
                || (next > *index + 2
                    && !matches!(
                        neighbor.kind.as_str(),
                        "paragraph" | "blockquote" | "listitem" | "list_item" | "item"
                    ))
            {
                break;
            }
            retain(next);
        }
        if page_read_text_is_rating(&content[*index].text) && *index > 0 {
            retain(*index - 1);
        }
        if *index > 0 && page_read_text_is_rating(&content[*index - 1].text) {
            retain(*index - 1);
        }
        if *index + 1 < content.len() && page_read_text_is_rating(&content[*index + 1].text) {
            retain(*index + 1);
        }
    }
    selected
}

fn page_read_contexts_overlap(left: Option<&str>, right: Option<&str>) -> bool {
    match (page_read_context(left), page_read_context(right)) {
        (Some(left), Some(right)) => {
            left == right
                || left
                    .strip_prefix(right)
                    .is_some_and(|tail| tail.starts_with(" > "))
                || right
                    .strip_prefix(left)
                    .is_some_and(|tail| tail.starts_with(" > "))
        }
        _ => true,
    }
}

fn page_read_coverage_content(content: &[ObservationContent], limit: usize) -> Vec<(usize, usize)> {
    if content.len() <= limit {
        return (0..content.len()).map(|index| (index, 1)).collect();
    }
    if limit == 1 {
        return vec![(0, 1)];
    }
    let mut selected = BTreeSet::new();
    selected.insert(0);
    selected.insert(content.len() - 1);
    let heading_budget = (limit / 3).clamp(1, 8);
    let headings = content
        .iter()
        .enumerate()
        .filter_map(|(index, item)| (item.kind == "heading").then_some(index))
        .collect::<Vec<_>>();
    for index in evenly_spaced_indices(headings.len(), heading_budget.min(headings.len())) {
        selected.insert(headings[index]);
    }
    for index in evenly_spaced_indices(content.len(), limit) {
        if selected.len() >= limit {
            break;
        }
        selected.insert(index);
    }
    if selected.len() < limit {
        for index in 0..content.len() {
            if selected.len() >= limit {
                break;
            }
            selected.insert(index);
        }
    }
    selected.into_iter().map(|index| (index, 1)).collect()
}

fn evenly_spaced_indices(length: usize, count: usize) -> Vec<usize> {
    match (length, count) {
        (_, 0) | (0, _) => Vec::new(),
        (_, 1) => vec![0],
        _ if count >= length => (0..length).collect(),
        _ => (0..count)
            .map(|slot| slot * (length - 1) / (count - 1))
            .collect(),
    }
}

fn page_read_outline(content: &[ObservationContent], limit: usize) -> Vec<usize> {
    let headings = content
        .iter()
        .enumerate()
        .filter_map(|(index, item)| (item.kind == "heading").then_some(index))
        .collect::<Vec<_>>();
    evenly_spaced_indices(headings.len(), limit.min(headings.len()))
        .into_iter()
        .map(|index| headings[index])
        .collect()
}

fn page_read_limits(
    max_chars: Option<usize>,
    max_sections: Option<usize>,
) -> Result<(usize, usize), ClientError> {
    let max_chars = max_chars.unwrap_or(DEFAULT_PAGE_READ_MAX_CHARS);
    if !(MIN_PAGE_READ_MAX_CHARS..=MAX_PAGE_READ_MAX_CHARS).contains(&max_chars) {
        return Err(ClientError::Protocol(format!(
            "max_chars must be between {MIN_PAGE_READ_MAX_CHARS} and {MAX_PAGE_READ_MAX_CHARS}"
        )));
    }
    let max_sections = max_sections.unwrap_or(DEFAULT_PAGE_READ_MAX_SECTIONS);
    if !(1..=MAX_PAGE_READ_MAX_SECTIONS).contains(&max_sections) {
        return Err(ClientError::Protocol(format!(
            "max_sections must be between 1 and {MAX_PAGE_READ_MAX_SECTIONS}"
        )));
    }
    Ok((max_chars, max_sections))
}

fn page_read_query_terms(query: &str) -> Vec<String> {
    const STOP_WORDS: &[&str] = &[
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is", "it",
        "of", "on", "or", "that", "the", "this", "to", "was", "what", "when", "where", "which",
        "who", "why", "with",
    ];
    let mut terms = query
        .split(|character: char| !character.is_alphanumeric() && !matches!(character, '_' | '.'))
        .map(|term| term.trim_matches('.'))
        .map(str::to_lowercase)
        .filter(|term| term.len() >= 2 && !STOP_WORDS.contains(&term.as_str()))
        .collect::<BTreeSet<_>>();
    let originals = terms.iter().cloned().collect::<Vec<_>>();
    for term in originals {
        // Keep qualified identifiers intact. Their final component can match a
        // separately rendered method name, but the qualifier alone must not
        // turn `Path.copy_into` into a search for every mention of `Path`.
        if let Some((_, member)) = term.rsplit_once('.') {
            if member.len() >= 2 {
                terms.insert(member.to_string());
            }
        }
        match term.as_str() {
            "critic" | "critics" | "rating" | "ratings" | "score" | "scores" => {
                terms.extend(["review", "reviews", "rating", "score"].map(str::to_string));
            }
            "genre" | "genres" => {
                terms.extend(["genre", "genres", "style"].map(str::to_string));
            }
            _ => {}
        }
    }
    terms.into_iter().collect()
}

fn page_read_query_requests_ratings(terms: &[String]) -> bool {
    terms.iter().any(|term| {
        matches!(
            term.as_str(),
            "critic"
                | "critics"
                | "rating"
                | "ratings"
                | "review"
                | "reviews"
                | "score"
                | "scores"
                | "signal"
        )
    })
}

fn page_read_text_is_rating(text: &str) -> bool {
    let text = text.trim();
    if text.parse::<u8>().is_ok_and(|value| value <= 100) {
        return true;
    }
    text.split_whitespace().any(|token| {
        let token = token.trim_matches(|character: char| {
            !character.is_ascii_digit() && !matches!(character, '.' | '/' | '%')
        });
        if let Some(percent) = token.strip_suffix('%') {
            return percent
                .parse::<f64>()
                .is_ok_and(|value| (0.0..=100.0).contains(&value));
        }
        if let Some((value, scale)) = token.split_once('/') {
            return value
                .parse::<f64>()
                .ok()
                .zip(scale.parse::<f64>().ok())
                .is_some_and(|(value, scale)| scale > 0.0 && value >= 0.0 && value <= scale);
        }
        token.contains('.')
            && token
                .parse::<f64>()
                .is_ok_and(|value| (0.0..=100.0).contains(&value))
    })
}

// A named structural region supplies the missing association between its
// caption/heading and descendants whose own text does not repeat that name.
// Match a complete literal word sequence in the name only: generic path roles
// and loose matches to one word in a longer query must not select whole regions.
fn page_read_named_context_score(context: Option<&str>, query: Option<&str>) -> usize {
    let (Some(context), Some(query)) = (context, query) else {
        return 0;
    };
    let words = |value: &str| {
        value
            .split(|character: char| !character.is_alphanumeric())
            .filter(|word| !word.is_empty())
            .map(str::to_lowercase)
            .collect::<Vec<_>>()
    };
    let query_words = words(query);
    const STRUCTURAL_WORDS: &[&str] = &[
        "main",
        "header",
        "footer",
        "navigation",
        "section",
        "table",
        "form",
        "region",
        "article",
        "list",
        "row",
        "content",
        "page",
    ];
    if query_words.is_empty()
        || !query_words
            .iter()
            .any(|word| !STRUCTURAL_WORDS.contains(&word.as_str()))
    {
        return 0;
    }
    for component in context.split(" > ") {
        let Some((kind, name)) = component.split_once(':') else {
            continue;
        };
        if !matches!(kind.trim(), "table" | "section" | "form" | "region") {
            continue;
        }
        let name_words = words(name);
        if name_words
            .windows(query_words.len())
            .any(|candidate| candidate == query_words)
        {
            return 12;
        }
    }
    0
}

fn page_read_link_intent_score(destination: &str, terms: &[String]) -> usize {
    let destination = destination.to_ascii_lowercase();
    let has_term =
        |candidates: &[&str]| terms.iter().any(|term| candidates.contains(&term.as_str()));
    if destination.contains("/genres/") && has_term(&["genre", "genres", "style"]) {
        return 6;
    }
    if destination.contains("/label/") && has_term(&["label", "labels"]) {
        return 6;
    }
    0
}

fn page_read_match_score(
    text: &str,
    query: Option<&str>,
    terms: &[String],
    is_heading: bool,
) -> usize {
    let Some(query) = query else {
        return 1;
    };
    let text = text.to_lowercase();
    let query = query.to_lowercase();
    let mut score = if !query.is_empty() && page_read_term_matches(&text, &query) {
        128
    } else {
        0
    };
    for term in terms {
        if page_read_term_matches(&text, term) {
            score += if term.contains(['_', '.']) { 64 } else { 8 };
        } else if !term.contains(['_', '.'])
            && text
                .split(|character: char| !character.is_alphanumeric() && character != '_')
                .any(|word| word.starts_with(term))
        {
            // Retain weak lexical matches such as install/installation, but
            // repeated boilerplate must never gain score from repetition.
            score += 1;
        }
    }
    if is_heading && score > 0 {
        score *= 2;
    }
    score
}

fn page_read_term_matches(text: &str, term: &str) -> bool {
    let continues_word = |character: char| character.is_alphanumeric() || character == '_';
    text.match_indices(term).any(|(start, _)| {
        !text[..start]
            .chars()
            .next_back()
            .is_some_and(continues_word)
            && !text[start + term.len()..]
                .chars()
                .next()
                .is_some_and(continues_word)
    })
}

fn page_read_normalize_text(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn page_read_context(context: Option<&str>) -> Option<&str> {
    context.map(str::trim).filter(|value| !value.is_empty())
}

struct PageReadLink {
    index: usize,
    score: usize,
    in_viewport: bool,
}

fn page_read_unique_links(
    elements: &[ObservationElement],
    query: Option<&str>,
    terms: &[String],
) -> Vec<PageReadLink> {
    let mut seen: BTreeMap<_, usize> = BTreeMap::new();
    let mut links: Vec<PageReadLink> = Vec::new();
    for (index, element) in elements.iter().enumerate() {
        let Some(destination) = element
            .destination
            .as_deref()
            .map(str::trim)
            .filter(|value| !value.is_empty())
        else {
            continue;
        };
        let mut states = element.states.clone();
        states.sort();
        let key = (
            page_read_normalize_text(&element.name),
            destination,
            page_read_context(element.context.as_deref()),
            &element.role,
            states,
            &element.value,
        );
        if let Some(previous) = seen.get(&key).copied() {
            // One logical link can have responsive copies inside/outside the
            // viewport. Preserve visibility if any identical copy is visible.
            links[previous].in_viewport |= element.in_viewport;
            continue;
        }
        seen.insert(key, links.len());
        links.push(PageReadLink {
            index,
            score: page_read_match_score(&element.name, query, terms, false)
                .max(page_read_link_intent_score(destination, terms))
                .max(page_read_named_context_score(
                    element.context.as_deref(),
                    query,
                )),
            in_viewport: element.in_viewport,
        });
    }
    links
}

fn page_read_link_markdown(element: &ObservationElement, in_viewport: bool) -> String {
    let destination = element.destination.as_deref().unwrap_or_default();
    let label = if element.name.trim().is_empty() {
        destination
    } else {
        element.name.trim()
    };
    let mut details = vec![if in_viewport {
        "in viewport".to_string()
    } else {
        "offscreen".to_string()
    }];
    if element.role != "link" {
        details.push(element.role.clone());
    }
    details.extend(
        element
            .states
            .iter()
            .filter(|state| state.as_str() != "enabled")
            .cloned(),
    );
    if let Some(value) = &element.value {
        details.push(format!("value: {value}"));
    }
    format!(
        "[{}](<{}>) ({})",
        escape_markdown_text(label),
        escape_markdown_url(destination),
        escape_markdown_text(&details.join(", "))
    )
}

fn page_read_with_context(block: &str, context: Option<&str>, previous: Option<&str>) -> String {
    if context == previous {
        return block.to_string();
    }
    match context {
        Some(context) => format!("Context: {}\n\n{block}", escape_markdown_text(context)),
        // Explicitly end a contextual run before unrelated unscoped content.
        None if previous.is_some() => format!("Context: unspecified\n\n{block}"),
        None => block.to_string(),
    }
}

fn page_read_content_with_text(content: &ObservationContent, text: &str) -> String {
    match content.kind.as_str() {
        "heading" => format!(
            "{} {text}",
            "#".repeat(content.level.unwrap_or(2).clamp(2, 6) as usize)
        ),
        "listitem" | "list_item" | "item" => format!("- {text}"),
        _ => text.to_string(),
    }
}

fn page_read_content_markdown(content: &ObservationContent) -> String {
    page_read_content_with_text(content, &escape_markdown_text(content.text.trim()))
}

fn page_read_content_body(
    content: &ObservationContent,
    elements: &[ObservationElement],
    links: &[PageReadLink],
    max_chars: usize,
) -> (String, Option<usize>) {
    // Link only an unambiguous exact label in the same structural context.
    // Repeated generic labels with different destinations stay separate.
    let candidates = links
        .iter()
        .filter(|link| {
            let element = &elements[link.index];
            page_read_normalize_text(&element.name) == page_read_normalize_text(&content.text)
                && page_read_context(element.context.as_deref())
                    == page_read_context(content.context.as_deref())
        })
        .collect::<Vec<_>>();
    if let [link] = candidates.as_slice() {
        let body = page_read_content_with_text(
            content,
            &page_read_link_markdown(&elements[link.index], link.in_viewport),
        );
        if body.chars().count() <= page_read_block_limit(max_chars) {
            return (body, Some(link.index));
        }
    }
    (page_read_content_markdown(content), None)
}

fn page_read_block_limit(max_chars: usize) -> usize {
    (max_chars / 3).clamp(128, 2_048)
}

fn page_read_bounded_content_block(block: String, max_chars: usize) -> (String, bool) {
    let maximum = page_read_block_limit(max_chars);
    if block.chars().count() <= maximum {
        return (block, false);
    }
    let mut bounded = block
        .chars()
        .take(maximum.saturating_sub(1))
        .collect::<String>();
    bounded.push('…');
    (bounded, true)
}

fn push_page_read_block(output: &mut String, block: &str, max_chars: usize) -> bool {
    let separator = if output.is_empty() { "" } else { "\n\n" };
    let required = separator.chars().count() + block.chars().count();
    if output.chars().count() + required > max_chars {
        return false;
    }
    output.push_str(separator);
    output.push_str(block);
    true
}

fn push_page_read_excerpt(output: &mut String, block: &str, max_chars: usize) -> (bool, bool) {
    if push_page_read_block(output, block, max_chars) {
        return (true, false);
    }
    let separator = if output.is_empty() { "" } else { "\n\n" };
    let used = output.chars().count() + separator.chars().count();
    let available = max_chars.saturating_sub(used);
    if available < 2 {
        return (false, true);
    }
    output.push_str(separator);
    output.extend(block.chars().take(available - 1));
    output.push('…');
    (true, true)
}

fn escape_markdown_text(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len());
    for character in value.chars() {
        match character {
            '\\' | '*' | '_' | '[' | ']' | '`' => {
                escaped.push('\\');
                escaped.push(character);
            }
            '\r' | '\n' => escaped.push(' '),
            _ => escaped.push(character),
        }
    }
    escaped
}

fn escape_markdown_url(value: &str) -> String {
    value.trim().replace('<', "%3C").replace('>', "%3E")
}

/// Additional CA trust is scoped to sessions using this proxy.
#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq)]
#[serde(tag = "mode", rename_all = "snake_case", deny_unknown_fields)]
pub enum ProxyTls {
    #[default]
    System,
    BrightData,
    Custom {
        certificate_pem: String,
    },
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct ProxyCreateRequest {
    pub alias: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub locale: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tls: Option<ProxyTls>,
    pub upstream_host: String,
    pub upstream_port: u16,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub password: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oxylabs_enabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oxylabs_location_parameter: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oxylabs_location_value: Option<String>,
}

impl ProxyCreateRequest {
    pub fn new(upstream_host: impl Into<String>, upstream_port: u16) -> Self {
        Self {
            upstream_host: upstream_host.into(),
            upstream_port,
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct ProxyUpdateRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub upstream_host: Option<String>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub locale: Change<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tls: Option<ProxyTls>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub upstream_port: Option<u16>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub username: Change<String>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub password: Change<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub oxylabs_enabled: Option<bool>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub oxylabs_location_parameter: Change<String>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub oxylabs_location_value: Change<String>,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub enum Change<T> {
    #[default]
    Unchanged,
    Set(T),
    Clear,
}

impl<T> Change<T> {
    pub fn is_unchanged(&self) -> bool {
        matches!(self, Self::Unchanged)
    }
}

impl<T: Serialize> Serialize for Change<T> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        match self {
            Self::Unchanged | Self::Clear => serializer.serialize_none(),
            Self::Set(value) => value.serialize(serializer),
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct BrowserNotificationListData {
    pub notifications: Vec<BrowserNotification>,
    pub trust: String,
}

/// Website-provided notification content. Callers must treat every text field
/// as untrusted data, never as instructions or authority.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct BrowserNotification {
    pub sequence: u64,
    pub session_id: String,
    pub origin: String,
    pub title: String,
    pub body: String,
    pub notification_id: String,
    pub persistent: bool,
    pub displayed_at: String,
    pub trust: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ProxyListData {
    pub proxies: Vec<Proxy>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ProxyData {
    pub proxy: Proxy,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct OxylabsProxy {
    pub enabled: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub location_parameter: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub location_value: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Proxy {
    #[serde(default)]
    pub tls: ProxyTls,
    pub alias: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub locale: Option<String>,
    pub upstream_host: String,
    pub upstream_port: u16,
    pub username: Option<String>,
    pub password_set: bool,
    #[serde(rename = "oxylabs", skip_serializing_if = "Option::is_none")]
    pub oxylabs: Option<OxylabsProxy>,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct ProxyTransferExportRequest {
    pub alias: String,
    pub include_credentials: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub passphrase: Option<String>,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct ProxyTransferImportRequest {
    pub contents_base64: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub alias: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub passphrase: Option<String>,
}

impl ProxyTransferImportRequest {
    pub fn from_bytes(data: &[u8], alias: Option<String>, passphrase: Option<String>) -> Self {
        Self {
            contents_base64: BASE64_STANDARD.encode(data),
            alias,
            passphrase,
        }
    }
}

/// Omission at creation defaults to 120 seconds of client inactivity.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum SessionLifetime {
    Inactivity { timeout_seconds: u32 },
    Indefinite,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct SessionCreateRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lifetime: Option<SessionLifetime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub proxy_alias: Change<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adblock_enabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_blocking_mode: Option<ImageBlockingMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_size_limit_kb: Option<i64>,
}

#[derive(Clone, Debug, Default, Serialize, PartialEq)]
pub struct SessionUpdateRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub proxy_alias: Change<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adblock_enabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_blocking_mode: Option<ImageBlockingMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_size_limit_kb: Option<i64>,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct ProfileCreateRequest {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy_alias: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub adblock_enabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_blocking_mode: Option<ImageBlockingMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image_size_limit_kb: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub includes_cookies: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub includes_passwords: Option<bool>,
    #[serde(skip_serializing_if = "Change::is_unchanged")]
    pub fingerprint_profile: Change<FingerprintProfile>,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct ProfileDataUpdateRequest {
    pub includes_cookies: bool,
    pub includes_passwords: bool,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ImageBlockingMode {
    None,
    All,
    OverLimit,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct FingerprintProfile {
    pub schema_version: u64,
    pub seed: String,
    pub platform: FingerprintPlatform,
    pub browser_brand: FingerprintBrowserBrand,
    pub browser_version: String,
    pub user_agent: String,
    pub locale: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub locale_mode: Option<FingerprintLocaleMode>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub overrides: Option<Vec<String>>,
    pub timezone: String,
    pub network_profile: FingerprintNetworkProfile,
    pub hardware_concurrency: u64,
    pub device_memory_gib: u64,
    pub max_touch_points: u64,
    pub screen: FingerprintScreen,
    pub graphics_profile: String,
    pub storage_quota_bytes: u64,
    pub canvas_noise_mode: FingerprintNoiseMode,
    pub audio_noise_mode: FingerprintNoiseMode,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum FingerprintLocaleMode {
    Automatic,
    Custom,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum FingerprintPlatform {
    Macos,
    Linux,
    Windows,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum FingerprintBrowserBrand {
    Chromium,
    Chrome,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum FingerprintNetworkProfile {
    Desktop,
    Residential,
    Datacenter,
    Mobile,
    Slow,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum FingerprintNoiseMode {
    Native,
    Deterministic,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct FingerprintScreen {
    pub width: u64,
    pub height: u64,
    pub available_height: u64,
    pub device_scale_factor: u64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct SessionListData {
    pub sessions: Vec<Session>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct SessionData {
    pub session: Session,
    #[serde(default)]
    pub closed_session_ids: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct SessionNetworkStateData {
    pub session_id: String,
    pub network_paused: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ProfileListData {
    pub profiles: Vec<Profile>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ProfileData {
    pub profile: Profile,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Profile {
    pub id: String,
    pub name: String,
    pub proxy_alias: Option<String>,
    pub adblock_enabled: bool,
    pub image_blocking_mode: ImageBlockingMode,
    pub image_size_limit_kb: i64,
    pub includes_cookies: bool,
    pub includes_passwords: bool,
    #[serde(default)]
    pub fingerprint_profile: Option<FingerprintProfile>,
    pub is_builtin: bool,
    pub created_at: i64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct TransferExportData {
    pub filename: String,
    pub contents_base64: String,
}

impl TransferExportData {
    pub fn contents(&self) -> Result<Vec<u8>, String> {
        BASE64_STANDARD
            .decode(&self.contents_base64)
            .map_err(|error| format!("REL returned invalid transfer data: {error}"))
    }
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct ProfileTransferExportRequest {
    pub name: String,
    pub include_cookies: bool,
    pub include_passwords: bool,
    pub include_proxy_credentials: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub passphrase: Option<String>,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct ProfileTransferImportRequest {
    pub contents_base64: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub passphrase: Option<String>,
    #[serde(skip_serializing_if = "is_false")]
    pub browser_data_ready: bool,
}

impl ProfileTransferImportRequest {
    pub fn from_bytes(data: &[u8], name: Option<String>, passphrase: Option<String>) -> Self {
        Self {
            contents_base64: BASE64_STANDARD.encode(data),
            name,
            passphrase,
            browser_data_ready: false,
        }
    }
}

fn is_false(value: &bool) -> bool {
    !*value
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Session {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lifetime: Option<SessionLifetime>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_activity_at: Option<i64>,
    pub id: String,
    pub name: String,
    pub profile: String,
    pub profile_data_id: Option<String>,
    pub group: Option<String>,
    pub proxy_alias: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proxy_locale: Option<String>,
    pub adblock_enabled: bool,
    pub image_blocking_mode: ImageBlockingMode,
    pub image_size_limit_kb: i64,
    pub created_at: i64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct DeletedData {
    pub deleted_id: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ClosedSessionGroupData {
    pub group: String,
    pub deleted_ids: Vec<String>,
}

#[derive(Serialize)]
struct SessionGroupCloseRequest<'a> {
    group: &'a str,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct ProxyDeletedData {
    pub deleted_alias: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Health {
    pub version: String,
    pub pid: u32,
    pub browser_proxy_port: u16,
    pub build: Option<BuildIdentity>,
    pub worker: Worker,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub database_recovery: Option<DatabaseRecoverySummary>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct DatabaseRecoverySummary {
    pub schema_version: u32,
    pub backup_path: String,
    pub report_path: String,
    pub issue_count: u64,
    pub retained_sessions: u64,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct BuildIdentity {
    pub id: String,
    pub configuration: String,
    pub worktree: String,
    pub branch: String,
    pub commit: String,
    pub dirty: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct Worker {
    pub state: String,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct StatusReport {
    pub overall_status: String,
    pub running_count: usize,
    pub total_count: usize,
    pub build: Option<BuildIdentity>,
    pub checks: Vec<StatusCheck>,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct StatusCheck {
    pub id: String,
    pub name: String,
    pub kind: String,
    pub running: bool,
    pub status: String,
    pub detail: String,
    pub pids: Vec<u32>,
}

fn capture_request_timeout(request: &CaptureRequest) -> Duration {
    let timeout = request.timeout.unwrap_or(90.0);
    let wait = request.wait.unwrap_or(1.0);
    let retries = request.retry.unwrap_or(1);
    let retry_delay = request.retry_delay.unwrap_or(3.0);
    let attempts = f64::from(retries) + 1.0;
    bounded_duration(
        ((timeout + wait + 30.0).max(30.0) * attempts) + retry_delay * f64::from(retries),
        180.0,
    )
}

fn page_request_timeout(timeout: Option<f64>, wait: Option<f64>) -> Duration {
    bounded_duration(timeout.unwrap_or(90.0) + wait.unwrap_or(1.0) + 30.0, 120.0)
}

fn bounded_duration(seconds: f64, fallback: f64) -> Duration {
    const MAX_CLIENT_TIMEOUT_SECONDS: f64 = 7.0 * 24.0 * 60.0 * 60.0;
    let seconds = if seconds.is_finite() && seconds > 0.0 {
        seconds.min(MAX_CLIENT_TIMEOUT_SECONDS)
    } else {
        fallback
    };
    Duration::from_secs_f64(seconds)
}

fn encode_path_segment(value: &str) -> String {
    let mut encoded = String::new();
    for byte in value.bytes() {
        if byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b'~') {
            encoded.push(char::from(byte));
        } else {
            encoded.push_str(&format!("%{byte:02X}"));
        }
    }
    encoded
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::io::{BufRead, BufReader, Read, Write};
    use std::net::{TcpListener, TcpStream};
    use std::thread::{self, JoinHandle};

    #[test]
    fn rpc_error_codes_use_a_distinct_high_numeric_namespace() {
        let codes = [
            rpc_error_codes::INVALID_REQUEST,
            rpc_error_codes::ROUTE_NOT_FOUND,
            rpc_error_codes::METHOD_NOT_ALLOWED,
            rpc_error_codes::PAYLOAD_TOO_LARGE,
            rpc_error_codes::UNSUPPORTED_MEDIA_TYPE,
            rpc_error_codes::VALIDATION_FAILED,
            rpc_error_codes::UNSUPPORTED_MODALITY,
            rpc_error_codes::OBSERVATION_TOO_LARGE,
            rpc_error_codes::SESSION_NOT_FOUND,
            rpc_error_codes::PAGE_NOT_FOUND,
            rpc_error_codes::PAGE_MISMATCH,
            rpc_error_codes::PROXY_NOT_FOUND,
            rpc_error_codes::ACTIVE_PAGE_NOT_FOUND,
            rpc_error_codes::CONFLICT,
            rpc_error_codes::BROWSER_BUSY,
            rpc_error_codes::NETWORK_PAUSED,
            rpc_error_codes::ACTION_TARGET_NOT_FOUND,
            rpc_error_codes::REQUEST_CANCELLED,
            rpc_error_codes::RATE_LIMITED,
            rpc_error_codes::ACTION_TIMEOUT,
            rpc_error_codes::OBSERVATION_STALE,
            rpc_error_codes::PRO_REQUIRED,
            rpc_error_codes::UPSTREAM_UNAVAILABLE,
            rpc_error_codes::BROWSER_UNAVAILABLE,
            rpc_error_codes::AGENT_UNHEALTHY,
            rpc_error_codes::TIMEOUT,
            rpc_error_codes::PROXY_CONFIGURATION_FAILED,
            rpc_error_codes::BROWSER_CREATION_FAILED,
            rpc_error_codes::SEMANTIC_EXTRACTION_FAILED,
            rpc_error_codes::INTERNAL_ERROR,
        ];

        assert!(codes.iter().all(|code| *code >= rpc_error_codes::MINIMUM));
        let unique = codes
            .iter()
            .copied()
            .collect::<std::collections::BTreeSet<_>>();
        assert_eq!(unique.len(), codes.len());
        assert_eq!(
            rpc_error_codes::for_id("UNKNOWN_ERROR"),
            rpc_error_codes::INTERNAL_ERROR
        );
        assert!(rpc_error_codes::is_valid("FUTURE_ERROR", 11_000));
        assert!(!rpc_error_codes::is_valid("SESSION_NOT_FOUND", 10_303));
    }

    #[derive(Debug)]
    struct TestRequest {
        method: String,
        path: String,
        body: String,
    }

    fn start_test_server<F>(
        request_count: usize,
        mut responder: F,
    ) -> (String, JoinHandle<Vec<TestRequest>>)
    where
        F: FnMut(usize, &TestRequest) -> String + Send + 'static,
    {
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let address = listener.local_addr().unwrap();
        let handle = thread::spawn(move || {
            let mut requests = Vec::new();
            for index in 0..request_count {
                let (stream, _) = listener.accept().unwrap();
                let (request, mut stream) = read_test_request(stream);
                let response = responder(index, &request);
                stream.write_all(response.as_bytes()).unwrap();
                requests.push(request);
            }
            requests
        });
        (format!("http://{address}/v1"), handle)
    }

    fn read_test_request(stream: TcpStream) -> (TestRequest, TcpStream) {
        let mut reader = BufReader::new(stream);
        let mut request_line = String::new();
        reader.read_line(&mut request_line).unwrap();
        let mut fields = request_line.split_whitespace();
        let method = fields.next().unwrap().to_string();
        let path = fields.next().unwrap().to_string();
        let mut content_length = 0_usize;
        loop {
            let mut line = String::new();
            reader.read_line(&mut line).unwrap();
            if line == "\r\n" || line.is_empty() {
                break;
            }
            if let Some((name, value)) = line.split_once(':') {
                if name.eq_ignore_ascii_case("Content-Length") {
                    content_length = value.trim().parse().unwrap();
                }
            }
        }
        let mut body = vec![0_u8; content_length];
        reader.read_exact(&mut body).unwrap();
        let stream = reader.into_inner();
        (
            TestRequest {
                method,
                path,
                body: String::from_utf8(body).unwrap(),
            },
            stream,
        )
    }

    fn http_json(status: u16, request_id: &str, body: Value) -> String {
        http_response(
            status,
            "application/json",
            Some(request_id),
            &body.to_string(),
        )
    }

    fn http_response(
        status: u16,
        content_type: &str,
        request_id: Option<&str>,
        body: &str,
    ) -> String {
        let reason = match status {
            200 => "OK",
            404 => "Not Found",
            _ => "Error",
        };
        let request_id = request_id
            .map(|request_id| format!("X-Request-Id: {request_id}\r\n"))
            .unwrap_or_default();
        format!(
            "HTTP/1.1 {status} {reason}\r\nContent-Type: {content_type}\r\n{request_id}Content-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.len()
        )
    }

    fn proxy_json() -> Value {
        json!({
            "alias": "office",
            "upstream_host": "proxy.example.com",
            "upstream_port": 8000,
            "username": null,
            "password_set": false
        })
    }

    fn session_json() -> Value {
        json!({
            "id": "machine-a.Session1",
            "name": "Session1",
            "profile": "Default",
            "profile_data_id": null,
            "group": "pgm",
            "proxy_alias": null,
            "adblock_enabled": true,
            "image_blocking_mode": "over_limit",
            "image_size_limit_kb": 100,
            "created_at": 1
        })
    }

    fn profile_json() -> Value {
        json!({
            "id": "builtin-default",
            "name": "Private",
            "proxy_alias": null,
            "adblock_enabled": false,
            "image_blocking_mode": "none",
            "image_size_limit_kb": 100,
            "includes_cookies": false,
            "includes_passwords": false,
            "fingerprint_profile": {
                "schema_version": 1,
                "seed": "12345",
                "platform": "macos",
                "browser_brand": "chromium",
                "browser_version": "151.0.7922.76",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.7922.76 Safari/537.36",
                "locale": "en-US",
                "timezone": "America/Los_Angeles",
                "network_profile": "desktop",
                "hardware_concurrency": 8,
                "device_memory_gib": 8,
                "max_touch_points": 0,
                "screen": {
                    "width": 1920,
                    "height": 1080,
                    "available_height": 985,
                    "device_scale_factor": 2
                },
                "graphics_profile": "apple-m2",
                "storage_quota_bytes": 107374182400_u64,
                "canvas_noise_mode": "deterministic",
                "audio_noise_mode": "deterministic"
            },
            "is_builtin": true,
            "created_at": 0
        })
    }

    fn observation_operation() -> ObservationOperationData {
        ObservationOperationData {
            page: Page {
                id: "page-1".to_string(),
                session_id: "session-1".to_string(),
                url: "https://example.com/guide".to_string(),
            },
            observation: PageObservation {
                id: "observation-1".to_string(),
                mode: ObservationMode::Semantic,
                document_sequence: 1,
                captured_at: "2026-08-19T00:00:00Z".to_string(),
                title: "Example Guide".to_string(),
                truncated: false,
                omitted_node_count: 0,
                clipped_text_count: 0,
                visited_node_count: 12,
                semantic_bytes: 200,
                viewport: ObservationViewport {
                    css_width: 1280,
                    css_height: 720,
                    scroll_x: 0,
                    scroll_y: 0,
                    document_width: 1280,
                    document_height: 1800,
                },
                content: vec![
                    ObservationContent {
                        kind: "heading".to_string(),
                        level: Some(2),
                        context: Some("main".to_string()),
                        text: "Installation".to_string(),
                    },
                    ObservationContent {
                        kind: "paragraph".to_string(),
                        level: None,
                        context: Some("main > section: Installation".to_string()),
                        text: "Install the package with Cargo.".to_string(),
                    },
                    ObservationContent {
                        kind: "paragraph".to_string(),
                        level: None,
                        context: Some("main > section: History".to_string()),
                        text: "Unrelated company history.".to_string(),
                    },
                ],
                elements: vec![ObservationElement {
                    element_ref: "e1".to_string(),
                    role: "link".to_string(),
                    name: "Installation reference".to_string(),
                    states: Vec::new(),
                    value: None,
                    destination: Some("https://example.com/install".to_string()),
                    context: Some("main > navigation: Documentation".to_string()),
                    in_viewport: true,
                    bounds: ObservationBounds {
                        x: 0.0,
                        y: 0.0,
                        width: 100.0,
                        height: 20.0,
                    },
                }],
                screenshot: None,
            },
        }
    }

    #[test]
    fn page_read_compacts_repeated_context_and_inline_links_without_losing_records() {
        let mut operation = observation_operation();
        operation.observation.content = [
            ("heading", Some("main > section: Guide"), "Guide"),
            (
                "paragraph",
                Some("main > section: Guide"),
                "First paragraph.",
            ),
            ("listitem", Some("main > section: Guide"), "Reference"),
            (
                "table_row",
                Some("main > table: Results > row 1"),
                "Result | 42",
            ),
            (
                "table_row",
                Some("main > table: Results > row 2"),
                "Result | 42",
            ),
            ("text", Some("main > form: Signup"), "Email"),
            ("text", Some("main > form: Signup"), "Required"),
            ("text", None, "No heading or region."),
            ("text", None, "Advertisement: a sponsored result"),
            ("text", None, "Ad"),
        ]
        .into_iter()
        .map(|(kind, context, text)| ObservationContent {
            kind: kind.into(),
            level: (kind == "heading").then_some(2),
            context: context.map(str::to_string),
            text: text.into(),
        })
        .collect();
        operation.observation.elements[0].name = "Reference".into();
        operation.observation.elements[0].context = Some("main > section: Guide".into());
        let read = page_read_data(operation, None, 8_000, 100);
        assert_eq!(read.selected_content_count, 10);
        assert_eq!(read.selected_link_count, 1);
        assert_eq!(read.selected_outline_count, 0);
        assert_eq!(
            read.markdown
                .matches("Context: main > section: Guide")
                .count(),
            1
        );
        assert_eq!(read.markdown.matches("Reference").count(), 1);
        assert_eq!(read.markdown.matches("Result | 42").count(), 2);
        assert!(read.markdown.contains("row 1"));
        assert!(read.markdown.contains("row 2"));
        assert!(read.markdown.contains("Email\n\nRequired"));
        assert!(read
            .markdown
            .contains("Context: unspecified\n\nNo heading or region."));
        assert!(read
            .markdown
            .contains("Advertisement: a sponsored result\n\nAd"));
        assert!(read
            .markdown
            .contains("- [Reference](<https://example.com/install>) (in viewport)"));
        assert!(!read.markdown.contains("## Links"));
        assert!(!read.truncated);
    }

    #[test]
    fn page_read_deduplicates_only_identical_link_meaning_and_combines_visibility() {
        let mut operation = observation_operation();
        operation.observation.content.clear();
        let mut link = operation.observation.elements[0].clone();
        link.name = "Details".into();
        link.context = Some("main > article".into());
        link.in_viewport = false;
        let mut copy = link.clone();
        copy.name = "  Details \n ".into();
        copy.in_viewport = true;
        let mut different_url = link.clone();
        different_url.destination = Some("https://example.com/another".into());
        let mut navigation = link.clone();
        navigation.context = Some("navigation".into());
        let mut disabled = link.clone();
        disabled.states = vec!["disabled".into()];
        operation.observation.elements = vec![link, copy, different_url, navigation, disabled];
        let read = page_read_data(operation, None, 8_000, 100);
        assert_eq!(read.available_link_count, 4);
        assert_eq!(read.selected_link_count, 4);
        assert_eq!(
            read.markdown.matches("https://example.com/install").count(),
            3
        );
        assert!(read.markdown.contains("https://example.com/another"));
        assert_eq!(read.markdown.matches("in viewport").count(), 1);
        assert!(read.markdown.contains("offscreen, disabled"));
        assert!(read.markdown.contains("Context: navigation"));
        assert!(!read.truncated);
    }

    #[test]
    fn page_read_ambiguous_unheaded_labels_keep_destinations_and_source_scope() {
        let mut operation = observation_operation();
        operation.observation.content = vec![ObservationContent {
            kind: "text".into(),
            level: None,
            context: None,
            text: "Details".into(),
        }];
        let mut link = operation.observation.elements[0].clone();
        link.name = "Details".into();
        link.context = None;
        let mut other = link.clone();
        other.destination = Some("https://example.com/other".into());
        operation.observation.elements = vec![link, other];
        operation.observation.document_sequence = 7;
        operation.observation.viewport.scroll_y = 900;
        operation.observation.truncated = true;
        let read = page_read_data(operation, None, 8_000, 100);
        assert!(read.markdown.contains("\n\nDetails\n\n## Links"));
        assert_eq!(read.available_link_count, 2);
        assert_eq!(read.selected_link_count, 2);
        assert!(read.markdown.contains("2026-08-19T00:00:00Z / document 7"));
        assert!(read
            .markdown
            .contains("Viewport: 1280×720 at 0,900 of 1280×1800"));
        assert!(read.source_truncated);
        assert!(!read.truncated);
    }

    #[test]
    fn named_table_query_keeps_all_associated_rows_and_duplicate_values_within_bounds() {
        let mut operation = observation_operation();
        operation.observation.elements.clear();
        operation.observation.content = [
            ("heading", "main", "Warehouse report"),
            ("text", "main", "Shipment weights"),
            ("text", "main > table: Shipment weights", "Shipment weights"),
            (
                "text",
                "main > table: Shipment weights > tr: Shipment",
                "Shipment",
            ),
            (
                "text",
                "main > table: Shipment weights > tr: Shipment",
                "Weight (kg)",
            ),
            (
                "text",
                "main > table: Shipment weights > tr: Orion",
                "Orion",
            ),
            ("text", "main > table: Shipment weights > tr: Orion", "25"),
            ("text", "main > table: Shipment weights > tr: Lyra", "Lyra"),
            ("text", "main > table: Shipment weights > tr: Lyra", "14"),
            ("text", "main > table: Shipment weights > tr: Vega", "Vega"),
            ("text", "main > table: Shipment weights > tr: Vega", "25"),
            ("heading", "main > form: Shipment contact", "Contact"),
            ("text", "main > form: Shipment contact", "Email address"),
            (
                "text",
                "main > form: Shipment contact",
                "person@example.test",
            ),
        ]
        .into_iter()
        .map(|(kind, context, text)| ObservationContent {
            kind: kind.into(),
            level: (kind == "heading").then_some(2),
            context: Some(context.into()),
            text: text.into(),
        })
        .collect();
        let read = page_read_data(operation.clone(), Some("shipment weights"), 4_000, 100);
        assert!(read.matched_query);
        assert!(read.markdown.contains("Orion\n\n25"));
        assert!(read.markdown.contains("Lyra\n\n14"));
        assert!(read.markdown.contains("Vega\n\n25"));
        assert_eq!(read.markdown.matches("\n\n25").count(), 2);
        assert!(!read.markdown.contains("person@example.test"));
        assert!(!read.markdown.contains("Email address"));
        assert_eq!(read.available_content_count, 11);
        assert_eq!(read.selected_content_count, 11);
        assert!(!read.truncated);
        let bounded = page_read_data(operation.clone(), Some("shipment weights"), 4_000, 5);
        assert_eq!(bounded.selected_content_count, 5);
        assert_eq!(bounded.available_content_count, 11);
        assert!(bounded.truncated);
        let generic = page_read_data(operation, Some("table"), 4_000, 100);
        assert_eq!(generic.selected_content_count, 0);
        assert!(!generic.matched_query);
    }

    #[test]
    fn named_sections_and_forms_match_names_without_matching_generic_path_roles() {
        for kind in ["section", "form", "region"] {
            let context = format!("main > {kind}: Delivery preferences > group: Address");
            assert!(
                page_read_named_context_score(Some(&context), Some("DELIVERY preferences")) > 0
            );
            assert_eq!(
                page_read_named_context_score(Some(&context), Some("delivery charges")),
                0
            );
            assert_eq!(
                page_read_named_context_score(Some(&context), Some("main")),
                0
            );
            assert_eq!(page_read_named_context_score(Some(&context), Some(kind)), 0);
        }
    }

    #[test]
    fn page_read_is_query_directed_and_markdown_bounded() {
        let data = page_read_data(observation_operation(), Some("install package"), 1_024, 10);
        assert!(data.markdown.contains("## Installation"));
        assert!(data.markdown.contains("Install the package with Cargo."));
        assert!(
            data.markdown.contains("Installation reference"),
            "{}",
            data.markdown
        );
        assert!(data.markdown.contains("Context: main"));
        assert!(!data.markdown.contains("company history"));
        assert!(data.matched_query);
        assert!(data.markdown.chars().count() <= 1_024);

        let mut operation = observation_operation();
        operation.observation.content[1].text = "x".repeat(1_000);
        let bounded = page_read_data(operation, None, 512, 10);
        assert!(bounded.markdown.chars().count() <= 512);
        assert!(bounded.markdown.contains('…'));
        assert!(bounded.selected_content_count >= 2);
        assert!(bounded.truncated);

        let mut source_limited = observation_operation();
        source_limited.observation.truncated = true;
        let source_limited = page_read_data(source_limited, None, 32_768, 10);
        assert!(source_limited.source_truncated);
        assert!(!source_limited.truncated);
    }

    fn long_reference_operation() -> ObservationOperationData {
        let mut operation = observation_operation();
        operation.observation.elements.clear();
        operation.observation.content = (0..80)
            .map(|index| ObservationContent {
                kind: "text".into(),
                level: None,
                context: Some("main > section: Examples".into()),
                text: format!(
                    "Copy Copy Copy example {index}. {}",
                    "Ordinary example text. ".repeat(8)
                ),
            })
            .collect();
        operation.observation.content.extend([
            ("heading", "Transfer reference"),
            ("text", "Archive.copy(target, follow_symlinks=True, preserve_metadata=False)"),
            ("text", "Copy to the complete target path. Symlinks are followed by default. Metadata preservation defaults to false. Supported metadata is always preserved on platform Z."),
            ("paragraph", "Copy to the complete target path."),
            ("paragraph", "Symlinks are followed by default."),
            ("paragraph", "Metadata preservation defaults to false."),
            ("paragraph", "Supported metadata is always preserved on platform Z."),
            ("text", "Archive.copy_into(target_dir, follow_symlinks=True, preserve_metadata=False)"),
            ("text", "The destination must be an existing directory. Other options follow Archive.copy(). Returns the destination joined with the source name."),
            ("paragraph", "The destination must be an existing directory."),
            ("paragraph", "Other options follow Archive.copy()."),
            ("paragraph", "Returns the destination joined with the source name."),
            ("text", "Archive.move(target)"),
            ("text", "Unrelated move behavior."),
        ].into_iter().map(|(kind, text)| ObservationContent {
            kind: kind.into(),
            level: (kind == "heading").then_some(2),
            context: Some("main > section: Transfer reference".into()),
            text: text.into(),
        }));
        operation
    }

    #[test]
    fn late_identifier_hits_keep_definition_bodies_before_early_common_labels() {
        for (max_chars, max_sections) in [(8_000, 12), (2_000, 100)] {
            let read = page_read_data(
                long_reference_operation(),
                Some("copy copy_into metadata symlinks"),
                max_chars,
                max_sections,
            );
            assert!(
                read.markdown.contains("Archive.copy\\_into"),
                "{}",
                read.markdown
            );
            assert!(
                read.markdown.contains("existing directory"),
                "{}",
                read.markdown
            );
            assert!(read.markdown.contains("platform Z"), "{}", read.markdown);
            assert!(!read.markdown.contains("Unrelated move behavior"));
            assert!(read.markdown.chars().count() <= max_chars);
            assert!(read.selected_content_count <= max_sections);
            assert!(read.available_content_count > read.selected_content_count);
            assert!(read.truncated);
        }
    }

    #[test]
    fn qualified_identifier_queries_do_not_expand_into_generic_qualifiers_or_substrings() {
        let terms = page_read_query_terms("Archive.copy_into");
        assert_eq!(terms, ["archive.copy_into", "copy_into"]);
        for text in [
            "Archive examples",
            "Copy into an archive",
            "Archive.copy_into_extra()",
        ] {
            assert_eq!(
                page_read_match_score(text, Some("Archive.copy_into"), &terms, false),
                0
            );
        }
        let read = page_read_data(
            long_reference_operation(),
            Some("Archive.copy_into"),
            4_000,
            10,
        );
        assert!(read.markdown.contains("existing directory"));
        assert!(read.markdown.contains("Returns the destination joined"));
        assert!(!read.markdown.contains("Ordinary example text"));
        assert!(!read.markdown.contains("Archive.move"));
        assert!(!read.markdown.contains("Unrelated move behavior"));
    }

    #[test]
    fn description_queries_keep_the_label_and_continuing_prose_without_crossing_regions() {
        let mut operation = observation_operation();
        operation.observation.elements.clear();
        operation.observation.content = serde_json::from_value(json!([
            {"kind":"heading","level":2,"context":"main > section: Network","text":"Network options"},
            {"kind":"text","context":"main > section: Network","text":"Connection.retry(count, delay)"},
            {"kind":"paragraph","context":"main > section: Network","text":"Backoff grows after each failure."},
            {"kind":"paragraph","context":"main > section: Network","text":"The default count is three."},
            {"kind":"paragraph","context":"main > section: Network","text":"The default delay is one second."},
            {"kind":"paragraph","context":"main > section: Network","text":"A zero count disables retries."},
            {"kind":"paragraph","context":"main > section: Network","text":"Timer precision varies by platform."},
            {"kind":"paragraph","context":"main > section: Storage","text":"Private unrelated storage value."}
        ])).unwrap();
        let read = page_read_data(operation, Some("backoff"), 4_000, 10);
        assert!(read.markdown.contains("Connection.retry"));
        assert!(read.markdown.contains("default count is three"));
        assert!(read.markdown.contains("Timer precision varies"));
        assert!(!read.markdown.contains("Private unrelated storage"));
        assert!(!read.truncated);
    }

    #[test]
    fn unqueried_page_read_samples_the_whole_document_and_reports_availability() {
        let mut operation = observation_operation();
        operation.observation.content = (0..30)
            .map(|index| ObservationContent {
                kind: if index % 10 == 0 {
                    "heading".to_string()
                } else {
                    "paragraph".to_string()
                },
                level: (index % 10 == 0).then_some(2),
                context: Some(format!("main > section {}", index / 10 + 1)),
                text: format!("Document section {index}"),
            })
            .collect();

        let data = page_read_data(operation, None, 8_000, 6);

        assert!(data.markdown.contains("Document section 0"));
        assert!(data.markdown.contains("Document section 29"));
        assert_eq!(data.available_content_count, 30);
        assert_eq!(data.selected_content_count, 6);
        assert_eq!(data.selected_outline_count, 1);
        assert!(data.truncated);
    }

    #[test]
    fn observation_actions_reject_unknown_fields_and_variants() {
        assert!(serde_json::from_value::<ObservationAction>(
            json!({"action":"click","ref":"e1","selector":"#secret"})
        )
        .is_err());
        assert!(serde_json::from_value::<ObservationAction>(json!({"action":"reload"})).is_err());
        assert!(
            serde_json::from_value::<ObservationAction>(json!({"action":"click","ref":"e1"}))
                .is_ok()
        );
    }

    #[test]
    fn query_retains_generated_output_beneath_matching_label() {
        let content: Vec<ObservationContent> = serde_json::from_value(json!([
            {"kind":"heading","level":1,"context":"main > section","text":"Hipster Ipsum"},
            {"kind":"text","context":"main > section","text":"Plain Text Output"},
            {"kind":"text","text":"Copy"},
            {"kind":"text","context":"main > section","text":"Etsy echo park blue bottle activated charcoal."},
            {"kind":"heading","level":2,"context":"main > section","text":"Unrelated help"},
            {"kind":"text","context":"footer","text":"Private footer value"}
        ])).unwrap();
        let selected = page_read_matched_content_with_context(&content, &[(1, 4)]);
        assert!(selected.iter().any(|(index, _)| *index == 3));
        assert!(!selected.iter().any(|(index, _)| *index >= 4));
        assert!(selected.len() <= 4);
    }

    #[test]
    fn page_read_keeps_rating_pairs_and_ignores_generic_url_path_matches() {
        let mut operation = observation_operation();
        operation.observation.title = "Materia by Julia Holter".to_string();
        operation.observation.content = [
            ("heading", Some(1), "Materia"),
            ("paragraph", None, "2026 / Aug 21 / 7 tracks / 35m"),
            ("text", None, "Metacritic"),
            ("text", None, "87%"),
            ("text", None, "Paste"),
            ("text", None, "8.3/10"),
            ("text", None, "Pitchfork 9.2 Adventurous and precise."),
            ("text", None, "Guardian 5/5 A singular achievement."),
            ("paragraph", None, "Unrelated album history"),
        ]
        .into_iter()
        .map(|(kind, level, text)| ObservationContent {
            kind: kind.to_string(),
            level,
            context: None,
            text: text.to_string(),
        })
        .collect();
        operation.observation.elements = vec![
            ObservationElement {
                element_ref: "e1".to_string(),
                role: "link".to_string(),
                name: "Read Metacritic review".to_string(),
                states: Vec::new(),
                value: None,
                destination: Some("https://reviews.example/materia".to_string()),
                context: None,
                in_viewport: true,
                bounds: ObservationBounds {
                    x: 0.0,
                    y: 0.0,
                    width: 10.0,
                    height: 10.0,
                },
            },
            ObservationElement {
                element_ref: "e2".to_string(),
                role: "link".to_string(),
                name: "Other record".to_string(),
                states: Vec::new(),
                value: None,
                destination: Some("https://example.com/album/other".to_string()),
                context: None,
                in_viewport: false,
                bounds: ObservationBounds {
                    x: 0.0,
                    y: 0.0,
                    width: 10.0,
                    height: 10.0,
                },
            },
            ObservationElement {
                element_ref: "e3".to_string(),
                role: "link".to_string(),
                name: "Art Pop".to_string(),
                states: Vec::new(),
                value: None,
                destination: Some("https://example.com/genres/pop/art-pop".to_string()),
                context: None,
                in_viewport: true,
                bounds: ObservationBounds {
                    x: 0.0,
                    y: 0.0,
                    width: 10.0,
                    height: 10.0,
                },
            },
        ];

        let data = page_read_data(
            operation,
            Some("album details, genres, critic ratings and scores"),
            4_000,
            20,
        );
        let metacritic = data.markdown.find("Metacritic").unwrap();
        let metacritic_score = data.markdown.find("87%").unwrap();
        let paste = data.markdown.find("Paste").unwrap();
        let paste_score = data.markdown.find("8.3/10").unwrap();
        let pitchfork_score = data.markdown.find("Pitchfork 9.2").unwrap();
        let guardian_score = data.markdown.find("Guardian 5/5").unwrap();
        assert!(metacritic < metacritic_score);
        assert!(metacritic_score < paste);
        assert!(paste < paste_score);
        assert!(paste_score < pitchfork_score);
        assert!(pitchfork_score < guardian_score);
        assert!(data.markdown.contains("Art Pop"));
        assert!(data.markdown.contains("Read Metacritic review"));
        assert!(!data.markdown.contains("https://example.com/album/other"));
    }

    #[test]
    fn page_read_url_uses_semantic_navigate_observe() {
        let response_body = json!({
            "status": "ok",
            "request_id": "request-1",
            "data": observation_operation()
        });
        let (base_url, handle) = start_test_server(1, move |_, _| {
            http_json(200, "request-1", response_body.clone())
        });
        let response = RelClient::new(base_url)
            .read_page(&PageReadRequest {
                url: Some("https://example.com/guide".to_string()),
                query: Some("install".to_string()),
                ..PageReadRequest::default()
            })
            .unwrap();
        assert_eq!(response.data.observation_id, "observation-1");
        let requests = handle.join().unwrap();
        assert_eq!(requests[0].method, "POST");
        assert_eq!(requests[0].path, "/v1/navigate/observe");
        let body: Value = serde_json::from_str(&requests[0].body).unwrap();
        assert_eq!(body["mode"], "semantic");
    }

    #[test]
    fn retained_observation_can_be_read_without_navigation() {
        let response_body = json!({
            "status": "ok",
            "request_id": "request-1",
            "data": observation_operation()
        });
        let (base_url, handle) = start_test_server(1, move |_, _| {
            http_json(200, "request-1", response_body.clone())
        });
        let response = RelClient::new(base_url)
            .read_observation(
                "observation-1",
                &ObservationReadRequest {
                    query: Some("install".to_string()),
                    ..ObservationReadRequest::default()
                },
            )
            .unwrap();
        assert!(response.data.markdown.contains("Install the package"));
        let requests = handle.join().unwrap();
        assert_eq!(requests[0].method, "GET");
        assert_eq!(requests[0].path, "/v1/observations/observation-1");
    }

    #[test]
    fn fingerprint_round_trip_preserves_locale_mode_and_selected_controls() {
        let mut value = profile_json()["fingerprint_profile"].clone();
        value["locale_mode"] = json!("custom");
        value["locale"] = json!("fr-CA");
        value["overrides"] = json!(["locale", "audio"]);
        let profile: FingerprintProfile = serde_json::from_value(value.clone()).unwrap();
        assert_eq!(profile.locale_mode, Some(FingerprintLocaleMode::Custom));
        assert_eq!(serde_json::to_value(profile).unwrap(), value);
    }

    #[test]
    fn change_serializes_unchanged_as_missing_and_clear_as_null() {
        let request = ProxyUpdateRequest {
            upstream_host: Some("proxy.example.com".to_string()),
            username: Change::Clear,
            ..ProxyUpdateRequest::default()
        };
        assert_eq!(
            serde_json::to_value(request).unwrap(),
            serde_json::json!({"upstream_host":"proxy.example.com", "username":null})
        );
    }

    #[test]
    fn session_create_uses_default_profile_when_unchanged_and_accepts_named_profile() {
        assert_eq!(
            serde_json::to_value(SessionCreateRequest::default()).unwrap(),
            json!({})
        );
        assert_eq!(
            serde_json::to_value(SessionCreateRequest {
                group: Some("pgm".to_string()),
                profile: Some("BandwidthSaver".to_string()),
                proxy_alias: Change::Clear,
                ..SessionCreateRequest::default()
            })
            .unwrap(),
            json!({"group":"pgm", "profile":"BandwidthSaver", "proxy_alias":null})
        );
        let mut capture = CaptureRequest::new("https://example.com");
        capture.group = Some("pgm".to_string());
        capture.profile = Some("AdBlock".to_string());
        assert_eq!(
            serde_json::to_value(capture).unwrap(),
            json!({"url":"https://example.com", "profile":"AdBlock", "group":"pgm"})
        );
        assert_eq!(
            serde_json::to_value(SessionCreateRequest {
                image_blocking_mode: Some(ImageBlockingMode::None),
                ..SessionCreateRequest::default()
            })
            .unwrap(),
            json!({"image_blocking_mode":"none"})
        );
    }

    #[test]
    fn action_uses_the_canonical_rpc_shape() {
        let action = Action::ClickLink {
            link: "https://example.com/next".to_string(),
            match_rule: FuzzyLinkMatch::new(0.9),
            mouse_move: None,
            scroll: None,
        };
        assert_eq!(
            serde_json::to_value(action).unwrap(),
            serde_json::json!({
                "action":"click-link",
                "link":"https://example.com/next",
                "match":{"type":"fuzzy-link", "threshold":0.9}
            })
        );
        assert_eq!(
            serde_json::to_value(Action::Click {
                selector: "button.more".to_string(),
                mouse_move: None,
                scroll: None,
            })
            .unwrap(),
            serde_json::json!({"action":"click", "selector":"button.more"})
        );
        assert_eq!(
            serde_json::to_value(Action::Click {
                selector: "button.more".to_string(),
                mouse_move: Some(false),
                scroll: Some(false),
            })
            .unwrap(),
            serde_json::json!({
                "action":"click",
                "selector":"button.more",
                "mouse_move":false,
                "scroll":false
            })
        );
        assert_eq!(
            serde_json::to_value(Action::WaitFor {
                selector: "#loaded".to_string(),
                timeout: None,
            })
            .unwrap(),
            serde_json::json!({"action":"wait-for", "selector":"#loaded"})
        );
        assert_eq!(
            serde_json::to_value(Action::WaitFor {
                selector: "#loaded".to_string(),
                timeout: Some(2.5),
            })
            .unwrap(),
            serde_json::json!({
                "action":"wait-for", "selector":"#loaded", "timeout":2.5
            })
        );
        for (action, expected) in [
            (
                Action::Type {
                    selector: "#search".to_string(),
                    text: "Magickraft".to_string(),
                },
                serde_json::json!({
                    "action":"type", "selector":"#search", "text":"Magickraft"
                }),
            ),
            (
                Action::Clear {
                    selector: "#query".to_string(),
                },
                serde_json::json!({"action":"clear", "selector":"#query"}),
            ),
            (
                Action::Press {
                    selector: "#search".to_string(),
                    key: "Enter".to_string(),
                },
                serde_json::json!({
                    "action":"press", "selector":"#search", "key":"Enter"
                }),
            ),
            (
                Action::Select {
                    selector: "#genre".to_string(),
                    value: "disco".to_string(),
                },
                serde_json::json!({
                    "action":"select", "selector":"#genre", "value":"disco"
                }),
            ),
        ] {
            assert_eq!(serde_json::to_value(action).unwrap(), expected);
        }
    }

    #[test]
    fn observation_actions_serialize_as_one_sequence() {
        assert_eq!(
            serde_json::to_value(NavigateObservationRequest {
                navigation: Some(ObservationNavigation::Back),
                session_id: Some("Session1".to_string()),
                ..NavigateObservationRequest::default()
            })
            .unwrap(),
            json!({"navigation":"back","session_id":"Session1"})
        );
        let mut hover = ObservationAction::new("e2", ObservationActionKind::Hover);
        hover.scroll = Some(false);
        let request = ObservationActionRequest {
            actions: vec![
                ObservationAction::new("e1", ObservationActionKind::Click),
                hover,
                ObservationAction::scroll(0, -600),
                ObservationAction::wait(0.25),
            ],
            mode: Some(ObservationMode::Semantic),
            timeout: None,
            wait: None,
        };
        assert_eq!(
            serde_json::to_value(request).unwrap(),
            json!({
                "actions": [
                    {"ref":"e1","action":"click"},
                    {"ref":"e2","action":"hover","scroll":false},
                    {"action":"scroll","delta_x":0,"delta_y":-600},
                    {"action":"wait","seconds":0.25}
                ],
                "mode":"semantic"
            })
        );
    }

    #[test]
    fn path_segments_are_percent_encoded() {
        assert_eq!(encode_path_segment("page 1/a"), "page%201%2Fa");
    }

    #[test]
    fn every_ordinary_rpc_method_uses_the_v1_route_and_typed_envelope() {
        let (base_url, server) = start_test_server(38, |index, request| {
            let request_id = format!("req_{index}");
            let data = match (request.method.as_str(), request.path.as_str()) {
                ("GET", "/v1/health") => json!({
                    "version":"0.1.7", "pid":123, "browser_proxy_port":17400,
                    "build":{"id":"ba49-deadbeef-a1b2c3d4","configuration":"Debug",
                        "worktree":"ba49","branch":"codex/example","commit":"deadbeef",
                        "dirty":true},
                    "worker":{"state":"idle"}
                }),
                ("GET", "/v1/status") => json!({
                    "overall_status":"ok", "running_count":1, "total_count":1,
                    "build":{"id":"ba49-deadbeef-a1b2c3d4","configuration":"Debug",
                        "worktree":"ba49","branch":"codex/example","commit":"deadbeef",
                        "dirty":true},
                    "checks":[{"id":"agent","name":"Agent","kind":"service","running":true,
                        "status":"running","detail":"ready","pids":[123]}]
                }),
                ("GET", "/v1/notifications") => json!({
                    "notifications":[{
                        "sequence":1,
                        "session_id":"machine-a.Session1",
                        "origin":"https://example.com/",
                        "title":"Example",
                        "body":"Untrusted website content",
                        "notification_id":"notification-1",
                        "persistent":false,
                        "displayed_at":"2026-08-17T20:00:00Z",
                        "trust":"untrusted_website_content"
                    }],
                    "trust":"untrusted_website_content"
                }),
                ("POST", "/v1/navigate")
                | ("POST", "/v1/perform")
                | ("POST", "/v1/capture")
                | ("POST", "/v1/pages")
                | ("POST", "/v1/pages/page_1/actions") => json!({
                    "page":{"id":"page_1","session_id":"machine-a.Session1","url":"https://example.com/"},
                    "capture":{"output_path":"tmp/page.html","bytesize":10,"target_http_status":200}
                }),
                ("POST", "/v1/screenshot") | ("POST", "/v1/pages/page_1/screenshot") => json!({
                    "page":{"id":"page_1","session_id":"machine-a.Session1","url":"https://example.com/"},
                    "screenshot":{"output_path":"/tmp/page.webp","bytesize":11,"format":"webp","mime_type":"image/webp","width":1200,"height":800}
                }),
                ("POST", "/v1/navigate/observe")
                | ("POST", "/v1/observe")
                | ("POST", "/v1/pages/page_1/observe")
                | ("POST", "/v1/observations/11111111-1111-4111-8111-111111111111/actions") => {
                    json!({
                        "page":{"id":"page_1","session_id":"machine-a.Session1","url":"https://example.com/"},
                        "observation":{
                            "id":"22222222-2222-4222-8222-222222222222",
                            "mode":"semantic","document_sequence":4,"captured_at":"2026-08-17T00:00:00Z",
                            "title":"Example","truncated":false,"omitted_node_count":0,
                            "clipped_text_count":0,
                            "visited_node_count":3,"semantic_bytes":20,
                            "viewport":{"css_width":1200,"css_height":800,"scroll_x":0,"scroll_y":0,"document_width":1200,"document_height":800},
                            "content":[{"kind":"heading","level":1,"text":"Example"}],
                            "elements":[{"ref":"e1","role":"button","name":"Continue","states":["enabled"],"in_viewport":true,"bounds":{"x":10.0,"y":20.0,"width":100.0,"height":40.0}}]
                        }
                    })
                }
                ("POST", "/v1/observations/11111111-1111-4111-8111-111111111111/find") => json!({
                    "observation_id":"11111111-1111-4111-8111-111111111111",
                    "query":"continue","role":"button",
                    "matches":[{"type":"element","element":{"ref":"e1","role":"button","name":"Continue","states":["enabled"],"in_viewport":true,"bounds":{"x":10.0,"y":20.0,"width":100.0,"height":40.0}}}],
                    "total_matches":1,"truncated":false
                }),
                ("GET", "/v1/proxies") => json!({"proxies":[proxy_json()]}),
                ("GET", "/v1/proxies/office")
                | ("POST", "/v1/proxies")
                | ("PATCH", "/v1/proxies/office")
                | ("POST", "/v1/proxies/office/rotate-session") => json!({"proxy":proxy_json()}),
                ("DELETE", "/v1/proxies/office") => {
                    json!({"deleted_alias":"office"})
                }
                ("POST", "/v1/proxy-transfers/export") => {
                    json!({"filename":"office.relproxy","contents_base64":"U1FMaXRlIGZvcm1hdCAzAA=="})
                }
                ("POST", "/v1/proxy-transfers/import") => json!({"proxy":proxy_json()}),
                ("DELETE", "/v1/sessions/machine-a.Session1") => {
                    json!({"deleted_id":"machine-a.Session1"})
                }
                ("POST", "/v1/sessions/machine-a.Session1/pause") => {
                    json!({"session_id":"machine-a.Session1", "network_paused":true})
                }
                ("POST", "/v1/sessions/machine-a.Session1/play") => {
                    json!({"session_id":"machine-a.Session1", "network_paused":false})
                }
                ("POST", "/v1/sessions/close") => {
                    json!({"group":"pgm", "deleted_ids":["machine-a.Session1"]})
                }
                ("GET", "/v1/sessions") => json!({"sessions":[session_json()]}),
                ("GET", "/v1/sessions/machine-a.Session1")
                | ("POST", "/v1/sessions/machine-a.Session1/ping")
                | ("POST", "/v1/sessions")
                | ("PATCH", "/v1/sessions/machine-a.Session1") => json!({"session":session_json()}),
                ("GET", "/v1/profiles") => json!({"profiles":[profile_json()]}),
                ("POST", "/v1/profiles") | ("PATCH", "/v1/profiles/custom-profile-id") => {
                    json!({"profile":profile_json()})
                }
                ("DELETE", "/v1/profiles/custom-profile-id") => {
                    json!({"deleted_id":"custom-profile-id"})
                }
                ("POST", "/v1/profile-transfers/export") => {
                    json!({"filename":"Research.relprofile","contents_base64":"U1FMaXRlIGZvcm1hdCAzAA=="})
                }
                ("POST", "/v1/profile-transfers/import") => {
                    json!({"profile":profile_json()})
                }
                route => panic!("unexpected route {route:?}"),
            };
            http_json(
                200,
                &request_id,
                json!({"status":"ok", "request_id":request_id, "data":data}),
            )
        });
        let client = RelClient::new(base_url);

        let health = client.health().unwrap();
        assert_eq!(health.data.build.as_ref().unwrap().worktree, "ba49");
        let status = client.status().unwrap();
        assert_eq!(status.data.build, health.data.build);
        let notifications = client.list_notifications().unwrap();
        assert_eq!(notifications.data.notifications[0].sequence, 1);
        assert_eq!(notifications.data.trust, "untrusted_website_content");
        client
            .navigate(&NavigateRequest::new("example.com"))
            .unwrap();
        let mut perform = PerformRequest::new(vec![
            Action::ClickLink {
                link: "https://example.com/more".to_string(),
                match_rule: FuzzyLinkMatch::new(1.0),
                mouse_move: None,
                scroll: None,
            },
            Action::Wait { seconds: 0.0 },
        ]);
        perform.session_id = Some("machine-a.Session1".to_string());
        client.perform(&perform).unwrap();
        client
            .capture_current_page(&PageCaptureRequest {
                session_id: Some("machine-a.Session1".to_string()),
                ..PageCaptureRequest::default()
            })
            .unwrap();
        client
            .screenshot_current_page(&ScreenshotRequest {
                session_id: Some("machine-a.Session1".to_string()),
                format: Some(ScreenshotFormat::Webp),
                quality: Some(80),
                full_page: true,
                ..ScreenshotRequest::default()
            })
            .unwrap();
        client
            .attach_page(&PageAttachRequest::new("example.com"))
            .unwrap();
        client
            .perform_page_action(
                "page_1",
                &PageActionRequest {
                    action: Action::Wait { seconds: 0.0 },
                    output: None,
                    timeout: None,
                    wait: None,
                },
            )
            .unwrap();
        client
            .take_page_screenshot(
                "page_1",
                &PageScreenshotRequest {
                    format: Some(ScreenshotFormat::Png),
                    ..PageScreenshotRequest::default()
                },
            )
            .unwrap();
        client
            .observe_current_page(&ObservationRequest {
                session_id: Some("machine-a.Session1".to_string()),
                mode: Some(ObservationMode::Semantic),
                timeout: None,
                wait: None,
            })
            .unwrap();
        client
            .navigate_and_observe(&NavigateObservationRequest::new("example.com"))
            .unwrap();
        client
            .observe_page("page_1", &PageObservationRequest::default())
            .unwrap();
        client
            .perform_observation_action(
                "11111111-1111-4111-8111-111111111111",
                &ObservationActionRequest::new("e1", ObservationActionKind::Click),
            )
            .unwrap();
        client
            .find_in_observation(
                "11111111-1111-4111-8111-111111111111",
                &ObservationFindRequest {
                    query: Some("continue".to_string()),
                    role: Some("button".to_string()),
                    limit: Some(5),
                },
            )
            .unwrap();
        client.list_proxies().unwrap();
        client.get_proxy("office").unwrap();
        client
            .create_proxy(&ProxyCreateRequest {
                alias: "office".to_string(),
                upstream_host: "proxy.example.com".to_string(),
                upstream_port: 8000,
                ..ProxyCreateRequest::default()
            })
            .unwrap();
        client
            .update_proxy(
                "office",
                &ProxyUpdateRequest {
                    username: Change::Clear,
                    ..ProxyUpdateRequest::default()
                },
            )
            .unwrap();
        client.delete_proxy("office").unwrap();
        client.rotate_proxy_session("office").unwrap();
        client
            .export_proxy_transfer(&ProxyTransferExportRequest {
                alias: "office".to_string(),
                include_credentials: false,
                passphrase: None,
            })
            .unwrap();
        client
            .import_proxy_transfer(&ProxyTransferImportRequest::from_bytes(
                b"SQLite format 3\0",
                Some("backup".to_string()),
                None,
            ))
            .unwrap();
        let sessions = client.list_sessions().unwrap();
        assert_eq!(sessions.data.sessions[0].id, "machine-a.Session1");
        assert_eq!(sessions.data.sessions[0].group.as_deref(), Some("pgm"));
        client.get_session("machine-a.Session1").unwrap();
        client
            .create_session(&SessionCreateRequest::default())
            .unwrap();
        client.ping_session("machine-a.Session1").unwrap();
        let profiles = client.list_profiles().unwrap();
        assert_eq!(
            profiles.data.profiles[0]
                .fingerprint_profile
                .as_ref()
                .map(|profile| profile.seed.as_str()),
            Some("12345")
        );
        client
            .create_profile(&ProfileCreateRequest {
                name: "Research".to_string(),
                proxy_alias: None,
                adblock_enabled: Some(true),
                image_blocking_mode: Some(ImageBlockingMode::OverLimit),
                image_size_limit_kb: Some(10),
                includes_cookies: Some(false),
                includes_passwords: Some(false),
                fingerprint_profile: Change::Unchanged,
            })
            .unwrap();
        client
            .update_profile_data(
                "custom-profile-id",
                &ProfileDataUpdateRequest {
                    includes_cookies: true,
                    includes_passwords: true,
                },
            )
            .unwrap();
        client.delete_profile("custom-profile-id").unwrap();
        client
            .export_profile_transfer(&ProfileTransferExportRequest {
                name: "Research".to_string(),
                include_cookies: false,
                include_passwords: false,
                include_proxy_credentials: false,
                passphrase: None,
            })
            .unwrap();
        client
            .import_profile_transfer(&ProfileTransferImportRequest::from_bytes(
                b"SQLite format 3\0",
                Some("Research Copy".to_string()),
                None,
            ))
            .unwrap();
        client
            .update_session(
                "machine-a.Session1",
                &SessionUpdateRequest {
                    proxy_alias: Change::Clear,
                    ..SessionUpdateRequest::default()
                },
            )
            .unwrap();
        let paused = client.pause_session("machine-a.Session1").unwrap();
        assert!(paused.data.network_paused);
        let playing = client.play_session("machine-a.Session1").unwrap();
        assert!(!playing.data.network_paused);
        let deleted = client.delete_session("machine-a.Session1").unwrap();
        assert_eq!(deleted.data.deleted_id, "machine-a.Session1");
        let closed = client.close_session_group("pgm").unwrap();
        assert_eq!(closed.data.deleted_ids, ["machine-a.Session1"]);

        let requests = server.join().unwrap();
        let routes = requests
            .iter()
            .map(|request| (request.method.as_str(), request.path.as_str()))
            .collect::<Vec<_>>();
        assert_eq!(
            routes,
            vec![
                ("GET", "/v1/health"),
                ("GET", "/v1/status"),
                ("GET", "/v1/notifications"),
                ("POST", "/v1/navigate"),
                ("POST", "/v1/perform"),
                ("POST", "/v1/capture"),
                ("POST", "/v1/screenshot"),
                ("POST", "/v1/pages"),
                ("POST", "/v1/pages/page_1/actions"),
                ("POST", "/v1/pages/page_1/screenshot"),
                ("POST", "/v1/observe"),
                ("POST", "/v1/navigate/observe"),
                ("POST", "/v1/pages/page_1/observe"),
                (
                    "POST",
                    "/v1/observations/11111111-1111-4111-8111-111111111111/actions"
                ),
                (
                    "POST",
                    "/v1/observations/11111111-1111-4111-8111-111111111111/find"
                ),
                ("GET", "/v1/proxies"),
                ("GET", "/v1/proxies/office"),
                ("POST", "/v1/proxies"),
                ("PATCH", "/v1/proxies/office"),
                ("DELETE", "/v1/proxies/office"),
                ("POST", "/v1/proxies/office/rotate-session"),
                ("POST", "/v1/proxy-transfers/export"),
                ("POST", "/v1/proxy-transfers/import"),
                ("GET", "/v1/sessions"),
                ("GET", "/v1/sessions/machine-a.Session1"),
                ("POST", "/v1/sessions"),
                ("POST", "/v1/sessions/machine-a.Session1/ping"),
                ("GET", "/v1/profiles"),
                ("POST", "/v1/profiles"),
                ("PATCH", "/v1/profiles/custom-profile-id"),
                ("DELETE", "/v1/profiles/custom-profile-id"),
                ("POST", "/v1/profile-transfers/export"),
                ("POST", "/v1/profile-transfers/import"),
                ("PATCH", "/v1/sessions/machine-a.Session1"),
                ("POST", "/v1/sessions/machine-a.Session1/pause"),
                ("POST", "/v1/sessions/machine-a.Session1/play"),
                ("DELETE", "/v1/sessions/machine-a.Session1"),
                ("POST", "/v1/sessions/close"),
            ]
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[37].body).unwrap(),
            json!({"group":"pgm"})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[3].body).unwrap(),
            json!({"url":"example.com"})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[4].body).unwrap(),
            json!({"session_id":"machine-a.Session1","actions":[
                {"action":"click-link","link":"https://example.com/more","match":{"type":"fuzzy-link","threshold":1.0}},
                {"action":"wait","seconds":0.0}
            ]})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[5].body).unwrap(),
            json!({"session_id":"machine-a.Session1"})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[6].body).unwrap(),
            json!({
                "session_id":"machine-a.Session1",
                "format":"webp",
                "quality":80,
                "full_page":true
            })
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[11].body).unwrap(),
            json!({"url":"example.com"})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[13].body).unwrap(),
            json!({"actions":[{"ref":"e1","action":"click"}]})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[14].body).unwrap(),
            json!({"query":"continue","role":"button","limit":5})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[17].body).unwrap(),
            json!({"alias":"office","upstream_host":"proxy.example.com","upstream_port":8000})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[18].body).unwrap(),
            json!({"username":null})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[21].body).unwrap(),
            json!({"alias":"office","include_credentials":false})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[22].body).unwrap(),
            json!({"contents_base64":"U1FMaXRlIGZvcm1hdCAzAA==","alias":"backup"})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[28].body).unwrap(),
            json!({
                "name":"Research",
                "adblock_enabled":true,
                "image_blocking_mode":"over_limit",
                "image_size_limit_kb":10,
                "includes_cookies":false,
                "includes_passwords":false
            })
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[29].body).unwrap(),
            json!({"includes_cookies":true,"includes_passwords":true})
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[31].body).unwrap(),
            json!({
                "name":"Research",
                "include_cookies":false,
                "include_passwords":false,
                "include_proxy_credentials":false
            })
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[32].body).unwrap(),
            json!({
                "contents_base64":"U1FMaXRlIGZvcm1hdCAzAA==",
                "name":"Research Copy"
            })
        );
        assert_eq!(
            serde_json::from_str::<Value>(&requests[33].body).unwrap(),
            json!({"proxy_alias":null})
        );
    }

    #[test]
    fn structured_rpc_errors_are_preserved_and_protocol_is_validated() {
        let (base_url, server) = start_test_server(1, |_index, _request| {
            http_json(
                404,
                "req_missing",
                json!({
                    "status":"error",
                    "request_id":"req_missing",
                    "error":{
                        "id":"SESSION_NOT_FOUND",
                        "code":10100,
                        "message":"Session machine-a.Session999 was not found.",
                        "retryable":false,
                        "details":{"id":"machine-a.Session999"}
                    }
                }),
            )
        });
        let error = RelClient::new(base_url)
            .get_session("machine-a.Session999")
            .unwrap_err();
        let failure = error.rpc_failure().unwrap();
        assert_eq!(failure.request_id, "req_missing");
        assert_eq!(failure.error.id, "SESSION_NOT_FOUND");
        assert_eq!(failure.error.code, rpc_error_codes::SESSION_NOT_FOUND);
        assert_eq!(
            failure.error.details.as_ref().unwrap()["id"],
            "machine-a.Session999"
        );
        server.join().unwrap();

        let (base_url, server) = start_test_server(1, |_index, _request| {
            http_json(
                404,
                "req_legacy",
                json!({
                    "status":"error",
                    "request_id":"req_legacy",
                    "error":{
                        "id":"SESSION_NOT_FOUND",
                        "http_code":404,
                        "message":"Session machine-a.Session999 was not found.",
                        "retryable":false
                    }
                }),
            )
        });
        assert!(matches!(
            RelClient::new(base_url).get_session("machine-a.Session999"),
            Err(ClientError::Protocol(message)) if message.contains("unknown field `http_code`")
        ));
        server.join().unwrap();

        let (base_url, server) = start_test_server(1, |_index, _request| {
            http_json(
                404,
                "req_http_like_code",
                json!({
                    "status":"error",
                    "request_id":"req_http_like_code",
                    "error":{
                        "id":"SESSION_NOT_FOUND",
                        "code":404,
                        "message":"Session machine-a.Session999 was not found.",
                        "retryable":false
                    }
                }),
            )
        });
        assert!(matches!(
            RelClient::new(base_url).get_session("machine-a.Session999"),
            Err(ClientError::Protocol(message)) if message.contains("incomplete error object")
        ));
        server.join().unwrap();

        let (base_url, server) = start_test_server(1, |_index, _request| {
            http_json(
                404,
                "req_mismatched_code",
                json!({
                    "status":"error",
                    "request_id":"req_mismatched_code",
                    "error":{
                        "id":"SESSION_NOT_FOUND",
                        "code":10303,
                        "message":"Session machine-a.Session999 was not found.",
                        "retryable":false
                    }
                }),
            )
        });
        assert!(matches!(
            RelClient::new(base_url).get_session("machine-a.Session999"),
            Err(ClientError::Protocol(message)) if message.contains("incomplete error object")
        ));
        server.join().unwrap();

        let (base_url, server) = start_test_server(1, |_index, _request| {
            http_response(
                200,
                "text/plain",
                Some("req_wrong_type"),
                r#"{"status":"ok","request_id":"req_wrong_type","data":{}}"#,
            )
        });
        assert!(matches!(
            RelClient::new(base_url).list_proxies(),
            Err(ClientError::Protocol(message)) if message.contains("Content-Type")
        ));
        server.join().unwrap();

        let (base_url, server) = start_test_server(1, |_index, _request| {
            http_json(
                200,
                "req_header",
                json!({"status":"ok","request_id":"req_body","data":{"proxies":[]}}),
            )
        });
        assert!(matches!(
            RelClient::new(base_url).list_proxies(),
            Err(ClientError::Protocol(message)) if message.contains("request ID mismatch")
        ));
        server.join().unwrap();
    }

    #[test]
    fn capture_stream_is_validated_and_exposes_the_terminal_exit_code() {
        let (base_url, server) = start_test_server(1, |_index, _request| {
            let body = [
                json!({"status":"ok","request_id":"req_capture","event":"capture.started","data":{"url":"https://example.com/"}}).to_string(),
                json!({"status":"error","request_id":"req_capture","event":"capture.failed","error":{"id":"TIMEOUT","code":10303,"message":"Timed out.","retryable":true},"data":{}}).to_string(),
                json!({"status":"ok","request_id":"req_capture","event":"capture.finished","data":{"exit_code":1}}).to_string(),
            ]
            .join("\n")
                + "\n";
            http_response(200, "application/x-ndjson", Some("req_capture"), &body)
        });
        let client = RelClient::new(base_url);
        let mut stream = client.capture(&CaptureRequest::new("example.com")).unwrap();
        let events = stream
            .by_ref()
            .collect::<Result<Vec<_>, ClientError>>()
            .unwrap();
        assert_eq!(events.len(), 3);
        assert_eq!(events[1].error.as_ref().unwrap().id, "TIMEOUT");
        assert!(stream.is_finished());
        assert_eq!(stream.exit_code(), Some(1));
        let requests = server.join().unwrap();
        assert_eq!(requests[0].method, "POST");
        assert_eq!(requests[0].path, "/v1/captures");
        assert_eq!(
            serde_json::from_str::<Value>(&requests[0].body).unwrap(),
            json!({"url":"example.com"})
        );
    }
}

#[cfg(test)]
mod database_recovery_tests {
    use super::*;

    #[test]
    fn health_preserves_recovery_summary_and_accepts_older_agents() {
        let mut json = serde_json::json!({
            "version": "0.1.39", "pid": 42, "browser_proxy_port": 17400,
            "build": null, "worker": {"state": "idle"}
        });
        let legacy: Health = serde_json::from_value(json.clone()).unwrap();
        assert!(legacy.database_recovery.is_none());
        json["database_recovery"] = serde_json::json!({
            "schema_version": 14, "backup_path": "/tmp/original.sqlite3",
            "report_path": "/tmp/report.json", "issue_count": 1, "retained_sessions": 2
        });
        let health: Health = serde_json::from_value(json.clone()).unwrap();
        assert_eq!(serde_json::to_value(health).unwrap(), json);
    }
}
