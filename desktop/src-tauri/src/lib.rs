use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct ApiSidecar(std::sync::Mutex<Option<CommandChild>>);

fn start_sidecar(app: &AppHandle) -> Option<CommandChild> {
    match app.shell().sidecar("jarvis-api-sidecar") {
        Ok(command) => match command.spawn() {
            Ok((mut rx, child)) => {
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = rx.recv().await {
                        println!("jarvis-api-sidecar: {:?}", event);
                    }
                });
                Some(child)
            }
            Err(error) => {
                eprintln!("No se pudo iniciar sidecar Jarvis: {error}");
                None
            }
        },
        Err(error) => {
            eprintln!("Sidecar Jarvis no configurado: {error}");
            None
        }
    }
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "Mostrar Jarvis", true, None::<&str>)?;
    let toggle = MenuItem::with_id(app, "toggle", "Jarvis esta escuchando", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Salir", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &toggle, &quit])?;

    TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("Jarvis esta escuchando")
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "toggle" => {
                let _ = app.notification().builder()
                    .title("Jarvis")
                    .body("Usa Ctrl+Shift+J para alternar la escucha.")
                    .show();
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                if let Some(window) = tray.app_handle().get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            build_tray(app.handle())?;
            let child = start_sidecar(app.handle());
            app.manage(ApiSidecar(std::sync::Mutex::new(child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Jarvis");
}
