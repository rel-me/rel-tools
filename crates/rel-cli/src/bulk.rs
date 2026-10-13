use super::*;
use std::path::Path;

pub(super) fn export(
    client: &RelClient,
    profiles: bool,
    directory: &Path,
) -> Result<i32, CliError> {
    // Built-in profiles already exist on every installation and cannot be imported as custom profiles.
    let names: Vec<String> = if profiles {
        client
            .list_profiles()?
            .data
            .profiles
            .into_iter()
            .filter(|p| !p.is_builtin)
            .map(|p| p.name)
            .collect()
    } else {
        client
            .list_proxies()?
            .data
            .proxies
            .into_iter()
            .map(|p| p.alias)
            .collect()
    };
    fs::DirBuilder::new()
        .mode(0o700)
        .create(directory)
        .map_err(|error| {
            CliError::Message(format!(
                "Could not create export directory {}: {error}",
                directory.display()
            ))
        })?;
    let mut results = Vec::new();
    for (index, name) in names.into_iter().enumerate() {
        let result = (|| {
            let transfer = if profiles {
                client
                    .export_profile_transfer(&ProfileTransferExportRequest {
                        name: name.clone(),
                        include_cookies: false,
                        include_passwords: false,
                        include_proxy_credentials: false,
                        passphrase: None,
                    })?
                    .data
            } else {
                client
                    .export_proxy_transfer(&ProxyTransferExportRequest {
                        alias: name.clone(),
                        include_credentials: false,
                        passphrase: None,
                    })?
                    .data
            };
            let contents = transfer.contents().map_err(CliError::Message)?;
            validate_transfer_file(&contents).map_err(CliError::Message)?;
            // A numeric prefix keeps sanitized names distinct and prevents path traversal.
            let extension = if profiles { "relprofile" } else { "relproxy" };
            let path = directory.join(format!("{:06}.{extension}", index + 1));
            let path =
                write_transfer_file(&contents, Some(path), "unused").map_err(CliError::Message)?;
            Ok::<_, CliError>(serde_json::json!({"name": name, "path": path, "status": "ok"}))
        })();
        results.push(result.unwrap_or_else(|error| failure(&name, error)));
    }
    eprintln!("warning: bulk exports contain settings only; app-protected secrets are excluded");
    report(results)
}

pub(super) fn import(
    client: &RelClient,
    profiles: bool,
    directory: &Path,
) -> Result<i32, CliError> {
    let extension = if profiles { "relprofile" } else { "relproxy" };
    let mut paths = fs::read_dir(directory)
        .map_err(|error| {
            CliError::Message(format!(
                "Could not read import directory {}: {error}",
                directory.display()
            ))
        })?
        .map(|entry| entry.map(|entry| entry.path()))
        .collect::<Result<Vec<_>, _>>()
        .map_err(|error| CliError::Message(format!("Could not list transfer files: {error}")))?;
    paths.retain(|path| path.extension().and_then(|value| value.to_str()) == Some(extension));
    paths.sort();
    if paths.is_empty() {
        return Err(CliError::Message(format!(
            "No .{extension} files in {}",
            directory.display()
        )));
    }
    // Validate every local file before making any remote changes.
    let files = paths
        .into_iter()
        .map(|path| {
            let data = read_transfer_file(&path).map_err(CliError::Message)?;
            validate_transfer_file(&data).map_err(CliError::Message)?;
            Ok((path, data))
        })
        .collect::<Result<Vec<_>, CliError>>()?;
    let mut results = Vec::new();
    for (path, data) in files {
        let result = if profiles {
            client
                .import_profile_transfer(&ProfileTransferImportRequest::from_bytes(
                    &data, None, None,
                ))
                .map(|response| serde_json::to_value(response).expect("serializable response"))
        } else {
            client
                .import_proxy_transfer(&ProxyTransferImportRequest::from_bytes(&data, None, None))
                .map(|response| serde_json::to_value(response).expect("serializable response"))
        };
        results.push(match result {
            Ok(response) => serde_json::json!({"path": path, "status": "ok", "response": response}),
            Err(error) => failure(&path.display().to_string(), CliError::Client(error)),
        });
    }
    report(results)
}

fn failure(item: &str, error: CliError) -> serde_json::Value {
    let message = match error {
        CliError::Client(error) => error.to_string(),
        CliError::Message(message) => message,
        _ => "Transfer failed".into(),
    };
    serde_json::json!({"item": item, "status": "error", "error": message})
}

fn report(results: Vec<serde_json::Value>) -> Result<i32, CliError> {
    let failed = results
        .iter()
        .filter(|result| result["status"] == "error")
        .count();
    print_json(&serde_json::json!({
        "status": if failed == 0 { "ok" } else { "error" },
        "succeeded": results.len() - failed, "failed": failed, "results": results,
    }))?;
    Ok(i32::from(failed != 0))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn invalid_local_file_prevents_all_import_requests() {
        let directory = std::env::temp_dir().join(format!("rel-bulk-{}", Uuid::new_v4()));
        fs::create_dir(&directory).unwrap();
        fs::write(directory.join("a.relproxy"), b"SQLite format 3\0fixture").unwrap();
        fs::write(directory.join("b.relproxy"), b"not a transfer").unwrap();
        let error =
            import(&RelClient::new("http://127.0.0.1:1/v1"), false, &directory).unwrap_err();
        assert!(matches!(error, CliError::Message(message) if message.contains("SQLite")));
        fs::remove_dir_all(directory).unwrap();
    }
}
