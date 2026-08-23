use rel_client::transfer::MAX_TRANSFER_FILE_BYTES;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};

pub(crate) fn read_transfer_file(path: &Path) -> Result<Vec<u8>, String> {
    let metadata = fs::metadata(path).map_err(|error| {
        format!(
            "Could not inspect transfer file {}: {error}",
            path.display()
        )
    })?;
    if !metadata.is_file() {
        return Err(format!("Transfer path {} is not a file", path.display()));
    }
    if metadata.len() > MAX_TRANSFER_FILE_BYTES as u64 {
        return Err(format!(
            "Transfer file {} exceeds the {} byte limit",
            path.display(),
            MAX_TRANSFER_FILE_BYTES
        ));
    }
    fs::read(path)
        .map_err(|error| format!("Could not read transfer file {}: {error}", path.display()))
}

pub(crate) fn write_transfer_file(
    data: &[u8],
    output: Option<PathBuf>,
    default_filename: &str,
) -> Result<PathBuf, String> {
    if data.len() > MAX_TRANSFER_FILE_BYTES {
        return Err(format!(
            "Transfer file exceeds the {MAX_TRANSFER_FILE_BYTES} byte limit"
        ));
    }
    let requested_path = output.unwrap_or_else(|| PathBuf::from(default_filename));
    let path = if requested_path.is_absolute() {
        requested_path
    } else {
        std::env::current_dir()
            .map_err(|error| format!("Could not resolve the current directory: {error}"))?
            .join(requested_path)
    };

    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&path)
        .map_err(|error| format!("Could not create transfer file {}: {error}", path.display()))?;
    if let Err(error) = file.write_all(data).and_then(|()| file.flush()) {
        drop(file);
        let _ = fs::remove_file(&path);
        return Err(format!(
            "Could not write transfer file {}: {error}",
            path.display()
        ));
    }
    Ok(path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;
    use uuid::Uuid;

    #[test]
    fn transfer_files_are_private_bounded_and_never_overwritten() {
        let directory = std::env::temp_dir().join(format!("rel-transfer-test-{}", Uuid::new_v4()));
        fs::create_dir(&directory).unwrap();
        let path = directory.join("profile.relprofile");
        let data = b"SQLite format 3\0transfer-test";

        let written = write_transfer_file(data, Some(path.clone()), "unused").unwrap();
        assert_eq!(written, path);
        assert_eq!(
            fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
        assert_eq!(read_transfer_file(&path).unwrap(), data);
        assert!(write_transfer_file(data, Some(path.clone()), "unused").is_err());

        fs::remove_file(path).unwrap();
        fs::remove_dir(directory).unwrap();
    }
}
