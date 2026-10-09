use std::env;
use std::ffi::OsStr;
use std::fs::{File, OpenOptions};
use std::io;
use std::os::fd::AsRawFd;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const DEFAULT_AGENT_PORT: u16 = 17319;
const REL_AGENT_PORT_ENV: &str = "REL_AGENT_PORT";
const REL_APP_PATH_ENV: &str = "REL_APP_PATH";

pub(crate) fn ensure_agent_running() -> Result<(), String> {
    let port = agent_port();
    if agent_is_healthy(port) {
        return Ok(());
    }

    let _launch_lock = acquire_launch_lock(port)?;
    if agent_is_healthy(port) {
        return Ok(());
    }

    launch_app()?;
    wait_for_agent(port, Duration::from_secs(8))
}

fn acquire_launch_lock(port: u16) -> Result<File, String> {
    let path = env::temp_dir().join(format!("rel-agent-{port}.launch.lock"));
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .open(&path)
        .map_err(|error| format!("Could not open REL launch lock {}: {error}", path.display()))?;

    loop {
        // SAFETY: `file` owns a valid descriptor for the duration of the lock,
        // and `flock` does not retain the descriptor after returning.
        let result = unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX) };
        if result == 0 {
            return Ok(file);
        }
        let error = io::Error::last_os_error();
        if error.kind() != io::ErrorKind::Interrupted {
            return Err(format!(
                "Could not lock REL launch coordination file {}: {error}",
                path.display()
            ));
        }
    }
}

fn agent_port() -> u16 {
    env::var(REL_AGENT_PORT_ENV)
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .filter(|port| *port != 0)
        .unwrap_or(DEFAULT_AGENT_PORT)
}

fn agent_is_healthy(port: u16) -> bool {
    let response = ureq::get(&format!("http://127.0.0.1:{port}/v1/health"))
        .timeout(Duration::from_millis(300))
        .call();
    let Ok(response) = response else {
        return false;
    };
    response
        .into_string()
        .map(|body| body.contains("\"status\":\"ok\""))
        .unwrap_or(false)
}

fn wait_for_agent(port: u16, timeout: Duration) -> Result<(), String> {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if agent_is_healthy(port) {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(150));
    }
    Err(format!(
        "REL agent did not become ready on 127.0.0.1:{port}"
    ))
}

fn launch_app() -> Result<(), String> {
    let app_path = app_path()?;
    let status = Command::new("/usr/bin/open")
        .args(["-gj"])
        .arg(&app_path)
        .stdout(Stdio::null())
        .status()
        .map_err(|error| format!("Could not launch {}: {error}", app_path.display()))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!(
            "Could not launch REL.app at {}",
            app_path.display()
        ))
    }
}

fn app_path() -> Result<PathBuf, String> {
    if let Some(path) = env::var_os(REL_APP_PATH_ENV).filter(|path| !path.is_empty()) {
        let path = PathBuf::from(path);
        return if path.is_dir() {
            Ok(path)
        } else {
            Err(format!(
                "REL_APP_PATH is not an app directory: {}",
                path.display()
            ))
        };
    }

    if let Ok(executable) = env::current_exe() {
        if let Some(app) = app_bundle_ancestor(&executable) {
            return Ok(app);
        }
    }

    let home = env::var_os("HOME")
        .filter(|home| !home.is_empty())
        .map(PathBuf::from);
    let installed_app = find_app_in_directories(
        Path::new("/Applications"),
        home.as_deref(),
        registered_app_path,
    );
    installed_app.ok_or_else(|| {
        "REL.app was not found. Download REL from https://rel.me or set REL_APP_PATH to its app bundle.".to_string()
    })
}

fn find_app_in_directories(
    applications: &Path,
    home: Option<&Path>,
    registered_app: impl FnOnce() -> Option<PathBuf>,
) -> Option<PathBuf> {
    let installed_app = applications.join("REL.app");
    if installed_app.is_dir() {
        return Some(installed_app);
    }
    if let Some(home) = home {
        let user_app = home.join("Applications/REL.app");
        if user_app.is_dir() {
            return Some(user_app);
        }
    }
    registered_app().filter(|app| app.is_dir())
}

fn registered_app_path() -> Option<PathBuf> {
    // Resolving an application through Launch Services does not launch it.
    let output = Command::new("/usr/bin/osascript")
        .args([
            "-e",
            "POSIX path of (path to application id \"me.rel.Rel\")",
        ])
        .stderr(Stdio::null())
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let path = String::from_utf8(output.stdout).ok()?;
    let path = path.trim_end_matches(['\r', '\n']);
    (!path.is_empty()).then(|| PathBuf::from(path))
}

fn app_bundle_ancestor(path: &Path) -> Option<PathBuf> {
    path.ancestors()
        .find(|ancestor| ancestor.extension() == Some(OsStr::new("app")))
        .map(Path::to_path_buf)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;

    #[test]
    fn finds_an_app_bundle_ancestor() {
        assert_eq!(
            app_bundle_ancestor(Path::new("/Applications/REL.app/Contents/Resources/rel")),
            Some(PathBuf::from("/Applications/REL.app"))
        );
        assert_eq!(app_bundle_ancestor(Path::new("/usr/local/bin/rel")), None);
        assert_eq!(
            app_bundle_ancestor(Path::new(
                "/Users/me/My Apps/REL.app/Contents/Resources/rel"
            )),
            Some(PathBuf::from("/Users/me/My Apps/REL.app"))
        );
    }

    #[test]
    fn discovers_installed_apps_in_priority_order() {
        let root = env::temp_dir().join(format!("rel-discovery-{}", uuid::Uuid::new_v4()));
        let applications = root.join("Applications");
        let home = root.join("home");
        let system_app = applications.join("REL.app");
        let user_app = home.join("Applications/REL.app");
        let registered_app = root.join("Custom Apps/Renamed REL.app");
        for app in [&system_app, &user_app, &registered_app] {
            std::fs::create_dir_all(app).unwrap();
        }
        let discover =
            || find_app_in_directories(&applications, Some(&home), || Some(registered_app.clone()));
        assert_eq!(discover(), Some(system_app.clone()));
        std::fs::remove_dir(system_app).unwrap();
        assert_eq!(discover(), Some(user_app.clone()));
        std::fs::remove_dir(user_app).unwrap();
        assert_eq!(discover(), Some(registered_app.clone()));
        std::fs::remove_dir(&registered_app).unwrap();
        assert_eq!(discover(), None);
        assert_eq!(find_app_in_directories(&applications, None, || None), None);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn launch_lock_serializes_callers() {
        let listener = std::net::TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        drop(listener);

        let first = acquire_launch_lock(port).unwrap();
        let (sender, receiver) = mpsc::channel();
        let waiter = thread::spawn(move || {
            let second = acquire_launch_lock(port).unwrap();
            sender.send(()).unwrap();
            drop(second);
        });

        assert!(receiver.recv_timeout(Duration::from_millis(100)).is_err());
        drop(first);
        receiver.recv_timeout(Duration::from_secs(1)).unwrap();
        waiter.join().unwrap();
    }
}
