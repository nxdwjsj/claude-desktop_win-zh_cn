use serde::Serialize;
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::Manager;

const EMBEDDED_FILES: &[(&str, &[u8])] = &[
    ("tools/launcher_bridge.py", include_bytes!("../../tools/launcher_bridge.py")),
    ("patch_windowsapps_json_only.py", include_bytes!("../../patch_windowsapps_json_only.py")),
    ("patch_chunks_zh_cn.py", include_bytes!("../../patch_chunks_zh_cn.py")),
    ("restore_claude_zh_cn_windowsapps.py", include_bytes!("../../restore_claude_zh_cn_windowsapps.py")),
    ("best_effort_io.py", include_bytes!("../../best_effort_io.py")),
    ("resources/desktop-zh-CN.json", include_bytes!("../../resources/desktop-zh-CN.json")),
    ("resources/frontend-zh-CN.json", include_bytes!("../../resources/frontend-zh-CN.json")),
    ("resources/statsig-zh-CN.json", include_bytes!("../../resources/statsig-zh-CN.json")),
];

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BridgeError {
    ok: bool,
    state: String,
    message: String,
    log: String,
}

fn materialize_embedded_files(root: &Path) -> Result<(), String> {
    for (relative_path, contents) in EMBEDDED_FILES {
        let destination = root.join(relative_path);
        if fs::read(&destination).map(|current| current == *contents).unwrap_or(false) {
            continue;
        }
        if let Some(parent) = destination.parent() {
            fs::create_dir_all(parent).map_err(|err| {
                format!("failed to create runtime directory {}: {err}", parent.display())
            })?;
        }
        fs::write(&destination, contents).map_err(|err| {
            format!("failed to write runtime resource {}: {err}", destination.display())
        })?;
    }
    Ok(())
}

fn project_root(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let development_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    if cfg!(debug_assertions)
        && development_root.join("tools").join("launcher_bridge.py").exists()
    {
        return Ok(development_root);
    }

    let root = app
        .path()
        .app_local_data_dir()
        .map_err(|err| format!("failed to resolve app data directory: {err}"))?
        .join("runtime")
        .join(env!("CARGO_PKG_VERSION"));
    materialize_embedded_files(&root)?;
    Ok(root)
}

fn python_command() -> Command {
    let mut candidates = vec![
        "python".to_string(),
        "py".to_string(),
    ];
    if let Ok(custom) = std::env::var("CLAUDE_ZH_PYTHON") {
        candidates.insert(0, custom);
    }

    for name in candidates {
        let mut probe = Command::new(&name);
        probe.arg("--version");
        if probe.output().map(|o| o.status.success()).unwrap_or(false) {
            return Command::new(name);
        }
    }
    Command::new("python")
}

fn bridge_script(root: &Path) -> PathBuf {
    let primary = root.join("tools").join("launcher_bridge.py");
    if primary.exists() {
        return primary;
    }
    root.join("launcher_bridge.py")
}

fn bridge_args(command: &str, target: Option<String>, app_dir: Option<String>) -> Vec<String> {
    let mut args = vec![
        command.to_string(),
        "--target".to_string(),
        target.unwrap_or_else(|| "auto".into()),
    ];
    if let Some(path) = app_dir.filter(|path| !path.trim().is_empty()) {
        args.push("--app-dir".to_string());
        args.push(path);
    }
    args
}

