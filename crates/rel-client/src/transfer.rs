pub const PROFILE_TRANSFER_FORMAT: &str = "rel.profile";
pub const PROXY_TRANSFER_FORMAT: &str = "rel.proxy";
pub const TRANSFER_FORMAT_VERSION: u32 = 1;
pub const MAX_TRANSFER_FILE_BYTES: usize = 12 * 1024 * 1024;

const SQLITE_HEADER: &[u8; 16] = b"SQLite format 3\0";

pub fn validate_transfer_file(data: &[u8]) -> Result<(), String> {
    if data.len() > MAX_TRANSFER_FILE_BYTES {
        return Err(format!(
            "Transfer file exceeds the {MAX_TRANSFER_FILE_BYTES} byte limit"
        ));
    }
    if !data.starts_with(SQLITE_HEADER) {
        return Err("REL transfer files must be SQLite databases".to_string());
    }
    Ok(())
}

pub fn profile_transfer_filename(name: &str) -> String {
    transfer_filename(name, "relprofile", "Profile")
}

pub fn proxy_transfer_filename(alias: &str) -> String {
    transfer_filename(alias, "relproxy", "Proxy")
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

    #[test]
    fn accepts_bounded_sqlite_files() {
        let mut data = SQLITE_HEADER.to_vec();
        data.extend_from_slice(&[0; 32]);
        assert!(validate_transfer_file(&data).is_ok());
        assert!(validate_transfer_file(br#"{"format":"rel.profile"}"#)
            .unwrap_err()
            .contains("SQLite"));
        assert!(
            validate_transfer_file(&vec![0; MAX_TRANSFER_FILE_BYTES + 1])
                .unwrap_err()
                .contains("byte limit")
        );
    }

    #[test]
    fn produces_private_transfer_names() {
        assert_eq!(
            profile_transfer_filename("Research/Primary"),
            "Research-Primary.relprofile"
        );
        assert_eq!(proxy_transfer_filename("office"), "office.relproxy");
    }
}