fn run_bridge(app: &tauri::AppHandle, args: &[String]) -> Result<Value, String> {
    let root = project_root(app)?;
    let script = bridge_script(&root);
    if !script.exists() {
        return Err(format!("launcher_bridge.py not found under {}", root.display()));
    }

    let mut command = python_command();
    command.arg("-B").arg(&script);
    for arg in args {
        command.arg(arg);
    }
    command
        .current_dir(&root)
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8");

    let output = command
        .output()
        .map_err(|err| format!("failed to spawn python bridge: {err}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if stdout.is_empty() {
        return Err(if stderr.is_empty() {
            format!("bridge returned empty output (exit {})", output.status)
        } else {
            stderr
        });
    }

    serde_json::from_str::<Value>(&stdout).map_err(|err| {
        format!(
            "invalid bridge json: {err}; stdout={stdout}; stderr={stderr}"
        )
    })
}

#[cfg(test)]
mod tests {
    use super::{materialize_embedded_files, EMBEDDED_FILES};
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn portable_payload_contains_every_runtime_file() {
        let paths: Vec<&str> = EMBEDDED_FILES.iter().map(|(path, _)| *path).collect();
        for expected in [
            "tools/launcher_bridge.py",
            "patch_windowsapps_json_only.py",
            "patch_chunks_zh_cn.py",
            "restore_claude_zh_cn_windowsapps.py",
            "best_effort_io.py",
            "resources/desktop-zh-CN.json",
            "resources/frontend-zh-CN.json",
            "resources/statsig-zh-CN.json",
        ] {
            assert!(paths.contains(&expected));
        }
        assert!(EMBEDDED_FILES.iter().all(|(_, contents)| !contents.is_empty()));

        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock must be after Unix epoch")
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "claude-desktop-zh-cn-portable-test-{}-{unique}",
            std::process::id()
        ));
        materialize_embedded_files(&root).expect("embedded files must materialize");
        for (relative_path, expected) in EMBEDDED_FILES {
            let actual = fs::read(root.join(relative_path)).expect("materialized file must be readable");
            assert_eq!(actual, *expected);
        }
        fs::remove_dir_all(root).expect("portable test directory must be removable");
    }
}

fn error_payload(message: String) -> Value {
    serde_json::to_value(BridgeError {
        ok: false,
        state: "error".into(),
        message: message.clone(),
        log: message,
    })
    .unwrap_or_else(|_| Value::Null)
}

#[tauri::command]
fn get_status(
    app: tauri::AppHandle,
    target: Option<String>,
    app_dir: Option<String>,
) -> Result<Value, String> {
    let args = bridge_args("status", target, app_dir);
    match run_bridge(&app, &args) {
        Ok(value) => {
            if let Some(status) = value.get("status") {
                Ok(status.clone())
            } else {
                Ok(value)
            }
        }
        Err(err) => Err(err),
    }
}

#[tauri::command]
fn install_patch(
    app: tauri::AppHandle,
    target: Option<String>,
    app_dir: Option<String>,
) -> Result<Value, String> {
    let args = bridge_args("install", target, app_dir);
    match run_bridge(&app, &args) {
        Ok(value) => Ok(value),
        Err(err) => Ok(error_payload(err)),
    }
}

#[tauri::command]
fn restore_patch(
    app: tauri::AppHandle,
    target: Option<String>,
    app_dir: Option<String>,
) -> Result<Value, String> {
    let args = bridge_args("restore", target, app_dir);
    match run_bridge(&app, &args) {
        Ok(value) => Ok(value),
        Err(err) => Ok(error_payload(err)),
    }
}

#[tauri::command]
fn open_claude(
    app: tauri::AppHandle,
    target: Option<String>,
    app_dir: Option<String>,
) -> Result<Value, String> {
    let args = bridge_args("open", target, app_dir);
    match run_bridge(&app, &args) {
        Ok(value) => Ok(value),
        Err(err) => Ok(error_payload(err)),
    }
}

#[tauri::command]
fn check_update(
    app: tauri::AppHandle,
    target: Option<String>,
    app_dir: Option<String>,
) -> Result<Value, String> {
    let args = bridge_args("check-update", target, app_dir);
    match run_bridge(&app, &args) {
        Ok(value) => Ok(value),
        Err(err) => Ok(error_payload(err)),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            get_status,
            install_patch,
            restore_patch,
            open_claude,
            check_update
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
